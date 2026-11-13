"""Pages, served by the app over the fixture database."""

import html
import logging
import re
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen


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
    assert '<dd class="gloss">and by/with their book</dd>' in reading
    # The attached pronoun is part of the grammar too, as in the M1 design (#14).
    assert '<ul class="grammar"><li>masculine singular</li><li>construct state</li><li>attached: their</li></ul>' in reading
    # Word parts: a native disclosure, closed by default, one labelled chip per part, right to left.
    assert '<details class="parts"><summary>Word parts</summary><ol class="chips" dir="rtl">' in reading
    assert ('<li class="chip prefix"><span class="kind" dir="ltr">prefix<span class="sr-only">: </span></span>'
            '<span class="ar" lang="ar">بِـ</span><span class="label" dir="ltr">by/with</span></li>') in reading
    assert '<span class="ar" lang="ar">ـهم</span><span class="label" dir="ltr">their</span>' in reading
    assert '<p class="pos"><span class="badge">noun</span></p>' in page  # the entry's part of speech, in plain English


def test_word_parts_explain_a_letter_two_parts_share(client):
    page = client.get("/", params={"q": "مدرستي"}).text
    # مَدْرَسَتَيَّ "my two schools": the dual ending and "my" share one ي, written with a shadda.
    assert '<span class="ar" lang="ar">ـَتَيْ</span><span class="label" dir="ltr">dual ending</span>' in page
    assert '<span class="ar" lang="ar">ـيَ</span><span class="label" dir="ltr">my</span>' in page
    assert '<p class="note"><span class="ar" lang="ar" dir="rtl">ـَتَيْ</span> + <span class="ar" lang="ar" dir="rtl">ـيَ</span> are written' in page


def test_unknown_word_says_so_and_suggests_next_steps(client):
    page = client.get("/", params={"q": "قخغثص"})
    assert page.status_code == 200
    assert "No entry for" in page.text
    assert "Check the spelling" in page.text
    assert "without vowel marks" in page.text
    assert "Latin letters (Arabizi)" in page.text
    assert 'class="reading"' not in page.text
    assert re.search(r'<a href="/\?lang=en">[^<]*English → Arabic</a>', page.text)  # or switch direction


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
    page = client.get("/", params={"q": "", "lang": "en"}, headers={"HX-Request": "true"})
    assert page.headers["HX-Push-Url"] == "/?lang=en"  # and so does the direction


def test_home_intro_follows_the_search_box_until_a_word_is_looked_up(client):
    home = client.get("/").text
    assert 'class="intro"' in home
    assert home.index('class="search"') < home.index('class="intro"')
    assert "Modern Standard Arabic" in home
    assert 'class="intro"' not in client.get("/", params={"q": "كتب"}).text


def test_about_answers_what_a_visitor_needs_before_trusting_a_result(client):
    about = client.get("/about").text
    # Coverage: the language variety, the corpus, and its measured size (#17; tests/test_acceptance.py checks the numbers).
    assert "Modern Standard Arabic" in about and "calima-msa-r13" in about
    coverage = about[about.index('id="coverage"'):about.index('id="typing"')]
    for measure in ("entries", "headwords", "roots", "measure", "no root"):
        assert measure in coverage, measure
    assert "placeholder" not in about.lower()
    # Typing Arabic: hamza, diacritics, the on-screen keyboard, phone keyboards, Arabizi.
    typing = about[about.index('id="typing"'):]
    for topic in ("hamza", "vowel marks", "on-screen keyboard", "phone", "Arabizi", "mar7aba", "kitab"):
        assert topic in typing, topic
    # Privacy: no accounts, history on the device, passages not logged.
    privacy = about[about.index('id="privacy"'):]
    for fact in ("no accounts", "stay in this browser", "never sent", "not logged"):
        assert fact in privacy, fact
    # What reaches the Text view through its address: a Word lookup's words, which a link caps.
    assert "at most 100 characters" in privacy[:privacy.index("</section>")]
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


