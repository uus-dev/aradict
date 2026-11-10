"""The dictionary contract: Arabic and English lookup, Arabizi, text analysis and autocomplete on the CAMeL calima-msa-r13 morphology database."""

from __future__ import annotations

import itertools
import re
import unicodedata
from bisect import bisect_left
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from . import readable
from .readable import Segment

LOOK_ALIKES = str.maketrans({"ی": "ي", "ک": "ك", "ـ": None})  # Persian/Urdu letters; tatweel
MARK = re.compile("[\u064b-\u065f\u0670]")  # tanween, short vowels, shadda, sukun, dagger alif
# The database leaves the fatha before a long ا unwritten (كِتاب): a letter, maybe a shadda, then ا.
# It also leaves out the fatha a dagger alif implies (اللّٰه).
IMPLIED_FATHA = re.compile("(?<=[\u0621-\u064a])(\u0651?)(?=\u0627)")
# A passage, cut into runs of: Arabic letters with their marks (tatweel, ی and ک included), digits
# (Western, Arabic-Indic, Persian), whitespace, other letters, and any other single character.
TOKEN = re.compile(
    "(?P<word>[\u0621-\u065f\u0670\u0671\u06a9\u06cc]+)|(?P<number>[0-9\u0660-\u0669\u06f0-\u06f9]+)"
    "|(?P<space>\\s+)|(?P<foreign>[^\\W\\d_\u0600-\u06ff]+)|(?P<punctuation>.)",
    re.S,
)
# The database keys stems by their bare letters: أ, إ, آ and ٱ as ا, ى as ي, and ة as ه.
STEM_KEY = str.maketrans("أإآٱىة", "اااايه")
SUGGESTIONS = 25

# Arabizi: Arabic in Latin letters and digits. Each token stands for one or more Arabic spellings,
# the likelier first.
ARABIZI_CONSONANTS = {
    "b": "ب", "p": "ب", "t": "تط", "th": "ثذ", "j": "ج", "g": "جغق", "7": "ح", "h": "هح", "kh": "خ", "5": "خ",
    "d": "دض", "dh": "ذظض", "r": "ر", "z": "زظ", "s": "سص", "sh": "ش", "3": "ع", "gh": "غ", "f": "ف", "v": "ف",
    "q": "ق", "9": "ق", "k": "ك", "l": "ل", "m": "م", "n": "ن", "w": "و", "y": "ي", "2": "أإءئؤ",
}
FATHA, KASRA, DAMMA, SHADDA = "\u064e", "\u0650", "\u064f", "\u0651"
# A vowel is short, written as a vowel mark that filters readings like a typed one, or long,
# written as a letter; at the end of a word, a letter first. A word-initial vowel is always ا.
ARABIZI_VOWELS = {  # token: (inside a word, at its end)
    "a": ([FATHA, "ا"], ["ة", "ا", FATHA, "ى"]),
    "i": ([KASRA, KASRA + "ي"], [KASRA + "ي", KASRA]),
    "u": ([DAMMA, DAMMA + "و"], [DAMMA + "و", DAMMA]),
    "o": ([DAMMA, "و"], ["و", DAMMA]),
    "e": (["", "ي"], ["ة", "ي", ""]),
    "aa": (["ا"], ["ا"]), "ee": (["ي"], ["ي"]), "ii": (["ي"], ["ي"]), "oo": (["و"], ["و"]), "uu": (["و"], ["و"]),
    "ei": ([FATHA + "ي"], [FATHA + "ي"]),
    "an": ([], ["اً", FATHA + "ن", "ان"]),  # only at the end of a word, where it may be tanween (shukran)
}
ARABIZI_TOKEN = re.compile("(?<=.)an$|" + "|".join(sorted(ARABIZI_CONSONANTS.keys() | ARABIZI_VOWELS.keys() - {"an"}, key=len, reverse=True)))
SPELLING_LIMIT = 2048  # spellings tried per word, at most about 0.3 s for the longest word
ARABIZI_LONGEST = 24  # letters; wabimudarrisatihim has 18
# Every mark but tanween fath, which a spelling must match (شكراً), so a final ا isn't a case ending.
UNSPELLED = re.compile("[\u064c-\u065f\u0670]")
ALIFS = str.maketrans("أإآٱ", "اااا")

