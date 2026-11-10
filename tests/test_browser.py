"""Browser journeys in Chromium against a real server on the fixture database."""

import re
import threading
import time
from urllib.parse import quote

import pytest
import uvicorn
from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

from aradict.app import app


@pytest.fixture(scope="module")
def base_url(fixture_env):
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield "http://127.0.0.1:%d" % server.servers[0].sockets[0].getsockname()[1]
    server.should_exit = True
    thread.join(5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def lookup_url(base_url: str, query: str) -> re.Pattern:
    return re.compile(re.escape(f"{base_url}/?q={quote(query)}") + "$")


def test_lookup_without_javascript_on_a_phone(base_url, browser):
    page = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844}).new_page()

    page.goto(base_url)
    page.get_by_role("textbox", name="Arabic word").fill("كتب")
    page.get_by_role("button", name="Look up").click()

    page.wait_for_url("**/?q=*")
    expect(page.locator(".reading")).to_have_count(3)
    assert page.locator(".reading .ar").first.evaluate("e => getComputedStyle(e).direction") == "rtl"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    page.goto(page.url)  # the result URL is shareable: loading it again shows the same readings
    expect(page.locator(".reading")).to_have_count(3)

    page.get_by_role("link", name="Clear").click()
    expect(page).to_have_url(f"{base_url}/")
    expect(page.get_by_role("textbox", name="Arabic word")).to_have_value("")


def test_the_query_stays_in_view_while_reading_results(base_url, browser):
    page = browser.new_page(viewport={"width": 390, "height": 360})  # a phone with its keyboard open
    page.goto(f"{base_url}/?q={quote('كتب')}")
    page.locator(".reading").last.scroll_into_view_if_needed()
    assert page.evaluate("scrollY") > 150
    expect(page.get_by_label("Arabic word")).to_be_in_viewport(ratio=1)


