"""The Wiktionary layer: English Wiktionary's Arabic entries, from a pinned kaikki.org extraction.

Wiktionary text is licensed CC BY-SA 4.0 and GFDL, which can't be merged with the GPL v2-only
CAMeL data (PRD, Wiktionary layer). So the entries are built into a dataset of their own, a
SQLite file that is never committed and never part of the CAMeL database, and joined to the
CAMeL lemmas at request time by vocalized lemma and part of speech.

`uv run python -m aradict.wiktionary [JSONL]` downloads the pinned extraction (about 870 MB), or
takes an already downloaded copy, checks it against the pin and builds the dataset at
`dataset_path()`. Refreshing means moving the pin and building again.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from hashlib import file_digest
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlopen

from .readable import MARK, SHADDA

# kaikki.org's extraction of 2026-10-30, from the English Wiktionary dump of 2026-10-01.
# ponytail: the URL isn't dated. kaikki.org overwrites the file with each new extraction, after which
# it no longer matches this pin and the build stops, saying how to move the pin (`_verify`).
URL = "https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl"
SHA256 = "19eee17681c23b3da039878ee7c970d93b75a339989a17a842f14aa7f44ea236"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "wiktionary"
SOURCE = DEFAULT_DIR / "kaikki.org-dictionary-Arabic.jsonl"
WIKI = "https://en.wiktionary.org/wiki/"


# What the build keeps: raised whenever that changes, so that an older dataset is rebuilt, not misread.
# 1 (#20) kept each sense's text; 2 (#22) its labels and sub-senses too.
LAYOUT = 2


def dataset_path() -> Path:
    """The dataset the app reads; override with ARADICT_WIKTIONARY_PATH. The app runs without it."""
    return Path(os.environ.get("ARADICT_WIKTIONARY_PATH", DEFAULT_DIR / "wiktionary.db"))


def check(dataset: Path) -> None:
    """Refuses a dataset an older build wrote, saying how to build it again."""
    with closing(sqlite3.connect(f"{dataset.resolve().as_uri()}?mode=ro", uri=True)) as db:
        layout = db.execute("PRAGMA user_version").fetchone()[0]
    if layout != LAYOUT:
        raise RuntimeError(
            f"The Wiktionary dataset at {dataset} was built by another version of AraDict. "
            f"Build it again with `uv run python -m aradict.wiktionary`."
        )


@dataclass(frozen=True)
class Sense:
    """One of an entry's numbered senses, or one of a sense's lettered sub-senses."""

    gloss: str  # "to cause to write, to make someone write"
    labels: tuple[str, ...] = ()  # Wiktionary's qualifiers and register labels: "transitive", "obsolete", "Classical"
    subsenses: tuple[Sense, ...] = ()


@dataclass(frozen=True)
class Entry:
    """One Wiktionary entry: a headword with one part of speech and etymology."""

    word: str  # vocalized, كِتَاب
    pos: str  # Wiktionary's part of speech: noun, verb, adj, name, …
    senses: tuple[Sense, ...]  # its meanings, in Wiktionary's order; relations ("verbal noun of …") are not senses
    forms: tuple[tuple[str, tuple[str, ...]], ...]  # the headword line's forms with their tags: (كُتُب, ("plural",)), the headword with its gender
    inflections: tuple[str, ...]  # each spelling in its declension or conjugation table, once
    romanization: str | None  # kitāb
    ipa: tuple[tuple[str, str], ...]  # each pronunciation with where it is said, "" for Modern Standard Arabic
    root: str | None  # its letters, "ك ت ب"; None when Wiktionary gives none, or two
    url: str  # the Wiktionary page

    @property
    def page(self) -> str:
        """The Wiktionary page's title: the headword without its marks, كتاب."""
        return self.url.removeprefix(WIKI).removesuffix("#Arabic").replace("_", " ")


# --- The join -------------------------------------------------------------------------------

# CAMeL's part of speech (noun, noun_prop, adj_comp, …) as Wiktionary names it: the class before
# the "_", but a proper noun is a "name".
POS = {"noun_prop": "name", "part": "particle", "interj": "intj"}


def wiktionary_pos(pos: str) -> str:
    return POS.get(pos) or POS.get(pos.split("_")[0]) or pos.split("_")[0]


