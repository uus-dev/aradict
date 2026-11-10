"""Pages, served by the app over the fixture database."""

import html
import re
from urllib.parse import parse_qs, urlsplit


def test_word_page_lists_readings_grouped_by_lemma(client):
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 200
    assert page.text.count('class="reading"') == 3
    assert page.text.count('class="entry"') == 2  # كِتاب, and كَتَب with two readings
    assert '<html lang="en" dir="ltr">' in page.text
    assert '<span class="ar" lang="ar" dir="rtl">كَتَب</span>' in page.text


def test_reading_shows_marked_parts_gloss_grammar_and_word_parts(client):
    page = client.get("/", params={"q": "وبكتابهم"}).text
    start = page.index('<li class="reading">')
    reading = page[start:page.index("</details>", start)]
    # The form, with each part marked by its role.
    assert ('<span class="ar form" lang="ar" dir="rtl"><span class="prefix">وَ</span><span class="prefix">بِ</span>'
            '<span class="stem">كِتاب</span><span class="suffix">هم</span></span>') in reading
    assert '<p class="gloss">and by/with their book</p>' in reading
    assert '<p class="grammar"><span class="tag">masculine singular</span> construct state</p>' in reading
    # Word parts: a native disclosure, closed by default, one labelled chip per part, right to left.
    assert '<details class="parts"><summary>Word parts</summary><ol class="chips" dir="rtl">' in reading
    assert ('<li class="chip prefix"><span class="ar" lang="ar">بِـ</span>'
            '<span class="label"><span class="sr-only">prefix: </span>by/with</span></li>') in reading
    assert '<span class="ar" lang="ar">ـهم</span><span class="label"><span class="sr-only">suffix: </span>their</span>' in reading
    assert '<p class="pos">noun</p>' in page  # the entry's part of speech, in plain English


def test_word_parts_explain_a_letter_two_parts_share(client):
    page = client.get("/", params={"q": "مدرستي"}).text
    # مَدْرَسَتَيَّ "my two schools": the dual ending and "my" share one ي, written with a shadda.
    assert '<span class="ar" lang="ar">ـَتَيْ</span><span class="label"><span class="sr-only">suffix: </span>dual ending</span>' in page
    assert '<span class="ar" lang="ar">ـيَ</span><span class="label"><span class="sr-only">suffix: </span>my</span>' in page
    assert '<p class="note"><span class="ar" lang="ar" dir="rtl">ـَتَيْ</span> + <span class="ar" lang="ar" dir="rtl">ـيَ</span> are written' in page


def test_unknown_word_says_so_and_suggests_next_steps(client):
    page = client.get("/", params={"q": "قخغثص"})
    assert page.status_code == 200
    assert "No entry for" in page.text
    assert "Check the spelling" in page.text
    assert "without vowel marks" in page.text
    assert "Latin letters (Arabizi)" in page.text
    assert 'class="reading"' not in page.text


def test_home_has_a_plain_get_form(client):
    page = client.get("/")
    assert 'class="search" method="get" action="/"' in page.text
    assert "No entry" not in page.text


def test_live_lookup_gets_only_the_results_and_status(client):
    page = client.get("/", params={"q": "كتب"}, headers={"HX-Request": "true"})
    assert page.status_code == 200
    assert "<html" not in page.text and "<form" not in page.text
    assert page.text.count('class="reading"') == 3
    assert "3 readings for" in page.text
    assert "HX-Request" in page.headers["vary"]  # a cached fragment must never stand in for the page


def test_live_lookup_of_a_blank_query_returns_to_the_home_url(client):
    page = client.get("/", params={"q": " "}, headers={"HX-Request": "true"})
    assert page.headers["HX-Push-Url"] == "/"
    assert 'class="reading"' not in page.text
    page = client.get("/", params={"q": "", "diacritics": "off"}, headers={"HX-Request": "true"})
    assert page.headers["HX-Push-Url"] == "/?diacritics=off"  # the switch survives clearing


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
    for topic in ("hamza", "vowel marks", "on-screen keyboard", "phone", "Arabizi", "mar7aba", "kitab"):
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


def test_overlong_query_shows_the_invalid_state_and_keeps_the_input(client):
    page = client.get("/", params={"q": "ك" * 101})
    assert page.status_code == 200
    assert "at most 100 characters" in page.text
    assert f'value="{"ك" * 101}"' in page.text


def test_query_without_letters_shows_the_invalid_state(client):
    page = client.get("/", params={"q": "123 !?"})
    assert "Type a word" in page.text
    assert "No entry for" not in page.text


def test_service_failure_offers_retry_and_keeps_the_input(client, monkeypatch):
    class Broken:
        def lookup_ar(self, word):
            raise RuntimeError("database gone")

    monkeypatch.setattr("aradict.app.dictionary", Broken)
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 500
    assert "Lookup failed" in page.text
    assert 'value="كتب"' in page.text
    assert 'type="submit" form="search">Retry</button>' in page.text  # resubmits the kept input