def test_clear_and_deleting_the_query_return_to_the_empty_start(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتب')}")
    box = page.get_by_label("Arabic word")
    clear = page.get_by_role("link", name="Clear")
    expect(page.locator(".reading")).to_have_count(3)

    clear.click()
    expect(box).to_have_value("")
    expect(box).to_be_focused()
    expect(page.locator(".reading")).to_have_count(0)
    expect(page.get_by_role("status")).to_have_text("")
    expect(page).to_have_url(f"{base_url}/")
    expect(clear).to_be_hidden()

    box.press_sequentially("كتب")
    expect(page.locator(".reading")).to_have_count(3)
    expect(clear).to_be_visible()
    box.fill("")
    expect(page.locator(".reading")).to_have_count(0)
    expect(page).to_have_url(f"{base_url}/")


def test_live_lookup_while_typing_and_on_enter_with_history(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_label("Arabic word")
    status = page.get_by_role("status")

    box.press_sequentially("كتب")  # no button pressed
    expect(page.locator(".reading")).to_have_count(3)
    expect(status).to_have_text("3 readings for كتب")
    expect(page).to_have_url(lookup_url(base_url, "كتب"))

    page.evaluate("window.samePage = true")
    box.evaluate("(e, v) => e.value = v", "كاتب")  # no input event, so only Enter can look it up
    box.press("Enter")
    expect(status).to_contain_text("كاتب")
    expect(page).to_have_url(lookup_url(base_url, "كاتب"))
    assert page.evaluate("window.samePage")  # updated in place, not by loading a new page

    page.go_back()
    expect(page).to_have_url(lookup_url(base_url, "كتب"))
    expect(box).to_have_value("كتب")
    expect(status).to_have_text("3 readings for كتب")

    page.go_forward()
    expect(box).to_have_value("كاتب")
    expect(status).to_contain_text("كاتب")

    page.reload()
    expect(box).to_have_value("كاتب")
    expect(status).to_contain_text("كاتب")


def test_a_slow_earlier_response_never_replaces_a_newer_one(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_label("Arabic word")
    status = page.get_by_role("status")
    held = []
    page.route(lambda url: url.endswith(f"?q={quote('ك')}"), lambda route: held.append(route))

    box.press_sequentially("ك")
    expect(status).to_have_text("Looking up…")
    box.press_sequentially("تب")
    expect(status).to_have_text("3 readings for كتب")

    try:
        held[0].continue_()  # the response for ك arrives last
    except PlaywrightError:
        pass  # the browser already gave up on that request
    page.wait_for_timeout(500)
    expect(status).to_have_text("3 readings for كتب")
    expect(page.locator(".reading")).to_have_count(3)
    expect(page).to_have_url(lookup_url(base_url, "كتب"))


def test_a_failed_lookup_offers_retry_and_keeps_the_input(base_url, browser, monkeypatch):
    class Broken:
        def lookup_ar(self, word):
            raise RuntimeError("database gone")

    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_label("Arabic word")
    status = page.get_by_role("status")

    monkeypatch.setattr("aradict.app.dictionary", Broken)
    box.press_sequentially("كتب")
    expect(status).to_contain_text("Lookup failed")
    expect(box).to_have_value("كتب")

    monkeypatch.undo()
    page.get_by_role("button", name="Retry").click()
    expect(status).to_have_text("3 readings for كتب")
    expect(page.locator(".reading")).to_have_count(3)


def test_home_intro_sits_below_the_search_box_on_a_phone(base_url, browser):
    page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()

    page.goto(base_url)
    search = page.get_by_label("Arabic word").bounding_box()
    intro = page.locator(".intro").bounding_box()
    assert search["y"] + search["height"] <= intro["y"]  # the explanation never sits in front of the search box
    assert intro["y"] + intro["height"] <= 844  # and is short enough to read on the first screen
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_the_diacritics_switch_looks_up_again_and_lives_in_the_url(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كَتَبَ')}")
    switch = page.get_by_role("checkbox", name="Ignore diacritics")
    expect(page.locator(".reading")).to_have_count(1)

    switch.check()
    expect(page.locator(".reading")).to_have_count(3)
    expect(page).to_have_url(re.compile(re.escape(f"{base_url}/?q={quote('كَتَبَ')}&diacritics=off") + "$"))

    page.reload()
    expect(switch).to_be_checked()
    expect(page.locator(".reading")).to_have_count(3)

    page.go_back()
    expect(switch).not_to_be_checked()
    expect(page.locator(".reading")).to_have_count(1)

    page.get_by_label("Arabic word").fill("كتب كتاب")  # notices update live too
    expect(page.get_by_text("Only the first word")).to_be_visible()


def test_choose_a_suggestion_with_the_keyboard_alone(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_role("combobox", name="Arabic word")
    suggestions = page.get_by_role("listbox", name="Suggestions")
    expect(box).to_have_attribute("aria-expanded", "false")

    box.press_sequentially("كتا")
    expect(suggestions.get_by_role("option")).to_have_text(["كِتاب", "كُتّاب", "كَتاتِيب"])
    expect(page.get_by_role("status")).to_contain_text("كتا")  # the typed word is looked up meanwhile
    expect(box).to_have_attribute("aria-controls", suggestions.evaluate("e => e.id"))
    box.press("ArrowDown")
    box.press("ArrowDown")
    box.press("ArrowUp")
    # The active option is the selected one, and the field points to it while keeping focus.
    expect(page.locator("form")).to_match_aria_snapshot("""
        - combobox "Arabic word" [expanded]: كتا
        - listbox "Suggestions":
          - option "كِتاب" [selected]
          - option "كُتّاب"
          - option "كَتاتِيب"
    """)
    first = suggestions.get_by_role("option", name="كِتاب")
    expect(box).to_have_attribute("aria-activedescendant", first.evaluate("e => e.id"))
    expect(box).to_be_focused()

    page.evaluate("window.samePage = true")
    box.press("Enter")
    expect(box).to_have_value("كِتاب")
    expect(box).to_have_attribute("aria-expanded", "false")
    expect(suggestions).to_be_hidden()
    expect(page.get_by_role("status")).to_have_text("1 reading for كِتاب")  # that exact reading
    expect(page).to_have_url(lookup_url(base_url, "كِتاب"))
    assert page.evaluate("window.samePage")  # chosen through the live lookup, not a page load

    page.go_back()  # the typed word's own lookup is in the history before it
    expect(box).to_have_value("كتا")


def test_escape_closes_the_suggestions_and_keeps_the_typed_lookup(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_role("combobox", name="Arabic word")
    suggestions = page.get_by_role("listbox", name="Suggestions")

    box.press_sequentially("كتب")
    expect(suggestions).to_be_visible()
    box.press("ArrowDown")
    box.press("Escape")
    expect(suggestions).to_be_hidden()
    expect(box).to_have_attribute("aria-expanded", "false")
    expect(box).not_to_have_attribute("aria-activedescendant", re.compile(".*"))
    expect(box).to_have_value("كتب")
    expect(page.get_by_role("status")).to_have_text("3 readings for كتب")
    expect(page).to_have_url(lookup_url(base_url, "كتب"))


def test_a_suggestion_can_be_chosen_by_pointer(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    page.get_by_label("Arabic word").press_sequentially("وكتا")
    page.get_by_role("option", name="وَكُتّاب").click()
    expect(page.get_by_label("Arabic word")).to_have_value("وَكُتّاب")
    expect(page).to_have_url(lookup_url(base_url, "وَكُتّاب"))


def test_turning_suggestions_off_stops_them_at_once(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_label("Arabic word")
    suggestions = page.get_by_role("listbox", name="Suggestions")
    switch = page.get_by_role("checkbox", name="Show suggestions")
    expect(switch).to_be_checked()

    box.press_sequentially("كتا")
    expect(suggestions).to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("كتا")
    history = page.evaluate("history.length")
    held = []
    is_suggest = lambda url: "/suggest?" in url
    page.route(is_suggest, lambda route: held.append(route))
    box.press_sequentially("ب")  # its suggestions are on their way when the switch goes off
    page.wait_for_timeout(100)

    # The open list covers the switch, so reach it from the keyboard.
    switch.focus()
    page.keyboard.press("Space")
    expect(switch).not_to_be_checked()
    expect(suggestions).to_be_hidden()
    expect(page.get_by_role("combobox")).to_have_count(0)  # a plain text field again
    for route in held:
        try:
            route.continue_()
        except PlaywrightError:
            pass  # the browser already gave up on that request
    page.wait_for_timeout(300)
    expect(suggestions).to_be_hidden()
    expect(page.get_by_role("status")).to_have_text("3 readings for كتاب")  # lookup goes on
    assert page.evaluate("history.length") == history + 1  # only the lookup of كتاب; the switch adds no entry

    page.unroute(is_suggest)
    asked = []
    page.on("request", lambda request: is_suggest(request.url) and asked.append(request.url))
    box.focus()
    box.evaluate("e => e.setSelectionRange(e.value.length, e.value.length)")
    page.keyboard.type("ي")
    expect(page.get_by_role("status")).to_contain_text("كتابي")
    page.wait_for_timeout(300)
    expect(suggestions).to_be_hidden()
    assert asked == []  # no suggestions are even asked for
    assert page.evaluate("new URLSearchParams(location.search).size") == 1  # the switch is not part of the URL