# Verb measures as the consonants of the lemma (the perfect "he" form), vowels left out and
# shadda kept. Digits stand for the root's letters in order (1 2 3 are ف ع ل), so a template
# matches only where the root's letters stand; an unresolved radical (# in the root) can be any
# weak or hamza letter. Variants cover doubled roots (12ّ: رَدّ), Form VIII's assimilated ت
# (اتّ23: اِتَّخَذ, ا1ّ23: اِطَّلَع, ا1ط23: اِصْطَدَم) and verbs that add a fourth letter to three
# root letters and conjugate as quadriliterals (م123: مَرْكَز, 1ي23: سَيْطَر).
MEASURES = {
    "I": ("123", "12ّ"),
    "II": ("12ّ3",),
    "III": ("1ا23", "1ا2ّ"),
    "IV": ("أ123", "أ12ّ"),
    "V": ("ت12ّ3",),
    "VI": ("ت1ا23", "ت1ا2ّ"),
    "VII": ("ان123", "ان12ّ"),
    "VIII": ("ا1ت23", "ا1ت2ّ", "اتّ23", "ا1ّ23", "ا1[طد]23", "ا1[طد]2ّ"),
    "IX": ("ا123ّ",),
    "X": ("است123", "است12ّ"),
    "XI": ("ا12ا3ّ",),
    "XII": ("ا12و23",),
    "QI": ("1234", "م123", "1[وي]23", "12[وي]3", "123ن", "1233"),
    "QII": ("ت1234", "تم123", "ت1[وي]23", "ت12[وي]3", "ت123ن", "ت1233"),
    "QIII": ("ا12ن34",),
    "QIV": ("ا1234ّ",),
}
TEMPLATES = [
    (name, re.compile(re.sub("[1-4]", "(.)", t)), [int(d) for d in re.findall("[1-4]", t)])
    for name, templates in MEASURES.items() for t in templates
]
WEAK = "اأإءؤئوىي"
ROOT = re.compile("[\u0621-\u064a#](\\.[\u0621-\u064a#])+")  # letters joined by dots; a few stored roots are junk ("لس", "NTWS")
VOWELS = re.compile("[\u064b-\u0650\u0652\u0670]")  # everything but shadda
# The database's categories for the short imperfect stem of hollow, doubled and weak-final verbs,
# which stands before consonant endings and in the jussive: قُل (يَقُلْنَ, لَمْ يَقُلْ) beside قُول.
# ponytail: relies on calima-msa-r13's category names; check them when the database changes.
SHORT_STEM = re.compile("_C(_|$)|0hwnyn")


@dataclass(frozen=True)
class Reading:
    """One way to read the typed word, after merging analyses that differ only in a case or
    mood ending or in how a proclitic is read."""

    form: str
    gloss: str  # the whole word in English, e.g. "and by/with their book"
    tags: tuple[str, ...]  # part of speech, voice, agreement, e.g. ("verb", "active", "3rd person masculine singular")
    grammar: str  # the rest in plain English, e.g. "perfect (past)"; empty when the spelling fixes nothing more
    segments: tuple[Segment, ...]  # prefixes, the stem, suffixes
    pos: str
    lemma: str
    root: str | None
    frequency: float | None  # lemma log-probability; None when the database has no figure
    top_percent: float | None  # the share of lemmas at least as frequent as this one, among those with a frequency
    measure: str | None  # a verb's measure, "I" to "XII" or "QI" to "QIV"; None for other parts of speech or when it can't be derived


@dataclass(frozen=True)
class Token:
    """One run of a passage, at passage[start:end]. A word with no reading is "unknown"."""

    text: str
    kind: str  # word, unknown, number, space (line breaks too), foreign (non-Arabic letters) or punctuation
    start: int
    end: int
    readings: tuple[Reading, ...] = ()


def _reading_key(analysis: dict) -> tuple:
    # Ignoring case (cas), state (stt) and mood (mod) folds case and mood endings into one
    # reading. Treating every وَ reading (and, while, particle) as one folds the proclitic.
    # Only analyses that share a gloss merge: a lemma stored twice with different senses
    # (كاتِب "clerk" and "writer;author") gives two readings.
    wa = "wa" if analysis["prc2"].startswith("wa_") else analysis["prc2"]
    return tuple(analysis[f] for f in ("lex", "pos", "stemgloss", "prc3")) + (wa,) + tuple(
        analysis[f] for f in ("prc1", "prc0", "enc0", "vox", "asp", "per", "gen", "num")
    )


