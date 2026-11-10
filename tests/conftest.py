import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
