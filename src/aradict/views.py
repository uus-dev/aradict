"""Server-rendered pages, written with htpy."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import NamedTuple
from urllib.parse import urlencode

from htpy import Element, Node, a, blockquote, body, br, button, caption, code, dd, details, div, dl, dt, form, fragment, h1, h2, h3, head, header, html, i, input, label, li, link, main, meta, nav, ol, p, path, rect, script, section, span, summary, svg, table, tbody, td, template, textarea, th, thead, title, tr, ul

from .dictionary import MEASURES, Lookup, Reading, Segment, Token, alphabetical
from .readable import POS

ARABIC = re.compile("[\u0600-\u06ff]")  # Arabic script
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
                    a(href="/", class_="brand")["AraDict"],
                    nav({"aria-label": "Main"})[
                        (a({"aria-current": "page"} if key == active else {}, href=href)[name] for key, href, name in PAGES)
                    ],
                ]
            ],
            main(class_="wrap")[content],
        ],
    ]


def _root(root: str | None) -> Node:
    # A "#" marks a weak or hamza radical the database leaves unresolved.
    return ar(" ".join("◌" if letter == "#" else letter for letter in root.split("."))) if root else span(class_="muted")["unavailable"]


def _kind(r: Reading) -> str:
    """The part of speech, and a verb's measure."""
    if r.pos != "verb":
        return r.tags[0]
    return f"{r.tags[0]} · {f'Measure {r.measure}' if r.measure else 'measure unavailable'}"


def _use(top_percent: float | None) -> str:
    """How common the lemma is, from its rank among all lemmas with a frequency."""
    if top_percent is None:
        return "frequency unknown"
    band = "very common" if top_percent <= 1 else "common" if top_percent <= 10 else "less common" if top_percent <= 40 else "rare"
    # The least frequent lemmas share the lowest figure, so they are all "top 100%", which says nothing.
    return band if round(top_percent) >= 100 else f"{band} · top {max(1, round(top_percent))}% of words"


def _chip_text(s: Segment) -> str:
    """A part on its own, with a tatweel where it joins the rest of the word."""
    return {"prefix": f"{s.spelling}ـ", "suffix": f"ـ{s.spelling}"}.get(s.role, s.spelling)


def _parts(r: Reading) -> Node:
    """The reading's parts as labelled chips, behind a native disclosure that needs no script."""
    shared = [(a, b) for a, b in zip(r.segments, r.segments[1:]) if a.spelling != a.text and b.spelling != b.text]
    return details(class_="parts")[
        summary["Word parts"],
        ol(class_="chips", dir="rtl")[(
            li(class_=f"chip {s.role}")[
                span(class_="ar", lang="ar")[_chip_text(s)],
                span(class_="label")[span(class_="sr-only")[f"{s.role}: "], s.label],
            ]
            for s in r.segments
        )],
        # Two parts that share one written letter (a shadda or madda) each show their own copy.
        (p(class_="note")[ar(_chip_text(a)), " + ", ar(_chip_text(b)), " are written ", ar(f"ـ{a.text}{b.text}")] for a, b in shared),
    ]


def _reading(group: list[Reading]) -> Node:
    """One result: the readings that share a gloss, such as an adjective's singular, dual and
    plural. The gloss is said once; each form keeps its own grammar and parts."""
    return li(class_="reading")[(
        fragment[
            span(class_="ar form", lang="ar", dir="rtl")[(span(class_=s.role)[s.text] for s in r.segments)],
            div(class_="sense")[
                r is group[0] and p(class_="gloss")[r.gloss],
                # The part of speech heads the entry; voice, agreement and the rest go with each reading.
                (r.tags[1:] or r.grammar) and p(class_="grammar")[(span(class_="tag")[t] for t in r.tags[1:]), r.grammar and f" {r.grammar}"],
                len(r.segments) > 1 and _parts(r),
            ],
        ]
        for r in group
    )]


class Links(NamedTuple):
    """What a Word entry links its root and related forms with: the lookup's own URL parameters,
    which every link keeps so that its view can return to the lookup, and how many forms each
    lemma (with its part of speech) has."""

    lookup: dict[str, str]
    forms: dict[tuple[str, str], int]


def _url(params: dict[str, str]) -> str:
    return f"/?{urlencode(params)}" if params else "/"


