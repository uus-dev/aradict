"""The AraDict web app."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import parse_qs

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import views
from .data import db_path
from .dictionary import Dictionary

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def dictionary() -> Dictionary:
    return Dictionary(db_path())


@asynccontextmanager
async def lifespan(app: FastAPI):
    dictionary()  # load at startup, so a missing database fails loudly before the first request
    yield


app = FastAPI(title="AraDict", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


MAX_QUERY = 100


FAMILY = ("root", "related", "pos", "sort")  # the URL parameters of a root or related-forms view


@app.get("/", response_class=HTMLResponse)
def word(
    request: Request,
    q: str = "",
    diacritics: Literal["on", "off"] = "on",
    root: str | None = None,
    related: str | None = None,
    pos: str = "",
    sort: str = "",
    hx_request: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    """A lookup, or with root or related (and pos) a root's words or a lemma's forms in its place,
    sorted by sort. The lookup's own URL parameters go with every root and related-forms link, so
    their view can return to it."""
    lookup = {key: value for key, value in request.query_params.items() if key not in FAMILY}
    q, filter_diacritics = q.strip(), diacritics == "on"
    status_code = 200
    try:
        if root is not None:
            state = views.root_view(root, dictionary().root_family(root), lookup, sort)
        elif related is not None:
            state = views.related_view(related, pos, dictionary().related(related, pos), lookup, sort)
        elif not q:
            state = views.INITIAL
        elif len(q) > MAX_QUERY:
            state = views.State(f"That's too long. Type at most {MAX_QUERY} characters.")
        elif not any(c.isalpha() for c in q):
            state = views.State("Type a word: letters, not only numbers or symbols.")
        else:
            arabizi = dictionary().arabizi(q)  # None unless q is Arabizi
            readings = dictionary().lookup_ar(arabizi or q, filter_diacritics)
            forms = {lemma: len(dictionary().related(*lemma)) for lemma in {(r.lemma, r.pos) for r in readings}}
            state = views.looked_up(q, readings, arabizi, views.Links(lookup, forms))
    except Exception:
        logger.exception("Lookup failed")  # the query stays out of the log
        state, status_code = views.FAILURE, 500
    page = views.live_results(state) if hx_request else views.word_page(q, state, filter_diacritics)
    headers = {"Vary": "HX-Request"}
    if hx_request and not q:
        # A cleared live lookup returns to "/", not "/?q=", keeping the diacritics switch.
        headers["HX-Push-Url"] = "/" if filter_diacritics else "/?diacritics=off"
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
        except Exception:
            logger.exception("Text analysis failed")  # the passage stays out of the log
            state, status_code = views.TEXT_FAILURE, 500
    page = views.live_analysis(state) if hx_request else views.text_page(text, state)
    return HTMLResponse(str(page), status_code, {"Vary": "HX-Request"})


@app.get("/suggest")
def suggest(q: str = "", diacritics: Literal["on", "off"] = "on") -> list[str]:
    """Autocomplete for the Word field: vocalized forms that complete the typed word."""
    return dictionary().suggest(q, diacritics == "on")


@app.get("/text", response_class=HTMLResponse)
def text(q: str = "") -> HTMLResponse:
    """The Text view. q carries the words the Word page hands over; a passage typed here is posted."""
    return _analyse(q)


@app.post("/text", response_class=HTMLResponse)
async def analyse(request: Request, hx_request: Annotated[str | None, Header()] = None) -> HTMLResponse:
    # ponytail: parsed by hand; FastAPI's Form() would add python-multipart for this one field.
    form = parse_qs((await request.body()).decode(errors="replace"))
    return _analyse(form.get("text", [""])[0], hx_request)


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return str(views.about_page())
