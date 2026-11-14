"""Write a small Wiktionary dataset for browser and app tests.

It keeps the real dataset's entries spelled with the letters of the fixture database's lemmas
(make_fixture_db.LEMMAS) and of words only Wiktionary has (ONLY), every part of speech and homograph,
with their forms, so pages show the real entries.
Usage: python tests/make_fixture_wiktionary.py SOURCE_DATASET TARGET_DATASET
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from aradict.wiktionary import letters
from make_fixture_db import LEMMAS

ONLY = frozenset({
    "تَغْرِيدَة",  # "a tweet", which the dictionary reads as تَغْرِيد "his twittering"
    "آفَاق",  # a headword of its own in Wiktionary, the plural of أُفُق in the dictionary
})


def make_fixture(source: Path, target: Path, lemmas: frozenset[str] = LEMMAS | ONLY) -> Path:
    keys = sorted({letters(lemma) for lemma in lemmas})
    shutil.copyfile(source, target)  # its tables, indexes and format, as the build wrote them
    with closing(sqlite3.connect(target)) as db:
        db.execute(f"DELETE FROM entry WHERE letters NOT IN ({', '.join('?' * len(keys))})", keys)
        db.execute("DELETE FROM form WHERE entry NOT IN (SELECT id FROM entry)")
        db.commit()
        db.execute("VACUUM")
    return target


if __name__ == "__main__":
    make_fixture(Path(sys.argv[1]), Path(sys.argv[2]))