def _entry(lemma: str, glosses: dict[str, list[Reading]], heading: Element, links: Links | None) -> Node:
    """A lemma's heading, said once, then its readings, one result per gloss. With links, the
    root opens the root's words, and a lemma with more than one form links to all of them."""
    first = next(iter(glosses.values()))[0]
    forms = links.forms.get((first.lemma, first.pos), 0) if links else 0
    # A lemma's senses may be stored under different roots (إِجارَة "rent" and "protection"): each is offered.
    roots = list(dict.fromkeys(r.root for group in glosses.values() for r in group if r.root)) or [None]
    return section(class_="entry")[
        div(class_="head")[
            heading[ar(lemma)],
            p(class_="pos")[_kind(first)],
            dl[
                dt["Root"],
                dd[([
                    i > 0 and ", ",
                    a(href=_url(links.lookup | {"root": root}))[span(class_="sr-only")["Words from the root "], _root(root)]
                    if links and root else _root(root),
                ] for i, root in enumerate(roots))],
                dt["Use"], dd[_use(first.top_percent)],
                forms > 1 and [dt["Forms"], dd[
                    a(href=_url(links.lookup | {"related": first.lemma, "pos": first.pos}))[f"all {forms} forms", span(class_="sr-only")[" of ", ar(lemma)]],
                ]],
            ],
        ],
        ul(class_="readings")[(_reading(group) for group in glosses.values())],
    ]


LEGEND = p(class_="legend")["In each form: ", span(class_="prefix")["prefix"], " · stem · ", span(class_="suffix")["suffix"]]


def _count(readings) -> str:
    return f"{len(readings)} reading{'s' if len(readings) != 1 else ''}"


def _entries(readings: Iterable[Reading], heading: Element = h2, links: Links | None = None) -> Node:
    """One entry per lemma and part of speech, in the order the readings arrive."""
    groups: dict[tuple[str, str], dict[str, list[Reading]]] = {}
    for reading in readings:
        groups.setdefault((reading.lemma, reading.pos), {}).setdefault(reading.gloss, []).append(reading)
    return div(class_="entries")[(_entry(lemma, glosses, heading, links) for (lemma, _), glosses in groups.items())]


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
    if found.readings:
        arabizi = found.query if found.mode == "arabizi" else None
        return State([f"{_count(found.readings)} for ", ar(found.query)], [notice, LEGEND, _entries(found.readings, h2, links)], arabizi)
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
    "English → Arabic is limited: it matches the dictionary's short English glosses, a whole word or phrase at a time. "
    "A word it doesn't find may still have an Arabic translation, listed under a synonym."
]

INITIAL_EN = State(body=[
    p(class_="intro")["Type an English word or phrase, such as “book” or “piece of writing”, to find the Arabic words it translates."],
    COVERAGE,
])


def looked_up_en(found: Lookup, links: Links | None = None) -> State:
    """The outcome of a completed English → Arabic lookup, with the coverage note. Entries link to
    their root and related forms with links."""
    query = found.query
    if found.readings:
        n = len(found.readings)
        return State(f"{n} Arabic word{'s' if n != 1 else ''} for “{query}”", [COVERAGE, LEGEND, _entries(found.readings, h2, links)])
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


def _sorted(rows: list[Reading], sort: str) -> list[Reading]:
    """Rows sorted by a column ("gloss"), or in reverse ("-gloss"). Python's sort is stable, so rows
    that tie keep the family order, whichever the direction."""
    key = SORT_KEYS.get(sort.removeprefix("-"))
    if not key:
        return rows
    return sorted((r for r in rows if key(r) is not None), key=key, reverse=sort.startswith("-")) + [r for r in rows if key(r) is None]


def _family(label: str, name: Node, status: Node, rows: list[Reading], lookup: dict[str, str], view: dict[str, str], sort: str) -> State:
    """A root's words or a lemma's forms in place of the lookup's results. A chip says which, and
    closing it returns to the lookup. Each column header links to the list sorted by it, then in
    reverse, then back in family order; the sorted column says so to assistive technology."""
    column = sort.removeprefix("-") if sort.removeprefix("-") in SORT_KEYS else None
    order = column and ("descending" if sort.startswith("-") else "ascending")

    def header(key: str | None, text: str) -> Node:
        if key is None:
            return th(scope="col")[text]
        following = {"ascending": f"-{key}", "descending": None}.get(order) if key == column else key
        return th(scope="col", aria_sort=order if key == column else None)[a(href=_url(lookup | view | ({"sort": following} if following else {})))[text]]

    return State(status, [
        p(class_="context")[
            label, ": ", name,
            a(href=_url(lookup), class_="dismiss")[span(aria_hidden="true")["×"], span(class_="sr-only")["Back to your lookup" if lookup.get("q") else "Close"]],
        ],
        rows and table(class_="family")[
            caption(class_="sr-only")[status],
            thead[tr[(header(key, name) for key, name in COLUMNS)]],
            tbody[(
                tr[
                    td(data_label="Form")[ar(r.form)],
                    td(data_label="Meaning")[r.gloss],
                    td(data_label="Part of speech")[r.tags[0]],
                    td(data_label="Grammar")[", ".join(r.tags[1:] + ((r.grammar,) if r.grammar else ()))],
                    td(data_label="Root")[_root(r.root)],
                    td(data_label="Measure")[r.measure or ("unavailable" if r.pos == "verb" else "")],
                ]
                for r in _sorted(rows, sort)
            )],
        ],
    ])


def _forms(rows: list[Reading]) -> str:
    return f"{len(rows) or 'No'} form{'s' if len(rows) != 1 else ''}"


