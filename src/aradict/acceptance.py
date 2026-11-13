"""The release gate's data acceptance pass and local performance measurements (#17).

    uv run python -m aradict.acceptance > ACCEPTANCE.md

checks the pinned database as users see it, through the dictionary contract; checks the
provenance and license notices, the privacy statement and the support destination; times a
real server on this machine; and prints the report. It takes a few minutes. Run it again whenever the database pin, the readable layer or the
About page changes, and commit the new report.
"""

from __future__ import annotations

import os
import platform
import re
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import views
from .data import EXPECTED, VERSION, db_path
from .dictionary import ROOT, Dictionary, Reading
from .readable import IRREGULAR_PLURALS, MARK, SHADDA, head_noun, is_participle

REPO = Path(__file__).resolve().parents[2]
LETTERS = "\u0621-\u063a\u0641-\u064a\u0671"  # Arabic's letters, ٱ included; no tatweel
CLASHING = re.compile("[\u064b-\u0650\u0652]")  # harakat, tanween and sukun: one of them per letter


# --- Checks on one value ---------------------------------------------------------------------

def malformed(text: str) -> str | None:
    """What is wrong with an Arabic form or lemma, or None."""
    if re.search("[A-Za-z]", text):
        return "Latin letters"
    if re.search(f"[^{LETTERS}{MARK.pattern[1:-1]}]", text):
        return "other characters"
    if MARK.match(text):
        return "a mark with no letter"
    if any(len(CLASHING.findall(marks)) > 1 or marks.count(SHADDA) > 1 for marks in re.findall(f"[{LETTERS}]({MARK.pattern}*)", text)):
        return "clashing marks on one letter"
    return None


def singular_after_two(sense: str) -> bool:
    """The "two school" defect: a singular noun after "two", the noun found as readable.plural
    finds it (two period of time). A participle ("two wounded") is not counted, as English leaves
    it bare; that exempts what the fix exempts, so the report lists the words it exempts."""
    found = re.search(r"\btwo (.+)", sense)
    if not found:
        return False
    _, word, _ = head_noun(found.group(1))
    # ponytail: a word ending in s counts as plural, so "two walrus" passes; list such words if they turn up.
    return not (word.endswith("s") or word in IRREGULAR_PLURALS.values() or is_participle(word))


# A phrasal verb's particle (taking over) with a plural -s.
PHRASAL = re.compile(r"\b(?:out|over|away|up|off|down)s\b")


def overpluralized(sense: str) -> bool:
    """An adjective-like sense given a plural ending: a participle, as readable.is_participle tells
    one ("two firmly establisheds"), or a phrasal verb's particle ("two taking overs"). A heuristic:
    it misses adjectives in -ing ("two pantings"), which it can't tell from nouns ("two buildings")."""
    return any(w.endswith("eds") and is_participle(w[:-1]) for w in re.findall(r"[\w-]+", sense)) or bool(PHRASAL.search(sense))


def approx(n: int) -> str:
    """A count rounded to two significant figures for a learner: 38,353 → "38,000"."""
    return f"{round(n, 2 - len(str(n))):,}"


# --- The data pass ---------------------------------------------------------------------------

def inventory(db) -> tuple[list[dict], list[tuple[str, str]], set[str], list[str]]:
    """The database's stem entries, entries (lemma and part of speech), lemmas and well-formed
    roots. NOAN, the database's placeholder for an unanalysable word, is left out."""
    stems = [f for entries in db.stem_hash.values() for _, f in entries if f["lex"] != "NOAN"]
    entries = sorted({(f["lex"], f["pos"]) for f in stems})
    roots = sorted({f.get("root", "") for f in stems if ROOT.fullmatch(f.get("root", ""))})
    return stems, entries, {lemma for lemma, _ in entries}, roots


