"""Write a small morphology database for browser and app tests.

It keeps every section of the real calima-msa-r13 database (prefixes, suffixes and the
compatibility tables), but only the stems of the lemmas listed below, so results stay
small and stable. Usage: python tests/make_fixture_db.py SOURCE_DB TARGET_DB
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

# Enough for the reference words كتب, وبكتابهم, سيكتبون and استخدم, مدرستي's shared letter,
# a root with an unresolved radical (قال, and مَقال, which Wiktionary can't resolve), a verb with no usable root or measure (لَيْسَ),
# forms that share a gloss (سابقي: "my former" as singular, dual and plural), سِفْر, the
# other Arabic word for English "book", آر, at the database's lowest frequency, and إِجارَة, whose two
# senses are stored under two roots. For the Wiktionary layer: جِدَّة, whose senses Wiktionary labels
# obsolete and which has a homograph, and جَزْر, whose gloss has a meaning of each of its two homographs.
LEMMAS = frozenset({
    "كَتَب", "كِتاب", "كاتِب", "كُتّاب", "أَكْتَب", "مَدْرَسَة", "ٱِسْتَخْدَم", "قال", "مَقال", "لَيْسَ", "سابِق", "سِفْر", "آر", "إِجارَة",
    "جِدَّة", "جَزْر",
})


def make_fixture(source: Path, target: Path, lemmas: frozenset[str] = LEMMAS) -> Path:
    # The database may order a letter's marks otherwise than they are typed here.
    lemmas = {unicodedata.normalize("NFC", lemma) for lemma in lemmas}
    section = None
    with source.open(encoding="utf-8") as src, target.open("w", encoding="utf-8") as out:
        for line in src:
            if line.startswith("###"):
                section = line.strip()
            elif section == "###STEMS###" and line.strip():
                lex = re.search(r"(?:^|\s)lex:(\S+)", line)
                # Stored lemmas carry a sense suffix (كَتَب-u_1); the analyzer reports them without it.
                if not lex or unicodedata.normalize("NFC", re.split(r"[-_]", lex.group(1))[0]) not in lemmas:
                    continue
            out.write(line)
    return target


if __name__ == "__main__":
    make_fixture(Path(sys.argv[1]), Path(sys.argv[2]))
