import os
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from aradict.app import app, dictionary
from aradict.data import db_path
from make_fixture_db import make_fixture


@pytest.fixture(scope="session")
def real_db() -> Path:
    path = db_path()
    if not path.is_file():
        if os.environ.get("CI"):
            pytest.fail(f"No CAMeL database at {path}")
        pytest.skip("CAMeL database not downloaded; run `uv run python -m aradict.data`")
    return path


@pytest.fixture(scope="session")
def fixture_db(real_db, tmp_path_factory) -> Path:
    return make_fixture(real_db, tmp_path_factory.mktemp("db") / "morphology.db")


@pytest.fixture(scope="session")
def fixture_env(fixture_db):
    """Point the app at the fixture database for the whole session."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ARADICT_DB_PATH", str(fixture_db))
        dictionary.cache_clear()
        yield fixture_db
    dictionary.cache_clear()


@pytest.fixture
def client(fixture_env):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def base_url(fixture_env):
    """A real server on the fixture database, for browser journeys: one per test module."""
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
    """Chromium, shared by a test module's journeys."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()
