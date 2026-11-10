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
    expect(page.get_by_role("textbox", name="Arabic word")).to_be_in_viewport(ratio=1)


def test_clear_and_deleting_the_query_return_to_the_empty_start(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتب')}")
    box = page.get_by_role("textbox", name="Arabic word")
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
    box = page.get_by_role("textbox", name="Arabic word")
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
    box = page.get_by_role("textbox", name="Arabic word")
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
    box = page.get_by_role("textbox", name="Arabic word")
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
    search = page.get_by_role("textbox", name="Arabic word").bounding_box()
    intro = page.locator(".intro").bounding_box()
    assert search["y"] + search["height"] <= intro["y"]  # the explanation never sits in front of the search box
    assert intro["y"] + intro["height"] <= 844  # and is short enough to read on the first screen
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