def test_several_words_look_up_the_first_and_offer_the_text_view(client):
    page = client.get("/", params={"q": "كتب كتاب"})
    assert page.text.count('class="reading"') == 3  # the readings of كتب
    assert "Only the first word" in page.text
    href = re.search(r'href="(/text\?[^"]*)"', page.text).group(1)
    assert parse_qs(urlsplit(html.unescape(href)).query) == {"q": ["كتب كتاب"]}


def test_diacritic_filter_is_on_by_default_and_can_be_switched_off(client):
    assert client.get("/", params={"q": "كَتَبَ"}).text.count('class="reading"') == 1
    page = client.get("/", params={"q": "كَتَبَ", "diacritics": "off"})
    assert page.text.count('class="reading"') == 3
    assert re.search(r'<input[^>]*name="diacritics"[^>]*checked', page.text)  # the switch shows its state


def test_form_has_a_labelled_diacritics_switch(client):
    page = client.get("/").text
    assert re.search(r'<label[^>]*>\s*<input type="checkbox" name="diacritics" value="off"[^>]*>\s*Ignore diacritics', page)


def test_latin_word_with_no_arabic_match_shows_the_no_results_guidance(client):
    page = client.get("/", params={"q": "hello"}).text
    assert 'class="reading"' not in page
    assert "No Arabic word for" in page
    assert "Check the spelling" in page and "7 for" in page  # the Arabizi digits
    assert "English" in page  # perhaps it was an English word
    assert "English" not in client.get("/", params={"q": "قخغثص"}).text
    assert chip(page) == ""


def test_one_word_has_no_multi_word_notice(client):
    assert "Only the first word" not in client.get("/", params={"q": "كتب"}).text


def test_suggestions_come_as_a_list_of_vocalized_forms(client):
    response = client.get("/suggest", params={"q": "كتا"})
    assert response.status_code == 200
    assert response.json()[:2] == ["كِتاب", "كُتّاب"]
    assert client.get("/suggest", params={"q": "كُتّا"}).json() == ["كُتّاب"]
    assert "كِتاب" in client.get("/suggest", params={"q": "كُتّا", "diacritics": "off"}).json()  # follows the switch
    assert client.get("/suggest", params={"q": ""}).json() == []


def test_server_does_not_log_looked_up_words(monkeypatch):
    import aradict.__main__ as entry

    options = {}
    monkeypatch.setenv("ARADICT_DB_PATH", "unused")
    monkeypatch.setattr(entry.uvicorn, "run", lambda *args, **kwargs: options.update(kwargs))
    entry.main()
    assert options["access_log"] is False


def test_text_page_starts_with_an_empty_passage_box_and_documents_its_limit(client):
    page = client.get("/text").text
    assert re.search(r'<textarea[^>]*placeholder="[^"]+"[^>]*></textarea>', page)
    assert "at most 2,000 characters" in page
    assert 'method="post" action="/text"' in page  # a passage never goes into the page address


def passage_of(page: str) -> str:
    return re.search(r'<div class="passage"[^>]*>(.*?)</div>', page, re.S).group(1)


def test_text_keeps_the_passage_in_order_and_marks_unknown_words(client):
    passage = passage_of(client.post("/text", data={"text": "كتب، 3 BBC\r\nقخغثص كتب"}).text)
    # What a reader sees is the passage as typed: punctuation, number, Latin text and line break in place.
    shown = re.sub(r'<span class="sr-only".*?</span>|<[^>]+>', "", passage)
    assert html.unescape(shown) == "كتب، 3 BBC\nقخغثص كتب"
    # Each word is a button; an unknown word is marked by its class and its accessible name, not by colour alone.
    assert re.findall(r'<button type="button" class="tok (\w+)" popovertarget="(\w+)">', passage) == [
        ("word", "w0"), ("unknown", "w1"), ("word", "w0"),  # the repeated word opens the same details
    ]
    assert '<span class="sr-only" lang="en">, 3 readings</span>' in passage
    assert '<span class="sr-only" lang="en">, not in the dictionary</span>' in passage


