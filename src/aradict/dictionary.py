"""The dictionary contract: Arabic lookup on the CAMeL calima-msa-r13 morphology database."""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

from . import readable
from .readable import Segment

LOOK_ALIKES = str.maketrans({"ی": "ي", "ک": "ك", "ـ": None})  # Persian/Urdu letters; tatweel
MARK = re.compile("[\u064b-\u065f\u0670]")  # tanween, short vowels, shadda, sukun, dagger alif
# The database leaves the fatha before a long ا unwritten (كِتاب): a letter, maybe a shadda, then ا.
IMPLIED_FATHA = re.compile("(?<=[\u0621-\u064a])(\u0651?)(?=\u0627)")

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
    letters = _letters(IMPLIED_FATHA.sub("\u064e\\1", form))
    return len(letters) == len(typed) and all(
        (letter not in "أإآ" or letter == other) and (not check_marks or marks <= other_marks)
        for (letter, marks), (other, other_marks) in zip(typed, letters)
    )


class Dictionary:
    def __init__(self, db_path: Path):
        if not db_path.is_file():
            raise RuntimeError(
                f"No morphology database at {db_path}. Run `uv run aradict` or `uv run python -m aradict.data` to download it."
            )
        from camel_tools.morphology.analyzer import Analyzer
        from camel_tools.morphology.database import MorphologyDB

        db = MorphologyDB(str(db_path), "a")
        self._analyzer = Analyzer(db, backoff="NONE")
        # آ hides whether its ا is a root letter (IV آمَن, imperfect يُؤْمِن) or Form III's long
        # vowel (آخَذ, يُؤاخِذ); the lemma's imperfect stems tell.
        self._hamza_measures: dict[str, set[str]] = {}
        lemmas: dict[tuple[str, str], float] = {}
        for entries in db.stem_hash.values():
            for _, f in entries:
                lemmas[f["lex"], f["pos"]] = float(f.get("lex_logprob", -99))
                if f["pos"] == "verb" and f["lex"].startswith("آ") and f["asp"] == "i":
                    self._hamza_measures.setdefault(f["lex"], set()).add("III" if f["diac"].startswith("ؤا") else "IV")
        self._frequencies = sorted(logprob for logprob in lemmas.values() if logprob > -99)

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
