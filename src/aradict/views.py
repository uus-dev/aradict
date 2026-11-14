"""Server-rendered pages, written with htpy."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import NamedTuple
from urllib.parse import urlencode

from htpy import Element, Node, a, blockquote, body, br, button, caption, code, dd, details, div, dl, dt, form, fragment, h1, h2, h3, head, header, html, i, input, label, li, link, main, meta, nav, ol, p, path, rect, script, section, span, summary, svg, table, tbody, td, template, textarea, th, thead, title, tr, ul

from . import wiktionary
from .dictionary import MEASURES, Lookup, Reading, Segment, Token, alphabetical, opened
from .readable import MARK, OBJECT, POS, POSSESSIVE
from .wiktionary import Entry as WiktionaryEntry, Join, Sense

ARABIC = re.compile("[\u0600-\u06ff]")  # Arabic script
MARK_END = re.compile(f"{MARK.pattern}+$")  # the marks on a word's last letter
ARABIC_RUN = re.compile("([\u0600-\u06ff]+(?:\\s+[\u0600-\u06ff]+)*)")  # Arabic words, with the spaces between them
PRONOUNS = {*POSSESSIVE.values(), *OBJECT.values()}  # what an attached pronoun's part is labelled
PAGES = [("word", "/", "Word"), ("text", "/text", "Text"), ("about", "/about", "About")]


def ar(text: str) -> Node:
    """Arabic inside an English page: its own language and right-to-left direction."""
    return span(class_="ar", lang="ar", dir="rtl")[text]


def _arabizi(text: str) -> Node:
    return i(lang="ar-Latn")[text]


def _page(heading: str, active: str, content: Node) -> Node:
    return html(lang="en", dir="ltr")[
        head[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            title[f"{heading} · AraDict"],
            link(rel="stylesheet", href="/static/style.css"),
            # No history snapshots: Back and Forward reload the page, so they show exactly what loading the URL shows.
            meta(name="htmx-config", content='{"historyCacheSize": 0, "refreshOnHistoryMiss": true}'),
            script(src="/static/vendor/htmx.min.js", defer=True),
        ],
        body[
            header(class_="site")[
                div(class_="wrap")[
                    a(href="/", class_="brand")["AraDict", " ", span(class_="stamp", lang="ar", dir="rtl")["قاموس"]],
                    nav({"aria-label": "Main"})[
                        (a({"aria-current": "page"} if key == active else {}, href=href)[name] for key, href, name in PAGES)
                    ],
                ]
            ],
            main(class_="wrap")[content],
        ],
    ]


def _root(root: str | None, full: str | None = None) -> Node:
    """A root's letters. A "#" marks a weak or hamza radical the database leaves unresolved, shown
    as ◌, or with full ("ق.و.ل") as full's letter, in a dotted box that says it is from Wiktionary."""
    if not root:
        return span(class_="muted")["unavailable"]
    letters = [
        (span(class_="fill")[filled, span(class_="sr-only", lang="en")[" (filled from Wiktionary)"]] if full else "◌") if letter == "#" else letter
        for letter, filled in zip(root.split("."), (full or root).split("."))
    ]
    return span(class_="ar", lang="ar", dir="rtl")[[(" " if i else None, letter) for i, letter in enumerate(letters)]]  # a list: the name may show twice


def _measure(r: Reading) -> str | None:
    """A verb's measure, or "unavailable" where it can't be derived; None for any other part of speech."""
    return (r.measure or "unavailable") if r.pos == "verb" else None


def _badges(r: Reading, homograph: int | None = None) -> Node:
    """The part of speech, a verb's measure and which of Wiktionary's homographs it is, each in its own box."""
    measure = _measure(r)
    badge = measure and (span(class_="badge measure")[f"Measure {measure}"] if r.measure else span(class_="badge measure na")[f"measure {measure}"])
    return p(class_="pos")[span(class_="badge")[r.tags[0]], badge and [" ", badge], homograph and [" ", _homograph(homograph)]]


def _homograph(number: int) -> Node:
    return span(class_="badge measure")[f"Homograph {number}"]


def _how_common(top_percent: float | None) -> Node:
    """How common the lemma is, from its rank among all lemmas with a frequency: one to four bars, and in words."""
    if top_percent is None:
        band, bars = "frequency unknown", 0
    else:
        band, bars = ("very common", 4) if top_percent <= 1 else ("common", 3) if top_percent <= 10 else ("less common", 2) if top_percent <= 40 else ("rare", 1)
    # The least frequent lemmas share the lowest figure, so they are all "top 100%", which says nothing.
    detail = top_percent is not None and round(top_percent) < 100 and f"top {max(1, round(top_percent))}% of words"
    return [
        span(class_="bars", aria_hidden="true")[(span(class_="on" if n <= bars else None) for n in range(1, 5))],
        span(class_="band")[band],
        detail and [" ", span(class_="pct")[detail]],
    ]


def _chip_text(s: Segment) -> str:
    """A part on its own, with a tatweel where it joins the rest of the word."""
    return {"prefix": f"{s.spelling}ـ", "suffix": f"ـ{s.spelling}"}.get(s.role, s.spelling)


def _parts(r: Reading) -> Node:
    """The reading's parts as labelled chips, behind a native disclosure that needs no script."""
    shared = [(earlier, later) for earlier, later in zip(r.segments, r.segments[1:]) if earlier.spelling != earlier.text and later.spelling != later.text]
    return details(class_="parts")[
        summary["Word parts"],
        ol(class_="chips", dir="rtl")[(
            li(class_=f"chip {s.role}")[
                # English inside the right-to-left list keeps its own direction, so "my (f.)" keeps its brackets.
                span(class_="kind", dir="ltr")[s.role, span(class_="sr-only")[": "]],
                span(class_="ar", lang="ar")[_chip_text(s)],
                span(class_="label", dir="ltr")[s.label],
            ]
            for s in r.segments
        )],
        # Two parts that share one written letter (a shadda or madda) each show their own copy.
        (p(class_="note")[ar(_chip_text(earlier)), " + ", ar(_chip_text(later)), " are written ", ar(f"ـ{earlier.text}{later.text}")]
         for earlier, later in shared),
    ]


def _grammar(r: Reading) -> Node:
    """Voice, agreement, the rest of the grammar and any attached pronoun ("attached: their"), each in
    its own box. The part of speech heads the entry."""
    # ponytail: readable.grammar joins its details with ", ", and none has a comma of its own.
    details = [
        *r.tags[1:], *filter(None, r.grammar.split(", ")),
        *(f"attached: {s.label}" for s in r.segments if s.role == "suffix" and s.label in PRONOUNS),
    ]
    return ul(class_="grammar")[(li[d] for d in details)] if details else span(class_="nil")["None marked"]