FATHA, DAMMA, KASRA, SUKUN, TANWEEN_FATH = "\N{ARABIC FATHA}", "\N{ARABIC DAMMA}", "\N{ARABIC KASRA}", "\N{ARABIC SUKUN}", "\N{ARABIC FATHATAN}"


def spelling(word: str) -> str:
    """A vocalized word as the join compares it. The two sources write the same lemma
    differently, and this is the one place that evens that out:

    - the marks on a letter in one order (NFC), whichever order they were typed in;
    - ٱ (alif wasla) as ا;
    - tanween fath on the ا it is written beside (أَيْضاً, أَيْضًا), and on a final ى as a fatha (مُسْتَوَى, مُسْتَوًى);
    - no fatha before a long ا, which CAMeL leaves unwritten (كِتاب, كِتَاب; كُتّاب, كُتَّاب);
    - no short vowel at the end of the word, which CAMeL leaves off its verbs (كَتَب, كَتَبَ; أَشَعّ, أَشَعَّ);
    - no sukun, which either source may leave unwritten (إِنْجلِيزِيّ, إِنْجْلِيزِيّ).

    A lemma either source writes with no marks at all (CAMeL's قال) is matched on its letters alone.
    """
    word = unicodedata.normalize("NFC", word).replace("ٱ", "ا").replace(TANWEEN_FATH + "ا", "ا" + TANWEEN_FATH)
    word = re.sub(f"{TANWEEN_FATH}(?={SHADDA}?ى$)", FATHA, word)
    word = re.sub(f"{FATHA}(?={SHADDA}?ا)", "", word)
    word = re.sub(f"[{FATHA}{DAMMA}{KASRA}](?={SHADDA}?$)", "", word)  # NFC puts a final vowel before its shadda
    return word.replace(SUKUN, "")


def letters(word: str) -> str:
    """The word's letters, without marks, as the dataset is keyed."""
    return MARK.sub("", spelling(word))