def test_word_details_show_its_readings_and_open_in_word_lookup(client):
    page = client.post("/text", data={"text": "كَتَبَ كتب قخغثص"}).text
    vocalized, bare, unknown = (page[page.index(f'<div id="{i}"'):] for i in ("w0", "w1", "w2"))
    assert re.match(r'<div id="w0" class="tok-pop" popover role="dialog" aria-labelledby="w0-h">', vocalized)
    # The same entries as the Word page: one per lemma, with its part of speech and root, then its readings.
    assert vocalized[:vocalized.index('id="w1"')].count('class="reading"') == 1  # only the vocalized reading
    assert bare[:bare.index('id="w2"')].count('class="entry"') == 2 and bare[:bare.index('id="w2"')].count('class="reading"') == 3
    assert '<p class="gloss">he/it wrote</p>' in vocalized and "<dt>Root</dt>" in vocalized
    assert "not in the dictionary" in unknown and 'class="reading"' not in unknown
    hrefs = [html.unescape(h) for h in re.findall(r'<a href="([^"]*)">Open in Word lookup</a>', page)]
    assert [parse_qs(urlsplit(h).query) for h in hrefs] == [{"q": ["كَتَبَ"]}, {"q": ["كتب"]}, {"q": ["قخغثص"]}]
    assert all(h.startswith("/?") for h in hrefs)


def test_overlong_text_shows_the_limit_and_keeps_all_of_it(client):
    text = "كتب " * 500 + "كتاب"  # 2,004 characters
    page = client.post("/text", data={"text": text})
    assert page.status_code == 200
    assert "2,004 characters" in page.text and "at most 2,000" in page.text
    assert 'class="passage"' not in page.text
    assert f">{text}</textarea>" in page.text  # nothing is cut off


def test_pasted_markup_is_shown_as_text(client):
    page = client.post("/text", data={"text": "<script>alert(1)</script> كتب"}).text
    assert "<script>alert" not in page
    assert html.unescape(re.sub(r"<[^>]+>", "", passage_of(page))).startswith("<script>alert(1)</script> كتب")


def test_the_word_pages_text_view_link_analyses_all_its_words(client):
    word_page = client.get("/", params={"q": "كتب كتاب"}).text
    page = client.get(html.unescape(re.search(r'href="(/text\?[^"]*)"', word_page).group(1))).text
    assert ">كتب كتاب</textarea>" in page
    assert passage_of(page).count('class="tok word"') == 2


def test_live_analysis_returns_the_passage_and_its_status(client):
    page = client.post("/text", data={"text": "كتب قخغثص كتب"}, headers={"HX-Request": "true"})
    assert "<html" not in page.text and "<textarea" not in page.text
    assert 'id="arabizi"' not in page.text  # the Word page's Arabizi chip has no place to land here
    assert '<p id="status" hx-swap-oob="innerHTML">3 words, 1 not in the dictionary</p>' in page.text
    assert passage_of(page.text).count('class="tok ') == 3
    assert page.headers["Vary"] == "HX-Request"


def test_failed_analysis_keeps_the_text_and_never_logs_it(client, monkeypatch, caplog):
    class Broken:
        def analyze_text(self, text):
            raise RuntimeError("database gone")

    monkeypatch.setattr("aradict.app.dictionary", Broken)
    page = client.post("/text", data={"text": "كتب سرّي"})
    assert page.status_code == 500
    assert "Analysis failed" in page.text and ">كتب سرّي</textarea>" in page.text
    assert "database gone" in caplog.text and "سرّي" not in caplog.text


def chip(page: str) -> str:
    """The text of the Arabizi chip next to the input, or "" when it is hidden."""
    tag = re.search(r'<p id="arabizi"([^>]*)>(.*?)</p>', page)
    return "" if "hidden" in tag.group(1) else html.unescape(re.sub("<[^>]+>", "", tag.group(2)))


def test_arabizi_is_looked_up_as_the_arabic_it_stands_for(client):
    page = client.get("/", params={"q": "ktb"}).text
    assert page.count('class="reading"') == 3  # the readings of كتب
    assert '3 readings for <span class="ar" lang="ar" dir="rtl">كتب</span>' in page
    assert "كتب" in chip(page)
    assert 'value="ktb"' in page  # the input keeps what was typed

    page = client.get("/", params={"q": "kitab"}).text
    assert "كِتاب" in chip(page)  # Arabic script, with the vowel typed


def test_arabic_input_shows_no_arabizi_chip(client):
    assert chip(client.get("/", params={"q": "كتب"}).text) == ""
    assert chip(client.get("/").text) == ""


def test_live_lookup_updates_the_arabizi_chip(client):
    live = {"HX-Request": "true"}
    page = client.get("/", params={"q": "ktb"}, headers=live).text
    assert 'hx-swap-oob="true"' in re.search(r'<p id="arabizi"[^>]*>', page).group(0)
    assert "كتب" in chip(page)
    for query in ("كتب", "hello", ""):  # Arabic, no match, and cleared all hide it
        assert chip(client.get("/", params={"q": query}, headers=live).text) == "", query


def test_several_latin_words_look_up_the_first(client):
    page = client.get("/", params={"q": "ktb kitab"}).text
    assert page.count('class="reading"') == 3
    assert "Only the first word" in page
    assert "/text?" not in page  # the Text view reads Arabic script only
