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


def test_unknown_word_says_so(client):
    page = client.get("/", params={"q": "قخغثص"})
    assert page.status_code == 200
    assert "No entry for" in page.text
    assert 'class="reading"' not in page.text


def test_home_has_a_plain_get_form(client):
    page = client.get("/")
    assert '<form class="search" method="get" action="/"' in page.text
    assert "No entry" not in page.text


def test_other_pages_and_assets(client):
    assert 'aria-current="page" href="/text"' in client.get("/text").text
    assert "GNU GPL" in client.get("/about").text
    assert client.get("/static/vendor/htmx.min.js").status_code == 200


def test_overlong_query_is_rejected(client):
    assert client.get("/", params={"q": "ك" * 101}).status_code == 422


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
    assert re.search(r'<label[^>]*>\s*<input type="checkbox" name="diacritics" value="off"\s*>\s*Ignore diacritics', page)


def test_latin_letters_get_a_hint_towards_english(client):
    page = client.get("/", params={"q": "hello"}).text
    assert 'class="reading"' not in page
    assert "English" in page
    assert "English" not in client.get("/", params={"q": "قخغثص"}).text


def test_one_word_has_no_multi_word_notice(client):
    assert "Only the first word" not in client.get("/", params={"q": "كتب"}).text