def entries(dataset: Path, lemma: str, pos: str) -> list[Entry]:
    """The Wiktionary entries of a CAMeL lemma with this part of speech, in Wiktionary's order.
    Homographs from different etymologies (قَالَ "say" and قَالَ "nap") are separate entries."""
    with closing(sqlite3.connect(f"{dataset.resolve().as_uri()}?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT entry FROM entry WHERE letters = ? AND pos = ? ORDER BY rowid", (letters(lemma), wiktionary_pos(pos)))
        found = [_entry(json.loads(row)) for row, in rows]
    return [e for e in found if not MARK.search(lemma) or not MARK.search(e.word) or spelling(e.word) == spelling(lemma)]


class Join(NamedTuple):
    """A CAMeL lemma's Wiktionary entries, in Wiktionary's order, and the one joined to the lemma:
    its only entry, or of homographs (قَالَ "say" and قَالَ "nap") the one the lemma's CAMeL glosses
    pick. None when they pick none, or more than one."""

    entries: list[Entry]
    joined: Entry | None


# Words too common to tell two meanings apart.
COMMON = {"to", "be", "a", "an", "the", "of", "in", "on", "at", "by", "for", "from", "with", "into", "and", "or", "as",
          "one", "someone", "something", "oneself", "it", "its", "s"}


def _words(text: str) -> set[str]:
    return set(re.findall("[a-z]+", text.casefold())) - COMMON


def join(found: list[Entry], glosses: Iterable[str]) -> Join:
    """Joins a lemma to the one of its homographs whose senses share a word with its CAMeL glosses
    ("say;tell": قَالَ "to say", "to tell", not قَالَ "to nap"). Where the glosses share words with
    more than one (جَدّ "grandfather; good luck"), the lemma covers them all, and none is joined."""
    if len(found) < 2:
        return Join(found, found[0] if found else None)
    camel = set().union(*(_words(gloss.replace("_", " ")) for gloss in glosses))
    # ponytail: whole words only, so "said" misses "say"; a lemma's other stems ("say") usually make up for it.
    matching = [e for e in found if camel & set().union(*(_words(s.gloss) for sense in e.senses for s in (sense, *sense.subsenses)))]
    return Join(found, matching[0] if len(matching) == 1 else None)


def _entry(data: dict) -> Entry:
    def tuples(value):
        return tuple(map(tuples, value)) if isinstance(value, list) else value

    def sense(data: dict) -> Sense:
        return Sense(data["gloss"], tuple(data["labels"]), tuple(map(sense, data["subsenses"])))
    return Entry(**{key: tuples(value) for key, value in data.items()} | {"senses": tuple(map(sense, data["senses"]))})


# --- The build ------------------------------------------------------------------------------

# The parts of speech AraDict shows: those CAMeL's map to. Phrases, affixes, letters and roots are left out.
KEPT_POS = {"noun", "name", "adj", "verb", "adv", "pron", "prep", "conj", "particle", "intj", "num", "abbrev"}
# Form tags that describe the extraction, not the word.
NOT_FORMS = {"romanization", "table-tags", "inflection-template"}
ROOT_CATEGORY = "Arabic terms belonging to the root "


def _relation(sense: dict) -> bool:
    """A sense that only relates the word to another ("verbal noun of كَتَبَ", "plural of كَاتِب",
    "Classical Arabic spelling of كِتَاب") rather than saying what it means."""
    return bool({"form-of", "alt-of"} & set(sense.get("tags", ()))) or "form_of" in sense or "alt_of" in sense


def _template_root(template: dict) -> str | None:
    """The root an etymology template names: {{ar-root|ك ت ب}}, {{ar-rootbox|…}} or {{etymon|ar|:root|ك ت ب<id:root>}}."""
    args = template.get("args", {})
    if template["name"] in ("ar-root", "ar-rootbox"):
        root = args.get("1")
    elif template["name"] == "etymon" and args.get("2") == ":root":
        root = args.get("3")
    else:
        return None
    return root and re.sub("<[^>]*>", "", root).removeprefix("ar:").strip()


def _root(item: dict) -> str | None:
    """The root the entry's etymology names, or else the one its categories or its senses'
    categories name; None if none, or two."""
    roots = {root for t in item.get("etymology_templates", ()) if (root := _template_root(t))}
    categories = [*item.get("categories", ()), *(c for s in item.get("senses", ()) for c in s.get("categories", ()))]
    names = (c["name"] if isinstance(c, dict) else c for c in categories)  # kaikki.org writes either
    roots = roots or {name.removeprefix(ROOT_CATEGORY) for name in names if name.startswith(ROOT_CATEGORY)}
    return roots.pop() if len(roots) == 1 else None


# The register labels the PRD names (Wiktionary layer, Register) as kaikki.org tags a sense with them.
# Wiktionary shows some only in the sense's tags, not in its text: 894 of the 2,051 labelled senses.
REGISTER = {
    "obsolete", "archaic", "dated", "Classical", "historical", "rare", "poetic", "literary", "Quranic", "dialectal",
    "colloquial", "Gulf-Arabic", "Egyptian-Arabic", "Levantine-Arabic", "Maghrebi-Arabic",
}
QUALIFIER = re.compile(r"\(([^()]*)\)\s*")  # Wiktionary's labels before a gloss: "(transitive, causative) to cause to write"


def _labelled(gloss: str) -> tuple[str, list[str]]:
    """A gloss as Wiktionary shows it, split into its text and the labels in front of it."""
    m = QUALIFIER.match(gloss)
    return (gloss[m.end():], [label.strip() for label in m.group(1).split(",")]) if m else (gloss, [])


def _senses(item: dict) -> list[dict]:
    """The entry's meanings as numbered senses, each with its labels. kaikki.org lists a sub-sense
    with its sense's gloss in front ("to produce or generate by writing", "to compose"), and
    usually the sense alone just before it: such sub-senses go under the sense they follow."""
    senses: list[dict] = []
    for s in item.get("senses", ()):
        if not s.get("glosses") or _relation(s):
            continue
        levels = [_labelled(gloss) for gloss in s.get("raw_glosses") or s["glosses"]]
        shown = " ".join(label for _, labels in levels for label in labels).casefold()
        register = [tag.replace("-", " ") for tag in s.get("tags", ()) if tag in REGISTER and tag.replace("-", " ").casefold() not in shown]
        (gloss, labels), subs = levels[0], levels[1:]
        if not senses or senses[-1]["gloss"] != gloss:
            senses.append({"gloss": gloss, "labels": [], "subsenses": []})
        sense = senses[-1]
        sense["labels"] += [label for label in labels + ([] if subs else register) if label not in sense["labels"]]
        if subs:
            # ponytail: the 35 senses three levels deep keep their middle level in the sub-sense's text.
            sense["subsenses"].append({
                "gloss": ": ".join(text for text, _ in subs), "labels": [label for _, labels in subs for label in labels] + register, "subsenses": [],
            })
    return senses


def from_kaikki(item: dict) -> dict | None:
    """What the dataset keeps of one kaikki.org entry, or None for an entry AraDict doesn't show:
    one of another part of speech, or one whose senses are all relations (كُتُب "plural of كِتَاب")."""
    if item.get("pos") not in KEPT_POS:
        return None
    senses = _senses(item)
    if not senses:
        return None
    forms = [f for f in item.get("forms", ()) if not NOT_FORMS & set(f.get("tags", ()))]
    # The forms its headword line gives, with their tags; those of its declension or conjugation table by spelling only.
    head = [(f["form"], f.get("tags", [])) for f in forms if "source" not in f]
    canonical = next((form for form, tags in head if "canonical" in tags), item["word"])
    return {
        "word": canonical,
        "pos": item["pos"],
        "senses": senses,
        "forms": head,
        "inflections": list(dict.fromkeys(f["form"] for f in forms if "source" in f)),
        "romanization": next((f["form"] for f in item.get("forms", ()) if "romanization" in f.get("tags", ())), None),
        "ipa": [(s["ipa"], s.get("note") or ", ".join(s.get("tags", ()))) for s in item.get("sounds", ()) if "ipa" in s],
        "root": _root(item),
        "url": f"{WIKI}{item['word'].replace(' ', '_')}#Arabic",
    }


def build(source: Path, target: Path) -> int:
    """Builds the dataset at target from a kaikki.org JSONL file; returns how many entries it holds."""
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(partial)) as db, source.open(encoding="utf-8") as lines:
        db.execute("CREATE TABLE entry (letters TEXT NOT NULL, pos TEXT NOT NULL, entry TEXT NOT NULL)")
        kept = (entry for line in lines if (entry := from_kaikki(json.loads(line))))
        db.executemany("INSERT INTO entry VALUES (?, ?, ?)", (
            (letters(entry["word"]), entry["pos"], json.dumps(entry, ensure_ascii=False, separators=(",", ":"))) for entry in kept
        ))
        db.execute("CREATE INDEX entry_letters ON entry (letters, pos)")
        db.execute(f"PRAGMA user_version = {LAYOUT}")
        db.commit()
        count = db.execute("SELECT count(*) FROM entry").fetchone()[0]
        db.execute("VACUUM")
    partial.replace(target)
    return count


