"""Pages, served by the app over the fixture database."""


def test_word_page_lists_readings_grouped_by_lemma(client):
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 200
    assert page.text.count('class="reading"') == 3
    assert page.text.count('class="entry"') == 2  # كِتاب, and كَتَب with two readings
    assert '<html lang="en" dir="ltr">' in page.text
    assert '<span class="ar" lang="ar" dir="rtl">كَتَب</span>' in page.text


def test_unknown_word_says_so_and_suggests_next_steps(client):
    page = client.get("/", params={"q": "قخغثص"})
    assert page.status_code == 200
    assert "No entry for" in page.text
    assert "Check the spelling" in page.text
    assert "without vowel marks" in page.text
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


def test_other_pages_and_assets(client):
    assert 'aria-current="page" href="/text"' in client.get("/text").text
    assert "GNU GPL" in client.get("/about").text
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