def _representative(analyses: list[dict]) -> dict:
    """Prefer وَ read as "and", then the analysis written without a case ending."""
    return min(analyses, key=lambda a: (a["prc2"] not in ("0", "wa_conj"), a["cas"] not in ("u", "na")))


def _letters(word: str) -> list[tuple[str, set[str]]]:
    """Each letter with the marks written on it."""
    letters: list[tuple[str, set[str]]] = []
    for char in word:
        if MARK.match(char) and letters:
            letters[-1][1].add(char)
        else:
            letters.append((char, set()))
    return letters


def _typed(word: str) -> list[tuple[str, set[str]]]:
    return _letters(word.replace("\u064b\u0627", "\u0627\u064b"))  # the database puts tanween fath on the ا


def _agrees(typed: list[tuple[str, set[str]]], form: str, check_marks: bool, whole: bool = True) -> bool:
    """A hamza the user typed is the analysis's hamza (bare ا matches any), and, when
    check_marks is on, every mark the user typed is on the same letter of the analysis.
    Unless whole is set, the typed letters need only begin the form."""
    letters = _letters(IMPLIED_FATHA.sub("\u064e\\1", form).replace("\u0670", "\u064e\u0670"))
    return (len(letters) == len(typed) if whole else len(letters) >= len(typed)) and all(
        (letter not in "أإآ" or letter == other) and (not check_marks or marks <= other_marks)
        for (letter, marks), (other, other_marks) in zip(typed, letters)
    )


def _logprob(analysis: dict) -> float:
    return float(analysis.get("lex_logprob", -99))


def _key(text: str) -> str:
    return MARK.sub("", text).translate(STEM_KEY)


def alphabetical(text: str) -> tuple[str, str]:
    """A sort key for Arabic in alphabetical order: by its letters (hamza forms as ا), then its vowels."""
    return _key(text), text


def family_order(r: Reading) -> tuple:
    """Related forms and a root's words: verbs by measure (I to X, then the rare XI and XII and
    the four-letter measures), then the other parts of speech; then by lemma, then by form."""
    return (r.pos != "verb", list(MEASURES).index(r.measure) if r.measure else len(MEASURES),
            alphabetical(r.lemma), alphabetical(r.form), r.pos, r.gloss)


def _first_word(text: str) -> str:
    """The first word, with look-alike letters read as Arabic, or "" for blank text."""
    words = unicodedata.normalize("NFC", text.translate(LOOK_ALIKES)).split()
    return words[0] if words else ""


def _spelled(form: str) -> str:
    """The letters of a form, with alif and its hamza forms alike."""
    return UNSPELLED.sub("", form).translate(ALIFS)


def _arabizi_spellings(word: str) -> list[str]:
    """The Arabic spellings an Arabizi word may stand for, likeliest first; [] if it isn't Arabizi."""
    word = word.lower().replace("-", "")  # al-kitab
    tokens = ARABIZI_TOKEN.findall(word)
    if not tokens or "".join(tokens) != word or len(word) > ARABIZI_LONGEST:
        return []
    options = []
    for i, token in enumerate(tokens):
        if token in ARABIZI_VOWELS:
            spellings = ["ا"] if i == 0 else ARABIZI_VOWELS[token][i == len(tokens) - 1]
        else:
            spellings = list(ARABIZI_CONSONANTS[token])
            if i and tokens[i - 1] == token:  # a doubled consonant is a shadda (mudarris) or two letters (allah)
                spellings.insert(0, SHADDA)
        options.append(list(enumerate(spellings)))
    # ponytail: a long word tries only the first SPELLING_LIMIT combinations; prune with the stem index if that bites.
    combinations = itertools.islice(itertools.product(*options), SPELLING_LIMIT)
    return ["".join(spelling for _, spelling in combination) for combination in sorted(combinations, key=lambda c: sum(rank for rank, _ in c))]


