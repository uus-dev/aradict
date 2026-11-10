"""The dictionary contract: Arabic lookup on the CAMeL calima-msa-r13 morphology database."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Reading:
    """One way to read the typed word, after merging analyses that differ only in a case or
    mood ending or in how a proclitic is read."""

    form: str
    gloss: str
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
    """Prefer the analysis written without a case ending and with وَ read as "and"."""
    return next(
        (a for a in analyses if a["cas"] in ("u", "na") and a["prc2"] in ("0", "wa_conj")),
        analyses[0],
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

    def lookup_ar(self, word: str) -> list[Reading]:
        """Readings for an Arabic word, most frequent lemma first. Unknown words give []."""
        groups: dict[tuple, list[dict]] = {}
        for analysis in self._analyzer.analyze(word.strip()):
            groups.setdefault(_reading_key(analysis), []).append(analysis)
        readings = []
        for analyses in groups.values():
            a = _representative(analyses)
            logprob = float(a.get("lex_logprob", -99))
            readings.append(Reading(
                form=a["diac"],
                gloss=a["gloss"].replace("_", " "),  # ponytail: raw CAMeL gloss; readable wording is #4
                pos=a["pos"],
                lemma=a["lex"],
                root=a.get("root") or None,
                frequency=None if logprob <= -99 else logprob,
            ))
        # Python's sort is stable, so equal keys keep the analyzer's order.
        return sorted(readings, key=lambda r: (r.frequency is None, -(r.frequency or 0), r.lemma))