class Broken:
    """A dictionary whose every call fails, quoting its arguments in the error as a library might."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise RuntimeError(f"{name} failed on {args}")
        return fail


def test_service_failure_offers_retry_and_keeps_the_input_out_of_the_log(client, monkeypatch, caplog):
    monkeypatch.setattr("aradict.app.dictionary", Broken)
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 500
    assert "Lookup failed" in page.text
    assert 'value="كتب"' in page.text
    assert 'type="submit" form="search">Retry</button>' in page.text  # resubmits the kept input
    # The log says what failed and where, but not the error's message, which quotes the word.
    assert "RuntimeError" in caplog.text and "test_app.py" in caplog.text
    assert "كتب" not in caplog.text


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
    assert 'href="/?q=hello&amp;lang=en"' in page  # perhaps it was an English word: look it up as one
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


def entries(page: str) -> list[str]:
    return page.split('<section class="entry">')[1:]


def test_each_entry_heads_its_readings_with_part_of_speech_measure_root_and_use(client):
    # سيكتبون: two lemmas, each with an active and a passive reading.
    katab, aktab = entries(client.get("/", params={"q": "سيكتبون"}).text)
    verb = '<p class="pos"><span class="badge">verb</span> <span class="badge measure">Measure {}</span></p>'
    assert '<h2><span class="ar" lang="ar" dir="rtl">كَتَب</span></h2>' + verb.format("I") in katab
    assert '<h2><span class="ar" lang="ar" dir="rtl">أَكْتَب</span></h2>' + verb.format("IV") in aktab
    assert katab.count('class="reading"') == aktab.count('class="reading"') == 2
    assert "Root ك ت ب 16 words" in links(heading(katab))  # the root, as a link to its words, as many as the root view lists
    assert re.search(r'<dt>Frequency</dt><dd class="freq">.*?<span class="band">(very common|common|less common|rare)</span>'
                     r' <span class="pct">top \d+% of words</span></dd>', katab)
    assert '<span class="band">frequency unknown</span></dd>' in aktab  # the database has no figure for أَكْتَب
    assert verb.format("X") in client.get("/", params={"q": "استخدم"}).text


def test_the_least_frequent_lemmas_read_just_rare(client):
    # آر "area" is at the database's lowest frequency, where "top 100% of words" says nothing.
    assert '<span class="band">rare</span></dd>' in client.get("/", params={"q": "آر"}).text


def test_unresolved_radicals_and_missing_root_or_measure_show_as_such(client):
    qal = entries(client.get("/", params={"q": "قال"}).text)[0]
    assert [params["root"] for name, params in links(qal).items() if name.startswith("Root ق ◌ ل")] == [["ق.#.ل"]]  # its words are a link away
    assert "#" not in qal
    laysa = entries(client.get("/", params={"q": "ليس"}).text)[0]
    assert '<p class="pos"><span class="badge">verb</span> <span class="badge measure na">measure unavailable</span></p>' in laysa
    assert '<span class="root-tab na"><span class="rt-k">Root</span> <span class="muted">unavailable</span></span>' in laysa


def test_readings_that_share_a_gloss_are_one_result_listing_every_form(client):
    page = client.get("/", params={"q": "سابقي"}).text
    result = next(r for r in page.split('<li class="reading">')[1:] if "my former" in r)
    forms = [unicodedata.normalize("NFC", re.sub("<[^>]+>", "", f)) for f in re.findall(
        r'<span class="ar form" lang="ar" dir="rtl">(?:<span class="\w+">[^<]*</span>)+</span>', result)]
    assert sorted(forms) == sorted(["سابِقِي", "سابِقَيَّ", "سابِقِيَّ"])  # singular, dual and plural
    assert result.count('class="gloss"') == 1
    assert result.count('class="grammar"') == 3  # each form keeps its own grammar


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
    assert '<dd class="gloss">he/it wrote</dd>' in vocalized
    # The root links to its words as on the Word page (#14), without the count, which is too slow
    # to work out for every root of a long passage; closing the root view returns to the word's lookup.
    assert links(vocalized[:vocalized.index('id="w1"')]) == {
        "Root ك ت ب words": {"q": ["كَتَبَ"], "root": ["ك.ت.ب"]},
        "Open in Word lookup": {"q": ["كَتَبَ"]},
    }
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


class Unreachable:
    """A dictionary that fails every call: input refused at the door never reaches it."""

    def __getattr__(self, name):
        raise AssertionError(f"dictionary().{name} was called")


def test_an_oversized_passage_is_refused_without_being_analysed(client, monkeypatch):
    monkeypatch.setattr("aradict.app.dictionary", Unreachable)
    form = {"content-type": "application/x-www-form-urlencoded"}
    body = urlencode({"text": "كتب " * 20_000})  # 80,000 characters, far past what a form of 2,000 can need
    sized = client.post("/text", content=body, headers=form)  # refused by its Content-Length
    streamed = client.post("/text", content=iter([body.encode()]), headers=form)  # no length: refused while reading
    for page in (sized, streamed):
        assert page.status_code == 200
        assert "Your text is too long. Analyse at most 2,000 characters at a time" in page.text
        assert "كتب كتب" not in page.text


def test_overlong_parameters_show_the_invalid_state_before_any_lookup(client, monkeypatch):
    monkeypatch.setattr("aradict.app.dictionary", Unreachable)
    long = "ك" * 101
    for params in ({"root": long}, {"related": long, "pos": "noun"}, {"related": "كِتاب", "pos": long},
                   {"root": "ك.ت.ب", "sort": long}, {"q": long, "root": "ك.ت.ب"}):
        page = client.get("/", params=params)
        assert page.status_code == 200, params
        assert "at most 100 characters" in page.text, params
    assert client.get("/suggest", params={"q": long}).json() == []


def test_only_the_lookups_own_parameters_go_into_its_links(client):
    page = client.get("/", params={"q": "كتب", "diacritics": "off", "other": "x" * 50})
    assert "other" not in page.text
    assert {"q": ["كتب"], "diacritics": ["off"], "root": ["ك.ت.ب"]} in links(heading(entries(page.text)[0])).values()


def test_pasted_markup_is_shown_as_text(client):
    page = client.post("/text", data={"text": "<script>alert(1)</script> كتب"}).text
    assert "<script>alert" not in page
    assert html.unescape(re.sub(r"<[^>]+>", "", passage_of(page))).startswith("<script>alert(1)</script> كتب")


def test_the_word_pages_text_view_link_analyses_all_its_words(client):
    word_page = client.get("/", params={"q": "كتب كتاب"}).text
    page = client.get(html.unescape(re.search(r'href="(/text\?[^"]*)"', word_page).group(1))).text
    assert ">كتب كتاب</textarea>" in page
    assert passage_of(page).count('class="tok word"') == 2


def test_a_text_view_link_carries_no_more_than_a_word_lookup(client, monkeypatch):
    monkeypatch.setattr("aradict.app.dictionary", Unreachable)
    passage = "كتب " * 25 + "كتاب"  # 104 characters: a passage, not a lookup's words
    page = client.get("/text", params={"q": passage}).text
    assert "A link brings at most 100 characters to the Text view" in page
    assert passage not in page and 'class="passage"' not in page


def test_live_analysis_returns_the_passage_and_its_status(client):
    page = client.post("/text", data={"text": "كتب قخغثص كتب"}, headers={"HX-Request": "true"})
    assert "<html" not in page.text and "<textarea" not in page.text
    assert 'id="arabizi"' not in page.text  # the Word page's Arabizi chip has no place to land here
    assert '<p id="status" hx-swap-oob="innerHTML">3 words, 1 not in the dictionary</p>' in page.text
    assert passage_of(page.text).count('class="tok ') == 3
    assert page.headers["Vary"] == "HX-Request"


def test_failed_analysis_keeps_the_text_and_never_logs_it(client, monkeypatch, caplog):
    monkeypatch.setattr("aradict.app.dictionary", Broken)
    page = client.post("/text", data={"text": "كتب سرّي"})
    assert page.status_code == 500
    assert "Analysis failed" in page.text and ">كتب سرّي</textarea>" in page.text
    assert 'type="submit" form="analyse">Retry</button>' in page.text  # resubmits the kept text
    assert "RuntimeError" in caplog.text and "سرّي" not in caplog.text


def test_the_access_log_leaves_out_what_was_looked_up(base_url, caplog):
    # Run as `uvicorn aradict.app:app`, the server logs each request; its query string holds the word.
    access = logging.getLogger("uvicorn.access")
    caplog.set_level(logging.INFO, logger="uvicorn.access")
    access.addHandler(caplog.handler)
    try:
        urlopen(f"{base_url}/?{urlencode({'q': 'سرّي'})}").close()
    finally:
        access.removeHandler(caplog.handler)
    assert '"GET / HTTP/1.1" 200' in caplog.text
    assert "q=" not in caplog.text


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


def links(part: str) -> dict[str, dict[str, list[str]]]:
    """The page links in part of a page, by accessible name, each with its URL parameters."""
    return {
        text(name): parse_qs(urlsplit(html.unescape(href)).query) if "?" in href else href
        for href, name in re.findall(r'<a href="(/(?:\?[^"]*)?)"[^>]*>(.*?)</a>', part)
    }


def text(markup: str) -> str:
    """What a screen reader reads: the text, without tags or what is hidden from it."""
    return unicodedata.normalize("NFC", html.unescape(re.sub(r'<span aria-hidden="true">.*?</span>|<[^>]+>', "", markup))).strip()


def heading(entry: str) -> str:
    """An entry's headword line: its root, headword and badges and how common it is."""
    return re.split('<ul class="readings">|<div class="about-hw">', entry)[0]


