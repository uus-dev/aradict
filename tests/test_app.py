"""Pages, served by the app over the fixture database."""


def test_word_page_lists_readings_grouped_by_lemma(client):
    page = client.get("/", params={"q": "كتب"})
    assert page.status_code == 200
    assert page.text.count('class="reading"') == 3
    assert page.text.count('class="entry"') == 2  # كِتاب, and كَتَب with two readings
    assert '<html lang="en" dir="ltr">' in page.text
    assert '<span class="ar" lang="ar" dir="rtl">كَتَب</span>' in page.text


def test_reading_shows_marked_parts_gloss_grammar_and_word_parts(client):
    page = client.get("/", params={"q": "وبكتابهم"}).text
    reading = page[page.index('<li class="reading">'):page.index("</details>")]
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