def _reading(group: list[Reading], brief: bool = False) -> Node:
    """One result: the readings that share a gloss, such as an adjective's singular, dual and
    plural. The gloss is said once; each form keeps its own grammar and, unless brief, its parts."""
    return li(class_="reading")[(
        div(class_="rd")[
            span(class_="ar form", lang="ar", dir="rtl")[(span(class_=s.role)[s.text] for s in r.segments)],
            dl(class_="facts")[
                r is group[0] and [dt["Meaning"], dd(class_="gloss")[r.gloss]],
                dt["Grammar"], dd[_grammar(r)],
            ],
            not brief and len(r.segments) > 1 and _parts(r),
        ]
        for r in group
    )]


class Links(NamedTuple):
    """What a Word entry links its root and related forms with: the lookup's own URL parameters,
    which every link keeps so that its view can return to the lookup, how many forms each lemma
    (with its part of speech) has, and how many words each root has. Also each lemma's Wiktionary
    entries, which link to their source, and the roots Wiktionary fills: by lemma, part of speech and
    the open root ("ق.#.ل"), the full one ("ق.و.ل")."""

    lookup: dict[str, str]
    form_counts: dict[tuple[str, str], int]
    root_counts: dict[str, int]
    wiktionary: dict[tuple[str, str], Join] = {}
    filled_roots: dict[tuple[str, str, str], str] = {}


def _url(params: dict[str, str]) -> str:
    return f"/?{urlencode(params)}" if params else "/"


def _filled(full: str) -> Node:
    """What Wiktionary fills in a root CAMeL leaves open: "و filled from Wiktionary; the core dictionary has ق ◌ ل"."""
    open_root = opened(full)
    letters = " ".join(letter for letter, open_letter in zip(full.split("."), open_root.split(".")) if open_letter == "#")
    return [ar(letters), " filled from Wiktionary; the core dictionary has ", _root(open_root)]


def _root_tab(root: str | None, links: Links | None, full: str | None = None) -> Node:
    """The root, on a tab above its entry, with any letter Wiktionary fills in (full). With links it
    opens the root's words and says how many there are, or just "words" where they weren't counted."""
    label = [span(class_="rt-k")["Root"], " ", _root(root, full)]
    count = links and links.root_counts.get(full or root)
    if not (links and root) or count == 0:  # none: a root from Wiktionary that the dictionary has no word from
        return span(class_="root-tab" if root else "root-tab na")[label]
    return a(href=_url(links.lookup | {"root": full or root}), class_="root-tab")[label, " ", span(class_="rt-go")[_n(count, "word") if count else "words"]]


NO_ENTRIES = Join([], None)


def _entry(lemma: str, glosses: dict[str, list[Reading]], heading: Element, links: Links | None, brief: bool, join: Join) -> Node:
    """A lemma in the order of the #21 design (W5): which word it is (its root, the headword with its
    part of speech, how to say it and how common it is), what the typed word means (its readings, one
    result per gloss), then everything about the headword (see _about). With links, the root opens the
    root's words and a lemma with more than one form links to all of them. Brief leaves out how common
    the lemma is, its forms, its regional pronunciations and the readings' parts."""
    first = next(iter(glosses.values()))[0]
    forms = links.form_counts.get((first.lemma, first.pos), 0) if links else 0
    # A lemma's senses may be stored under different roots (إِجارَة "rent" and "protection"): each is offered.
    roots = list(dict.fromkeys(r.root for group in glosses.values() for r in group if r.root)) or [None]
    # Homographs are numbered as they are shown: the one joined to the lemma first, the others after
    # every entry; those it keeps all go in Wiktionary's order.
    homographs = len(join.entries) > 1
    fills = {root: links and links.filled_roots.get((first.lemma, first.pos, root)) for root in roots}
    shown = [join.joined] if join.joined else join.entries
    return section(class_="entry")[
        div(class_="tabs")[(_root_tab(root, links, full) for root, full in fills.items())],
        div(class_="head")[
            div(class_="lemma")[heading[ar(lemma)], _say(shown), _badges(first, 1 if homographs and join.joined else None)],
            not brief and dl(class_="facts")[dt["Frequency"], dd(class_="freq")[_how_common(first.top_percent)]],
        ],
        ul(class_="readings")[(_reading(group, brief) for group in glosses.values())],
        _about(shown, homographs and not join.joined, [
            *([] if brief else [[dt["Forms"], dd[
                a(href=_url(links.lookup | {"related": first.lemma, "pos": first.pos}))[f"all {forms} forms", span(class_="sr-only")[" of ", ar(lemma)]]
                if forms > 1 else span(class_="nil")["No other forms"]
            ]]]),
            *([dt["Root"], dd[_filled(full)]] for full in fills.values() if full),
        ], brief),
    ]


def _wiktionary_only(entry: WiktionaryEntry, number: int | None, heading: Element, links: Links | None, brief: bool, read: bool = False) -> Node:
    """A word Wiktionary has and the dictionary doesn't: a homograph of a lemma (قَالَ "to nap" beside
    قَالَ "to say"), or a word of its own (تَغْرِيدَة "tweet"). Its headword line goes straight to its meanings.
    A headword the dictionary reads as another lemma's form (read: آفَاق, the plural of أُفُق) is marked as
    from Wiktionary, not as only there."""
    root = entry.root and entry.root.replace(" ", ".")  # Wiktionary spells it ق ي ل, the dictionary ق.ي.ل
    pos = POS.get(next((camel for camel, name in wiktionary.POS.items() if name == entry.pos), entry.pos), entry.pos)
    return section(class_="entry")[
        root and div(class_="tabs")[_root_tab(root, links)],
        div(class_="head")[div(class_="lemma")[
            heading[ar(entry.word)],
            _say([entry]),
            p(class_="pos")[span(class_="badge")[pos], number and [" ", _homograph(number)], " ", span(class_="badge only")["Wiktionary" if read else "Wiktionary only"]],
        ]],
        _about([entry], brief=brief),
        not read and p(class_="only-note")["Only in Wiktionary: no frequency, measure or word parts."],
    ]


def _say(entries: list[WiktionaryEntry]) -> Node:
    """How to say the headword, under it: Wiktionary's transliteration and Modern Standard Arabic
    pronunciation, where all the headword's entries agree on them."""
    said = {(e.romanization, ", ".join(ipa for ipa, where in e.ipa if not where)) for e in entries}
    romanization, ipa = said.pop() if len(said) == 1 else (None, "")
    if not (romanization or ipa):
        return None
    return p(class_="say")[
        span(class_="sr-only")["Pronunciation: "],
        romanization and span(class_="tr", lang="ar-Latn")[romanization], romanization and ipa and " ", ipa and span(class_="ipa")[ipa],
    ]


