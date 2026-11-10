"""The AraDict web app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

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
def word(q: str = Query("", max_length=100)) -> str:
    q = q.strip()
    return str(views.word_page(q, dictionary().lookup_ar(q) if q else None))


@app.get("/text", response_class=HTMLResponse)
def text() -> str:
    return str(views.text_page())


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return str(views.about_page())
