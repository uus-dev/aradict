"""The AraDict web app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import views
from .data import db_path
from .dictionary import Dictionary


@lru_cache(maxsize=1)
def dictionary() -> Dictionary:
    return Dictionary(db_path())


@asynccontextmanager
async def lifespan(app: FastAPI):
    dictionary()  # load at startup, so a missing database fails loudly before the first request
    yield


app = FastAPI(title="AraDict", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def word(q: str = Query("", max_length=100), diacritics: Literal["on", "off"] = "on") -> str:
    q, filter_diacritics = q.strip(), diacritics == "on"
    return str(views.word_page(q, dictionary().lookup_ar(q, filter_diacritics) if q else None, filter_diacritics))


@app.get("/text", response_class=HTMLResponse)
def text() -> str:
    return str(views.text_page())


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return str(views.about_page())