def test_entries_link_to_their_root_and_related_forms_keeping_the_lookup(client):
    kitab, katib, kuttab = entries(client.get("/", params={"q": "كتاب", "diacritics": "off"}).text)
    lookup = {"q": ["كتاب"], "diacritics": ["off"]}
    assert links(kitab) == {
        "Root ك ت ب 16 words": lookup | {"root": ["ك.ت.ب"]},
        "all 2 forms of كِتاب": lookup | {"related": ["كِتاب"], "pos": ["noun"]},
    }
    assert "all 4 forms of كاتِب" in links(katib)  # writer and clerk, and two plurals


def test_an_entry_offers_each_of_its_roots(client):
    # إِجارَة is stored under two roots, one per sense: "rent" (أ ج ر) and "protection" (ج و ر).
    ijara, = entries(client.get("/", params={"q": "إجارة"}).text)
    roots = {re.fullmatch(r"Root (.+?)(?: \d+ words?)?", name).group(1): params for name, params in links(heading(ijara)).items() if name.startswith("Root ")}
    assert roots == {
        "◌ ج ر": {"q": ["إجارة"], "root": ["#.ج.ر"]},
        "ج ◌ ر": {"q": ["إجارة"], "root": ["ج.#.ر"]},
    }
    assert "No forms" not in client.get("/", params={"root": "ج.#.ر"}).text  # each opens its own root view


