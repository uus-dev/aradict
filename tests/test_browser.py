"""Browser journeys in Chromium against a real server on the fixture database."""

import re
import threading
import time
import unicodedata
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

    page.get_by_role("textbox", name="Arabic word").fill("كتب كتاب")  # notices update live too
    expect(page.get_by_text("Only the first word")).to_be_visible()


def on_screen(page, *keys):
    """Press keys on the on-screen keyboard by name, pressing Shift first for a key on the shift layer."""
    keyboard = page.get_by_role("group", name="Arabic keyboard")
    for name in keys:
        key = keyboard.get_by_role("button", name=name, exact=True)
        if not key.count():
            keyboard.get_by_role("button", name="Shift", exact=True).click()
        key.click()


def test_typing_a_voweled_word_on_the_on_screen_keyboard(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    page.get_by_role("button", name="Arabic keyboard").click()

    on_screen(page, "kaf", "fatha", "teh", "fatha", "beh", "fatha")  # each vowel mark drops back to the letters

    expect(page.get_by_role("textbox", name="Arabic word")).to_have_value("كَتَبَ")
    expect(page.get_by_role("status")).to_have_text("1 reading for كَتَبَ")  # live lookup, no button pressed
    expect(page.locator(".reading")).to_have_count(1)
    expect(page).to_have_url(lookup_url(base_url, "كَتَبَ"))


def test_every_letter_haraka_and_hamza_form_has_a_named_key(base_url, browser):
    letters = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي" + "ةى"
    hamza_forms = "ءأإآؤئ"
    harakat = "\u064e\u064f\u0650\u064b\u064c\u064d\u0651\u0652"  # fatha, damma, kasra, the tanween, shadda, sukun
    typed = letters + hamza_forms + harakat
    page = browser.new_page()
    page.goto(base_url)
    page.get_by_role("button", name="Arabic keyboard").click()

    # Each key is named after its Unicode character name: "ARABIC LETTER BEH" is "beh".
    on_screen(page, *(unicodedata.name(ch).removeprefix("ARABIC ").removeprefix("LETTER ").lower() for ch in typed))
    on_screen(page, "lam alef", "lam alef with hamza above", "lam alef with hamza below", "lam alef with madda above")

    expect(page.get_by_role("textbox", name="Arabic word")).to_have_value(typed + "لالألإلآ")


def test_on_screen_keys_type_at_the_caret_and_leave_focus_in_the_field(base_url, browser):
    page = browser.new_page()
    page.goto(f"{base_url}/?q={quote('كتب')}")
    box = page.get_by_role("textbox", name="Arabic word")
    status = page.get_by_role("status")
    page.get_by_role("button", name="Arabic keyboard").click()

    on_screen(page, "alef")  # the field was never focused, so there is no caret yet: type at the end
    expect(box).to_have_value("كتبا")
    on_screen(page, "Delete")
    expect(box).to_have_value("كتب")

    box.focus()
    box.evaluate("e => e.setSelectionRange(1, 1)")  # after the ك
    on_screen(page, "alef")
    expect(box).to_have_value("كاتب")
    expect(box).to_be_focused()
    expect(status).to_contain_text("كاتب")

    on_screen(page, "Delete")  # takes the alef just typed: the caret moved past it
    expect(box).to_have_value("كتب")
    expect(status).to_have_text("3 readings for كتب")


def test_the_on_screen_keyboard_works_without_a_pointer(base_url, browser):
    page = browser.new_page()
    page.goto(base_url)
    box = page.get_by_role("textbox", name="Arabic word")
    toggle = page.get_by_role("button", name="Arabic keyboard")
    keyboard = page.get_by_role("group", name="Arabic keyboard")

    box.focus()
    page.keyboard.press("Tab")
    expect(toggle).to_be_focused()
    expect(keyboard).to_be_hidden()
    page.keyboard.press("Enter")
    expect(keyboard).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(box).to_have_attribute("inputmode", "none")  # a tap in the field won't raise the phone's own keyboard

    first_key = keyboard.get_by_role("button", name="thal", exact=True)
    for _ in range(5):  # past the rest of the search form, which also comes first on screen
        page.keyboard.press("Tab")
        if first_key.evaluate("e => e === document.activeElement"):
            break
    expect(first_key).to_be_focused()
    page.keyboard.press("Enter")
    expect(box).to_have_value("ذ")
    shift = keyboard.get_by_role("button", name="Shift")
    shift.focus()
    page.keyboard.press("Space")
    expect(shift).to_have_attribute("aria-pressed", "true")
    expect(shift).to_be_focused()

    keyboard.get_by_role("button", name="Hide").focus()
    page.keyboard.press("Enter")
    expect(keyboard).to_be_hidden()
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(box).not_to_have_attribute("inputmode", "none")

    page.keyboard.press("Enter")
    expect(keyboard).to_be_visible()
    expect(shift).to_have_attribute("aria-pressed", "false")  # it opens on the letters
    page.keyboard.press("Enter")
    expect(keyboard).to_be_hidden()


def test_the_on_screen_keyboard_fits_a_phone_with_large_keys(base_url, browser):
    phone = {"width": 390, "height": 844}
    no_script = browser.new_context(java_script_enabled=False, viewport=phone).new_page()
    no_script.goto(base_url)
    expect(no_script.get_by_role("button", name="Arabic keyboard")).to_be_hidden()  # no keys to show without JavaScript

    page = browser.new_context(viewport=phone).new_page()
    page.goto(base_url)
    page.get_by_role("button", name="Arabic keyboard").click()
    keys = [key.bounding_box() for key in page.get_by_role("group", name="Arabic keyboard").get_by_role("button").all()]
    assert len(keys) == 38  # 34 character keys, Shift, Delete, Hide and Space
    assert min(key["height"] for key in keys) >= 44
    assert min(key["width"] for key in keys) >= 24
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_word_parts_are_marked_without_colour_and_open_without_javascript(base_url, browser):
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
    page.context.close()


def test_text_details_open_by_tap_and_by_keyboard_and_fit_a_phone(base_url, browser):
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    page.goto(f"{base_url}/text")
    page.get_by_role("textbox", name="Arabic text").fill("كتب كتاب قخغثص كتب")
    page.get_by_role("button", name="Analyse").click()

    word = page.get_by_role("button", name=re.compile(r"^كتب\s*, 3 readings$"))
    expect(word).to_have_count(2)
    expect(page.get_by_role("button", name=re.compile(r"^قخغثص\s*, not in the dictionary$"))).to_be_visible()
    details = page.get_by_role("dialog", name="كتب")

    word.last.tap()
    expect(details).to_be_visible()
    expect(details.locator(".reading")).to_have_count(3)
    box = details.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["y"] + box["height"] <= 844
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    word_box = word.last.bounding_box()
    assert word_box["y"] + word_box["height"] <= box["y"]  # the tapped word stays in view above the panel
    details.get_by_role("button", name="Close").tap()
    expect(details).to_be_hidden()

    word.first.focus()
    page.keyboard.press("Enter")
    expect(details).to_be_visible()
    page.keyboard.press("Escape")
    expect(details).to_be_hidden()
    context.close()


def test_text_without_javascript_keeps_the_layout_and_opens_word_lookup(base_url, browser):
    page = browser.new_context(java_script_enabled=False).new_page()
    page.goto(f"{base_url}/text")
    page.get_by_role("textbox", name="Arabic text").fill("كتب، 3 BBC\nكتاب")
    page.get_by_role("button", name="Analyse").click()

    expect(page).to_have_url(f"{base_url}/text")  # posted: the passage stays out of the address
    passage = page.locator(".passage")
    expect(passage).to_contain_text("، 3 BBC")
    first, second = (tok.bounding_box() for tok in page.locator(".tok").all())
    assert second["y"] >= first["y"] + first["height"]  # the line break is kept
    box = passage.bounding_box()
    assert first["x"] > box["x"] + box["width"] / 2  # right to left: كتب starts the first line, on the right

    page.locator(".tok").first.click()
    details = page.get_by_role("dialog", name="كتب")
    expect(details).to_be_visible()
    details.get_by_role("link", name="Open in Word lookup").click()
    expect(page).to_have_url(lookup_url(base_url, "كتب"))
    expect(page.locator(".reading")).to_have_count(3)
    page.context.close()


def test_text_is_analysed_after_a_pause_and_markup_stays_text(base_url, browser):
    page = browser.new_page()
    dialogs = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    page.goto(f"{base_url}/text")
    box = page.get_by_role("textbox", name="Arabic text")
    status = page.get_by_role("status")

    box.fill("<script>alert(1)</script> كتب")  # no button pressed
    expect(status).to_have_text("1 word")
    expect(page.locator(".passage")).to_contain_text("<script>alert(1)</script> كتب")
    expect(page).to_have_url(f"{base_url}/text")

    box.fill("كتب " * 500 + "كتاب")
    expect(status).to_have_text("Your text has 2,004 characters. Analyse at most 2,000 at a time: shorten it and try again.")
    expect(page.locator(".passage")).to_have_count(0)
    expect(box).to_have_value("كتب " * 500 + "كتاب")
    assert dialogs == []


def test_text_details_sit_under_the_word_on_a_wide_screen(base_url, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(f"{base_url}/text?q={quote('كتب كتاب')}")
    word = page.locator(".tok").last
    word.click()
    details = page.get_by_role("dialog", name="كتاب")
    expect(details).to_be_visible()
    expect(word).to_have_class(re.compile(r"\bon\b"))
    w, d = word.bounding_box(), details.bounding_box()
    assert w["y"] + w["height"] <= d["y"] <= w["y"] + w["height"] + 12
    assert d["x"] <= w["x"] and w["x"] + w["width"] <= d["x"] + d["width"]
    page.keyboard.press("Escape")
    expect(word).not_to_have_class(re.compile(r"\bon\b"))


def test_arabizi_shows_the_arabic_it_looked_up_and_keeps_it_on_reload(base_url, browser, monkeypatch):
    class Broken:
        def arabizi(self, text):
            raise RuntimeError("database gone")

    page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
    page.goto(base_url)
    box = page.get_by_role("textbox", name="Arabic word")
    status = page.get_by_role("status")
    looked_up_as = page.locator("#arabizi")

    box.press_sequentially("ktb")
    expect(status).to_have_text("3 readings for كتب")
    expect(looked_up_as).to_have_text("Looked up as كتب")
    expect(page).to_have_url(lookup_url(base_url, "ktb"))
    assert looked_up_as.locator(".ar").get_attribute("dir") == "rtl"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    page.reload()  # the pushed URL reproduces the lookup, chip included
    expect(box).to_have_value("ktb")
    expect(looked_up_as).to_have_text("Looked up as كتب")
    expect(page.locator(".reading")).to_have_count(3)

    box.fill("كاتب")  # Arabic script needs no chip
    expect(status).to_contain_text("كاتب")
    expect(looked_up_as).to_be_hidden()

    page.go_back()
    expect(looked_up_as).to_have_text("Looked up as كتب")

    monkeypatch.setattr("aradict.app.dictionary", Broken)
    box.fill("kitab")
    expect(status).to_contain_text("Lookup failed")
    expect(looked_up_as).to_be_hidden()  # a failed lookup leaves no stale Arabic beside the input
    page.context.close()