# The rows of a headword line's forms, by their tags (an adjective's "feminine", a noun's female
# equivalent), and the order of those rows, with the headword's own gender after its plurals.
FORM_ROWS = {
    "plural": "Plural", "common plural": "Plural", "masculine plural": "Masculine plural", "feminine plural": "Feminine plural",
    "feminine": "Feminine", "masculine": "Masculine", "noun-from-verb": "Verbal noun",
}
ORDER = ["Plural", "Masculine plural", "Feminine plural", "Gender", "Feminine", "Masculine", "Verbal noun"]


def _facts(e: WiktionaryEntry) -> list[tuple[int, str, Node]]:
    """What a Wiktionary entry says about its headword, each as (its place in the #21 order, its label,
    what it says): its meanings, its plurals, gender and verbal nouns, then its relations ("verbal noun of")."""
    forms: dict[str, dict[str, wiktionary.Form]] = {}  # by row, each form once
    for f in e.forms:
        if label := FORM_ROWS.get(" ".join(sorted(set(f.tags) - wiktionary.REGISTER_LABELS))):
            forms.setdefault(label, {}).setdefault(f.form, f)
    canonical = next((f.tags for f in e.forms if "canonical" in f.tags), ())
    gender = [g for g in ("masculine", "feminine") if g in canonical and e.pos != "verb"]
    relations: dict[str, list[wiktionary.Relation]] = {}
    for r in e.relations:
        relations.setdefault(r.kind, []).append(r)
    return [
        *([(0, "Meanings", _senses(e.senses))] if e.senses else []),
        *((1 + ORDER.index(label), f"{label}s" if len(fs) > 1 and label.endswith(("plural", "noun")) else label,
           _words((f.form, f.romanization, [tag for tag in f.tags if tag in wiktionary.REGISTER_LABELS]) for f in fs.values()))
          for label, fs in sorted(forms.items(), key=lambda item: ORDER.index(item[0]))),
        *([(1 + ORDER.index("Gender"), "Gender", ul(class_="grammar")[(li[g] for g in gender)])] if gender else []),
        *((1 + len(ORDER), kind[:1].upper() + kind[1:], _words((r.word, r.romanization, r.labels) for r in rs)) for kind, rs in relations.items()),
    ]


def _words(words: Iterable[tuple[str, str | None, Iterable[str]]]) -> Node:
    """Words Wiktionary gives, each opening its own lookup, with its transliteration and any labels."""
    return ul(class_="words")[(li[_word(*word)] for word in words)]


def _word(word: str, romanization: str | None, labels: Iterable[str]) -> Node:
    return [a(href=_url({"q": word}))[ar(word)], romanization and [" ", span(class_="tr", lang="ar-Latn")[romanization]], ([" ", _label(label)] for label in labels)]


def _regional(e: WiktionaryEntry) -> Node:
    """An entry's regional pronunciations, behind a native disclosure."""
    said = [(where, ipa) for ipa, where in e.ipa if where]
    return said and details(class_="regional")[summary[_n(len(said), "pronunciation")], dl[([dt[where], dd[ipa]] for where, ipa in said)]]


def _about(entries: list[WiktionaryEntry], numbered: bool = False, rows: list = (), brief: bool = False) -> Node:
    """Everything about the headword after its readings, in the order of the #21 design (W5): what each
    Wiktionary entry says (see _facts), numbered as homographs where the lemma keeps several; then rows
    (its other forms, a root Wiktionary fills); then, unless brief, regional pronunciations; and the credit,
    which so covers all of it and the pronunciation under the headword."""
    facts = sorted(((place, n, label, said) for n, e in enumerate(entries, 1) for place, label, said in _facts(e)), key=lambda fact: fact[:2])
    regional = [] if brief else [(n, said) for n, e in enumerate(entries, 1) if (said := _regional(e))]
    if not (facts or rows):
        return None
    return div(class_="about-hw")[
        dl(class_="facts")[
            ([dt[label], dd(class_="wide" if label == "Meanings" else None)[numbered and [_homograph(n), " "], said]] for _, n, label, said in facts),
            rows,
            ([dt["Regional"], dd[numbered and [_homograph(n), " "], said]] for n, said in regional),
        ],
        entries and _credit(entries),
    ]


def _english(text: str) -> Node:
    """English that may quote Arabic: each Arabic run in its own language and direction."""
    return [ar(part) if i % 2 else part for i, part in enumerate(ARABIC_RUN.split(text))]


def _senses(senses: Iterable[Sense], lettered: bool = False) -> Node:
    """Wiktionary's senses, numbered, each with its labels in small boxes and its sub-senses lettered."""
    return ol(class_="senses", type="a" if lettered else None)[(
        li[
            (_label(label) for label in s.labels),
            s.labels and span(class_="sr-only")[": "],
            _english(s.gloss),
            s.subsenses and _senses(s.subsenses, True),
        ]
        for s in senses
    )]


def _label(label: str) -> Node:
    """One of Wiktionary's labels, "obsolete" or "transitive", in a small box."""
    return span(class_="qualifier")[label[:1].upper() + label[1:]]


LICENCE = "https://creativecommons.org/licenses/by-sa/4.0/"
EXTERNAL = svg(width="11", height="11", viewBox="0 0 12 12", aria_hidden="true")[
    path(d="M5 2.5H2.5v7h7V7M7 2.5h2.5V5M9.5 2.5 5.5 6.5", fill="none", stroke="currentColor", stroke_width="1.3", stroke_linecap="round", stroke_linejoin="round")
]


def _credit(entries: Iterable[WiktionaryEntry]) -> Node:
    """Wiktionary's credit (PRD, Wiktionary layer): its licence and the entries the senses come from,
    which open in a new tab, so the lookup stays."""
    pages = {e.url: e.page for e in entries}  # homographs share their page
    return p(class_="credit")[
        "From Wiktionary, ", a(href=LICENCE, target="_blank", rel="noopener")["CC BY-SA 4.0", span(class_="sr-only")[", opens in a new tab"]],
        " · ", "Entries: " if len(pages) > 1 else "Entry: ",
        [
            [", " if i else None, a(href=url, target="_blank", rel="noopener")[ar(page), span(class_="sr-only")[" on Wiktionary, opens in a new tab"], EXTERNAL]]
            for i, (url, page) in enumerate(pages.items())
        ],
    ]


LEGEND = p(class_="legend")[
    span(class_="sr-only")["How word parts are marked in each form: "],
    span(class_="prefix")["prefix"], " ", span(class_="stem")["stem"], " ", span(class_="suffix")["suffix"],
]