def test_no_root_or_related_forms_means_no_link(client):
    adjective = entries(client.get("/", params={"q": "كاتب"}).text)[-1]
    assert '<p class="pos"><span class="badge">adjective</span></p>' in adjective
    assert list(links(adjective)) == ["Root ك ت ب 16 words"]  # كاتِب "writing" has one form
    assert '<span class="nil">No other forms</span>' in adjective
    laysa = entries(client.get("/", params={"q": "ليس"}).text)[0]
    assert links(laysa) == {}
    assert "related=" not in client.post("/text", data={"text": "كتاب"}).text  # token details leave out the forms


def table(page: str) -> list[list[str]]:
    """The rows of the page's table, each as the text of its cells. Grammar tags read as a comma list."""
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S).group(1)
    return [[text(re.sub(r"</li><li>", ", ", cell)) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)] for row in re.findall(r"<tr>(.*?)</tr>", body, re.S)]


def context(page: str) -> str:
    return re.search(r'<p class="context">(.*?)</p>', page, re.S).group(1)


def test_related_forms_replace_the_results_and_keep_the_query(client):
    page = client.get("/", params={"q": "كتاب", "diacritics": "off", "related": "كِتاب", "pos": "noun"}).text
    assert table(page) == [
        ["كِتاب", "book", "noun", "masculine singular", "ك ت ب", ""],
        ["كُتُب", "books", "noun", "masculine plural, broken plural", "ك ت ب", ""],
    ]
    assert re.search(r'<p id="status" class="status" role="status">(.*?)</p>', page).group(1).endswith("2 forms of the noun <span class=\"ar\" lang=\"ar\" dir=\"rtl\">كِتاب</span>")
    assert 'value="كتاب"' in page and 'class="entry"' not in page  # the query stays; its readings make way
    # The chip says what the list is, and closing it returns to the lookup.
    assert text(context(page)).startswith("Related: كِتاب")
    assert links(context(page)) == {"Back to your lookup": {"q": ["كتاب"], "diacritics": ["off"]}}


