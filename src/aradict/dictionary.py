"""The dictionary contract: Arabic lookup on the CAMeL calima-msa-r13 morphology database."""

from __future__ import annotations

import itertools
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import readable
from .readable import Segment

LOOK_ALIKES = str.maketrans({"ی": "ي", "ک": "ك", "ـ": None})  # Persian/Urdu letters; tatweel
MARK = re.compile("[\u064b-\u065f\u0670]")  # tanween, short vowels, shadda, sukun, dagger alif
# The database leaves the fatha before a long ا unwritten (كِتاب): a letter, maybe a shadda, then ا.
# It also leaves out the fatha a dagger alif implies (اللّٰه).
IMPLIED_FATHA = re.compile("(?<=[\u0621-\u064a])(\u0651?)(?=\u0627)")

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


def _reading_key(analysis: dict) -> tuple:
    # Ignoring case (cas), state (stt) and mood (mod) folds case and mood endings into one
    # reading. Treating every وَ reading (and, while, particle) as one folds the proclitic.
    wa = "wa" if analysis["prc2"].startswith("wa_") else analysis["prc2"]
    return tuple(analysis[f] for f in ("lex", "pos", "prc3")) + (wa,) + tuple(
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


def _agrees(typed: list[tuple[str, set[str]]], form: str, check_marks: bool) -> bool:
    """A hamza the user typed is the analysis's hamza (bare ا matches any), and, when
    check_marks is on, every mark the user typed is on the same letter of the analysis."""
    letters = _letters(IMPLIED_FATHA.sub("\u064e\\1", form).replace("\u0670", "\u064e\u0670"))
    return len(letters) == len(typed) and all(
        (letter not in "أإآ" or letter == other) and (not check_marks or marks <= other_marks)
        for (letter, marks), (other, other_marks) in zip(typed, letters)
    )


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


class Dictionary:
    def __init__(self, db_path: Path):
        if not db_path.is_file():
            raise RuntimeError(
                f"No morphology database at {db_path}. Run `uv run aradict` or `uv run python -m aradict.data` to download it."
            )
        from camel_tools.morphology.analyzer import Analyzer
        from camel_tools.morphology.database import MorphologyDB

        self._analyzer = Analyzer(MorphologyDB(str(db_path), "a"), backoff="NONE")

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

    def lookup_ar(self, word: str, filter_diacritics: bool = True) -> list[Reading]:
        """Readings for an Arabic word (the first, if several), most frequent lemma first.
        Unknown words give [].

        A typed hamza must match the analysis's. Each typed diacritic must agree too, unless
        filter_diacritics is off."""
        words = unicodedata.normalize("NFC", word.translate(LOOK_ALIKES)).split()
        if not words:
            return []
        word = words[0]  # several words: only the first is looked up; the page says so
        typed = _letters(word.replace("\u064b\u0627", "\u0627\u064b"))  # the database puts tanween fath on the ا
        groups: dict[tuple, list[dict]] = {}
        for analysis in self._analyzer.analyze(word):
            # The analyzer makes up one analysis for a digit, punctuation or non-Arabic token.
            if analysis["source"] in ("digit", "punc", "foreign") or not _agrees(typed, analysis["diac"], filter_diacritics):
                continue
            groups.setdefault(_reading_key(analysis), []).append(analysis)
        readings = []
        for analyses in groups.values():
            a = _representative(analyses)
            logprob = float(a.get("lex_logprob", -99))
            readings.append(Reading(
                form=a["diac"],
                gloss=readable.gloss(a),
                tags=readable.tags(a),
                grammar=readable.grammar(analyses),
                segments=readable.segments(a),
                pos=a["pos"],
                lemma=a["lex"],
                root=a.get("root") or None,
                frequency=None if logprob <= -99 else logprob,
            ))
        # A word-final ه also finds ة and vice versa; readings ending as typed (مدرسه, not مدرسة)
        # come first. Then the most frequent lemma; Python's sort is stable, so equal keys keep
        # the analyzer's order.
        last = MARK.sub("", word)[-1:]
        return sorted(readings, key=lambda r: (
            last in ("ه", "ة") and MARK.sub("", r.form)[-1:] != last, r.frequency is None, -(r.frequency or 0), r.lemma,
        ))