def _n(count: int, noun: str) -> str:
    """A count and its noun, plural unless one: "1 reading", "3 readings"."""
    return f"{count} {noun}{'s' if count != 1 else ''}"


class Results(NamedTuple):
    """A word's results, in the order they are shown: the readings, one entry per lemma and part of speech
    (groups, each with its Wiktionary entries, joins); the entries only Wiktionary has (apart), each with its
    homograph number if it has one; and, last, the entries that only relate the word to another (also).
    Of the entries apart, read holds those a reading reads as another lemma's form (آفَاق, the plural of
    أُفُق): they are Wiktionary's headwords, but not words only Wiktionary has."""

    groups: dict[tuple[str, str], dict[str, list[Reading]]]
    joins: dict[tuple[str, str], Join]
    apart: list[tuple[WiktionaryEntry, int | None]]
    also: list[WiktionaryEntry]
    read: frozenset[WiktionaryEntry] = frozenset()


def _results(readings: Iterable[Reading], links: Links | None = None, homographs: bool = True, found: Iterable[WiktionaryEntry] = ()) -> Results:
    """One entry per lemma and part of speech, in the order the readings arrive. Then, unless homographs
    is false, Wiktionary's homographs that a gloss told apart from the lemma, once each. Then the word's
    entries that no lemma joins (found, see Dictionary.wiktionary_only): those with meanings, numbered as
    homographs where two share a headword and part of speech; and those that only relate the word to
    another, unless a reading already shows that word (كُتُب "plural of كِتَاب" is a reading of كِتاب)."""
    groups: dict[tuple[str, str], dict[str, list[Reading]]] = {}
    for reading in readings:
        groups.setdefault((reading.lemma, reading.pos), {}).setdefault(reading.gloss, []).append(reading)
    joins = {key: links.wiktionary.get(key, NO_ENTRIES) if links else NO_ENTRIES for key in groups}
    shown = [e for join in joins.values() for e in ([join.joined] if join.joined else join.entries)]
    apart: list[tuple[WiktionaryEntry, int | None]] = []
    for join in joins.values():
        if homographs and join.joined:
            others = [e for e in join.entries if e is not join.joined]
            apart += [(e, n) for n, e in enumerate(others, 2) if e not in shown and e not in (other for other, _ in apart)]
    found = [e for e in found if e not in shown and e not in (other for other, _ in apart)]
    only = [e for e in found if e.senses]
    headword = {e: (e.pos, wiktionary.spelling(e.word)) for e in only}
    sharing, numbered = Counter(headword.values()), Counter()
    for e in only:
        numbered[headword[e]] += 1
        apart.append((e, numbered[headword[e]] if sharing[headword[e]] > 1 else None))
    readings = [r for group in groups.values() for rs in group.values() for r in rs]
    shows = {_unattached(r) for r in readings}
    reads = {(wiktionary.wiktionary_pos(r.pos), _unattached(r)) for r in readings}
    read = frozenset(e for e in only if (e.pos, _bare(e.word)) in reads)
    return Results(groups, joins, apart, [e for e in found if not e.senses and _bare(e.word) not in shows], read)


def _bare(word: str) -> str:
    """A word as the join spells it (wiktionary.spelling), without the case or mood ending it may end with."""
    return MARK_END.sub("", wiktionary.spelling(word))


def _unattached(r: Reading) -> str:
    """The word a reading reads, as _bare spells it: its stem and endings, without attached words before it or a pronoun after it."""
    # ponytail: a verb's person prefix (يَـ) goes with the attached words; no entry only relates such a form to another yet.
    return _bare("".join(s.text for s in r.segments if s.role == "stem" or s.role == "suffix" and s.label not in PRONOUNS))


def _entries(results: Results, heading: Element = h2, links: Links | None = None, brief: bool = False) -> Node:
    return [
        div(class_="entries")[
            (_entry(lemma, glosses, heading, links, brief, results.joins[lemma, pos]) for (lemma, pos), glosses in results.groups.items()),
            (_wiktionary_only(e, n, heading, links, brief, e in results.read) for e, n in results.apart),
        ],
        _also(results.also, heading),
    ]


def _also(entries: list[WiktionaryEntry], heading: Element) -> Node:
    """The word's entries that only relate it to another word (كَتْب "verbal noun of كَتَبَ"), listed after
    its entries as in the #21 design, each with its relations and the credit."""
    return entries and section(class_="also")[
        heading["Also in Wiktionary"],
        p(class_="also-sub")["Listed there as forms of other words, so they have no meanings of their own."],
        ul[(
            li[
                p[
                    e.romanization and [span(class_="tr", lang="ar-Latn")[e.romanization], ": "],
                    [["; " if i else None, r.kind[:1].upper() + r.kind[1:], " ", _word(r.word, r.romanization, r.labels)] for i, r in enumerate(e.relations)],
                ],
                p(class_="form")[ar(e.word)],
            ]
            for e in entries
        )],
        _credit(entries),
    ]


def _more(results: Results) -> int:
    """How many entries the results show besides the dictionary's, as the #21 design counts them: Wiktionary's
    own, and those that only relate the word to another."""
    return len(results.apart) + len(results.also)


def _from_wiktionary(count: int) -> str:
    return f"{count} {'entry' if count == 1 else 'entries'} from Wiktionary"


def _intro() -> Node:
    """What AraDict does, below the search box and only before the first lookup, so it never pushes results down."""
    return p(class_="intro")[
        "An Arabic–English dictionary for Modern Standard Arabic. Type or paste any Arabic word, "
        "with or without vowel marks, to see every way it can be read. ",
        a(href="/about#typing")["How to type Arabic"],
    ]


class State(NamedTuple):
    """One outcome of a lookup: the status line, which screen readers announce, what fills
    the results area below it, and the Arabic an Arabizi query was looked up as."""

    status: Node = None
    body: Node = None
    arabizi: str | None = None


INITIAL = State(body=_intro())


