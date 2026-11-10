"""Server-rendered pages, written with htpy."""

from __future__ import annotations

from htpy import Node, a, body, button, dd, details, div, dl, dt, form, h1, h2, head, header, html, input, label, li, link, main, meta, nav, ol, p, script, section, span, summary, title, ul

from .dictionary import Reading, Segment

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


def _reading(r: Reading) -> Node:
    return li(class_="reading")[
        span(class_="ar form", lang="ar", dir="rtl")[(span(class_=s.role)[s.text] for s in r.segments)],
        div(class_="sense")[
            p(class_="gloss")[r.gloss],
            # The part of speech heads the entry; voice, agreement and the rest go with each reading.
            (r.tags[1:] or r.grammar) and p(class_="grammar")[(span(class_="tag")[t] for t in r.tags[1:]), r.grammar and f" {r.grammar}"],
            len(r.segments) > 1 and _parts(r),
        ],
    ]


def _entries(readings: list[Reading]) -> Node:
    """One entry per lemma and part of speech, in the order the readings arrive."""
    groups: dict[tuple[str, str], list[Reading]] = {}
    for reading in readings:
        groups.setdefault((reading.lemma, reading.pos), []).append(reading)
    return [
        p(class_="legend")["In each form: ", span(class_="prefix")["prefix"], " · stem · ", span(class_="suffix")["suffix"]],
        div(class_="entries")[
            (
                section(class_="entry")[
                    div(class_="head")[
                        h2[ar(lemma)],
                        p(class_="pos")[group[0].tags[0]],
                        dl[dt["Root"], dd[_root(group[0].root)]],
                    ],
                    ul(class_="readings")[(_reading(r) for r in group)],
                ]
                for (lemma, pos), group in groups.items()
            )
        ],
    ]


def word_page(query: str, readings: list[Reading] | None) -> Node:
    if not query:
        results: Node = None
    elif readings:
        results = [p(class_="count")[f"{len(readings)} reading{'s' if len(readings) != 1 else ''} for ", ar(query)], _entries(readings)]
    else:
        results = div(class_="empty")[
            h2["No entry for ", ar(query)],
            p["AraDict couldn't find this word in its Modern Standard Arabic dictionary. Check the spelling."],
        ]
    return _page("Word", "word", [
        h1(class_="sr-only")["Word lookup"],
        form(class_="search", method="get", action="/", role="search")[
            label(for_="q", class_="sr-only")["Arabic word"],
            input(id="q", name="q", value=query, dir="rtl", lang="ar", autocomplete="off", spellcheck="false", required=True),
            button(type="submit")["Look up"],
        ],
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
