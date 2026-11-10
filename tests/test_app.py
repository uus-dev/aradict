"""Pages, served by the app over the fixture database."""

import re


def test_word_page_lists_readings_grouped_by_lemma(client):
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 200
    assert page.text.count('class="reading"') == 3
    assert page.text.count('class="entry"') == 2  # كِتاب, and كَتَب with two readings
    assert '<html lang="en" dir="ltr">' in page.text
    assert '<span class="ar" lang="ar" dir="rtl">كَتَب</span>' in page.text


def test_unknown_word_says_so(client):
    page = client.get("/", params={"q": "قخغثص"})
    assert page.status_code == 200
    assert "No entry for" in page.text
    assert 'class="reading"' not in page.text


def test_home_has_a_plain_get_form(client):
    page = client.get("/")
    assert '<form class="search" method="get" action="/"' in page.text
    assert "No entry" not in page.text


def test_home_intro_follows_the_search_box_until_a_word_is_looked_up(client):
    home = client.get("/").text
    assert 'class="intro"' in home
    assert home.index('class="search"') < home.index('class="intro"')
    assert "Modern Standard Arabic" in home
    assert 'class="intro"' not in client.get("/", params={"q": "كتب"}).text


def test_about_answers_what_a_visitor_needs_before_trusting_a_result(client):
    about = client.get("/about").text
    # Coverage: the language variety, the corpus, and a marked slot for the measured numbers (#17).
    assert "Modern Standard Arabic" in about and "calima-msa-r13" in about
    assert 'class="placeholder"' in about
    # Typing Arabic: hamza, diacritics, the on-screen keyboard, phone keyboards, Arabizi.
    typing = about[about.index('id="typing"'):]
    for topic in ("hamza", "vowel marks", "on-screen keyboard", "phone", "Arabizi", "mar7aba"):
        assert topic in typing, topic
    # Privacy: no accounts, history on the device, passages not logged.
    privacy = about[about.index('id="privacy"'):]
    for fact in ("no accounts", "stay in this browser", "never sent", "not logged"):
        assert fact in privacy, fact
    # Support and native apps.
    assert 'href="https://github.com/uus-dev/aradict/issues"' in about
    assert "AraDict has no native apps" in about


def test_about_carries_the_gpl_notices_and_copyright_lines(client):
    about = client.get("/about").text
    # The data's notices, as the calima-msa-r13 LICENSE file states them.
    for line in (
        "Portions (c) 2002 QAMUS LLC (www.qamus.org)",
        "(c) 2002 Trustees of the University of Pennsylvania",
        "Portions (c) 2006 Jon Dehdari",
        "GNU General Public License version 2",
    ):
        assert line in about, line
    # AraDict's own GPL-2.0-or-later notice, as in README.md, with the source code.
    for line in (
        "Copyright (C) 2026 the AraDict contributors.",
        "either version 2 of the License, or (at your option) any later version",
        "WITHOUT ANY WARRANTY",
        'href="https://github.com/uus-dev/aradict"',
    ):
        assert line in about, line
    # Bundled assets keep their own licenses.
    assert "Zero-Clause BSD" in about and "SIL Open Font License" in about


def test_help_links_work(client):
    pages = {path: client.get(path).text for path in ("/", "/about")}
    for path, page in pages.items():
        for href in re.findall(r'href="(/[^"]*)"', page):
            target, _, anchor = href.partition("#")
            response = client.get(target)
            assert response.status_code == 200, (path, href)
            assert not anchor or f'id="{anchor}"' in response.text, (path, href)
    external = set(re.findall(r'href="(https?://[^"]+)"', pages["/about"]))
    assert all(href.startswith("https://") for href in external)
    assert {
        "https://github.com/uus-dev/aradict",  # source code
        "https://github.com/uus-dev/aradict/blob/main/LICENSE",
        "https://github.com/uus-dev/aradict/issues",  # support
        "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
        "https://github.com/CAMeL-Lab/camel-tools-data/releases/tag/2022.03.21",  # the pinned database release
    } <= external


def test_other_pages_and_assets(client):
    assert 'aria-current="page" href="/text"' in client.get("/text").text
    assert client.get("/static/vendor/htmx.min.js").status_code == 200


def test_overlong_query_is_rejected(client):
    assert client.get("/", params={"q": "ك" * 101}).status_code == 422


def test_server_does_not_log_looked_up_words(monkeypatch):
    import aradict.__main__ as entry

    options = {}
    monkeypatch.setenv("ARADICT_DB_PATH", "unused")
    monkeypatch.setattr(entry.uvicorn, "run", lambda *args, **kwargs: options.update(kwargs))
    entry.main()
    assert options["access_log"] is False