def looked_up(text: str, found: Lookup, links: Links | None = None) -> State:
    """The outcome of a completed lookup of the typed text. Of several words only the first is looked
    up, and a notice says so. An Arabizi word is looked up as the Arabic it stands for, which the
    page shows. Entries link to their root and related forms with links."""
    words = text.split()
    latin = bool(re.search("[A-Za-z]", text)) and not ARABIC.search(text)
    notice = p(class_="notice")[
        "Only the first word, ", _arabizi(words[0]) if latin else ar(words[0]), ", was looked up.",
        # The Text view reads Arabic script only.
        not latin and [" ", a(href=f"/text?{urlencode({'q': text})}")["Read them all in the Text view"], "."],
    ] if not found.complete else None
    if found.readings or found.wiktionary:
        arabizi = found.query if found.mode == "arabizi" else None
        results = _results(found.readings, links, found=found.wiktionary)
        more = _more(results)
        status = (
            [f"{_n(len(found.readings), 'reading')} for ", ar(found.query), f", and {more} more {'entry' if more == 1 else 'entries'} from Wiktionary" if more else None]
            if found.readings else [f"{_from_wiktionary(more)} for ", ar(found.query)]
        )
        return State(status, [notice, _entries(results, h2, links)], arabizi)
    if latin:
        return State(["No Arabic word for ", _arabizi(words[0])], [notice, div(class_="empty")[
            p["AraDict read this as Arabic in Latin letters (Arabizi), but found no word it could stand for. You could:"],
            ul[
                li[
                    "Check the spelling. Use digits for the letters Latin lacks: 2 for ", ar("ء"), ", 3 for ", ar("ع"), ", 5 for ",
                    ar("خ"), ", 7 for ", ar("ح"), " and 9 for ", ar("ق"), ". ", a(href="/about#typing")["More about Arabizi"],
                ],
                li["Type it in Arabic script."],
                li["Looking for an English word? ", a(href=f"/?{urlencode({'q': text, 'lang': 'en'})}")["Look it up in English → Arabic"]],
            ],
        ]])
    return State(["No entry for ", ar(words[0])], [notice, div(class_="empty")[
        p["AraDict couldn't find this word in its Modern Standard Arabic dictionary. You could:"],
        ul[
            li["Check the spelling."],
            li["Type it without vowel marks."],
            li["Type it in Latin letters (Arabizi), such as ", _arabizi("kitab"), " or ", _arabizi("3arabi"), "."],
            li["Looking for an English word? ", a(href="/?lang=en")["Switch to English → Arabic"]],
        ],
    ]])


COVERAGE = p(class_="notice coverage")[
    "English → Arabic is limited: it matches the dictionary's short English glosses and Wiktionary's meanings, a whole word or phrase at a time. "
    "A word it doesn't find may still have an Arabic translation, listed under a synonym."
]

INITIAL_EN = State(body=[
    p(class_="intro")["Type an English word or phrase, such as “book” or “piece of writing”, to find the Arabic words it translates."],
    COVERAGE,
])


def looked_up_en(found: Lookup, links: Links | None = None) -> State:
    """The outcome of a completed English → Arabic lookup, with the coverage note: the dictionary's words, then
    the entries only Wiktionary has (Lookup.wiktionary). Entries link to their root and related forms with links."""
    query = found.query
    if found.readings or found.wiktionary:
        results = _results(found.readings, links, homographs=False, found=found.wiktionary)
        more = _more(results)
        status = (
            f"{_n(len(found.readings), 'Arabic word')} for “{query}”" + (f", and {more} more {'entry' if more == 1 else 'entries'} from Wiktionary" if more else "")
            if found.readings else f"{_from_wiktionary(more)} for “{query}”"
        )
        return State(status, [COVERAGE, _entries(results, h2, links)])
    # Arabic typed here is meant the other way round, so switching direction keeps it.
    arabic = bool(ARABIC.search(query))
    back = f"/?{urlencode({'q': query})}" if arabic else "/"
    return State(["No Arabic word for “", ar(query) if arabic else query, "”"], [COVERAGE, div(class_="empty")[
        p["AraDict found no Arabic word with this English meaning. You could:"],
        ul[
            li["Check the spelling."],
            li["Try a synonym, or one word rather than a phrase."],
            li["Looking for an Arabic word? ", a(href=back)["Switch to Arabic → English"]],
        ],
    ]])


FAILURE = State(
    "Lookup failed. Your word is kept, so you can try again.",
    p(class_="retry")[button(type="submit", form="search")["Retry"]],
)


# A root's words and a lemma's forms are a table, sortable by the columns with a key.
COLUMNS = (("form", "Form"), ("gloss", "Meaning"), ("pos", "Part of speech"), (None, "Grammar"), ("root", "Root"), ("measure", "Measure"))
SORT_KEYS = {  # None for a row with no value, which goes last either way
    "form": lambda r: alphabetical(r.form),
    "gloss": lambda r: r.gloss.casefold(),
    "pos": lambda r: r.tags[0],
    "root": lambda r: r.root and alphabetical(r.root),
    "measure": lambda r: r.measure and list(MEASURES).index(r.measure),
}


def _sort_order(sort: str) -> tuple[str | None, bool]:
    """The column a sort parameter names, "gloss" or "-gloss" in reverse, and whether it is
    reversed; no column for anything else."""
    column = sort.removeprefix("-")
    return (column, sort.startswith("-")) if column in SORT_KEYS else (None, False)


def _sorted(rows: list[Reading], column: str | None, descending: bool) -> list[Reading]:
    """Rows sorted by a column, or in family order with none. Python's sort is stable, so rows that
    tie keep the family order, whichever the direction."""
    if column is None:
        return rows
    key = SORT_KEYS[column]
    return sorted((r for r in rows if key(r) is not None), key=key, reverse=descending) + [r for r in rows if key(r) is None]


def _context(label: str, name: Node, lookup: dict[str, str]) -> Node:
    """A chip that says which root's words or lemma's forms replace the lookup's results; closing it returns to the lookup."""
    return p(class_="context")[
        label, ": ", name,
        a(href=_url(lookup), class_="dismiss")[span(aria_hidden="true")["×"], span(class_="sr-only")["Back to your lookup" if lookup.get("q") else "Close"]],
    ]


def _table(rows: list[Reading], name: Node, view: dict[str, str], sort: str, full: str | None = None) -> Node:
    """A root's words or a lemma's forms, named for assistive technology. Each column header links to
    the list sorted by it, then in reverse, then back in family order (view is the URL's parameters
    but the sort); the sorted column says so. A row Wiktionary fills to the root full shows full's letters."""
    column, descending = _sort_order(sort)
    order = column and ("descending" if descending else "ascending")

    def header(key: str | None, text: str) -> Node:
        if key is None:
            return th(scope="col")[text]
        following = {"ascending": f"-{key}", "descending": None}.get(order) if key == column else key
        return th(scope="col", aria_sort=order if key == column else None)[a(href=_url(view | ({"sort": following} if following else {})))[text]]

    return rows and table(class_="family")[
        caption(class_="sr-only")[name],
        thead[tr[(header(key, name) for key, name in COLUMNS)]],
        tbody[(
            tr[
                td(data_label="Form")[ar(r.form)],
                td(data_label="Meaning")[r.gloss],
                td(data_label="Part of speech")[span(class_="badge")[r.tags[0]]],
                td(data_label="Grammar")[_grammar(r)],
                td(data_label="Root")[_root(r.root, full if full and r.root == opened(full) else None)],
                td(data_label="Measure")[_measure(r)],
            ]
            for r in _sorted(rows, column, descending)
        )],
    ]


