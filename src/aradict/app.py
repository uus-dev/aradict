"""The AraDict web app."""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import views, wiktionary
from .data import db_path
from .dictionary import Dictionary, opened

logger = logging.getLogger(__name__)


def _without_query(record: logging.LogRecord) -> bool:
    """Cuts the query string, which holds the looked-up word, from uvicorn's access log lines.
    `uv run aradict` turns that log off; this keeps `uvicorn aradict.app:app` safe as well."""
    if isinstance(record.args, tuple) and len(record.args) == 5:  # client, method, path?query, HTTP version, status
        client, method, path, version, status = record.args
        record.args = (client, method, path.partition("?")[0], version, status)
    return True


logging.getLogger("uvicorn.access").addFilter(_without_query)


def _log_failure(what: str, error: Exception) -> None:
    """Logs what failed with the exception's type and where it was raised, never its message,
    which may quote the word or passage (PRD: no query text in telemetry)."""
    stack = " < ".join(f"{frame.name} ({frame.filename}:{frame.lineno})" for frame in reversed(traceback.extract_tb(error.__traceback__)))
    logger.error("%s: %s in %s", what, type(error).__name__, stack)


@lru_cache(maxsize=1)
def dictionary() -> Dictionary:
    return Dictionary(db_path(), wiktionary.dataset_path())


@asynccontextmanager
async def lifespan(app: FastAPI):
    dictionary()  # load at startup, so a missing database fails loudly before the first request
    yield


# ponytail: no rate limiting yet; #17 adds it in front of the app, or as middleware here before any route does work.
app = FastAPI(title="AraDict", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# Bytes a Text form may post. MAX_TEXT characters take at most 24,000 URL-encoded; the rest lets
# a passage somewhat over the limit come back with its length, kept for the user to shorten.
MAX_BODY = 64_000


LOOKUP = ("q", "diacritics", "lang")  # the URL parameters of a lookup


@app.get("/", response_class=HTMLResponse)
def word(
    request: Request,
    q: str = "",
    diacritics: Literal["on", "off"] = "on",
    lang: Literal["ar", "en"] = "ar",  # the language typed: Arabic → English, or English → Arabic
    root: str | None = None,
    related: str | None = None,
    pos: str = "",
    sort: str = "",
    hx_request: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    """A lookup, or with root or related (and pos) a root's words or a lemma's forms in its place,
    sorted by sort. The lookup's own URL parameters go with every root and related-forms link, so
    their view can return to it."""
    lookup = {key: value for key, value in request.query_params.items() if key in LOOKUP}
    q, filter_diacritics, english = q.strip(), diacritics == "on", lang == "en"
    status_code = 200
    try:
        if any(len(value) > views.MAX_QUERY for value in (q, root or "", related or "", pos, sort)):
            state = views.State(f"That's too long. Type at most {views.MAX_QUERY} characters.")
        elif root is not None:
            rows = dictionary().root_family(root)
            filled = dict.fromkeys((r.lemma, r.pos) for r in rows if r.root == opened(root) != root)  # the lemmas Wiktionary filled to it, in order
            sources = {e.url: lemma for lemma, pos in filled for e in dictionary().wiktionary(lemma, pos)}
            state = views.root_view(root, rows, lookup, sort, dictionary().unconfirmed(root), [(lemma, url) for url, lemma in sources.items()])
        elif related is not None:
            state = views.related_view(related, pos, dictionary().related(related, pos), lookup, sort)
        elif not q:
            state = views.INITIAL_EN if english else views.INITIAL
        elif not any(c.isalpha() for c in q):
            state = views.State("Type a word: letters, not only numbers or symbols.")
        else:
            found = dictionary().lookup(q, english, filter_diacritics)
            lemmas = {(r.lemma, r.pos) for r in found.readings}
            roots = {(r.lemma, r.pos, r.root) for r in found.readings if r.root}
            filled = {root: full for root in roots if (full := dictionary().filled_root(*root))}
            links = views.Links(
                lookup,
                {lemma: len(dictionary().related(*lemma)) for lemma in lemmas},
                {root: dictionary().family_size(root) for root in {filled.get(root, root[2]) for root in roots}},
                {lemma: dictionary().wiktionary(*lemma) for lemma in lemmas},
                filled,
            )
            state = views.looked_up_en(found, links) if english else views.looked_up(q, found, links)
    except Exception as error:
        _log_failure("Lookup failed", error)
        state, status_code = views.FAILURE, 500
    page = views.live_results(state) if hx_request else views.word_page(q, state, filter_diacritics, english)
    headers = {"Vary": "HX-Request"}
    if hx_request and not q:
        # A cleared live lookup returns to "/", not "/?q=", keeping the diacritics switch and the direction.
        options = {"diacritics": "off"} if not filter_diacritics else {}
        if english:
            options["lang"] = "en"
        headers["HX-Push-Url"] = f"/?{urlencode(options)}" if options else "/"
    return HTMLResponse(str(page), status_code, headers)


def _analyse(text: str, hx_request: str | None = None) -> HTMLResponse:
    text = text.replace("\r\n", "\n").strip()  # a form posts line breaks as CR LF
    status_code = 200
    if not text:
        state = views.State()
    elif len(text) > views.MAX_TEXT:
        state = views.State(f"Your text has {len(text):,} characters. Analyse at most {views.MAX_TEXT:,} at a time: shorten it and try again.")
    else:
        try:
            state = views.analysed(dictionary().analyze_text(text))
        except Exception as error:
            _log_failure("Text analysis failed", error)
            state, status_code = views.TEXT_FAILURE, 500
    return _text_view(text, state, hx_request, status_code)


def _text_view(text: str, state: views.State, hx_request: str | None, status_code: int = 200) -> HTMLResponse:
    page = views.live_analysis(state) if hx_request else views.text_page(text, state)
    return HTMLResponse(str(page), status_code, {"Vary": "HX-Request"})


async def _body(request: Request) -> bytes | None:
    """The request body, or None when it is longer than MAX_BODY, which is then never read in full."""
    if int(request.headers.get("content-length", 0)) > MAX_BODY:
        return None
    body = bytearray()
    async for chunk in request.stream():  # a body sent without its length stops being read at the limit
        body += chunk
        if len(body) > MAX_BODY:
            return None
    return bytes(body)


@app.get("/suggest")
def suggest(q: str = "", diacritics: Literal["on", "off"] = "on") -> list[str]:
    """Autocomplete for the Word field: vocalized forms that complete the typed word."""
    return [] if len(q) > views.MAX_QUERY else dictionary().suggest(q, diacritics == "on")


@app.get("/text", response_class=HTMLResponse)
def text(q: str = "") -> HTMLResponse:
    """The Text view. q carries the words the Word page hands over, no more than a lookup holds,
    so a passage never travels in an address; a passage typed here is posted."""
    if len(q) > views.MAX_QUERY:
        state = views.State(f"A link brings at most {views.MAX_QUERY} characters to the Text view. Paste longer text into the box.")
        return _text_view("", state, None)
    return _analyse(q)


@app.post("/text", response_class=HTMLResponse)
async def analyse(request: Request, hx_request: Annotated[str | None, Header()] = None) -> HTMLResponse:
    body = await _body(request)
    if body is None:
        state = views.State(f"Your text is too long. Analyse at most {views.MAX_TEXT:,} characters at a time: shorten it and try again.")
        return _text_view("", state, hx_request)
    # ponytail: parsed by hand; FastAPI's Form() would add python-multipart for this one field.
    form = parse_qs(body.decode(errors="replace"))
    return _analyse(form.get("text", [""])[0], hx_request)


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return str(views.about_page())
