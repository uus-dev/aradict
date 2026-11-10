"""Pages, served by the app over the fixture database."""


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