def _forms(rows: list[Reading]) -> str:
    return _n(len(rows), "form") if rows else "No forms"


def related_view(lemma: str, pos: str, rows: list[Reading], lookup: dict[str, str], sort: str = "") -> State:
    """A lemma's forms, such as a noun's singular and plural, in place of the lookup's results."""
    status = [f"{_forms(rows)} of the {POS.get(pos, pos)} ", ar(lemma)]
    return State(status, [_context("Related", ar(lemma), lookup), _table(rows, status, lookup | {"related": lemma, "pos": pos}, sort)])


def root_view(
    root: str, rows: list[Reading], lookup: dict[str, str], sort: str = "",
    unconfirmed: list[Reading] | tuple = (), sources: Iterable[tuple[str, str]] = (),
) -> State:
    """Every form from a root, verbs by measure first, in place of the lookup's results. Where
    Wiktionary fills the root's weak or hamza letters, which CAMeL leaves open, the filled letters
    are marked; then come the forms still under CAMeL's open root that it can't place (unconfirmed),
    and the credit, linked to each filled lemma's entry (sources: the lemma and its Wiktionary page)."""
    view, open_root = lookup | {"root": root}, opened(root)
    if not any(r.root == open_root != root for r in rows):
        status = [f"{_forms(rows)} from the root ", _root(root)]
        return State(status, [_context("Root", _root(root), lookup), _table(rows, status, view, sort)])
    name = _root(open_root, root)
    status = [f"{_forms(rows)} from the root ", name, unconfirmed and f", {len(unconfirmed)} more not confirmed"]
    apart = ["Also under ", _root(open_root), " in the core dictionary, ", "letters" if open_root.count("#") > 1 else "letter", " not confirmed"]
    return State(status, [
        _context("Root", name, lookup),
        p(class_="filled")[_filled(root)],
        _table(rows, status, view, sort, root),
        unconfirmed and [h2(class_="rv-sub")[apart], _table(unconfirmed, apart, view, sort)],
        p(class_="credit")[
            "From Wiktionary, CC BY-SA 4.0: ",
            ([", " if i else None, a(href=url)[ar(lemma), span(class_="sr-only")[" on Wiktionary"]]] for i, (lemma, url) in enumerate(sources)),
        ],
    ])


def _keyboard_toggle(field: str) -> Node:
    """Opens the on-screen keyboard that types into a field. Hidden until keyboard.js draws the keys and shows it."""
    return button(type="button", hidden=True, data_keyboard=field, aria_controls=f"{field}-keyboard", aria_expanded="false", aria_label="Arabic keyboard")[
        svg(width="24", height="18", viewBox="0 0 24 18", fill="none", stroke="currentColor", stroke_width="1.6", aria_hidden="true")[
            rect(x="1", y="1", width="22", height="16", rx="2"),
            path(d="M5 6h1M9 6h1M13 6h1M17 6h1M5 10h1M9 10h1M13 10h1M17 10h1M7 13.5h10", stroke_linecap="round"),
        ]
    ]


def _keyboard_panel(field: str) -> Node:
    return div(id=f"{field}-keyboard", class_="osk", role="group", aria_label="Arabic keyboard", hidden=True)


def _arabizi_chip(arabic: str | None, **attributes) -> Node:
    """Next to the input: the Arabic an Arabizi query was looked up as."""
    return p(id="arabizi", class_="arabizi", hidden=not arabic, **attributes)[arabic and ["Looked up as ", ar(arabic)]]


def word_page(query: str, state: State, filter_diacritics: bool = True, english: bool = False) -> Node:
    return _page("Word", "word", [
        h1(class_="sr-only")["Word lookup"],
        # Live lookup: the same GET as the plain form, debounced while typing and immediate on Enter.
        # Its results replace the results area and the URL is pushed; a newer request aborts an older one.
        form(
            id="search", class_="search", method="get", action="/", role="search",
            hx_get="/", hx_trigger="input delay:150ms, submit", hx_target="#results", hx_push_url="true", hx_sync="this:replace",
        )[
            # lookup.js sets the label and the field's language when the direction switches. Arabic reads in the
            # direction of what is typed: right to left, or left to right for Arabizi.
            label(for_="q", class_="lbl")["English word" if english else "Arabic word"],
            input(
                id="q", name="q", value=query, dir="ltr" if english else "auto", lang="en" if english else "ar",
                autocomplete="off", autocapitalize="off", spellcheck="false", enterkeyhint="search",
            ),
            _keyboard_toggle("q"),
            a(href="/?lang=en" if english else "/", class_="clear", hidden=not query)["Clear"],
            button(type="submit")["Look up"],
            _arabizi_chip(state.arabizi),
            div(class_="opts")[
                label(class_="option")[input(type="checkbox", name="lang", value="en", checked=english, data_remember=True), " English → Arabic"],
                label(class_="option")[input(type="checkbox", name="diacritics", value="off", checked=not filter_diacritics, data_remember=True), " Ignore diacritics"],
                # Shown by autocomplete.js and remembered by history.js. form="" leaves it out of the lookup and its URL.
                label(class_="option", hidden=True)[input(type="checkbox", name="autocomplete", form="", checked=True, data_remember=True), " Show suggestions"],
            ],
        ],
        _keyboard_panel("q"),
        _history(),
        # The legend shows beside the status while the results have entries (style.css).
        div(class_="status-row")[p(id="status", class_="status", role="status")[state.status], LEGEND],
        div(id="results")[state.body],
        # Shown by lookup.js when a live lookup fails, including when the server can't be reached.
        template(id="failure", data_status=FAILURE.status)[FAILURE.body],
        script(src="/static/lookup.js", type="module"),
        script(src="/static/keyboard.js", type="module"),
        script(src="/static/history.js", type="module"),
        script(src="/static/autocomplete.js", type="module"),  # after history.js, which restores its switch
    ])


def _history() -> Node:
    """Recent lookups. history.js fills the list from this browser's storage and shows the panel,
    so without JavaScript, where there is no history, it stays hidden. It sits outside the search
    form, so nothing in it is ever sent with a lookup."""
    return details(id="history", class_="history", hidden=True)[
        summary["Recent lookups"],
        ol,
        p(class_="none")["Words you look up appear here."],
        p(class_="tools")[
            label["Keep ", input(type="number", name="history-size", min="0", value="50", data_remember=True), " lookups"],
            button(type="button")["Clear history"],
        ],
    ]


