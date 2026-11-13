"""Write a small Wiktionary dataset for browser and app tests.

It keeps the real dataset's entries spelled with the letters of the fixture database's lemmas
(make_fixture_db.LEMMAS), every part of speech and homograph, so pages show the real entries.
Usage: python tests/make_fixture_wiktionary.py SOURCE_DATASET TARGET_DATASET
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from aradict.wiktionary import letters
from make_fixture_db import LEMMAS


def make_fixture(source: Path, target: Path, lemmas: frozenset[str] = LEMMAS) -> Path:
    keys = sorted({letters(lemma) for lemma in lemmas})
    target.unlink(missing_ok=True)
    with closing(sqlite3.connect(target)) as db:
        db.execute("ATTACH ? AS real", (str(source),))
        db.execute(f"CREATE TABLE entry AS SELECT * FROM real.entry WHERE letters IN ({', '.join('?' * len(keys))}) ORDER BY rowid", keys)
        db.execute(f"PRAGMA user_version = {db.execute('PRAGMA real.user_version').fetchone()[0]}")  # the build that wrote it
        db.commit()
    return target


if __name__ == "__main__":
    make_fixture(Path(sys.argv[1]), Path(sys.argv[2]))
