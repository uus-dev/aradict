"""The accessibility pass (#15): automated axe checks, reflow on a narrow phone, text zoom, and the
core flows by keyboard alone, in Chromium against a real server on the fixture database, with
Wiktionary's senses and credit (#22)."""

import re
from urllib.parse import quote, urlencode

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect

from aradict.app import dictionary

WCAG = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]}}


@pytest.fixture(scope="module")
def base_url(wiktionary_base_url):
    return wiktionary_base_url


def open_word(page, base_url):
    """وبكتابهم with every reading's word parts open, the on-screen keyboard and the recent lookups."""
    page.goto(f"{base_url}/?q={quote('وبكتابهم')}")
    page.locator("details.parts").evaluate_all("all => all.forEach(d => d.open = true)")
    page.get_by_role("button", name="Arabic keyboard").click()
    page.locator("#history summary").click()


def open_text(page, base_url):
    page.goto(f"{base_url}/text?{urlencode({'q': 'كتب كتاب قخغثص'})}")
    page.locator(".tok").first.click()
    expect(page.get_by_role("dialog")).to_be_visible()


PAGES = {
    "word": open_word,
    "text": open_text,
    # Wiktionary's homographs, one only Wiktionary has, and senses with labels and sub-senses.
    "homographs": lambda page, base_url: page.goto(f"{base_url}/?q={quote('قال')}"),
    "labels": lambda page, base_url: page.goto(f"{base_url}/?q={quote('جدة')}"),
    # Plurals, gender, verbal nouns, relations and pronunciations (#23), the regional ones opened.
    "forms": lambda page, base_url: [
        page.goto(f"{base_url}/?{urlencode({'q': 'كتاب', 'diacritics': 'off'})}"),
        page.locator("details.regional summary").first.click(),
    ],
    # A word only Wiktionary has beside the dictionary's reading (#24), and entries that only relate a word to another.
    "only": lambda page, base_url: page.goto(f"{base_url}/?q={quote('تغريدة')}"),
    "also": lambda page, base_url: page.goto(f"{base_url}/?q={quote('كتب')}"),
    "text-only": lambda page, base_url: [
        page.goto(f"{base_url}/text?{urlencode({'q': 'تغريدتي كتب'})}"), page.locator(".tok").first.click(),
        expect(page.get_by_role("dialog")).to_be_visible(),
    ],
    "root": lambda page, base_url: page.goto(f"{base_url}/?{urlencode({'q': 'كتب', 'root': 'ك.ت.ب'})}"),
    "related": lambda page, base_url: page.goto(f"{base_url}/?{urlencode({'q': 'كتاب', 'related': 'كِتاب', 'pos': 'noun'})}"),
    "about": lambda page, base_url: page.goto(f"{base_url}/about"),
}


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("name", PAGES)
def test_pages_pass_axe(base_url, browser, name, width, scheme):
    context = browser.new_context(viewport={"width": width, "height": 800}, color_scheme=scheme)
    page = context.new_page()
    PAGES[name](page, base_url)
    if name in ("word", "text", "homographs", "labels", "forms", "only", "also", "text-only"):
        expect(page.locator(".credit:visible").first).to_contain_text("From Wiktionary")  # its content is checked too
    results = Axe().run(page, options=WCAG)
    context.close()
    assert results.violations_count == 0, results.generate_report()


