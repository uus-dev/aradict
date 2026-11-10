"""A browser journey in Chromium against a real server on the fixture database."""

import threading
import time
from urllib.parse import quote

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

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


def test_lookup_without_javascript_on_a_phone(base_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
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
        browser.close()


def test_word_parts_are_marked_without_colour_and_open_without_javascript(base_url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844}).new_page()
        page.goto(f"{base_url}/?q={quote('وبكتابهم')}")
        reading = page.locator(".reading").first

        def decoration(selector: str) -> str:
            return reading.locator(selector).first.evaluate(
                "e => getComputedStyle(e).textDecorationLine + ' ' + getComputedStyle(e).textDecorationStyle"
            )

        # Prefix, stem and suffix differ in line style as well as colour.
        assert decoration(".form .prefix") == "underline dotted"
        assert decoration(".form .suffix") == "underline solid"
        assert decoration(".form .stem").startswith("none")

        chips = reading.locator(".chips")
        expect(chips).to_be_hidden()
        reading.get_by_text("Word parts").click()
        expect(chips).to_be_visible()
        expect(chips.locator(".chip")).to_have_count(4)
        expect(chips.locator(".chip").nth(1)).to_contain_text("by/with")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()