def live_results(state: State) -> Node:
    """What a live lookup swaps into the results area, with the status line and Arabizi chip updated out of band."""
    return fragment[p(id="status", hx_swap_oob="innerHTML")[state.status], _arabizi_chip(state.arabizi, hx_swap_oob="true"), state.body]


def live_analysis(state: State) -> Node:
    """What live analysis swaps into the analysis area, with the status line updated out of band."""
    return fragment[p(id="status", hx_swap_oob="innerHTML")[state.status], state.body]


MAX_QUERY = 100  # characters a Word lookup, and so any URL parameter, may carry
MAX_TEXT = 2000
TEXT_FAILURE = State(
    "Analysis failed. Your text is kept, so you can try again.",
    p(class_="retry")[button(type="submit", form="analyse")["Retry"]],
)


def _found(results: Results) -> str:
    """What a word of a passage has, as its button and details say: "3 readings", "1 reading, 1 more from
    Wiktionary", "1 entry from Wiktionary", or "not in the dictionary"."""
    readings, more = sum(len(rs) for group in results.groups.values() for rs in group.values()), _more(results)
    if readings:
        return _n(readings, "reading") + (f", {more} more from Wiktionary" if more else "")
    return _from_wiktionary(more) if more else "not in the dictionary"


def _token(t: Token, ids: dict[str, str], found: str) -> Node:
    """A word as a button that opens its details, saying what it has (found)."""
    return button(type="button", class_=f"tok {t.kind}", popovertarget=ids[t.text])[t.text, span(class_="sr-only", lang="en")[", ", found]]


def _details(t: Token, id: str, links: Links, results: Results) -> Node:
    """A word's readings, grouped by lemma as on the Word page, then the entries only Wiktionary has, in a
    native popover. Each root links to its words, and the root view returns to the word's lookup."""
    return div(id=id, class_="tok-pop", popover=True, role="dialog", aria_labelledby=f"{id}-h")[
        div(class_="tp-head")[
            h2(id=f"{id}-h")[ar(t.text)],
            p[_found(results)],
        ],
        div(class_="tp-body")[
            _entries(results, h3, links, brief=True) if t.kind == "word" else p(class_="tp-msg")[
                "AraDict couldn't find this word in its Modern Standard Arabic dictionary."
            ],
        ],
        div(class_="tp-foot")[
            a(href=f"/?{urlencode({'q': t.text})}")["Open in Word lookup"],
            button(type="button", popovertarget=id, popovertargetaction="hide")["Close"],
        ],
    ]


def analysed(tokens: list[Token], joins: dict[tuple[str, str], Join] = {}, filled: dict[tuple[str, str, str], str] = {}) -> State:
    """The passage as typed, each word opening its details. A word written twice opens the same
    details. The roots there link without a word count: counting a root's words the first time
    takes about 27 ms, too slow for every root of a long passage."""
    words: dict[str, Token] = {}  # each word once, in order
    for t in tokens:
        if t.kind in ("word", "unknown"):
            words.setdefault(t.text, t)
    ids = {word: f"w{i}" for i, word in enumerate(words)}
    links = {word: Links({"q": word}, {}, {}, joins, filled) for word in words}
    results = {word: _results(t.readings, links[word], found=t.wiktionary) for word, t in words.items()}
    n, unknown = sum(t.kind in ("word", "unknown") for t in tokens), sum(t.kind == "unknown" for t in tokens)
    status = f"{_n(n, 'word')}{f', {unknown} not in the dictionary' if unknown else ''}" if n else "No Arabic words to analyse."
    return State(status, [
        section(class_="passage-box", aria_labelledby="passage-h")[
            div(class_="pb-head")[
                h2(id="passage-h")["Passage"],
                p(class_="key-legend")[span(class_="known")["has readings"], " ", span(class_="unknown")["not in the dictionary"]],
            ],
            # The passage keeps its spaces and line breaks (white-space: pre-wrap).
            div(class_="passage", lang="ar", dir="rtl")[(_token(t, ids, _found(results[t.text])) if t.text in words else t.text for t in tokens)],  # anything else as typed
        ],
        (_details(t, ids[word], links[word], results[word]) for word, t in words.items()),
    ])


def text_page(text: str, state: State) -> Node:
    return _page("Text", "text", [
        h1(class_="sr-only")["Text"],
        # Posted, so a passage stays out of the page address. Live analysis is the same POST, after a pause
        # in typing and at once on submit; a newer request aborts an older one.
        form(
            id="analyse", class_="text-in", method="post", action="/text",
            hx_post="/text", hx_trigger="input delay:500ms, submit", hx_target="#analysis", hx_sync="this:replace",
        )[
            label(for_="text", class_="lbl")["Arabic text"],
            textarea(
                id="text", name="text", rows="4", dir="rtl", lang="ar", spellcheck="false",
                placeholder="Paste or type Arabic text", aria_describedby="text-hint",
            )[text],
            p(id="text-hint", class_="hint")[f"Analyse at most {MAX_TEXT:,} characters at a time."],
            div(class_="actions")[_keyboard_toggle("text"), button(type="submit")["Analyse"]],
        ],
        _keyboard_panel("text"),
        p(id="status", class_="status", role="status")[state.status],
        div(id="analysis")[state.body],
        # Shown by text.js when live analysis fails, including when the server can't be reached.
        template(id="failure", data_status=TEXT_FAILURE.status)[TEXT_FAILURE.body],
        script(src="/static/text.js", type="module"),
        script(src="/static/keyboard.js", type="module"),
    ])


REPO = "https://github.com/uus-dev/aradict"