@pytest.fixture
def wiktionary_url(base_url, fixture_wiktionary):
    """The server at base_url, reading the fixture Wiktionary dataset for one test."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ARADICT_WIKTIONARY_PATH", str(fixture_wiktionary))
        dictionary.cache_clear()
        yield base_url
        dictionary.cache_clear()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [360, 1280])
def test_a_root_filled_from_wiktionary_passes_axe(wiktionary_url, browser, width, scheme):
    # قال's root tab, with و filled in, and the root view of ق و ل.
    context = browser.new_context(viewport={"width": width, "height": 800}, color_scheme=scheme)
    page = context.new_page()
    for params in ({"q": "قال"}, {"q": "قال", "root": "ق.و.ل"}):
        page.goto(f"{wiktionary_url}/?{urlencode(params)}")
        expect(page.locator(".fill").first).to_be_visible()
        results = Axe().run(page, options=WCAG)
        assert results.violations_count == 0, results.generate_report()
        assert not scrolls_sideways(page)
    context.close()


def test_the_dark_scheme_follows_the_system_setting(base_url, browser):
    def background(scheme: str) -> str:
        context = browser.new_context(color_scheme=scheme)
        page = context.new_page()
        page.goto(base_url)
        colour = page.evaluate("getComputedStyle(document.body).backgroundColor")
        context.close()
        return colour

    assert background("light") != background("dark")


def test_no_page_loads_anything_from_another_site(base_url, browser):
    page = browser.new_page()
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    open_word(page, base_url)
    open_text(page, base_url)
    page.goto(f"{base_url}/about")
    assert requested and all(url.startswith(base_url) for url in requested)
    # The interface font is self-hosted and in use.
    assert page.evaluate("document.fonts.check('15px \"Source Sans 3\"')")
    assert page.evaluate("[...document.fonts].some(f => f.family.includes('Source Sans 3') && f.status === 'loaded')")


def scrolls_sideways(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth > innerWidth")


def test_dense_results_never_scroll_sideways_on_a_narrow_phone(base_url, browser):
    page = browser.new_page(viewport={"width": 360, "height": 740})

    page.goto(f"{base_url}/?q={quote('وبكتابهم')}")
    page.locator("details.parts summary").first.wait_for()
    for summary in page.locator("details.parts summary").all():
        summary.click()
    expect(page.locator(".chips").first).to_be_visible()
    assert not scrolls_sideways(page)

    page.goto(f"{base_url}/?{urlencode({'q': 'كتب', 'root': 'ك.ت.ب'})}")
    expect(page.get_by_role("table")).to_be_visible()
    assert not scrolls_sideways(page)

    PAGES["forms"](page, base_url)
    expect(page.locator(".regional dl").first).to_be_visible()
    assert not scrolls_sideways(page)

    passage = "وبكتابهم سيكتبون كتب الكتاب، قخغثص https://example.com/a/very/long/address/that/does/not/break 2026\n" * 6
    page.goto(f"{base_url}/text")
    page.get_by_role("textbox", name="Arabic text").fill(passage)
    page.get_by_role("button", name="Analyse").click()
    expect(page.locator(".tok").first).to_be_visible()
    page.locator(".tok").first.click()
    expect(page.get_by_role("dialog").first).to_be_visible()
    assert not scrolls_sideways(page)


# Boxes that cut off what overflows them, and do: visually hidden text (1 × 1 px) aside.
CLIPPED = """() => [...document.querySelectorAll('body *')].filter(e => {
  if (!e.checkVisibility() || e.clientWidth <= 1) return false;
  const s = getComputedStyle(e);
  const clips = [s.overflowX, s.overflowY].some(o => o === 'hidden' || o === 'clip');
  return clips && (e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1);
}).map(e => e.outerHTML.slice(0, 80))"""

# Arabic text, its marks included, needs this much line height: a mark above or below a letter must
# not reach the next line, and a field, which cuts its text off at its edges, must be tall enough.
TIGHT = """() => [...document.querySelectorAll('[lang="ar"]')].filter(e => e.checkVisibility() && e.textContent.trim()).filter(e => {
  const s = getComputedStyle(e);
  const size = parseFloat(s.fontSize);
  const line = s.lineHeight === 'normal' ? Infinity : parseFloat(s.lineHeight);
  if (e.matches('input, textarea')) return line < 1.45 * size || e.clientHeight < 1.45 * size;
  const inner = e.clientHeight - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom);
  const lines = s.display === 'inline' ? e.getClientRects().length > 1 : inner > 1.5 * line;
  return lines && line < 1.45 * size;
}).map(e => e.outerHTML.slice(0, 80))"""


@pytest.mark.parametrize("name", ["word", "text", "homographs", "labels", "forms", "root", "about"])
def test_text_zoomed_to_200_percent_stays_usable(base_url, browser, name):
    # A 1280 × 800 window zoomed to 200% lays the page out in 640 × 400 CSS pixels.
    context = browser.new_context(viewport={"width": 640, "height": 400}, device_scale_factor=2)
    page = context.new_page()
    PAGES[name](page, base_url)
    assert not scrolls_sideways(page)
    assert page.evaluate(CLIPPED) == []
    assert page.evaluate(TIGHT) == []
    if name == "word":
        # The search stays in view with room below it for the results.
        page.locator(".reading").last.scroll_into_view_if_needed()
        expect(page.get_by_label("Arabic word")).to_be_in_viewport(ratio=1)
        assert page.locator("#search").bounding_box()["height"] <= 400 / 2
    context.close()


# How far each control's content reaches past its box, kept at the default text size (scale 0) and
# compared at a larger one: a control may overflow only as much as before, scaled. Arabic glyphs
# reach a little past a tight line at any size; a box that stays put while its text grows does not
# scale with it. A text field must also stay at least one line of its text tall.
CRAMPED = """scale => {
  const all = [...document.querySelectorAll(
    'button, input:not([type=checkbox]), textarea, summary, .site nav a, .clear, .root-tab, .rt-go, .dismiss, .badge, .grammar li, .history ol a, .family th a, .tp-foot a'
  )].filter(e => e.checkVisibility() && e.clientHeight);
  const over = e => [e.scrollWidth - e.clientWidth, e.scrollHeight - e.clientHeight];
  if (!scale) { window.defaultOverflow = new Map(all.map(e => [e, over(e)])); return []; }
  return all.filter(e => {
    const s = getComputedStyle(e);
    const line = s.lineHeight === 'normal' ? 1.2 * parseFloat(s.fontSize) : parseFloat(s.lineHeight);
    const before = window.defaultOverflow.get(e) || [0, 0];
    return over(e).some((d, i) => d > scale * Math.max(0, before[i]) + 1) || (e.matches('input, textarea') && e.clientHeight < line);
  }).map(e => e.outerHTML.slice(0, 80));
}"""

HEADWORD = {"word": ".lemma .ar", "text": ".tok-pop .lemma .ar", "root": ".family td:first-child .ar"}


@pytest.mark.parametrize("name", HEADWORD)
def test_the_browsers_text_size_setting_scales_the_text(base_url, browser, name):
    # A larger text size in the browser's settings sets the root font size; the page must follow it
    # (PRD story 81) and keep its text inside its controls.
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    PAGES[name](page, base_url)
    sizes = f"[...document.querySelectorAll('{HEADWORD[name]}, body')].map(e => parseFloat(getComputedStyle(e).fontSize))"
    default = page.evaluate(sizes)
    page.evaluate(CRAMPED, 0)
    page.add_style_tag(content="html { font-size: 200% }")
    assert page.evaluate(sizes) == [2 * size for size in default]
    assert not scrolls_sideways(page)
    assert page.evaluate(CRAMPED, 2) == []
    page.close()


def focus_ring(page) -> str:
    """The focused element's outline, which keyboard users follow."""
    return page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return `${s.outlineStyle} ${s.outlineWidth}`; })()")


