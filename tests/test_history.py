"""History and remembered preferences: browser journeys. Both live only in the browser's storage."""

from urllib.parse import parse_qs, quote, unquote, urlsplit

from playwright.sync_api import expect

from test_browser import base_url, browser  # noqa: F401  (shared server and browser fixtures)


def open_history(page):
    page.keyboard.press("Escape")  # while typing, the suggestion list (#8) lies over the panel
    page.get_by_text("Recent lookups").click()
    return page.locator("#history").get_by_role("link")


def test_a_lookup_appears_in_history_and_reopens_the_same_view(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كَتَبَ')}&diacritics=off")  # opened from a link: 3 readings, filter off
    box = page.get_by_label("Arabic word")
    box.fill("كاتب")  # a live lookup
    expect(page.get_by_role("status")).to_contain_text("كاتب")

    entries = open_history(page)
    expect(entries).to_have_text(["كاتب", "كَتَبَ · diacritics ignored"])  # newest first

    entries.nth(1).click()
    expect(page).to_have_url(f"{base_url}/?q={quote('كَتَبَ')}&diacritics=off")
    expect(box).to_have_value("كَتَبَ")
    expect(page.get_by_role("checkbox", name="Ignore diacritics")).to_be_checked()
    expect(page.locator(".reading")).to_have_count(3)


def test_a_word_looked_up_again_is_listed_once(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتب')}")
    page.goto(f"{base_url}/?q={quote('كاتب')}")
    page.get_by_role("checkbox", name="Ignore diacritics").check()  # كاتب again: without vowel marks, the switch changes nothing
    expect(page).to_have_url(f"{base_url}/?q={quote('كاتب')}&diacritics=off")
    page.goto(f"{base_url}/?q={quote('كتب')}")
    expect(open_history(page)).to_have_text(["كتب", "كاتب"])


def type_slowly(page, word):
    """Type one letter at a time, letting each live lookup finish, as a learner typing slowly does."""
    box = page.get_by_label("Arabic word")
    for letter in word:
        box.press_sequentially(letter)
        expect(page.get_by_role("status")).to_contain_text(box.input_value())


def test_typing_a_word_keeps_only_the_word_not_each_letter_on_the_way(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    type_slowly(page, "كتب")  # looks up ك, then كت, then كتب
    entries = open_history(page)
    expect(entries).to_have_text(["كتب"])

    page.get_by_label("Arabic word").select_text()
    type_slowly(page, "كاتب")  # typed over كتب: ك no longer extends it, so كتب stays
    expect(entries).to_have_text(["كاتب", "كتب"])

    page.get_by_label("Arabic word").press("Enter")  # an explicit lookup ends the word
    type_slowly(page, "ة")
    expect(entries).to_have_text(["كاتبة", "كاتب", "كتب"])


def test_history_keeps_as_many_lookups_as_set_and_can_be_cleared(base_url, browser):
    page = browser.new_page()
    for word in ("كتب", "كاتب", "كتاب"):
        page.goto(f"{base_url}/?q={quote(word)}")
    entries = open_history(page)
    expect(entries).to_have_text(["كتاب", "كاتب", "كتب"])

    size = page.locator("#history").get_by_role("spinbutton")
    expect(size).to_have_value("50")  # the default
    size.fill("2")
    size.press("Tab")
    expect(entries).to_have_text(["كتاب", "كاتب"])  # the oldest is dropped
    page.get_by_label("Arabic word").fill("كاتبة")
    expect(entries).to_have_text(["كاتبة", "كتاب"])

    page.get_by_role("button", name="Clear history").click()
    expect(entries).to_have_count(0)
    expect(page.locator("#history")).to_contain_text("Words you look up appear here.")
    page.goto(base_url)
    expect(open_history(page)).to_have_count(0)


def test_preferences_are_remembered_on_the_device(base_url, browser):
    device = browser.new_context()
    page = device.new_page()
    page.goto(base_url)
    page.get_by_role("checkbox", name="Ignore diacritics").check()
    open_history(page)
    page.locator("#history").get_by_role("spinbutton").fill("7")
    page.locator("#history").get_by_role("spinbutton").press("Tab")

    page = device.new_page()  # come back later
    page.goto(base_url)
    switch = page.get_by_role("checkbox", name="Ignore diacritics")
    expect(switch).to_be_checked()
    open_history(page)
    expect(page.locator("#history").get_by_role("spinbutton")).to_have_value("7")
    page.get_by_label("Arabic word").fill("كَتَبَ")  # the next lookup uses it
    expect(page.locator(".reading")).to_have_count(3)
    expect(page).to_have_url(f"{base_url}/?q={quote('كَتَبَ')}&diacritics=off")

    page.goto(f"{base_url}/?q={quote('كَتَبَ')}")  # a link names its own view, so its URL decides
    expect(switch).not_to_be_checked()
    expect(page.locator(".reading")).to_have_count(1)


BLOCK_STORAGE = """Object.defineProperty(window, "localStorage", {
  get() { throw new DOMException("The operation is insecure.", "SecurityError") },
})"""  # what Chromium does when the user blocks site data


def test_lookup_works_without_a_visible_error_when_storage_is_blocked(base_url, browser):
    device = browser.new_context()
    device.add_init_script(BLOCK_STORAGE)
    page = device.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    page.goto(f"{base_url}/?q={quote('كاتب')}")

    page.get_by_role("checkbox", name="Ignore diacritics").check()
    page.get_by_label("Arabic word").fill("كتب")
    expect(page.get_by_role("status")).to_have_text("3 readings for كتب")
    expect(page.locator(".reading")).to_have_count(3)
    expect(open_history(page)).to_have_text(["كتب", "كاتب"])  # kept for as long as the page is open
    page.get_by_role("button", name="Clear history").click()
    assert errors == []


def test_no_request_carries_history_or_preferences(base_url, browser):
    device = browser.new_context()
    page = device.new_page()
    page.goto(f"{base_url}/?q={quote('كاتب')}")  # history now holds كاتب
    page.get_by_role("checkbox", name="Ignore diacritics").check()
    open_history(page)
    page.locator("#history").get_by_role("spinbutton").fill("37")
    page.locator("#history").get_by_role("spinbutton").press("Tab")

    requests = []
    page.on("request", lambda request: requests.append(request))
    page.goto(base_url)  # loads the stored history and preferences into the page
    page.get_by_label("Arabic word").fill("كتب")
    expect(open_history(page)).to_have_text(["كتب", "كاتب"])
    page.reload()
    expect(open_history(page)).to_have_text(["كتب", "كاتب"])

    assert len(requests) > 4
    for request in requests:
        headers = request.all_headers()
        sent = unquote(f"{request.url} {headers} {request.post_data or ''}")
        assert "كاتب" not in sent, request.url  # a stored lookup is never sent again
        assert request.method == "GET" and "cookie" not in headers, request.url
        assert set(parse_qs(urlsplit(request.url).query)) <= {"q", "diacritics"}, request.url  # only the lookup itself
    assert device.cookies() == []


def test_root_and_related_views_are_listed_apart_from_their_lookup(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتاب')}")
    page.get_by_role("link", name="all 2 forms of كِتاب").click()
    expect(open_history(page)).to_have_text(["كتاب · forms of كِتاب", "كتاب"])
    page.go_back()
    page.get_by_role("link", name="Words from the root ك ت ب").first.click()
    meaning = page.get_by_role("columnheader", name="Meaning")
    meaning.get_by_role("link").click()  # sorting is the same view
    expect(meaning).to_have_attribute("aria-sort", "ascending")
    entries = open_history(page)
    expect(entries).to_have_text(["كتاب · root ك ت ب", "كتاب", "كتاب · forms of كِتاب"])
    expect(entries.first.locator("[lang=ar]")).to_have_count(2)  # the query and the root read as Arabic

    entries.nth(2).click()  # reopens that view
    expect(page.get_by_role("status")).to_have_text("2 forms of the noun كِتاب")
    open_history(page).filter(has_text="root").click()  # the root view, as it was sorted
    expect(meaning).to_have_attribute("aria-sort", "ascending")
