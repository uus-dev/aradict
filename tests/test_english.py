"""English → Arabic lookup and the direction switch: browser journeys."""

from urllib.parse import quote

from playwright.sync_api import Error as PlaywrightError, expect


def switch(page):
    return page.get_by_role("checkbox", name="English → Arabic")


def test_switching_direction_clears_the_word_and_its_results(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتب')}")
    status = page.get_by_role("status")
    expect(page.locator(".reading")).to_have_count(3)

    switch(page).check()
    box = page.get_by_label("English word")
    expect(box).to_have_value("")
    expect(box).to_be_focused()
    expect(page.locator(".reading")).to_have_count(0)
    expect(page).to_have_url(f"{base_url}/?lang=en")
    expect(page.locator(".coverage")).to_be_visible()
    assert box.evaluate("e => [e.lang, getComputedStyle(e).direction]") == ["en", "ltr"]
    expect(page.get_by_role("button", name="Arabic keyboard")).to_be_hidden()  # nothing Arabic to type
    expect(page.get_by_role("checkbox", name="Ignore diacritics")).to_be_hidden()

    box.press_sequentially("book")
    expect(status).to_have_text("2 Arabic words for “book”")
    expect(page.locator(".entry")).to_have_count(2)
    expect(page).to_have_url(f"{base_url}/?q=book&lang=en")

    switch(page).uncheck()
    box = page.get_by_label("Arabic word")
    expect(box).to_have_value("")
    expect(page.locator(".entry")).to_have_count(0)
    expect(status).to_have_text("")
    expect(page).to_have_url(f"{base_url}/")
    expect(page.get_by_role("button", name="Arabic keyboard")).to_be_visible()
    expect(page.locator(".coverage")).to_have_count(0)

    page.go_back()  # each direction's URL shows that direction
    expect(page.get_by_label("English word")).to_have_value("book")
    expect(page.locator(".entry")).to_have_count(2)


def test_a_lookup_from_the_other_direction_never_shows_after_switching(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    status = page.get_by_role("status")
    held = []
    page.route(lambda url: url.startswith(f"{base_url}/?q={quote('كتب')}"), lambda route: held.append(route))

    page.get_by_label("Arabic word").press_sequentially("كتب")
    expect(status).to_have_text("Looking up…")
    page.get_by_label("Arabic word").press("Escape")  # the suggestions cover the switch
    switch(page).check()
    expect(page).to_have_url(f"{base_url}/?lang=en")

    try:
        held[0].continue_()  # the Arabic response arrives after the switch
    except PlaywrightError:
        pass  # the browser already gave up on that request
    page.wait_for_timeout(500)
    expect(page.locator(".reading")).to_have_count(0)
    expect(status).not_to_contain_text("كتب")
    expect(page.locator(".coverage")).to_be_visible()


def test_the_direction_is_remembered_on_this_device(base_url, browser):
    device = browser.new_context()
    page = device.new_page()
    page.goto(base_url)
    switch(page).check()
    expect(page).to_have_url(f"{base_url}/?lang=en")

    page = device.new_page()  # come back later
    page.goto(base_url)
    expect(page).to_have_url(f"{base_url}/?lang=en")
    expect(switch(page)).to_be_checked()
    page.get_by_label("English word").fill("books")
    expect(page.locator(".entry")).to_have_count(2)

    page.goto(f"{base_url}/?q={quote('كتب')}")  # a link names its own direction
    expect(page.get_by_label("Arabic word")).to_have_value("كتب")
    expect(page.locator(".reading")).to_have_count(3)
    device.close()


def test_history_tells_an_english_lookup_from_the_same_letters_in_arabizi(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q=book&lang=en")
    page.goto(f"{base_url}/?q=book")  # Arabizi
    page.get_by_text("Recent lookups").click()
    entries = page.locator("#history").get_by_role("link")
    expect(entries).to_have_text(["book", "book · English"])
    entries.nth(1).click()
    expect(page).to_have_url(f"{base_url}/?q=book&lang=en")
    expect(page.locator(".entry")).to_have_count(2)


def test_english_mode_offers_no_arabic_suggestions(base_url, browser):
    page = browser.new_page()
    suggested = []
    page.on("request", lambda request: "/suggest" in request.url and suggested.append(request.url))
    page.goto(f"{base_url}/?lang=en")
    expect(page.get_by_role("checkbox", name="Show suggestions")).to_be_hidden()

    page.get_by_label("English word").press_sequentially("book")
    expect(page.get_by_role("status")).to_have_text("2 Arabic words for “book”")
    page.get_by_label("English word").press("ArrowDown")  # would open the list in Arabic
    expect(page.get_by_role("listbox", name="Suggestions")).to_be_hidden()
    assert suggested == []

    switch(page).uncheck()  # back in Arabic, suggestions work again
    page.get_by_label("Arabic word").press_sequentially("كتا")
    expect(page.get_by_role("listbox", name="Suggestions")).to_be_visible()


def test_the_arabic_field_reads_in_the_direction_of_what_is_typed(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_label("Arabic word")
    box.press_sequentially("ktb")  # Arabizi reads left to right
    expect(page.get_by_role("status")).to_have_text("3 readings for كتب")
    assert box.evaluate("e => e.matches(':dir(ltr)')")
    box.fill("كتب")
    assert box.evaluate("e => e.matches(':dir(rtl)')")


def test_english_lookup_without_javascript(base_url, browser):
    page = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844}).new_page()
    page.goto(base_url)
    switch(page).check()
    page.get_by_label("Arabic word").fill("book")
    page.get_by_role("button", name="Look up").click()

    page.wait_for_url(f"{base_url}/?q=book&lang=en")
    expect(page.locator(".entry")).to_have_count(2)
    expect(page.locator(".coverage")).to_be_visible()
    expect(page.get_by_role("checkbox", name="Ignore diacritics")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.context.close()