def _download(source: Path) -> None:
    print(f"Downloading the kaikki.org Arabic extraction (about 870 MB) to {source} …", flush=True)
    source.parent.mkdir(parents=True, exist_ok=True)
    partial = source.with_name(source.name + ".part")
    with urlopen(URL, timeout=120) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, 1 << 20)
    partial.replace(source)


def _verify(source: Path) -> None:
    with source.open("rb") as f:
        actual = file_digest(f, "sha256").hexdigest()
    if actual != SHA256:
        raise RuntimeError(
            f"{source} does not match the pinned kaikki.org extraction: its SHA-256 is {actual}, the pin is {SHA256}. "
            f"kaikki.org has probably published a newer extraction at {URL}, which it overwrites in place; "
            f"or the download was cut short. To move the pin, check the new extraction's date at "
            f"https://kaikki.org/dictionary/rawdata.html, set SHA256 in src/aradict/wiktionary.py to {actual} "
            f"and the date beside it, then build again and run the tests. Nothing was built."
        )


def ensure_dataset(source: Path = SOURCE, target: Path | None = None) -> Path:
    """Downloads the pinned extraction to source unless a copy is there, checks it against the pin,
    and builds the dataset at target (by default `dataset_path()`)."""
    target = target or dataset_path()
    if not source.is_file():
        _download(source)
    print(f"Checking {source} against the pin …", flush=True)
    _verify(source)
    started = time.monotonic()
    count = build(source, target)
    print(f"Built {target}: {count:,} entries in {time.monotonic() - started:.0f} s.", flush=True)
    return target


if __name__ == "__main__":
    ensure_dataset(*map(Path, sys.argv[1:2]))