def _by_frequency(r: Reading) -> tuple:
    """Most frequent lemma first; lemmas with no figure last."""
    return r.frequency is None, -(r.frequency or 0), r.lemma


# English → Arabic: an index from each English sense of a stem's gloss to the stems with it.
BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]|<[^>]*>")  # (Egyptian)_cheese, write_[fem.sg.], <verb>
THIRD_PERSON = {"be": "is", "have": "has", "do": "does", "go": "goes"}


def _citation(form: str, lemma: str, pos: str, stem: str | None = None, gloss: str | None = None):
    """Keeps the analyses of form that spell a lemma in its citation form: from the given stem,
    or else from any stem but with nothing attached. A verb is 3rd person masculine singular,
    the perfect when looked up from its perfect stem."""
    typed = _typed(form)

    def keep(a: dict) -> bool:
        return (a["lex"], a["pos"]) == (lemma, pos) and _agrees(typed, a["diac"], True) and (
            (a["stem"], a["stemgloss"]) == (stem, gloss) if stem else all(a[f] in ("0", "na") for f in ("prc3", "prc2", "prc1", "prc0", "enc0"))
        ) and (pos != "verb" or (a["per"], a["gen"], a["num"]) == ("3", "m", "s"))
    return keep


def _english_key(text: str) -> str:
    return " ".join(text.lower().split())


def _english_keys(gloss: str, pos: str) -> set[str]:
    """What a stem's gloss is found by: each sense, and for nouns and verbs the inflected forms
    learners type (books; wrote, writes). Bracketed annotations are left out."""
    keys = set()
    for sense in readable.senses(BRACKETED.sub("", gloss)):
        keys.add(sense := _english_key(sense))
        first, _, rest = sense.partition(" ")
        if pos == "noun":
            keys.add(readable._plural(sense))  # ponytail: inflects the last word, so "pieces of writing" isn't found
        elif pos == "verb" and first != "be":
            for inflected in (readable._past(first), THIRD_PERSON.get(first) or readable._plural(first)):
                keys.add(f"{inflected} {rest}".strip())
    return keys - {""}


def _english_index(stems) -> dict[str, tuple[tuple[str, str, str, str], ...]]:
    """Each English key with the stems it finds, as (lemma, part of speech, stem, gloss). A verb's
    stems are found as its perfect stems of the same voice, which spell its citation form."""
    # NOAN is the database's placeholder for words it has no analysis of.
    stems = {(a["lex"], a["pos"], a["diac"], a["gloss"], a["vox"], a["asp"]) for a in stems if a["lex"] != "NOAN"}
    perfect: dict[tuple[str, str], set] = {}
    for lemma, pos, stem, gloss, voice, aspect in stems:
        if pos == "verb" and aspect == "p":
            perfect.setdefault((lemma, voice), set()).add((lemma, pos, stem, gloss))
    index: dict[str, set] = {}
    for lemma, pos, stem, gloss, voice, aspect in stems:
        # A voice with no perfect stem (a passive met only in the imperfect) is found as the active verb.
        found = perfect.get((lemma, voice)) or perfect.get((lemma, "a"), ()) if pos == "verb" else [(lemma, pos, stem, gloss)]
        for key in _english_keys(gloss, pos):
            index.setdefault(key, set()).update(found)
    return {key: tuple(sorted(found)) for key, found in index.items()}  # sorted: the same order on every run