def _rootless(stems: list[dict], entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The entries none of whose stems has a well-formed root."""
    rooted = {(f["lex"], f["pos"]) for f in stems if ROOT.fullmatch(f.get("root", ""))}
    return [e for e in entries if e not in rooted]


def coverage(d: Dictionary, db) -> dict:
    """The coverage the About page states, measured: stem entries, entries, headwords and roots;
    the roots with an unresolved radical; the entries with no root, by part of speech, most first;
    and the verbs, counted by their root's length and whether they have a measure."""
    stems, entries, lemmas, roots = inventory(db)
    rootless = _rootless(stems, entries)
    stored_roots = Counter(f.get("root", "") for f in stems)
    unresolved = [root for root in roots if "#" in root]
    verb_roots = {f["lex"]: f.get("root", "") for f in stems if f["pos"] == "verb"}
    return {
        "stems": len(stems), "entries": len(entries), "lemmas": len(lemmas), "roots": len(roots),
        "unresolved": len(unresolved),
        "unresolved_example": max((root for root in unresolved if root.count("#") == 1), key=stored_roots.get, default=""),
        "unresolved_stems": sum(n for root, n in stored_roots.items() if "#" in root),
        "rootless": len(rootless), "rootless_by_pos": Counter(pos for _, pos in rootless).most_common(),
        "verbs": len(verb_roots),
        "measures": Counter(
            (root.count(".") + 1 if ROOT.fullmatch(root) else 0, ROOT.fullmatch(root) is not None and d.measure(lemma, root) is not None)
            for lemma, root in verb_roots.items()
        ),
    }


def root_fills(d: Dictionary, db) -> Counter:
    """How Wiktionary (d's dataset) does at filling the roots CAMeL leaves open, counted by entry
    and open root: filled, as its entries agree or as CAMeL's gloss picks one of them; not filled,
    as its root disagrees with CAMeL's letters, as its entries give several roots that the gloss
    can't choose between (homographs), as no entry gives a root, or as it has no entry."""
    stems, _, _, _ = inventory(db)
    found: Counter = Counter()
    for lemma, pos, root in {(f["lex"], f["pos"], f["root"]) for f in stems if ROOT.fullmatch(f.get("root", "")) and "#" in f["root"]}:
        entries = d.wiktionary(lemma, pos)
        roots = {e.root for e in entries}
        if d.filled_root(lemma, pos, root):
            found["filled: the gloss picks" if len(roots) > 1 else "filled: the entries agree"] += 1
        elif d.wiktionary_root(lemma, pos, root):
            found["disagrees with CAMeL's letters"] += 1
        else:
            found["homographs left open" if roots - {None} else "no root on Wiktionary" if entries else "no Wiktionary entry"] += 1
    return found


def _sample_words(db) -> list[str]:
    """Words to look up: every 20th stem, bare and with common attached parts, and the dual of
    every noun stem, which the "two school" check needs."""
    keys = sorted(db.stem_hash)
    nouns = [key for key in keys if any(f["pos"] == "noun" for _, f in db.stem_hash[key])]
    return [w for k in keys[::20] for w in (k, "و" + k, "بال" + k, k + "ها", "سي" + k)] + [k + end for k in nouns for end in ("ان", "تان")]


def _example(r: Reading) -> str:
    return f"{r.form} “{r.gloss}” ({r.lemma}, {r.pos})"


def _first(items) -> str:
    return next(iter(items), "")


def data_pass(d: Dictionary, db) -> dict:
    """Every entry's forms and every root's words, as the related and root views list them, plus
    the readings of a sample of words looked up: checked for what users would see wrong, and counted."""
    stems, entries, _, roots = inventory(db)
    related = {e: d.related(*e) for e in entries}
    family = {root: d.root_family(root) for root in roots}
    looked_up = [r for w in _sample_words(db) for r in d.lookup_ar(w)]
    lists = {**{f"{lemma} ({pos})": rs for (lemma, pos), rs in related.items()}, **family}
    shown = [r for rs in lists.values() for r in rs] + looked_up

    by_id: dict[str, set] = {}
    for r in shown:
        by_id.setdefault(r.id, set()).add((r.form, r.lemma, r.pos, r.gloss))
    twice = []  # (list, reading): a row the list shows more than once
    for name, rs in lists.items():
        for row, n in Counter((r.form, r.gloss, r.lemma, r.pos) for r in rs).items():
            if n > 1:
                twice.append((name, next(r for r in rs if (r.form, r.gloss, r.lemma, r.pos) == row)))
    stored_roots = Counter(f.get("root", "") for f in stems)
    bad_roots = Counter({root: n for root, n in stored_roots.items() if not ROOT.fullmatch(root)})
    bad_arabic: dict[tuple[str, str], Reading] = {}  # (what is wrong, the form or lemma): a reading that shows it
    for r in shown:
        for text in (r.form, r.lemma):
            if why := malformed(text):
                bad_arabic.setdefault((why, text), r)
    no_form = [e for e, rs in related.items() if not rs]
    in_family = {root: set(rs) for root, rs in family.items()}
    stray = [r for rs in related.values() for r in rs if r.root and r not in in_family[r.root]]
    found = {  # findings the report explains as known limits: (count, example)
        "twice": (len(twice), _first(f"{_example(r)}, in the list for {name}" for name, r in twice)),
        "no_form": (len(no_form), _first(f"{lemma} ({pos})" for lemma, pos in no_form)),
        "bad_roots": (sum(bad_roots.values()), ", ".join(f"{root or '(empty)'} ×{n:,}" for root, n in bad_roots.most_common(4))),
        "bad_arabic": (len(bad_arabic), "; ".join({why: f"{why}: {_example(r)}" for (why, _), r in bad_arabic.items()}.values())),
    }
    checks = [
        ("Duplicate identities", "one reading id for two different readings", sum(len(s) > 1 for s in by_id.values()), ""),
        ("Duplicate identities", "the same row (form, gloss, lemma, part of speech) twice in one related or root list", *found["twice"]),
        ("Broken relations", "a root link that opens an empty list", sum(not rs for rs in family.values()), ""),
        ("Broken relations", "a form missing from its own root's list", len(stray), _first(map(_example, stray))),
        ("Broken relations", "an entry with no stand-alone form, so in no related or root list (lookups still find it)", *found["no_form"]),
        ("Broken relations", "a stem whose stored root is not dotted letters, so its root shows as unavailable", *found["bad_roots"]),
        ("Empty required fields", "a reading with no form, lemma, gloss or part of speech",
         sum(not (r.form and r.lemma and r.gloss and r.pos) for r in shown), ""),
        *(("Malformed Arabic", f"a distinct form or lemma with {why}", n, _first(_example(r) for (w, _), r in bad_arabic.items() if w == why))
          for why, n in Counter(why for why, _ in bad_arabic).items()),
    ]
    if not bad_arabic:
        checks.append(("Malformed Arabic", "a form or lemma with Latin letters, other characters, a mark with no letter or clashing marks", 0, ""))

    # Known defects.
    visible = [text.lower() for r in shown for text in (r.gloss, *r.tags, r.grammar, *(s.label for s in r.segments))]
    raw = [f.get("gloss", "").lower() for table in (db.stem_hash, db.prefix_hash, db.suffix_hash) for e in table.values() for _, f in e]
    duals = [r for r in looked_up if r.pos == "noun" and r.tags[-1].endswith("dual")]
    plurals = duals + [r for r in looked_up if r.pos == "noun" and r.tags[-1].endswith("plural") and "broken plural" not in r.grammar]
    two_school = [r for r in duals if any(singular_after_two(s) for s in r.gloss.split("; "))]
    overplural = [r for r in plurals if overpluralized(r.gloss)]
    # Readings whose noun is a participle in -ed, which takes no plural ending, and so the "two
    # school" check passes too: the words, by how many dual and sound plural readings show each bare.
    bare = {r: [w for s in r.gloss.split("; ") if is_participle(w := head_noun(s)[1])] for r in plurals}
    bare = {r: words for r, words in bare.items() if words}
    entry_roots = {e: sorted({r.root for r in rs if r.root}) for e, rs in related.items()}
    alternatives = [(e, rs) for e, rs in entry_roots.items() if len(rs) > 1]
    proper_rootless = [e for e in _rootless(stems, entries) if e[1] == "noun_prop"]
    return {
        **coverage(d, db),
        "listed": len(shown) - len(looked_up), "looked_up": len(looked_up),
        "standalone": len(entries) - len(no_form),
        "checks": checks, "found": found,
        "misspelled": [(word, sum(word in t for t in visible), sum(word in g for g in raw)) for word in ("genetive", "possesive")],
        "two_school": (len(two_school), len(duals), _first(map(_example, two_school))),
        "participles": (len(bare), sum(r in bare for r in duals), Counter(w for words in bare.values() for w in set(words))),
        "overplural": (len(overplural), len(plurals), _first(map(_example, overplural))),
        "alternatives": (len(alternatives), sum("/" in root for root in stored_roots),
                         _first(f"{lemma} ({pos}): {' and '.join(rs)}" for (lemma, pos), rs in alternatives)),
        "proper": (len(proper_rootless), sum(pos == "noun_prop" for _, pos in entries),
                   _first(_example(related[e][0]) for e in proper_rootless if related[e]),
                   sum(f.get("root") == "NTWS" for f in stems if f["pos"] == "noun_prop")),
    }


# --- Provenance, licenses, privacy and support -----------------------------------------------

def notices(db: Path, digest: str) -> list[tuple[str, bool]]:
    """Each check, with whether it holds: of the database, whose SHA-256 digest is given, against
    its pin; of the About page's credits and the shipped license files against DATA-SOURCES.md
    and the database's own LICENSE; and of the privacy statement and support destination the
    release gate asks for."""
    about = str(views.about_page())
    sources = (REPO / "DATA-SOURCES.md").read_text(encoding="utf-8")
    data_license = (db.parent / "LICENSE").read_bytes()

    def section(name: str) -> str:
        found = re.search(f'<section id="{name}">(.*?)</section>', about, re.S)
        return found.group(1) if found else ""

    pages = [str(views.word_page("", views.INITIAL)), str(views.text_page("", views.State())), about]
    # The same facts, worded as DATA-SOURCES.md and the About page word them.
    facts = [
        ("calima-msa-r13", "calima-msa-r13"), ("2022.03.21", "2022.03.21"), ("GPL v2", "General Public License version 2"),
        ("Aramorph 1.2.1", "Aramorph 1.2.1"), ("Buckwalter 1.0", "Buckwalter Arabic Morphological Analyzer 1.0"),
    ]
    copyrights = re.findall(r"^; *((?:Portions )?\(c\) \d{4} .*?),? *$", data_license.decode().replace("\r", ""), re.M)
    shipped = re.findall(r'href="/static/(vendor/[^"]+)"', about)
    return [
        ("The database matches the SHA-256 checksum pinned in `data.py`", digest == EXPECTED["morphology.db"]),
        ("DATA-SOURCES.md quotes the same checksum", f"`{digest[:8]}…{digest[-4:]}`" in sources),
        ("The database's LICENSE file matches its pinned checksum and is the GPL version 2",
         sha256(data_license).hexdigest() == EXPECTED["LICENSE"] and b"GENERAL PUBLIC LICENSE Version 2" in data_license),
        *((f"DATA-SOURCES.md says “{ours}” and About says “{theirs}”", ours in sources and theirs in about) for ours, theirs in facts),
        *((f"About quotes the data's copyright line “{line}”", line in about) for line in copyrights),
        ("AraDict's LICENSE is the GPL version 2 text, and pyproject.toml says GPL-2.0-or-later, as About states",
         "GNU GENERAL PUBLIC LICENSE\n                       Version 2" in (REPO / "LICENSE").read_text(encoding="utf-8")
         and 'license = "GPL-2.0-or-later"' in (REPO / "pyproject.toml").read_text(encoding="utf-8")
         and "either version 2 of the License, or (at your option) any later version" in about),
        ("About links a license for each bundled asset (htmx and the two fonts)", len(shipped) == 3),
        *((f"About's link to `/static/{path}` reaches a shipped file", (Path(views.__file__).parent / "static" / path).is_file())
          for path in shipped),
        ("About has a privacy statement: no accounts, history and settings kept in the browser, what lookups and passages send "
         "to the server, and that passages are not logged (`tests/test_app.py` checks that no lookup or passage is logged)",
         all(claim in section("privacy") for claim in ("no accounts", "stay in this browser", "is sent there", "are not logged"))),
        ("About gives a support destination: the GitHub Issues of AraDict's repository, the one README.md links",
         f'href="{views.REPO}/issues"' in section("support") and views.REPO in (REPO / "README.md").read_text(encoding="utf-8")),
        ("Every page links to About and help from its main navigation", all('href="/about"' in page for page in pages)),
    ]


# --- Performance -----------------------------------------------------------------------------

WORDS = {
    "bare": ["كتب", "مدرسة", "قال", "علم", "الى", "من"],
    "marked": ["كَتَبَ", "كُتُب", "مَدْرَسَةٌ", "عِلْم"],
    "clitics": ["وبكتابهم", "سيكتبون", "مدرستي", "والكتاب", "فقالوا", "بالمدرسة"],
    "Arabizi": ["ktb", "mar7aba", "kitab", "3arabi", "shukran", "madrasa"],
    "English": ["book", "write", "school", "piece of writing", "eat", "go"],
    "not found": ["قخغثص", "qxzv"],  # an unknown Arabic word; Latin letters that spell no Arabic word
}
LOOKUPS = [(kind, {"q": w, "lang": "en"} if kind == "English" else {"q": w}) for kind, words in WORDS.items() for w in words]
LOOKUPS.append(("not found", {"q": "xyzzy", "lang": "en"}))
ROUNDS = 20  # timed rounds of every lookup, after the first
TEXT_SIZES = (100, 500, 2000)
TEXT_ROUNDS = 10
# Our own text, varied as news and a learner's reading are, with numbers, punctuation and one
# vocalized sentence. The Text view looks each word up once, so a passage that repeated itself
# would be quicker than real text.
PASSAGE = (
    "تعلم اللغة العربية رحلة طويلة تحتاج إلى صبر ووقت. يبدأ الطالب عادة بالحروف والأصوات، ثم ينتقل إلى الكلمات البسيطة "
    "والجمل القصيرة. وبعد أشهر من الدراسة يستطيع أن يقرأ نصوصا سهلة في الصحف والمجلات، لكن الكلمات الجديدة تظهر في كل "
    "صفحة، فيحتاج القارئ إلى قاموس يساعده على فهم معانيها وجذورها.\n"
    "في المدينة القديمة شوارع ضيقة وأسواق مزدحمة. يبيع التجار الخبز والفواكه والتوابل والأقمشة الملونة، ويجلس الرجال في "
    "المقاهي يشربون الشاي ويتحدثون عن أخبار اليوم. وفي المساء تمتلئ الساحات بالأطفال الذين يلعبون حتى يناديهم آباؤهم إلى البيوت.\n"
    "أعلنت الحكومة أمس عن خطة جديدة لتطوير التعليم في المدارس الحكومية. وقال الوزير في مؤتمر صحفي إن الخطة تشمل بناء "
    "مدارس حديثة وتدريب المعلمين على طرق التدريس الجديدة، كما تهدف إلى زيادة عدد الطلاب الذين يدرسون العلوم والرياضيات. "
    "وأضاف أن المشروع سيستمر خمس سنوات منذ عام 2025، وأن تكاليفه ستبلغ ملايين الدولارات.\n"
    "كان الجو باردا في الصباح، ثم أشرقت الشمس وارتفعت درجة الحرارة قليلا. خرجت العائلة إلى الحديقة القريبة، وحملت معها "
    "الطعام والماء والكتب. جلست الأم تحت شجرة كبيرة تقرأ رواية، بينما ركض الأولاد نحو البحيرة ليشاهدوا الطيور.\n"
    "قَالَ المُعَلِّمُ لِطُلَّابِهِ: اُكْتُبُوا الدَّرْسَ فِي دَفَاتِرِكُمْ، ثُمَّ اِقْرَؤُوهُ فِي البَيْتِ.\n"
    "يرى كثير من الباحثين أن القراءة اليومية أفضل طريقة لتحسين المفردات. فالقارئ الذي يقرأ مقالة واحدة كل يوم يتعرف على "
    "مئات الكلمات خلال سنة، ويتعلم كيف تستعمل في سياقات مختلفة. ولذلك ينصح المعلمون طلابهم باختيار موضوعات يحبونها، "
    "لأن الاهتمام بالموضوع يجعل التعلم أسهل وأمتع.\n"
    "وصلت الطائرة إلى المطار متأخرة ساعتين بسبب العاصفة. انتظر المسافرون في القاعة طويلا، ثم استلموا حقائبهم وخرجوا إلى "
    "سيارات الأجرة. وكتب أحدهم رسالة إلى أخيه يخبره بأنه وصل بسلام، وأنه سيزوره في الأسبوع القادم إن شاء الله.\n"
    "يعمل الأطباء في المستشفى ليلا ونهارا لعلاج المرضى. وفي الشتاء يزداد عدد المصابين بالبرد والحمى، فتطلب الإدارة من "
    "الموظفين أن يغسلوا أيديهم كثيرا وأن يلبسوا الكمامات. ويقول مدير المستشفى إن الوقاية أرخص من العلاج وأسهل منه.\n"
    "اشترى صديقي سيارة مستعملة من معرض في طرف المدينة. كانت السيارة نظيفة ورخيصة، لكن محركها توقف بعد أسبوع واحد. "
    "فذهب إلى البائع غاضبا، وطلب منه أن يصلحها أو أن يعيد إليه ماله."
)
# Proposed pass/fail budgets for server time and resources (see the report for why).
BUDGETS = {"lookup_p95": 50, "lookup_first": 500, "text_2000": 1000, "startup": 10, "memory": 768}  # ms, ms, ms, s, MB


def _start(db: Path) -> tuple[subprocess.Popen, str, float]:
    """A real server on this machine, and the seconds from starting its process to its first answer."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    start = time.perf_counter()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "aradict.app:app", "--port", str(port), "--log-level", "warning", "--no-access-log"],
        env=os.environ | {"ARADICT_DB_PATH": str(db), "PYTHONWARNINGS": "ignore::SyntaxWarning"},  # docopt's, as in pytest's config
    )
    url = f"http://127.0.0.1:{port}"
    while True:
        try:
            urlopen(f"{url}/about").read()
            return server, url, time.perf_counter() - start
        except OSError:
            if server.poll() is not None:
                raise RuntimeError("The server stopped before it answered") from None
            time.sleep(0.02)


def _ms(url: str, body: bytes | None = None) -> float:
    """Milliseconds for one request made as htmx makes it, read in full."""
    start = time.perf_counter()
    with urlopen(Request(url, body, {"HX-Request": "true"})) as response:
        response.read()
    return 1000 * (time.perf_counter() - start)


def _memory(server: subprocess.Popen) -> float:
    """The server's resident memory in MB."""
    return int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(server.pid)])) / 1024