def column(page: str, name: str) -> list[str]:
    i = [text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", page)].index(name)
    return [row[i] for row in table(page)]


def headers(page: str) -> dict[str, tuple[str | None, dict]]:
    """Each column header by name: the sort state it announces, and where its link goes."""
    return {
        text(name): (state or None, links(name).get(text(name)))
        for state, name in re.findall(r'<th scope="col"(?: aria-sort="(\w+)")?>(.*?)</th>', page)
    }


def test_a_root_or_lemma_with_no_forms_says_so(client):
    page = client.get("/", params={"root": "ق.خ.غ"}).text  # an address typed by hand, with no lookup to go back to
    assert "No forms from the root" in page and "<table" not in page
    assert links(context(page)) == {"Close": "/"}
    assert "No forms of the verb" in client.get("/", params={"q": "كتب", "related": "كِتاب", "pos": "verb"}).text


ROOT = {"q": ["كتب"], "root": ["ك.ت.ب"]}
VERBS = ["كَتَبَ", "كُتِبَ", "يَكْتُب", "يُكْتَب", "أَكْتَبَ", "يُكْتَب", "يُكْتِب"]  # I, then IV, each in form order


def test_root_view_lists_verbs_by_measure_then_nouns_and_adjectives(client):
    page = client.get("/", params=ROOT).text
    assert column(page, "Form")[:7] == VERBS
    assert column(page, "Measure") == ["I"] * 4 + ["IV"] * 3 + [""] * 9
    assert column(page, "Form")[7:] == ["كاتِب", "كاتِب", "كاتِب", "كُتّاب", "كَتَبَة", "كُتّاب", "كَتاتِيب", "كِتاب", "كُتُب"]
    assert set(column(page, "Root")) == {"ك ت ب"}
    # Part of speech and grammar are boxed as in the Word entries.
    assert '<td data-label="Part of speech"><span class="badge">verb</span></td>' in page
    assert '<td data-label="Grammar"><ul class="grammar"><li>active</li><li>3rd person masculine singular</li><li>perfect (past)</li></ul></td>' in page
    assert "16 forms from the root" in page and text(context(page)).startswith("Root: ك ت ب")
    assert links(context(page)) == {"Back to your lookup": {"q": ["كتب"]}}
    # In family order no column is sorted, and each header sorts by its column.
    assert headers(page) == {
        "Form": (None, ROOT | {"sort": ["form"]}), "Meaning": (None, ROOT | {"sort": ["gloss"]}),
        "Part of speech": (None, ROOT | {"sort": ["pos"]}), "Grammar": (None, None),
        "Root": (None, ROOT | {"sort": ["root"]}), "Measure": (None, ROOT | {"sort": ["measure"]}),
    }


def test_each_column_sorts_both_ways_keeping_family_order_among_equals(client):
    ascending = client.get("/", params=ROOT | {"sort": ["measure"]}).text
    descending = client.get("/", params=ROOT | {"sort": ["-measure"]}).text
    # Rows with the same measure keep their family order, and rows without one stay last.
    assert column(ascending, "Form")[:7] == VERBS
    assert column(descending, "Form")[:7] == VERBS[4:] + VERBS[:4]
    assert column(descending, "Form")[7:] == column(ascending, "Form")[7:]
    # The sorted column says so; its link reverses the order, and then returns to family order.
    assert headers(ascending)["Measure"] == ("ascending", ROOT | {"sort": ["-measure"]})
    assert headers(descending)["Measure"] == ("descending", ROOT)
    assert headers(descending)["Form"] == (None, ROOT | {"sort": ["form"]})

    by_pos = client.get("/", params=ROOT | {"sort": ["pos"]}).text
    assert column(by_pos, "Part of speech") == ["adjective"] + ["noun"] * 8 + ["verb"] * 7
    assert column(by_pos, "Form")[9:] == VERBS
    by_meaning = column(client.get("/", params=ROOT | {"sort": ["-gloss"]}).text, "Meaning")
    assert by_meaning == sorted(by_meaning, key=str.casefold, reverse=True) and by_meaning[0] == "writing"
    by_form = column(client.get("/", params=ROOT | {"sort": ["form"]}).text, "Form")
    assert by_form[:4] == ["أَكْتَبَ", "كاتِب", "كاتِب", "كاتِب"] and by_form[-4:] == ["يَكْتُب", "يُكْتَب", "يُكْتَب", "يُكْتِب"]  # by letters, hamza as ا
    assert column(client.get("/", params=ROOT | {"sort": ["nonsense"]}).text, "Form")[:7] == VERBS


# --- English → Arabic -------------------------------------------------------------------------

def field(page: str) -> str:
    return re.search(r'<input id="q"[^>]*>', page).group(0)


def english_switch(page: str) -> str:
    return re.search(r'<label[^>]*>\s*(<input type="checkbox" name="lang" value="en"[^>]*>)\s*English → Arabic\s*</label>', page).group(1)


COVERAGE = 'class="notice coverage"'


def test_english_lookup_shows_arabic_entries_like_arabic_lookup(client):
    page = client.get("/", params={"q": "book", "lang": "en"}).text
    assert page.count('class="entry"') == 2  # كِتاب and سِفْر, one entry per lemma as in Arabic lookup
    assert '<span class="ar" lang="ar" dir="rtl">كِتاب</span>' in page and '<span class="ar" lang="ar" dir="rtl">سِفْر</span>' in page
    assert '<dd class="gloss">book</dd>' in page
    assert "2 Arabic words for “book”" in page
    same = client.get("/", params={"q": "Book ", "lang": "en"}).text
    # The same entries; only their root and related-forms links keep the query as it was typed.
    assert entries(same) == [re.sub("q=book", "q=Book+", e) for e in entries(page)]


def test_english_entries_link_to_their_family_which_returns_to_the_english_lookup(client):
    kitab = next(e for e in entries(client.get("/", params={"q": "book", "lang": "en"}).text) if "كِتاب</span></h2>" in e)
    english = {"q": ["book"], "lang": ["en"]}
    assert links(kitab)["all 2 forms of كِتاب"] == english | {"related": ["كِتاب"], "pos": ["noun"]}
    page = client.get("/", params=english | {"root": "ك.ت.ب"}).text
    assert links(context(page)) == {"Back to your lookup": english}
    assert 'lang="en"' in field(page)  # the field stays in English


def test_english_direction_lives_in_the_url_and_sets_the_field(client):
    page = client.get("/", params={"lang": "en"}).text
    assert 'lang="en"' in field(page) and 'dir="ltr"' in field(page)
    assert '<label for="q" class="lbl">English word</label>' in page
    assert "checked" in english_switch(page) and "data-remember" in english_switch(page)
    assert 'href="/?lang=en"' in re.search(r'<a [^>]*class="clear"[^>]*>', page).group(0)  # Clear keeps the direction

    home = client.get("/").text
    assert 'lang="ar"' in field(home) and "checked" not in english_switch(home)
    assert '<label for="q" class="lbl">Arabic word</label>' in home


def test_arabic_field_follows_the_direction_of_what_is_typed(client):
    # Arabizi is typed in Latin letters, which read left to right; Arabic script reads right to left.
    assert 'dir="auto"' in field(client.get("/").text)


def test_english_mode_shows_its_coverage_limits(client):
    for params in ({"lang": "en"}, {"q": "book", "lang": "en"}, {"q": "xyzzy", "lang": "en"}):
        assert COVERAGE in client.get("/", params=params).text, params
        assert COVERAGE in client.get("/", params=params, headers={"HX-Request": "true"}).text, params
    assert COVERAGE not in client.get("/").text
    assert COVERAGE not in client.get("/", params={"q": "كتب"}).text


def test_english_with_no_match_suggests_next_steps_and_switching_direction(client):
    page = client.get("/", params={"q": "xyzzy", "lang": "en"}).text
    assert "No Arabic word for “xyzzy”" in page
    assert "Check the spelling" in page
    assert re.search(r'<a href="/">[^<]*Arabic → English</a>', page)
    # Arabic typed in English mode is looked up as Arabic by the switch.
    page = client.get("/", params={"q": "كتب", "lang": "en"}).text
    assert 'href="/?q=%D9%83%D8%AA%D8%A8"' in page
    assert 'No Arabic word for “<span class="ar" lang="ar" dir="rtl">كتب</span>”' in page  # in its own language and direction


def test_english_live_lookup_returns_only_results(client):
    page = client.get("/", params={"q": "books", "lang": "en"}, headers={"HX-Request": "true"}).text
    assert "<form" not in page
    assert page.count('class="entry"') == 2  # the "book" entries


def test_an_entry_says_which_word_then_what_the_typed_word_means_then_more_about_the_word(client):
    # The order of the #21 design (W5): the root, headword and how common it is; the readings; then
    # everything about the headword, its other forms here.
    kitab = entries(client.get("/", params={"q": "كتاب"}).text)[0]
    order = ['class="root-tab"', "<h2>", "<dt>Frequency</dt>", '<ul class="readings">', '<div class="about-hw">', "<dt>Forms</dt>"]
    assert [kitab.index(part) for part in order] == sorted(kitab.index(part) for part in order)
    assert "<dt>Forms</dt>" not in heading(kitab)


def about(entry: str) -> str:
    """Everything an entry says about its headword, after the readings."""
    return entry.split('<div class="about-hw">')[1]


def senses_of(part: str) -> list[str]:
    """The numbered Wiktionary senses listed first in part of a page, in order, as a screen reader reads them."""
    listed = re.search(r'<ol class="senses">(.*?)</ol></dd>', part).group(1)
    return [text(sense) for sense in re.findall(r"<li>(.*?)</li>", re.sub('<ol class="senses" type="a">.*?</ol>', "", listed))]


def credit(part: str) -> tuple[str, dict[str, str]]:
    """The Wiktionary credit in part of a page, as a screen reader reads it, and its links by accessible name."""
    markup = re.search(r'<p class="credit">(.*?)</p>', part).group(1)
    return text(markup), {text(name): html.unescape(href) for href, name in re.findall(r'<a href="([^"]*)"[^>]*>(.*?)</a>', markup)}


LICENCE = "https://creativecommons.org/licenses/by-sa/4.0/"


def test_a_word_lists_all_its_wiktionary_senses_numbered_after_its_readings_with_the_credit(wiktionary_client):
    kitab, katib, kuttab = entries(wiktionary_client.get("/", params={"q": "كتاب", "diacritics": "off"}).text)
    assert '<span class="ar" lang="ar" dir="rtl">كِتاب</span>' in heading(kitab)
    assert senses_of(about(kitab)) == [
        "book", "letter, note, paper, piece of writing, message", "the Scripture, the Qur'an or the Bible",
        "record, document, deed, contract", "a marriage contract.",
    ]  # not "verbal noun of كَتَبَ", a relation, not a meaning
    order = ['<ul class="readings">', "<dt>Meanings</dt>", "<dt>Forms</dt>", '<p class="credit">']
    assert [kitab.index(part) for part in order] == sorted(kitab.index(part) for part in order)
    assert credit(kitab) == ("From Wiktionary, CC BY-SA 4.0, opens in a new tab · Entry: كتاب on Wiktionary, opens in a new tab", {
        "CC BY-SA 4.0, opens in a new tab": LICENCE,
        "كتاب on Wiktionary, opens in a new tab": "https://en.wiktionary.org/wiki/كتاب#Arabic",
    })
    # كُتّاب "Quran school" lists its own sense, not كِتاب's, nor "plural of كاتِب".
    assert senses_of(about(kuttab)) == ["a traditional school for teaching Qur'an"]
    assert credit(katib)[1]["كاتب on Wiktionary, opens in a new tab"] == "https://en.wiktionary.org/wiki/كاتب#Arabic"  # كُتّاب "writers" is a form of كاتِب


def test_sub_senses_are_lettered_under_their_sense(wiktionary_client):
    katab = next(e for e in entries(wiktionary_client.get("/", params={"q": "كتب"}).text) if "كَتَب</span></h2>" in e)
    assert senses_of(katab)[1] == "to produce or generate by writing"
    assert ('<li>to mark (symbols, shapes, graphs, glyphs, letters, and the like) on a surface, to write, to inscribe'
            '<ol class="senses" type="a"><li>to draw (figures)</li><li>to cut (figures)</li></ol></li>') in katab


def test_a_sense_shows_the_labels_wiktionary_gives_it(wiktionary_client):
    # Obsolete is in the sense's tags only, which the #20 build dropped (PRD, Wiktionary layer, Register).
    jidda = next(e for e in entries(wiktionary_client.get("/", params={"q": "جدة"}).text) if "newness" in e)
    assert senses_of(about(jidda))[:2] == ["Obsolete: newness, recency", "Obsolete: novelty"]
    assert '<li><span class="qualifier">Obsolete</span><span class="sr-only">: </span>newness, recency</li>' in jidda


def test_token_details_show_the_senses_and_credit_but_not_frequency_or_forms(wiktionary_client):
    page = wiktionary_client.post("/text", data={"text": "كتب"}).text
    details = page[page.index('<div id="w0"'):]
    katab = next(e for e in entries(details) if "كَتَب</span></h3>" in e)
    assert senses_of(about(katab))[0].startswith("to mark (symbols")
    assert credit(katab)[1]["كتب on Wiktionary, opens in a new tab"] == "https://en.wiktionary.org/wiki/كتب#Arabic"
    assert "Frequency" not in details and "<dt>Forms</dt>" not in details


def test_homographs_stay_apart_and_are_labelled(wiktionary_client):
    # CAMeL's قال "say; said" joins Wiktionary's قَالَ "to say"; قَالَ "to nap" follows as its own entry.
    say, nap = entries(wiktionary_client.get("/", params={"q": "قال"}).text)
    assert '<span class="badge measure">Homograph 1</span>' in heading(say) and senses_of(about(say))[0] == "to say"
    assert 'class="reading"' in say
    assert senses_of(about(nap)) == ["To nap.", "To do something at noon.", "To cancel a contract or a promise."]
    assert '<h2><span class="ar" lang="ar" dir="rtl">قَالَ</span></h2>' in nap
    assert text(heading(nap)).endswith("verb Homograph 2 Wiktionary only")
    assert 'class="reading"' not in nap and "Frequency" not in nap
    # Its root is Wiktionary's, ق ي ل, where the dictionary's قال leaves a letter open. The fixture
    # dictionary has no word from it, so it opens no root view.
    assert '<span class="root-tab"><span class="rt-k">Root</span> <span class="ar" lang="ar" dir="rtl">ق ي ل</span></span>' in heading(nap)
    assert credit(nap)[1]["قال on Wiktionary, opens in a new tab"] == "https://en.wiktionary.org/wiki/قال#Arabic"
    # Numbered as they are shown: Wiktionary lists جِدَّة "bank" before جِدَّة "newness", which the dictionary has.
    jidda = entries(wiktionary_client.get("/", params={"q": "جدة"}).text)
    newness, bank = (next(e for e in jidda if word in e) for word in ("newness", "bank, side"))
    assert "Homograph 1" in heading(newness) and "Homograph 2 Wiktionary only" in text(heading(bank))
    assert jidda.index(newness) < jidda.index(bank)
    # Looking up an English word shows only the dictionary's entries.
    assert "Wiktionary only" not in wiktionary_client.get("/", params={"q": "say", "lang": "en"}).text


def test_homographs_a_gloss_cannot_tell_apart_stay_under_the_lemma_each_labelled(wiktionary_client):
    # CAMeL's جَزْر "slaughter; ebb" has a meaning of each of Wiktionary's homographs.
    [jazr] = [e for e in entries(wiktionary_client.get("/", params={"q": "جزر"}).text) if "جَزْر</span></h2>" in e]
    meanings = re.findall(r'<dt>Meanings</dt><dd class="wide">(.*?)</dd>', jazr)
    assert len(meanings) == 2
    assert text(meanings[0]).startswith("Homograph 1 slaughter") and text(meanings[1]).startswith("Homograph 2 ebb (of the sea)")
    assert "Homograph" not in heading(jazr)


def test_without_the_wiktionary_dataset_entries_show_no_wiktionary_content(client):
    page = client.get("/", params={"q": "قال"})
    assert page.status_code == 200 and page.text.count('class="entry"') == 1
    assert "Wiktionary" not in page.text and "Meanings" not in page.text and "Homograph" not in page.text


# --- Roots filled from Wiktionary (#26) -----------------------------------------------------------

FILLED = '<span class="fill">و<span class="sr-only" lang="en"> (filled from Wiktionary)</span></span>'


def test_an_open_root_letter_wiktionary_fills_is_marked_and_opens_the_full_roots_family(wiktionary_client):
    # CAMeL leaves قال's root open (ق ◌ ل); of Wiktionary's two قَالَ, its gloss "said" picks "to say", of ق و ل.
    qal = entries(wiktionary_client.get("/", params={"q": "قال"}).text)[0]
    assert links(qal) == {
        "Root ق و (filled from Wiktionary) ل 7 words": {"q": ["قال"], "root": ["ق.و.ل"]},
        "all 5 forms of قال": {"q": ["قال"], "related": ["قال"], "pos": ["verb"]},
    }
    assert f'<span class="ar" lang="ar" dir="rtl">ق {FILLED} ل</span>' in heading(qal)
    assert credit(qal)[1]["قال on Wiktionary, opens in a new tab"] == "https://en.wiktionary.org/wiki/قال#Arabic"


def test_more_about_a_word_says_which_root_letter_wiktionary_filled(wiktionary_client):
    # The Root row of the #21 design (W5), after the other forms and before the credit.
    qal = entries(wiktionary_client.get("/", params={"q": "قال"}).text)[0]
    row = re.search(r"<dt>Root</dt><dd>(.*?)</dd>", about(qal)).group(1)
    assert text(row) == "و filled from Wiktionary; the core dictionary has ق ◌ ل"
    order = ["<dt>Meanings</dt>", "<dt>Forms</dt>", "<dt>Root</dt>", '<p class="credit">']
    assert [qal.index(part) for part in order] == sorted(qal.index(part) for part in order)
    # Token details show the filled root too, without the other forms.
    page = wiktionary_client.post("/text", data={"text": "قال"}).text
    details = entries(page[page.index('<div id="w0"'):])[0]
    assert f'<span class="ar" lang="ar" dir="rtl">ق {FILLED} ل</span>' in heading(details)
    assert re.search(r"<dt>Root</dt><dd>(.*?)</dd>", about(details)) and "<dt>Forms</dt>" not in details
    # A root with nothing open, or one Wiktionary can't fill, has no such row.
    assert "<dt>Root</dt>" not in wiktionary_client.get("/", params={"q": "كتاب"}).text


def test_a_filled_roots_view_lists_its_words_then_the_open_roots_others_with_the_credit(wiktionary_client):
    lookup = {"q": ["قال"], "root": ["ق.و.ل"]}
    page = wiktionary_client.get("/", params=lookup).text
    filled, apart = page.split('<h2 class="rv-sub">')
    assert text(context(page)).startswith("Root: ق و (filled from Wiktionary) ل")
    assert "و filled from Wiktionary; the core dictionary has ق ◌ ل" in text(page)
    assert "5 forms from the root ق و (filled from Wiktionary) ل, 2 more not confirmed" in text(page)
    # قال's forms are from ق و ل; مَقال is of ق و ل or ق ي ل on Wiktionary, and CAMeL's gloss picks neither.
    assert column(filled, "Form") == ["قالَ", "قُلْ", "قِيلَ", "يُقال", "يَقُول"]
    assert set(column(filled, "Root")) == {"ق و (filled from Wiktionary) ل"}
    assert text(apart).startswith("Also under ق ◌ ل in the core dictionary, letter not confirmed")
    assert column(apart, "Form") == ["مَقال", "مَقالات"] and set(column(apart, "Root")) == {"ق ◌ ل"}
    assert '<a href="https://en.wiktionary.org/wiki/قال#Arabic">' in apart  # the credit, linked to the entry
    assert "From Wiktionary, CC BY-SA 4.0" in text(apart)
    # Sorting sorts both lists and keeps the root.
    by_form = wiktionary_client.get("/", params=lookup | {"sort": "-form"}).text
    assert column(by_form, "Form")[0] == "يَقُول" and headers(by_form)["Form"] == ("descending", lookup)
    assert column(by_form.split('<h2 class="rv-sub">')[1], "Form") == ["مَقالات", "مَقال"]
