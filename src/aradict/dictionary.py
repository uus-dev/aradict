"""The dictionary contract: Arabic lookup on the CAMeL calima-msa-r13 morphology database."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import readable
from .readable import Segment

LOOK_ALIKES = str.maketrans({"ی": "ي", "ک": "ك", "ـ": None})  # Persian/Urdu letters; tatweel
MARK = re.compile("[\u064b-\u065f\u0670]")  # tanween, short vowels, shadda, sukun, dagger alif
# The database leaves the fatha before a long ا unwritten (كِتاب): a letter, maybe a shadda, then ا.
IMPLIED_FATHA = re.compile("(?<=[\u0621-\u064a])(\u0651?)(?=\u0627)")


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

        self._analyzer = Analyzer(MorphologyDB(str(db_path), "a"), backoff="NONE")

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