def performance(db: Path) -> dict:
    """Startup time (median of three starts), resident memory, every lookup in LOOKUPS once after
    start and ROUNDS times more, and the Text view on the first 100, 500 and 2,000 characters of PASSAGE."""
    startups = []
    for _ in range(2):
        server, _, seconds = _start(db)
        server.terminate()
        server.wait()
        startups.append(seconds)
    server, url, seconds = _start(db)
    startups.append(seconds)
    try:
        idle = _memory(server)
        first: dict[str, list[float]] = {}
        warm: dict[str, list[float]] = {}
        for i in range(ROUNDS + 1):
            for kind, params in LOOKUPS:
                (warm if i else first).setdefault(kind, []).append(_ms(f"{url}/?{urlencode(params)}"))
        text = {n: [_ms(f"{url}/text", urlencode({"text": PASSAGE[:n]}).encode()) for _ in range(TEXT_ROUNDS)] for n in TEXT_SIZES}
        busy = _memory(server)
    finally:
        server.terminate()
        server.wait()
    return {"startup": statistics.median(startups), "idle": idle, "busy": busy, "first": first, "warm": warm, "text": text}


# --- The report ------------------------------------------------------------------------------

def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20, method="inclusive")[-1]


def _percent(part: int, whole: int) -> str:
    return f"{part:,} ({part / whole:.0%})" if whole else f"{part:,}"


