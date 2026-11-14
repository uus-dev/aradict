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
from contextlib import closing
from dataclasses import dataclass
from hashlib import file_digest
from pathlib import Path
from typing import NamedTuple
from urllib.request import urlopen

from .readable import MARK, SHADDA, STEM_KEY

# kaikki.org's extraction of 2026-10-30, from the English Wiktionary dump of 2026-10-01.
# ponytail: the URL isn't dated. kaikki.org overwrites the file with each new extraction, after which
# it no longer matches this pin and the build stops, saying how to move the pin (`_verify`).
URL = "https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl"
SHA256 = "19eee17681c23b3da039878ee7c970d93b75a339989a17a842f14aa7f44ea236"
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "wiktionary"
SOURCE = DEFAULT_DIR / "kaikki.org-dictionary-Arabic.jsonl"
WIKI = "https://en.wiktionary.org/wiki/"


# What the build keeps: raised whenever that changes, so that an older dataset is rebuilt, not misread.
# 1 (#20) kept each sense's text; 2 (#22) its labels and sub-senses too; 3 (#23) its relations, entries
# that are only relations, the forms' transliterations and only the pronunciations that are the entry's own;
# 4 (#24) indexes every entry by the letters of its headword and of each form it lists, for words only Wiktionary has,
# and leaves a verb's participles and verbal nouns, which are other words, out of its conjugation.
LAYOUT = 4


def dataset_path() -> Path:
    """The dataset the app reads; override with ARADICT_WIKTIONARY_PATH. The app runs without it."""
    return Path(os.environ.get("ARADICT_WIKTIONARY_PATH", DEFAULT_DIR / "wiktionary.db"))


def check(dataset: Path) -> None:
    """Refuses a dataset an older build wrote, saying how to build it again."""
    with closing(_connect(dataset)) as db:
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


class Form(NamedTuple):
    """A form an entry's headword line gives: the headword itself, its plural, a verb's verbal noun."""

    form: str  # كُتُب
    tags: tuple[str, ...]  # kaikki.org's, "canonical", "masculine", "plural", "noun-from-verb", with any register label: "obsolete"
    romanization: str | None  # kutub


class Relation(NamedTuple):
    """What a sense says when it relates the word to another rather than saying what it means."""

    kind: str  # "verbal noun of", "plural of", "Classical Arabic spelling of"
    word: str  # the other word, كَتَبَ
    romanization: str | None  # kataba
    labels: tuple[str, ...]  # "Measure I", and any register label: "obsolete"


@dataclass(frozen=True)
class Entry:
    """One Wiktionary entry: a headword with one part of speech and etymology."""

    word: str  # vocalized, كِتَاب
    pos: str  # Wiktionary's part of speech: noun, verb, adj, name, …
    senses: tuple[Sense, ...]  # its meanings, in Wiktionary's order; none for an entry that is only relations (كُتُب)
    relations: tuple[Relation, ...]  # "verbal noun of كَتَبَ", in Wiktionary's order; never meanings
    forms: tuple[Form, ...]  # the headword line's forms: the headword with its gender, كُتُب "plural"
    inflections: tuple[str, ...]  # each spelling in its declension or conjugation table, once; not its participles or verbal nouns
    romanization: str | None  # kitāb
    ipa: tuple[tuple[str, str], ...]  # each pronunciation with where it is said, "" for Modern Standard Arabic
    root: str | None  # its letters, "ك ت ب"; None when Wiktionary gives none, or two
    url: str  # the Wiktionary page

    @property
    def page(self) -> str:
        """The Wiktionary page's title: the headword without its marks, كتاب."""
        return self.url.removeprefix(WIKI).removesuffix("#Arabic").replace("_", " ")

    @property
    def spellings(self) -> tuple[str, ...]:
        """Every spelling of the word the entry gives: its headword, the forms of its headword line (its plural,
        an adjective's feminine) and its declension or conjugation; not its verbal nouns, which are other words."""
        return (self.word, *(f.form for f in self.forms if not OTHER_WORDS & set(f.tags)), *self.inflections)


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


def key(word: str) -> str:
    """A word's letters as Arabic lookup compares them (Dictionary.lookup_ar): no marks or tatweel, alif's
    hamza forms and wasla as ا, ى as ي and ة as ه. Each spelling of an entry is indexed so, for by_form."""
    return MARK.sub("", unicodedata.normalize("NFC", word).replace("ـ", "")).translate(STEM_KEY)


