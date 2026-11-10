"""Server-rendered pages, written with htpy."""

from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import urlencode

from htpy import Node, a, blockquote, body, br, button, code, dd, div, dl, dt, form, fragment, h1, h2, head, header, html, i, input, label, li, link, main, meta, nav, p, script, section, span, template, title, ul

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


def _intro() -> Node:
    """What AraDict does, below the search box and only before the first lookup, so it never pushes results down."""
    return p(class_="intro")[
        "An Arabic–English dictionary for Modern Standard Arabic. Type or paste any Arabic word, "
        "with or without vowel marks, to see every way it can be read. ",
        a(href="/about#typing")["How to type Arabic"],
    ]


class State(NamedTuple):
    """One outcome of a lookup: the status line, which screen readers announce, and what
    fills the results area below it."""

    status: Node = None
    body: Node = None


INITIAL = State(body=_intro())


def looked_up(query: str, readings: list[Reading]) -> State:
    """The outcome of a completed lookup. Of several words only the first is looked up, and a notice says so."""
    words = query.split()
    latin = bool(re.search("[A-Za-z]", query)) and not re.search("[\u0600-\u06ff]", query)
    notice = p(class_="notice")[
        "Only the first word, ", ar(words[0]), ", was looked up. ",
        a(href=f"/text?{urlencode({'q': query})}")["Read them all in the Text view"], ".",
    ] if len(words) > 1 and not latin else None
    if readings:
        return State([f"{len(readings)} reading{'s' if len(readings) != 1 else ''} for ", ar(words[0])], [notice, _entries(readings)])
    if latin:  # ponytail: a hint until Arabizi (#10) and English lookup (#9) ship
        return State("Type the word in Arabic script", div(class_="empty")[
            p["Arabic in Latin letters (Arabizi) isn't supported yet. Looking for an English word? English → Arabic lookup is coming soon."],
        ])
    return State(["No entry for ", ar(words[0])], [notice, div(class_="empty")[
        p["AraDict couldn't find this word in its Modern Standard Arabic dictionary. You could:"],
        ul[li["Check the spelling."], li["Type it without vowel marks."]],
    ]])


FAILURE = State(
    "Lookup failed. Your word is kept, so you can try again.",
    p(class_="retry")[button(type="submit", form="search")["Retry"]],
)


def word_page(query: str, state: State, filter_diacritics: bool = True) -> Node:
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
            label(class_="option")[input(type="checkbox", name="diacritics", value="off", checked=not filter_diacritics), " Ignore diacritics"],
        ],
        p(id="status", class_="status", role="status")[state.status],
        div(id="results")[state.body],
        # Shown by lookup.js when a live lookup fails, including when the server can't be reached.
        template(id="failure", data_status=FAILURE.status)[FAILURE.body],
        script(src="/static/lookup.js", type="module"),
        script(src="/static/autocomplete.js", type="module"),
    ])


def live_results(state: State) -> Node:
    """What a live lookup swaps into the results area, with the status line updated out of band."""
    return fragment[p(id="status", hx_swap_oob="innerHTML")[state.status], state.body]


def text_page() -> Node:
    return _page("Text", "text", [h1["Text"], p["Passage analysis is coming soon. For now, look up one word at a time on the Word page."]])


REPO = "https://github.com/uus-dev/aradict"


def _arabizi(text: str) -> Node:
    return i(lang="ar-Latn")[text]


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
                ar("ذ"), ". Short vowels are optional."
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
                li["Passages you paste into the Text view are sent to the server to be analysed, and are not logged. They never go into the page address."],
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