def report(digest: str, data: dict, checked: list[tuple[str, bool]], perf: dict) -> str:
    """The report, for the database with this SHA-256 digest."""
    m = data["measures"]
    three, four = (m[3, True], m[3, False]), (m[4, True], m[4, False])
    other = (sum(n for (k, ok), n in m.items() if k not in (3, 4) and ok), sum(n for (k, ok), n in m.items() if k not in (3, 4) and not ok))
    rootless = dict(data["rootless_by_pos"])
    rootless_other = data["rootless"] - rootless["noun_prop"] - rootless["noun"] - rootless["adj"]
    two, duals, two_example = data["two_school"]
    bare, bare_duals, bare_words = data["participles"]
    over, plurals, over_example = data["overplural"]
    alternatives, slashed, alternative_example = data["alternatives"]
    proper, proper_total, proper_example, ntws = data["proper"]
    warm = [ms for times in perf["warm"].values() for ms in times]
    first = [ms for times in perf["first"].values() for ms in times]
    measured = {
        "lookup_p95": _p95(warm), "lookup_first": max(first), "text_2000": max(perf["text"][2000]),
        "startup": perf["startup"], "memory": perf["busy"],
    }
    words = {n: len(PASSAGE[:n].split()) for n in TEXT_SIZES}
    twice, no_form, bad_roots, bad_arabic = (data["found"][key] for key in ("twice", "no_form", "bad_roots", "bad_arabic"))

    def cell(text: str) -> str:
        return text.replace("|", "\\|") or "—"

    lines = [
        "# Release acceptance: data and performance",
        "",
        f"Generated by `uv run python -m aradict.acceptance` on {date.today():%Y-%m-%d}, against the CAMeL Tools database "
        f"`calima-msa-r13` {VERSION}, SHA-256 `{digest}`.",
        "",
        "The data pass reads the database as users see it, through the dictionary contract (`Dictionary`): the related-forms list "
        f"of every entry ({data['entries']:,} lists) and the word list of every root ({data['roots']:,} lists), {data['listed']:,} rows in all, "
        f"plus {data['looked_up']:,} readings from looking up a sample of words with attached parts and the dual of every noun stem.",
        "",
        "Not covered here, because they are the owner's to decide or need a person (#17): hosting and deployment, rate limiting, "
        "the linguist review of a sample, screen-reader checks, and timing on real mobile hardware.",
        "",
        "## Data checks",
        "",
        "| Check | A failure is | Found | Example |",
        "|---|---|--:|---|",
        *(f"| {check} | {why} | {n:,} | {cell(example)} |" for check, why, n, example in data["checks"]),
        "",
        "Every non-zero finding is explained under Known defects and limits.",
        "",
        "## Provenance, licenses, privacy and support",
        "",
        "| Check | Result |",
        "|---|---|",
        *(f"| {cell(what)} | {'pass' if ok else '**FAIL**'} |" for what, ok in checked),
        "",
        "## Coverage",
        "",
        "| Measure | Count |",
        "|---|--:|",
        f"| Stem entries | {data['stems']:,} |",
        f"| Entries (distinct lemma and part of speech) | {data['entries']:,} |",
        f"| Entries with a stand-alone form, listed in related and root views | {data['standalone']:,} |",
        f"| Lemmas (headwords) | {data['lemmas']:,} |",
        f"| Roots | {data['roots']:,} |",
        f"| Unresolved roots: a weak or hamza radical left open (`#` in the data, ◌ on screen), such as {data['unresolved_example']} "
        f"| {_percent(data['unresolved'], data['roots'])} |",
        f"| Stem entries with an unresolved root | {_percent(data['unresolved_stems'], data['stems'])} |",
        f"| Entries with no root | {_percent(data['rootless'], data['entries'])} |",
        "",
        "Entries with no root, by part of speech: " + ", ".join(f"{pos} {n:,}" for pos, n in data["rootless_by_pos"]) + ".",
        "",
        "Measure derivation for verbs, by the number of letters in the verb's root:",
        "",
        "| Verb lemmas | With a measure | Without |",
        "|---|--:|--:|",
        f"| Three-letter root (I–XII) | {three[0]:,} ({three[0] / sum(three):.1%}) | {three[1]:,} |",
        f"| Four-letter root (QI–QIV) | {four[0]:,} | {four[1]:,} |",
        f"| Other or no root | {other[0]:,} | {other[1]:,} |",
        f"| All | {three[0] + four[0] + other[0]:,} | {three[1] + four[1] + other[1]:,} |",
        "",
        "The three-letter verbs without a measure are listed one by one, with the reason, in `UNMAPPED_VERBS` in "
        "`tests/test_contract.py`: the data merges a Form III and a Form IV verb into one lemma, spells Forms VIII and IX alike, "
        "gives a root that does not fit the lemma, or tags a non-verb as a verb.",
        "",
        f"The About page states these, rounded for a learner, and `tests/test_acceptance.py` checks each against the database: "
        f"about {approx(data['entries'])} entries, {approx(data['lemmas'])} headwords and {approx(data['roots'])} roots; a measure "
        f"for all but {approx(three[1] + four[1] + other[1])} of about {approx(data['verbs'])} verbs; an unresolved radical in about "
        f"1 root in {round(data['roots'] / data['unresolved'])}; and about {approx(data['rootless'])} entries with no root: about "
        f"{approx(rootless['noun_prop'])} proper nouns, {approx(rootless['noun'])} other nouns, {approx(rootless['adj'])} adjectives and "
        f"{approx(rootless_other)} of other parts of speech.",
        "",
        "## Known defects and limits",
        "",
        "| Defect | Count | Example | Outcome |",
        "|---|---|---|---|",
        *(f"| “{word}” | {shown:,} in what AraDict shows; {raw:,} in the data's glosses | — | Not present. AraDict writes its own "
          "grammar and part labels in `readable.py` (“genitive case”, “my”, “their”); the data carries no such label. |"
          for word, shown, raw in data["misspelled"]),
        f"| Dual glosses such as “two school” | {two:,} of {duals:,} dual noun readings | {cell(two_example)} | Fixed in `readable.py`. "
        "A dual or sound plural puts the English plural on its noun (“two schools”), and since 2026-11-11 on the noun before “of” "
        "(“two periods of time”, which read “two period of times”). The check counts a singular noun after “two”. It does not count "
        f"a participle in -ed (“two wounded”), which English and the fix both leave bare, so it cannot catch a noun the fix wrongly "
        f"takes for one: it exempts {bare_duals:,} dual readings, with {len(bare_words):,} distinct words, all listed below the table. |",
        f"| Adjective-like senses given a plural ending (found by this pass) | at least {over:,} of {plurals:,} dual and sound plural "
        f"noun readings | {cell(over_example)} | Partly fixed in `readable.py` on 2026-11-11. The data glosses many participles and "
        "adjectives as nouns; a participle in -ed now takes no plural ending (“two wounded”, which read “two woundeds”: "
        f"{bare:,} of these readings). Left as a known limit: phrasal senses (“two ruling outs”) and adjectives in -ing (“two pantings”), which "
        "no rule can tell from real nouns (“two buildings”) without a word list. The count is a heuristic and misses the -ing kind. |",
        f"| Root alternatives such as “الو/الي” | {slashed:,} root fields with alternatives; {alternatives:,} entries whose stems carry "
        f"different roots | {cell(alternative_example)} | Handled. The data writes no alternatives into one root field. An entry whose "
        "stems carry different roots, usually one root with its unresolved radical in another place, shows each root as its own tab, "
        "each opening its own list. |",
        f"| Proper nouns without roots | {proper:,} of {proper_total:,} proper-noun entries | {cell(proper_example)} | Known limit, shown "
        f"as the data has it: the root tab reads “unavailable” and links nowhere. Most are foreign names, which the data marks NTWS "
        f"({ntws:,} stems). |",
        f"| The same row twice in one list (found by this pass) | {twice[0]:,} | {cell(twice[1])} | Known limit. The data stores the "
        "form twice for the lemma, once with agreement features and once without, so the related list shows two rows with the "
        "same form and gloss. |",
        f"| Entries with no stand-alone form (found by this pass) | {no_form[0]:,} | {cell(no_form[1])} | Known limit. These "
        "entries' stems occur only with an ending or a clitic, so related and root lists have no citation form to show. Word "
        "lookup finds them, and no link opens an empty list. |",
        f"| Stored roots that are not dotted letters (found by this pass) | {bad_roots[0]:,} stems | {cell(bad_roots[1])} | Known "
        "limit: the root shows as unavailable. Most are NTWS (no root). The rest are consonant strings such as رضن for أَرْض "
        "that do not match the word's root, so adding dots would invent wrong roots. |",
        f"| Malformed Arabic in the data (found by this pass) | {bad_arabic[0]:,} distinct forms and lemmas | {cell(bad_arabic[1])} | Known limit, "
        "shown as stored. These are errors in the data itself. A fix would go in AraDict's own data file with a dated change note "
        "(GPL v2 §2(a)); AraDict has no such file yet, so whether to start one is the owner's call. |",
        "",
        "### Words in -ed left without a plural ending",
        "",
        "`readable.is_participle` takes these for participles, so dual and sound plural glosses leave them bare and the “two school” "
        "check exempts them. A noun among them that should take an -s belongs in `NOT_PARTICIPLES`. Each word is followed by the "
        "number of dual and sound plural readings that show it:",
        "",
        ", ".join(f"{word} {n:,}" for word, n in sorted(bare_words.items(), key=lambda item: (-item[1], item[0]))) + ".",
        "",
        "## Performance (this machine only)",
        "",
        f"Measured on {platform.platform()}, {os.cpu_count()} cores, Python {platform.python_version()}. A real server "
        "(`uvicorn aradict.app:app`, one worker) ran on this machine, and every request was made as htmx makes it, over the loopback "
        "interface: the times are server time plus well under a millisecond of local transport. **Real mobile hardware and the "
        "production host are not measured here; that is left for the owner, with the hosting decision.** Phones mostly add network "
        "time and rendering, not server time.",
        "",
        "### Word lookup",
        "",
        f"{len(LOOKUPS)} lookups, each made once after start (first), then {ROUNDS} more times.",
        "",
        "| Kind | Words | p50 (ms) | p95 (ms) | First, worst (ms) |",
        "|---|---|--:|--:|--:|",
        *(f"| {kind} | {', '.join(params['q'] for k, params in LOOKUPS if k == kind)} | {statistics.median(times):.0f} | "
          f"{_p95(times):.0f} | {max(perf['first'][kind]):.0f} |" for kind, times in perf["warm"].items()),
        f"| **All** | | **{statistics.median(warm):.0f}** | **{_p95(warm):.0f}** | **{max(first):.0f}** |",
        "",
        "### Text analysis",
        "",
        f"Our own news-style passage, cut at each size, analysed {TEXT_ROUNDS} times.",
        "",
        "| Characters | Words | Median (ms) | Worst (ms) |",
        "|--:|--:|--:|--:|",
        *(f"| {n:,} | {words[n]} | {statistics.median(times):.0f} | {max(times):.0f} |" for n, times in perf["text"].items()),
        "",
        "### Startup and memory",
        "",
        "| Measure | Value |",
        "|---|--:|",
        f"| Startup, from process start to the first answer (median of 3) | {perf['startup']:.1f} s |",
        f"| Resident memory after startup | {perf['idle']:.0f} MB |",
        f"| Resident memory after the timings above | {perf['busy']:.0f} MB |",
        "",
        "### Proposed budgets",
        "",
        "| Budget | Proposed | Measured here | Within |",
        "|---|--:|--:|---|",
        *(f"| {what} | ≤ {BUDGETS[key]:,} {unit} | {measured[key]:,.1f} {unit} | {'yes' if measured[key] <= BUDGETS[key] else '**no**'} |"
          for key, what, unit in (
              ("lookup_p95", "Word lookup, server time, p95", "ms"),
              ("lookup_first", "Word lookup, first time a word is looked up after start, worst", "ms"),
              ("text_2000", "Text analysis of 2,000 characters, worst", "ms"),
              ("startup", "Startup to the first answer", "s"),
              ("memory", "Resident memory after use", "MB"),
          )),
        "",
        "Why these: lookup runs while the user types, debounced at about 150 ms, so its server share should stay well under that, "
        "leaving room for a mobile network and a production CPU several times slower than this one. The first lookup of a word "
        "also counts each of its roots' words once, then remembers the count, so it may take longer. Text analysis runs once per "
        "pause and shows a loading state, so up to 1 s for the largest passage the Text view accepts is acceptable. Its token "
        "details link each root without counting the root's words, which would cost about 27 ms a root the first time: the first "
        f"analysis of the 2,000-character passage took {perf['text'][2000][0]:,.0f} ms, and later ones "
        f"{statistics.median(perf['text'][2000][1:]):,.0f} ms at the median. Startup only "
        "matters on deploy and restart. The memory budget leaves headroom on a 1 GB instance, the size the CAMeL spike suggested. "
        "The owner should confirm the budgets on the production host, and the whole experience on a mid-range phone, before they "
        "become pass/fail.",
        "",
        "Checked by a test: none of these. CI runs on shared runners whose speed varies by several times, so a test tight enough "
        "to catch a regression would be flaky, and a loose one would catch nothing. `tests/test_contract.py` already bounds the one "
        "input with an unbounded cost, a very long Arabizi word (under 2 s). Rerun this script before a release instead.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    path = db_path()
    from camel_tools.morphology.database import MorphologyDB

    digest = sha256(path.read_bytes()).hexdigest()
    data = data_pass(Dictionary(path), MorphologyDB(str(path), "a"))
    print(report(digest, data, notices(path, digest), performance(path)))


if __name__ == "__main__":
    main()