def related_view(lemma: str, pos: str, rows: list[Reading], lookup: dict[str, str], sort: str = "") -> State:
    """A lemma's forms, such as a noun's singular and plural."""
    status = [f"{_forms(rows)} of the {POS.get(pos, pos)} ", ar(lemma)]
    return _family("Related", ar(lemma), status, rows, lookup, {"related": lemma, "pos": pos}, sort)


def root_view(root: str, rows: list[Reading], lookup: dict[str, str], sort: str = "") -> State:
    """Every form from a root, verbs by measure first."""
    return _family("Root", _root(root), [f"{_forms(rows)} from the root ", _root(root)], rows, lookup, {"root": root}, sort)


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
            label(for_="q", class_="sr-only")["English word" if english else "Arabic word"],
            input(id="q", name="q", value=query, dir="ltr" if english else "auto", lang="en" if english else "ar", autocomplete="off", spellcheck="false"),
            _keyboard_toggle("q"),
            a(href="/?lang=en" if english else "/", class_="clear", hidden=not query)["Clear"],
            button(type="submit")["Look up"],
            _arabizi_chip(state.arabizi),
            label(class_="option")[input(type="checkbox", name="lang", value="en", checked=english, data_remember=True), " English → Arabic"],
            label(class_="option")[input(type="checkbox", name="diacritics", value="off", checked=not filter_diacritics, data_remember=True), " Ignore diacritics"],
            # Shown by autocomplete.js and remembered by history.js. form="" leaves it out of the lookup and its URL.
            label(class_="option", hidden=True)[input(type="checkbox", name="autocomplete", form="", checked=True, data_remember=True), " Show suggestions"],
        ],
        _keyboard_panel("q"),
        _history(),
        p(id="status", class_="status", role="status")[state.status],
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


def _token(t: Token, ids: dict[str, str]) -> Node:
    """A word as a button that opens its details; anything else as it was typed."""
    if t.kind not in ("word", "unknown"):
        return t.text
    return button(type="button", class_=f"tok {t.kind}", popovertarget=ids[t.text])[
        t.text, span(class_="sr-only", lang="en")[", ", _count(t.readings) if t.readings else "not in the dictionary"],
    ]


def _details(t: Token, id: str) -> Node:
    """A word's readings, grouped by lemma as on the Word page, in a native popover."""
    return div(id=id, class_="tok-pop", popover=True, role="dialog", aria_labelledby=f"{id}-h")[
        div(class_="tp-head")[
            h2(id=f"{id}-h")[ar(t.text)],
            p(class_="muted")[_count(t.readings) if t.readings else "not in the dictionary"],
            button(type="button", popovertarget=id, popovertargetaction="hide")["Close"],
        ],
        _entries(t.readings, h3) if t.readings else p(class_="tp-msg")[
            "AraDict couldn't find this word in its Modern Standard Arabic dictionary."
        ],
        p(class_="tp-foot")[a(href=f"/?{urlencode({'q': t.text})}")["Open in Word lookup"]],
    ]


def analysed(tokens: list[Token]) -> State:
    """The passage as typed, each word opening its details. A word written twice opens the same details."""
    words: dict[str, Token] = {}  # each word once, in order
    for t in tokens:
        if t.kind in ("word", "unknown"):
            words.setdefault(t.text, t)
    ids = {word: f"w{i}" for i, word in enumerate(words)}
    n, unknown = sum(t.kind in ("word", "unknown") for t in tokens), sum(t.kind == "unknown" for t in tokens)
    status = f"{n} word{'s' if n != 1 else ''}{f', {unknown} not in the dictionary' if unknown else ''}" if n else "No Arabic words to analyse."
    return State(status, [
        # The passage keeps its spaces and line breaks (white-space: pre-wrap).
        div(class_="passage", lang="ar", dir="rtl")[(_token(t, ids) for t in tokens)],
        (_details(t, ids[word]) for word, t in words.items()),
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
            label(for_="text")["Arabic text"],
            textarea(
                id="text", name="text", rows="4", dir="rtl", lang="ar", spellcheck="false",
                placeholder="Paste or type Arabic text", aria_describedby="text-hint",
            )[text],
            p(id="text-hint", class_="hint")[f"Analyse at most {MAX_TEXT:,} characters at a time."],
            div(class_="actions")[button(type="submit")["Analyse"], _keyboard_toggle("text")],
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
    return _page("About and help", "about", [
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
                "so newer words, such as the ones for “tweet” and “podcast”, are missing."
            ],
            # TODO(#17): replace this placeholder with the measured coverage from the data acceptance report.
            p(class_="placeholder")["Placeholder: the measured coverage (entries, lemmas and roots) will be added here before release."],
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
                a(href="/static/vendor/LICENSE-htmx")["Zero-Clause BSD license"], ", and the ",
                a(href="https://software.sil.org/scheherazade/")["Scheherazade New"], " font by SIL under the ",
                a(href="/static/vendor/OFL-ScheherazadeNew.txt")["SIL Open Font License"], ".",
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