class Dictionary:
    def __init__(self, db_path: Path):
        if not db_path.is_file():
            raise RuntimeError(
                f"No morphology database at {db_path}. Run `uv run aradict` or `uv run python -m aradict.data` to download it."
            )
        from camel_tools.morphology.analyzer import Analyzer
        from camel_tools.morphology.database import MorphologyDB

        self._db = MorphologyDB(str(db_path), "a")
        self._analyzer = Analyzer(self._db, backoff="NONE")
        # The stem prefix index for suggestions: every stem, sorted by its key.
        self._stems = sorted(
            (key, cat, analysis["diac"], _logprob(analysis)) for key, entries in self._db.stem_hash.items() for cat, analysis in entries
        )
        self._stem_keys = [stem[0] for stem in self._stems]
        # آ hides whether its ا is a root letter (IV آمَن, imperfect يُؤْمِن) or Form III's long
        # vowel (آخَذ, يُؤاخِذ); the lemma's imperfect stems tell.
        self._hamza_measures: dict[str, set[str]] = {}
        lemmas: dict[tuple[str, str], float] = {}
        # Each lemma's stems, for its related forms: (stem key, stem entry), each stem once.
        self._lemma_stems: dict[tuple[str, str], dict[tuple, tuple[str, dict]]] = {}
        for key, entries in self._db.stem_hash.items():
            for _, f in entries:
                self._lemma_stems.setdefault((f["lex"], f["pos"]), {}).setdefault((f["diac"], f["gloss"], f["asp"], f.get("root")), (key, f))
                lemmas[f["lex"], f["pos"]] = _logprob(f)
                if f["pos"] == "verb" and f["lex"].startswith("آ") and f["asp"] == "i":
                    self._hamza_measures.setdefault(f["lex"], set()).add("III" if f["diac"].startswith("ؤا") else "IV")
        # Each root's stems, for its family.
        self._root_stems: dict[str, list[tuple[str, dict]]] = {}
        for stems in self._lemma_stems.values():
            for key, f in stems.values():
                if ROOT.fullmatch(f.get("root", "")):
                    self._root_stems.setdefault(f["root"], []).append((key, f))
        self._frequencies = sorted(logprob for logprob in lemmas.values() if logprob > -99)
        self._english = _english_index(analysis for stems in self._db.stem_hash.values() for _, analysis in stems)

    def measure(self, lemma: str, root: str) -> str | None:
        """A verb's measure: the one template the lemma fits with the root's letters in its
        slots. Three-letter measures go before the quadriliteral ones. None when no template
        fits or the lemma fits two."""
        radicals = root.split(".")
        word = VOWELS.sub("", lemma).replace("ٱ", "ا").replace("آ", "أا")
        found = list(dict.fromkeys(
            name for name, template, slots in TEMPLATES
            if (m := template.fullmatch(word)) and all(
                d <= len(radicals) and (letter == radicals[d - 1] or letter in WEAK and radicals[d - 1] in WEAK + "#")
                for d, letter in zip(slots, m.groups())
            )
        ))
        if any(not name.startswith("Q") for name in found):
            found = [name for name in found if not name.startswith("Q")]
        if len(found) > 1:
            found = [name for name in found if name in self._hamza_measures.get(lemma, ())]
        return found[0] if len(found) == 1 else None

    def arabizi(self, text: str) -> str | None:
        """The Arabic an Arabizi word (the first, if several) stands for: of the spellings it may
        stand for, the one with the most frequent lemma. None if the text isn't Arabizi or no
        spelling is a known word."""
        words = text.split()
        # Only readings with exactly the spelling's letters count; a lookup also finds ة as ه and ى as ي.
        found = [
            (spelling, readings) for spelling in (_arabizi_spellings(words[0]) if words else [])
            if (readings := [r for r in self.lookup_ar(spelling) if _spelled(r.form) == _spelled(spelling)])
        ]
        # max keeps the likelier spelling of equally frequent ones; readings come most frequent first.
        return max(found, key=lambda f: -99 if f[1][0].frequency is None else f[1][0].frequency)[0] if found else None

    def _readings(self, word: str, keep: Callable[[dict], bool]) -> list[Reading]:
        """The readings of the analyses of word that keep accepts, merged as Reading describes."""
        groups: dict[tuple, list[dict]] = {}
        for analysis in self._analyzer.analyze(word):
            # The analyzer makes up one analysis for a digit, punctuation or non-Arabic token.
            if analysis["source"] in ("digit", "punc", "foreign") or not keep(analysis):
                continue
            groups.setdefault(_reading_key(analysis), []).append(analysis)
        readings = []
        for analyses in groups.values():
            a = _representative(analyses)
            logprob = _logprob(a)
            root = a.get("root") if ROOT.fullmatch(a.get("root", "")) else None
            readings.append(Reading(
                form=a["diac"],
                gloss=readable.gloss(a),
                tags=readable.tags(a),
                grammar=readable.grammar(analyses),
                segments=readable.segments(a),
                pos=a["pos"],
                lemma=a["lex"],
                root=root,
                frequency=None if logprob <= -99 else logprob,
                top_percent=None if logprob <= -99 else 100 * (1 - bisect_left(self._frequencies, logprob) / len(self._frequencies)),
                measure=self.measure(a["lex"], root) if a["pos"] == "verb" and root else None,
            ))
        return readings

    def lookup_en(self, query: str) -> list[Reading]:
        """Arabic words with an English sense that is the query, a phrase matched whole and
        ignoring case, or an inflected form of it ("books", "wrote"). Each reading appears once,
        verbs in their citation form ("he/it wrote"), most frequent lemma first. Unknown words give []."""
        found: dict[Reading, None] = {}  # an ordered set
        for lemma, pos, stem, gloss in self._english.get(_english_key(query), ()):
            # The lemma spells a singular noun or an active verb; a plural (كُتُب) or passive (كُتِب) stem spells
            # itself, and an adverb takes tanween (حالِيّاً). A stem that is no word on its own (طُماط, written
            # طُماطَة) gives its lemma's citation form instead.
            forms = (lemma, stem, stem + "اً") if pos == "adv" else (lemma, stem)
            readings = [r for form in dict.fromkeys(forms) for r in self._readings(form, _citation(form, lemma, pos, stem, gloss))]
            found.update(dict.fromkeys(readings or self._readings(lemma, _citation(lemma, lemma, pos))))
        # Within a lemma, its own form (كِتاب) before others (كُتُب).
        return sorted(found, key=lambda r: (*_by_frequency(r), MARK.sub("", r.form) != MARK.sub("", r.lemma)))

    def lookup_ar(self, word: str, filter_diacritics: bool = True) -> list[Reading]:
        """Readings for an Arabic word (the first, if several), most frequent lemma first.
        Unknown words give [].

        A typed hamza must match the analysis's. Each typed diacritic must agree too, unless
        filter_diacritics is off."""
        word = _first_word(word)  # several words: only the first is looked up; the page says so
        if not word:
            return []
        typed = _typed(word)
        readings = self._readings(word, lambda a: _agrees(typed, a["diac"], filter_diacritics))
        # A word-final ه also finds ة and vice versa; readings ending as typed (مدرسه, not مدرسة)
        # come first. Then the most frequent lemma. Each lemma's readings stay together, ranked
        # by its best one: the database can store two lemmas spelled alike, one without a
        # frequency. Python's sort is stable, so equal keys keep the analyzer's order.
        last = MARK.sub("", word)[-1:]
        rank = {r: (last in ("ه", "ة") and MARK.sub("", r.form)[-1:] != last, r.frequency is None, -(r.frequency or 0)) for r in readings}
        best = {}
        for r in readings:
            best[r.lemma, r.pos] = min(best.get((r.lemma, r.pos), rank[r]), rank[r])
        return sorted(readings, key=lambda r: (best[r.lemma, r.pos], r.lemma, r.pos, rank[r]))

    def related(self, lemma: str, pos: str) -> list[Reading]:
        """The forms of a lemma with this part of speech, such as a noun's singular and plural or
        a verb's perfect and imperfect, one reading each, in family order."""
        return self._family(self._lemma_stems.get((lemma, pos), {}).values())

    def root_family(self, root: str) -> list[Reading]:
        """Every form from a root, such as "ك.ت.ب" or, with an unresolved radical, "ق.#.ل", one
        reading each, in family order."""
        return self._family(self._root_stems.get(root, ()))

    def _family(self, stems: Iterable[tuple[str, dict]]) -> list[Reading]:
        readings = dict.fromkeys(r for key, f in stems if (r := self._stem_form(key, f)))  # each once, in order
        return sorted(readings, key=family_order)

    def _stem_form(self, key: str, f: dict) -> Reading | None:
        """A stem entry's dictionary form, with no attached words: a verb's "he" form (كَتَبَ,
        يَكْتُب), a noun or adjective alone or with the ending it needs (كِتابَة, كِتابات), an adverb
        with its tanween (طَوْعِيّاً). None for a stem that only stands before some endings, such as
        زَفَف, which زَفّ uses before -تُ, or the short imperfect stem of يَقُل beside يَقُول."""
        if f["pos"] == "verb":
            words, agreement = ["ي" + key] if f["asp"] == "i" else [key], ("2" if f["asp"] == "c" else "3", "m", "s")
        else:
            words, agreement = [key, key + "ة", key + "ات", key + "ا"], None

        def keep(a: dict) -> bool:
            return (
                (a["lex"], a["pos"], a["stem"], a["stemgloss"]) == (f["lex"], f["pos"], f["diac"], f["gloss"])
                and all(a[clitic] in ("0", "na") for clitic in ("prc3", "prc2", "prc1", "prc0", "enc0"))
                and ((a["per"], a["gen"], a["num"]) == agreement if agreement else a["num"] != "d")
                and not (f["asp"] == "i" and SHORT_STEM.search(a["stemcat"]))
            )

        return next((readings[0] for word in words if (readings := self._readings(word, keep))), None)

    def analyze_text(self, text: str) -> list[Token]:
        """Every run of the passage in order, each word with its readings. A word written twice is
        looked up once. The passage's diacritics filter their own word's readings."""
        seen: dict[str, tuple[Reading, ...]] = {}
        tokens = []
        for match in TOKEN.finditer(text):
            kind, word = match.lastgroup, match.group()
            readings = ()
            if kind == "word":
                if word not in seen:
                    seen[word] = tuple(self.lookup_ar(word))
                readings = seen[word]
                kind = "word" if readings else "unknown"
            tokens.append(Token(word, kind, match.start(), match.end(), readings))
        return tokens

    def suggest(self, text: str, filter_diacritics: bool = True) -> list[str]:
        """Vocalized words that complete the typed word, for autocomplete: at most 25, most
        frequent lemma first, each form once. Each completes a stem from the stem prefix index,
        alone or with a feminine ة, so looking it up shows its reading. Typed hamza and
        diacritics must agree as for lookup_ar.

        When the word starts with an attached prefix (وكتا), its stem is completed and the
        prefix kept. Completions that read fewer letters as a prefix come first."""
        word = _first_word(text)
        typed, letters = _typed(word), _key(word)
        suggestions: list[str] = []
        for i in range(min(len(letters) - 1, self._db.max_prefix_size) + 1):
            if len(suggestions) >= SUGGESTIONS:
                break
            completions = self._complete(typed, letters, i, SUGGESTIONS - len(suggestions), filter_diacritics)
            suggestions += [c for c in completions if c not in suggestions]
        return suggestions

    def _complete(self, typed: list, letters: str, i: int, wanted: int, check_marks: bool) -> list[str]:
        """Up to `wanted` vocalized forms that read the first i letters as a prefix and complete
        a stem from the rest, most frequent first."""
        prefix, rest = letters[:i], letters[i:]
        # The stem categories this prefix (empty, or letters such as و or وال) can attach to.
        cats = set().union(*(
            self._db.prefix_stem_compat.get(cat, ()) for cat, a in self._db.prefix_hash.get(prefix, ())
            if _agrees(typed[:i], a.get("diac", ""), check_marks)
        ))
        best: dict[str, float] = {}  # each matching stem key, with its most frequent lemma
        for key, cat, diac, freq in self._stems[bisect_left(self._stem_keys, rest):bisect_left(self._stem_keys, rest + "\uffff")]:
            # Typed marks short of the stem's last letter can be checked on the stem alone,
            # which saves analysing stems that can't agree.
            if cat in cats and (len(key) == len(rest) or _agrees(typed[i:], diac, check_marks, whole=False)):
                best[key] = max(best.get(key, -99.0), freq)
        found: dict[str, float] = {}
        for key in sorted(best, key=best.get, reverse=True):
            if len(found) >= wanted and best[key] <= sorted(found.values(), reverse=True)[wanted - 1]:
                break  # no later stem can rank higher
            # The stem alone or with a feminine ة (كِتابَة is كِتاب + ة), but not with a pronoun (كِتابه "his book").
            for word in (prefix + key, prefix + key + "ة"):
                for r in self._readings(word, lambda a: (
                    _key(a["stem"]) == key and a["enc0"] in ("0", "na") and _agrees(typed, a["diac"], check_marks, whole=False)
                )):
                    found[r.form] = max(found.get(r.form, -99.0), -99.0 if r.frequency is None else r.frequency)
        return sorted(found, key=found.get, reverse=True)[:wanted]
