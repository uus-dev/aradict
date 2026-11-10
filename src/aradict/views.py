"""Server-rendered pages, written with htpy."""

from __future__ import annotations

import re
from urllib.parse import urlencode

from htpy import Node, a, body, button, dd, div, dl, dt, form, h1, h2, head, header, html, input, label, li, link, main, meta, nav, p, script, section, span, title, ul

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


def word_page(query: str, readings: list[Reading] | None, filter_diacritics: bool = True) -> Node:
    words = query.split()
    latin = bool(re.search("[A-Za-z]", query)) and not re.search("[\u0600-\u06ff]", query)
    notice = p(class_="notice")[
        "Only the first word, ", ar(words[0]), ", was looked up. ",
        a(href=f"/text?{urlencode({'q': query})}")["Read them all in the Text view"], ".",
    ] if len(words) > 1 and not latin else None
    if not query:
        results: Node = None
    elif readings:
        results = [p(class_="count")[f"{len(readings)} reading{'s' if len(readings) != 1 else ''} for ", ar(words[0])], _entries(readings)]
    elif latin:  # ponytail: a hint until Arabizi (#10) and English lookup (#9) ship
        results = div(class_="empty")[
            h2["Type the word in Arabic script"],
            p["Arabic in Latin letters (Arabizi) isn't supported yet. Looking for an English word? English → Arabic lookup is coming soon."],
        ]
    else:
        results = div(class_="empty")[
            h2["No entry for ", ar(words[0])],
            p["AraDict couldn't find this word in its Modern Standard Arabic dictionary. Check the spelling."],
        ]
    return _page("Word", "word", [
        h1(class_="sr-only")["Word lookup"],
        form(class_="search", method="get", action="/", role="search")[
            label(for_="q", class_="sr-only")["Arabic word"],
            input(id="q", name="q", value=query, dir="rtl", lang="ar", autocomplete="off", spellcheck="false", required=True),
            button(type="submit")["Look up"],
            label(class_="option")[input(type="checkbox", name="diacritics", value="off", checked=not filter_diacritics), " Ignore diacritics"],
        ],
        notice,
        results,
    ])


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