WORD = re.compile("[ء-ي]+")  # a key that is one Arabic word: not "-" for an empty cell of a table, nor a phrase


def _connect(dataset: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{dataset.absolute().as_uri()}?mode=ro", uri=True)  # absolute, not resolve: no lstat per folder per query


def by_form(dataset: Path, keys: list[str]) -> list[Entry]:
    """The entries with a spelling (Entry.spellings) whose key is one of keys, in Wiktionary's order."""
    with closing(_connect(dataset)) as db:
        rows = db.execute(f"SELECT entry FROM entry WHERE id IN (SELECT entry FROM form WHERE key IN ({', '.join('?' * len(keys))})) ORDER BY id", keys)
        return [_entry(json.loads(row)) for row, in rows]


def by_prefix(dataset: Path, prefix: str, limit: int) -> list[Entry]:
    """Up to limit entries with meanings whose headword, one word, has a key that starts with prefix's,
    shortest first, then alphabetical."""
    with closing(_connect(dataset)) as db:
        rows = db.execute(
            "SELECT entry FROM entry WHERE key >= ? AND key < ? AND key NOT LIKE '% %' AND json_array_length(entry, '$.senses')"
            " ORDER BY length(key), key, id LIMIT ?",
            (key(prefix), key(prefix) + "￿", limit),
        )
        return [_entry(json.loads(row)) for row, in rows]


def entries(dataset: Path, lemma: str, pos: str | None = None) -> list[Entry]:
    """The Wiktionary entries of a CAMeL lemma with this part of speech (any, without pos), in Wiktionary's
    order. Homographs from different etymologies (قَالَ "say" and قَالَ "nap") are separate entries. An
    entry that is only relations stands for the lemma only where no entry with meanings does: the
    lemma كُتّاب is the Quran school, not the plural of كَاتِب, but the lemma كَتْب is "verbal noun of كَتَبَ"."""
    with closing(_connect(dataset)) as db:
        rows = db.execute("SELECT entry FROM entry WHERE letters = ? AND pos = coalesce(?, pos) ORDER BY id", (letters(lemma), pos and wiktionary_pos(pos)))
        found = [e for row, in rows if same_word(lemma, (e := _entry(json.loads(row))).word)]
    return [e for e in found if e.senses] or found


def same_word(lemma: str, headword: str) -> bool:
    """Whether a CAMeL lemma and a Wiktionary headword with its letters spell the same word: the join's
    spellings agree, or one of them has no marks to tell."""
    return not MARK.search(lemma) or not MARK.search(headword) or spelling(headword) == spelling(lemma)


class Join(NamedTuple):
    """A CAMeL lemma's Wiktionary entries, in Wiktionary's order, and the one joined to the lemma
    (see Dictionary.wiktionary); None when there are several and CAMeL's glosses don't pick one."""

    entries: list[Entry]
    joined: Entry | None


def _entry(data: dict) -> Entry:
    def tuples(value):
        return tuple(map(tuples, value)) if isinstance(value, list) else value

    def sense(data: dict) -> Sense:
        return Sense(data["gloss"], tuple(data["labels"]), tuple(map(sense, data["subsenses"])))
    return Entry(**{key: tuples(value) for key, value in data.items()} | {
        "senses": tuple(map(sense, data["senses"])),
        "relations": tuple(Relation(*r) for r in tuples(data["relations"])),
        "forms": tuple(Form(*f) for f in tuples(data["forms"])),
    })


# --- The build ------------------------------------------------------------------------------

# The parts of speech AraDict shows: those CAMeL's map to. Phrases, affixes, letters and roots are left out.
KEPT_POS = {"noun", "name", "adj", "verb", "adv", "pron", "prep", "conj", "particle", "intj", "num", "abbrev"}
# Form tags that describe the extraction, not the word.
NOT_FORMS = {"romanization", "table-tags", "inflection-template"}
# Forms that are other words, each with its own entry: a verb's verbal nouns and participles (كِتَابَة, كَاتِب).
OTHER_WORDS = {"noun-from-verb", "participle"}
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


REGISTER_LABELS = {tag.replace("-", " ") for tag in REGISTER}  # as AraDict writes them: "Egyptian Arabic"


def _labelled(gloss: str) -> tuple[str, list[str]]:
    """A gloss as Wiktionary shows it, split into its text and the labels in front of it."""
    m = QUALIFIER.match(gloss)
    return (gloss[m.end():], [label.strip() for label in m.group(1).split(",")]) if m else (gloss, [])


def _register(tags) -> list[str]:
    """The register labels among kaikki.org's tags, as AraDict writes them."""
    return [tag.replace("-", " ") for tag in tags if tag in REGISTER or tag in REGISTER_LABELS]


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
        register = [label for label in _register(s.get("tags", ())) if label.casefold() not in shown]
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


ARABIC = re.compile("[\u0600-\u06ff]")
ROMANIZATION = re.compile(r"\(?([^,()“”:+]+)")  # what kaikki.org gives with a relation: "kataba", "(kataba) (form I)", "kātib, “writer”"
FORM_OF_MEASURE = re.compile(r"\(form ([IVX]+q?)\)")


def _relations(item: dict) -> list[list]:
    """The entry's relations, each as [kind, word, romanization, labels]: "verbal noun of", كَتَبَ,
    kataba and ["Measure I", "obsolete"]. A label its kind already says ("Classical Arabic spelling of")
    isn't repeated, and a relation to no Arabic word ("capital of a column") is no relation."""
    relations = []
    for s in item.get("senses", ()):
        if not s.get("glosses") or not _relation(s):
            continue
        gloss, (_, labels) = s["glosses"][-1], _labelled((s.get("raw_glosses") or s["glosses"])[-1])
        labels += [label for label in _register(s.get("tags", ())) if label.casefold() not in " ".join(labels).casefold()]
        targets = [t for t in s.get("form_of") or s.get("alt_of") or () if ARABIC.search(t["word"]) and gloss.find(t["word"]) > 0]
        kind = targets and gloss[:min(gloss.find(t["word"]) for t in targets)].strip()  # "active participle of فَرَغَ or فَرِغَ"
        for target in targets:
            word, extra = target["word"], target.get("extra", "")
            romanization, measure = ROMANIZATION.match(extra), FORM_OF_MEASURE.search(extra)
            relations.append([kind, word, romanization and romanization.group(1).strip(), [
                *([f"Measure {measure.group(1)}"] if measure else []), *(label for label in labels if label.casefold() not in kind.casefold()),
            ]])
    return relations


# IPA's letters as kaikki.org's romanization writes them; IPA's j (romanized y) first, so the j that d͡ʒ becomes stays.
IPA_LETTERS = [
    ("j", "y"), ("d͡ʒ", "j"), ("ɡ", "g"), ("ðˤ", "ẓ"), ("sˤ", "ṣ"), ("dˤ", "ḍ"), ("tˤ", "ṭ"), ("lˤ", "l"), ("θ", "ṯ"), ("ħ", "ḥ"),
    ("x", "ḵ"), ("ð", "ḏ"), ("ʃ", "š"), ("ɣ", "ḡ"), ("aː", "ā"), ("iː", "ī"), ("uː", "ū"), ("eː", "ē"), ("oː", "ō"),
]


def says(ipa: str, romanization: str) -> bool:
    """Whether a pronunciation is of the word its romanization spells: /ki.taːb/ of kitāb, not /ka.ta.ba/
    of katb. kaikki.org can give an entry the pronunciations of other entries on its page."""
    said = re.sub(r"[/\[\].ˈˌ‿\s]", "", ipa)
    for letter, written in IPA_LETTERS:
        said = said.replace(letter, written)
    said = re.sub(r"(\w)ː", r"\1\1", said)  # a doubled consonant: /tˤibː/, ṭibb
    spelled = re.sub(r"[-\s]", "", romanization)
    return said in (spelled, re.sub(r"iyy\b", "ī", spelled))  # ʕarabiyy is said /ʕa.ra.biː/


def _form(f: dict) -> list:
    """A form of the headword line as [form, tags, romanization], its register labels as AraDict writes them."""
    form, romanization = f["form"], f.get("roman")
    if not romanization and (m := re.fullmatch(r"(\S+) \(([^()]+)\)", form)):  # kaikki.org may put it in the form: "سُفُور (sufūr)"
        form, romanization = m.groups()
    tags = f.get("tags", [])
    return [form, [tag for tag in tags if tag not in REGISTER] + _register(tags), romanization]


def from_kaikki(item: dict) -> dict | None:
    """What the dataset keeps of one kaikki.org entry, or None for an entry AraDict doesn't show:
    one of another part of speech, or one with neither meanings nor relations."""
    if item.get("pos") not in KEPT_POS:
        return None
    senses, relations = _senses(item), _relations(item)
    if not (senses or relations):
        return None
    forms = [f for f in item.get("forms", ()) if not NOT_FORMS & set(f.get("tags", ()))]
    # The forms its headword line gives, with their tags; those of its declension or conjugation table by spelling only.
    head = [_form(f) for f in forms if "source" not in f]
    canonical = next((form for form, tags, _ in head if "canonical" in tags), item["word"])
    romanization = next((f["form"] for f in item.get("forms", ()) if "romanization" in f.get("tags", ())), None)
    ipa = [(s["ipa"], s.get("note") or ", ".join(s.get("tags", ())).replace("-", " ")) for s in item.get("sounds", ()) if "ipa" in s]
    return {
        "word": canonical,
        "pos": item["pos"],
        "senses": senses,
        "relations": relations,
        "forms": head,
        "inflections": list(dict.fromkeys(f["form"] for f in forms if "source" in f and not OTHER_WORDS & set(f.get("tags", ())))),
        "romanization": romanization,
        # Modern Standard Arabic's only where they are the entry's own; kaikki.org can't tell whose the regional ones are.
        "ipa": [(said, where) for said, where in ipa if where or not romanization or says(said, romanization)],
        "root": _root(item),
        "url": f"{WIKI}{item['word'].replace(' ', '_')}#Arabic",
    }


def _share_labels(entries: list[dict]) -> None:
    """A register label on one side of a relation shows on the other (PRD, Wiktionary layer, Register):
    كِتَاب says it is an obsolete verbal noun of كَتَبَ, so كَتَبَ's verbal noun كِتَاب is marked obsolete
    too; and a plural its singular marks rare is a rare plural of it. Words are matched by spelling."""
    said: dict[tuple[str, str], set[str]] = {}  # (the word a relation is to, the word it is from): its register labels
    listed: dict[tuple[str, str], set[str]] = {}  # (a headword, one of its forms): the form's register labels
    for e in entries:
        for _, word, _, labels in e["relations"]:
            said.setdefault((spelling(word), spelling(e["word"])), set()).update(_register(labels))
        for form, tags, _ in e["forms"]:
            listed.setdefault((spelling(e["word"]), spelling(form)), set()).update(_register(tags))
    for e in entries:
        for form, tags, _ in e["forms"]:
            tags += sorted(said.get((spelling(e["word"]), spelling(form)), set()) - set(tags))
        for _, word, _, labels in e["relations"]:
            labels += sorted(listed.get((spelling(word), spelling(e["word"])), set()) - set(labels))


def build(source: Path, target: Path) -> int:
    """Builds the dataset at target from a kaikki.org JSONL file; returns how many entries it holds."""
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(partial)) as db, source.open(encoding="utf-8") as lines:
        # An explicit id: VACUUM may renumber a plain rowid, which the form table refers to.
        db.execute("CREATE TABLE entry (id INTEGER PRIMARY KEY, letters TEXT NOT NULL, pos TEXT NOT NULL, key TEXT NOT NULL, entry TEXT NOT NULL)")
        db.execute("CREATE TABLE form (key TEXT NOT NULL, entry INTEGER NOT NULL, PRIMARY KEY (key, entry)) WITHOUT ROWID")
        kept = [entry for line in lines if (entry := from_kaikki(json.loads(line)))]
        _share_labels(kept)
        db.executemany("INSERT INTO entry VALUES (?, ?, ?, ?, ?)", (
            (id, letters(entry["word"]), entry["pos"], key(entry["word"]), json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
            for id, entry in enumerate(kept, 1)
        ))
        db.executemany("INSERT INTO form VALUES (?, ?)", (  # of words only, not of phrases such as عَادَ أَدْرَاجَهُ
            (k, id) for id, entry in enumerate(kept, 1) if WORD.fullmatch(key(entry["word"]))
            for k in dict.fromkeys(map(key, _entry(entry).spellings)) if WORD.fullmatch(k)
        ))
        db.execute("CREATE INDEX entry_letters ON entry (letters, pos)")
        db.execute("CREATE INDEX entry_key ON entry (key)")
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