def about_page() -> Node:
    return _page("About and help", "about", div(class_="about")[
        h1["About and help"],
        p[
            "AraDict is an Arabic–English dictionary. Type or paste an Arabic word as it appears in a text, with its prefixes "
            "and suffixes and with or without vowel marks, and AraDict shows every way it can be read."
        ],
        section(id="coverage")[
            h2["What AraDict covers"],
            p["AraDict covers Modern Standard Arabic, the Arabic of newspapers, books and formal speech. It is not a dictionary of spoken dialects."],
            p[
                "Its words and English meanings come from the CAMeL Tools morphology database ", code["calima-msa-r13"],
                ", which builds on the Buckwalter Arabic Morphological Analyzer. That vocabulary dates from about 2002, "
                "so newer words, such as the ones for “tweet” and “podcast”, are missing from it. Where English Wiktionary has "
                "such a word, as it has the one for “tweet”, AraDict shows Wiktionary's entry, marked “Wiktionary only”."
            ],
            # Measured in ACCEPTANCE.md (#17); tests/test_acceptance.py checks every number here against the database.
            p[
                "AraDict has about 38,000 entries under 35,000 headwords, from about 4,500 roots. An entry is a headword with one part "
                "of speech, so a word that is both a noun and an adjective has two. Almost every verb shows its measure (I to X, "
                "or one of the rarer measures): all but 46 of about 9,000."
            ],
            p[
                "In about 1 root in 4, the data leaves a weak or hamza letter open. AraDict fills it in from Wiktionary where "
                "Wiktionary gives the word's root, and marks it so; otherwise it shows ", ar("◌"), ". About 5,000 "
                "entries have no root: about 2,700 proper nouns, 1,500 other nouns, 550 adjectives and 200 of other parts of speech."
            ],
        ],
        section(id="typing")[
            h2["Typing Arabic"],
            p[
                "Vowel marks are optional. Without them, AraDict shows every reading of the letters. Each mark you type keeps only "
                "the readings with that vowel: ", ar("كُتُب"), " finds “books” but not ", ar("كَتَبَ"), " “he wrote”. "
                "You can switch this filter off."
            ],
            p[
                "You don't need to type hamza. A bare ", ar("ا"), " also finds ", ar("أ"), ", ", ar("إ"), " and ", ar("آ"),
                ", so ", ar("اكل"), " finds ", ar("أكل"), ". If you do type a hamza form, AraDict keeps only the readings with that exact letter."
            ],
            p[
                "AraDict treats ", ar("ى"), " and ", ar("ي"), " alike (", ar("الى"), " finds ", ar("إلى"), "), also tries a final ",
                ar("ه"), " as ", ar("ة"), ", ignores the stretching stroke ", ar("ـ"), " (tatweel), and reads the Persian and Urdu letters ",
                ar("ی"), " and ", ar("ک"), " as ", ar("ي"), " and ", ar("ك"), "."
            ],
            p[
                "No Arabic keyboard? AraDict's on-screen keyboard has the standard Arabic layout. Its shift layer holds the vowel marks, "
                "the hamza seats and ", ar("لأ"), ", ", ar("لإ"), " and ", ar("لآ"), "."
            ],
            p[
                "On a phone, most keyboards include an Arabic layout that you can add in the phone's keyboard settings. "
                "If a hamza or vowel mark is hard to find on it, leave it out: AraDict finds the word without it."
            ],
            p[
                "You can also type Arabic in Latin letters (Arabizi), for example ", _arabizi("ktb"), ", ", _arabizi("mar7aba"), " or ",
                _arabizi("3arabi"), ". AraDict turns them into Arabic script and shows the Arabic it looked up. Digits stand for letters "
                "with no Latin match: 2 for ", ar("ء"), ", 3 for ", ar("ع"), ", 5 for ", ar("خ"), ", 7 for ", ar("ح"), " and 9 for ",
                ar("ق"), ". The pairs sh, kh, gh, th and dh stand for ", ar("ش"), ", ", ar("خ"), ", ", ar("غ"), ", ", ar("ث"), " and ",
                ar("ذ"), ". Short vowels are optional, and the ones you type work like vowel marks: ", _arabizi("kitab"), " finds ",
                ar("كِتاب"), " “book” but not ", ar("كُتّاب"), " “writers”."
            ],
        ],
        section(id="sources")[
            h2["Sources and licenses"],
            p[
                "The dictionary data is the ",
                a(href="https://github.com/CAMeL-Lab/camel-tools-data/releases/tag/2022.03.21")["CAMeL Tools morphology database calima-msa-r13"],
                " (release 2022.03.21) from the CAMeL Lab at New York University Abu Dhabi, licensed under the ",
                a(href="https://www.gnu.org/licenses/old-licenses/gpl-2.0.html")["GNU General Public License version 2"],
                ". It is derived from ", a(href="https://sourceforge.net/projects/aramorph/")["Aramorph 1.2.1"], ", the Java version of the ",
                a(href="https://catalog.ldc.upenn.edu/LDC2002L49")["Buckwalter Arabic Morphological Analyzer 1.0"],
                ", distributed by the Linguistic Data Consortium under the GPL version 2. Its copyright notices:",
            ],
            blockquote(class_="notice")[
                p["Portions (c) 2002 QAMUS LLC (www.qamus.org),", br, "(c) 2002 Trustees of the University of Pennsylvania", br, "Portions (c) 2006 Jon Dehdari"]
            ],
            p["AraDict's own code is free software. Its ", a(href=REPO)["source code is on GitHub"], "."],
            blockquote(class_="notice")[
                p["Copyright (C) 2026 the AraDict contributors."],
                p[
                    "This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License "
                    "as published by the Free Software Foundation, either version 2 of the License, or (at your option) any later version. See ",
                    a(href=f"{REPO}/blob/main/LICENSE")["LICENSE"], " for the full GPL version 2 text."
                ],
                p[
                    "This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY, without even the implied warranty "
                    "of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details."
                ],
            ],
            p[
                "Bundled with AraDict: ", a(href="https://htmx.org/")["htmx"], " 2.0.11 under the ",
                a(href="/static/vendor/LICENSE-htmx")["Zero-Clause BSD license"], "; the ",
                a(href="https://software.sil.org/scheherazade/")["Scheherazade New"], " font by SIL under the ",
                a(href="/static/vendor/OFL-ScheherazadeNew.txt")["SIL Open Font License"], "; and the ",
                a(href="https://github.com/adobe-fonts/source-sans")["Source Sans 3"], " font by Adobe under the ",
                a(href="/static/vendor/OFL-SourceSans3.txt")["SIL Open Font License"], ".",
            ],
        ],
        section(id="privacy")[
            h2["Privacy"],
            ul[
                li["AraDict has no accounts, no advertising and no user profiles."],
                li["Your lookup history and settings stay in this browser, on your device. They are never sent to AraDict, and you can clear them at any time."],
                li["Lookups run on AraDict's server, so each word you look up is sent there. The word is also part of the page address, so you can bookmark or share a result."],
                li[
                    "Passages you type or paste into the Text view are sent to the server to be analysed, and are not logged. "
                    "They never go into the page address. Only the link from a Word lookup to the Text view carries words in its "
                    f"address: the words you looked up, at most {MAX_QUERY} characters."
                ],
            ],
        ],
        section(id="support")[
            h2["Report a problem"],
            p[
                "Found a wrong result or a bug? Report it on ", a(href=f"{REPO}/issues")["GitHub Issues"],
                ", with the word you looked up and what you expected. Issues are public, and filing one needs a free GitHub account."
            ],
        ],
        section(id="apps")[
            h2["Apps"],
            p[
                "AraDict has no native apps. It is a website that works in the browser on phones, tablets and computers. "
                "Apps in the App Store or Google Play are not made by AraDict."
            ],
        ],
    ])
