"""Server-rendered pages, written with htpy."""

from __future__ import annotations

from typing import NamedTuple

from htpy import Node, a, body, button, dd, div, dl, dt, form, fragment, h1, h2, head, header, html, input, label, li, link, main, meta, nav, p, script, section, span, template, title, ul

from .dictionary import Reading

PAGES = [("word", "/", "Word"), ("text", "/text", "Text"), ("about", "/about", "About")]


def ar(text: str) -> Node:
    """Arabic inside an English page: its own language and right-to-left direction."""
    return span(class_="ar", lang="ar", dir="rtl")[text]


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


def _entries(readings: list[Reading]) -> Node:
    """One entry per lemma and part of speech, in the order the readings arrive."""
    groups: dict[tuple[str, str], list[Reading]] = {}
    for reading in readings:
        groups.setdefault((reading.lemma, reading.pos), []).append(reading)
    return div(class_="entries")[
        (
            section(class_="entry")[
                div(class_="head")[
                    h2[ar(lemma)],
                    p(class_="pos")[pos.replace("_", " ")],
                    dl[dt["Root"], dd[_root(group[0].root)]],
                ],
                ul(class_="readings")[(li(class_="reading")[ar(r.form), span(class_="gloss")[r.gloss]] for r in group)],
            ]
            for (lemma, pos), group in groups.items()
        )
    ]


class State(NamedTuple):
    """One outcome of a lookup: the status line, which screen readers announce, and what
    fills the results area below it."""

    status: Node = None
    body: Node = None


def found(query: str, readings: list[Reading]) -> State:
    return State([f"{len(readings)} reading{'s' if len(readings) != 1 else ''} for ", ar(query)], _entries(readings))


def not_found(query: str) -> State:
    return State(["No entry for ", ar(query)], div(class_="empty")[
        p["AraDict couldn't find this word in its Modern Standard Arabic dictionary. You could:"],
        ul[li["Check the spelling."], li["Type it without vowel marks."]],
    ])


FAILURE = State(
    "Lookup failed. Your word is kept, so you can try again.",
    p(class_="retry")[button(type="submit", form="search")["Retry"]],
)


def word_page(query: str, state: State) -> Node:
    return _page("Word", "word", [
        h1(class_="sr-only")["Word lookup"],
        # Live lookup: the same GET as the plain form, debounced while typing and immediate on Enter.
        # Its results replace the results area and the URL is pushed; a newer request aborts an older one.
        form(
            id="search", class_="search", method="get", action="/", role="search",
            hx_get="/", hx_trigger="input delay:150ms, submit", hx_target="#results", hx_push_url="true", hx_sync="this:replace",
        )[
            label(for_="q", class_="sr-only")["Arabic word"],
            input(id="q", name="q", value=query, dir="rtl", lang="ar", autocomplete="off", spellcheck="false"),
            a(href="/", class_="clear", hidden=not query)["Clear"],
            button(type="submit")["Look up"],
        ],
        p(id="status", class_="status", role="status")[state.status],
        div(id="results")[state.body],
        # Shown by lookup.js when a live lookup fails, including when the server can't be reached.
        template(id="failure", data_status=FAILURE.status)[FAILURE.body],
        script(src="/static/lookup.js", type="module"),
    ])


def live_results(state: State) -> Node:
    """What a live lookup swaps into the results area, with the status line updated out of band."""
    return fragment[p(id="status", hx_swap_oob="innerHTML")[state.status], state.body]


def text_page() -> Node:
    return _page("Text", "text", [h1["Text"], p["Passage analysis is coming soon. For now, look up one word at a time on the Word page."]])


def about_page() -> Node:
    return _page("About", "about", [
        h1["About AraDict"],
        p["AraDict is an Arabic–English dictionary for Modern Standard Arabic. Paste an inflected word and see every possible reading."],
        p[
            "Morphology data: the CAMeL Tools ",
            a(href="https://github.com/CAMeL-Lab/camel-tools-data")["calima-msa-r13"],
            " database, licensed under the GNU GPL version 2.",
        ],
    ])
