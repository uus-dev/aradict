"""The AraDict web app."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header
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


@app.get("/", response_class=HTMLResponse)
def word(q: str = "", hx_request: Annotated[str | None, Header()] = None) -> HTMLResponse:
    q = q.strip()
    status_code = 200
    if not q:
        state = views.INITIAL
    elif len(q) > MAX_QUERY:
        state = views.State(f"That's too long. Type at most {MAX_QUERY} characters.")
    elif not any(c.isalpha() for c in q):
        state = views.State("Type a word: letters, not only numbers or symbols.")
    else:
        try:
            readings = dictionary().lookup_ar(q)
        except Exception:
            logger.exception("Lookup failed")  # the query stays out of the log
            state, status_code = views.FAILURE, 500
        else:
            state = views.found(q, readings) if readings else views.not_found(q)
    page = views.live_results(state) if hx_request else views.word_page(q, state)
    headers = {"Vary": "HX-Request"}
    if hx_request and not q:
        headers["HX-Push-Url"] = "/"  # a cleared live lookup returns to "/", not "/?q="
    return HTMLResponse(str(page), status_code, headers)


@app.get("/text", response_class=HTMLResponse)
def text() -> str:
    return str(views.text_page())


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return str(views.about_page())