def tab_to(page, matches: str, key: str = "Tab", limit: int = 60):
    """Tab (or Shift+Tab) until the focused element matches a selector, checking each stop shows focus."""
    for _ in range(limit):
        page.keyboard.press(key)
        assert focus_ring(page).startswith("solid"), page.evaluate("document.activeElement.outerHTML.slice(0, 80)")
        if page.evaluate("s => document.activeElement.matches(s)", matches):
            return
    raise AssertionError(f"no focusable {matches} within {limit} tabs")


def test_core_flows_by_keyboard_alone(base_url, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    status = page.get_by_role("status")
    page.goto(base_url)

    # Look up a word: type it and press Enter.
    tab_to(page, "#q")
    page.keyboard.type("وبكتابهم")
    page.keyboard.press("Enter")
    expect(status).to_have_text("3 readings for وبكتابهم")

    # Open a reading's word parts.
    tab_to(page, "details.parts summary")
    page.keyboard.press("Enter")
    expect(page.locator(".chips").first).to_be_visible()

    # Open the root's words, sort them by meaning, and go back to the lookup.
    tab_to(page, ".root-tab")
    page.keyboard.press("Enter")
    expect(status).to_contain_text("forms from the root ك ت ب")
    tab_to(page, "th:nth-child(2) a")  # Meaning
    page.keyboard.press("Enter")
    expect(page.get_by_role("columnheader", name="Meaning")).to_have_attribute("aria-sort", "ascending")
    tab_to(page, ".dismiss")
    page.keyboard.press("Enter")
    expect(status).to_have_text("3 readings for وبكتابهم")

    # Open a headword's regional pronunciations, then look up its plural (#23).
    page.goto(f"{base_url}/?q={quote('كتاب')}")
    tab_to(page, "details.regional summary")
    page.keyboard.press("Enter")
    expect(page.locator(".regional dl").first).to_be_visible()
    tab_to(page, f".words a[href='/?{urlencode({'q': 'كُتُب'})}']", "Shift+Tab")
    page.keyboard.press("Enter")
    expect(status).to_contain_text("for كُتُب")

    # Analyse a passage and open, then close, a word's details.
    page.goto(f"{base_url}/text")
    tab_to(page, "#text")
    page.keyboard.type("كتب قخغثص")
    tab_to(page, "button[type=submit]")
    page.keyboard.press("Enter")
    expect(status).to_have_text("2 words, 1 not in the dictionary")
    tab_to(page, ".tok")
    page.keyboard.press("Enter")
    details = page.get_by_role("dialog", name="كتب")
    expect(details).to_be_visible()
    page.keyboard.press("Escape")
    expect(details).to_be_hidden()

    # Open the About page from the main navigation.
    tab_to(page, "nav a[href='/about']", "Shift+Tab")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile("/about$"))
    expect(page.get_by_role("heading", level=1)).to_have_text("About and help")
