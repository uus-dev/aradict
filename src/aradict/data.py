"""Download and verify the pinned CAMeL calima-msa-r13 morphology database.

The database is licensed GPL v2 (see DATA-SOURCES.md) and is never committed. Run
`python -m aradict.data` to fetch it, or start the app with `aradict`, which fetches it first.
"""

from __future__ import annotations

import io
import os
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

URL = "https://github.com/CAMeL-Lab/camel-tools-data/releases/download/2022.03.21/morphology_db_calima-msa-r13-0.4.0.zip"
EXPECTED = {
    "morphology.db": "195bc25a333237a2126470da888d7936b59ed3729f9210e0a4194ba43497dd70",
    "LICENSE": "7a71f85f07e46759dcc1c16dba64352d9932447759cf71ca3deae3729d85d23e",
}
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "calima-msa-r13"


def db_path() -> Path:
    """The database file the app reads; override with ARADICT_DB_PATH."""
    return Path(os.environ.get("ARADICT_DB_PATH", DEFAULT_DIR / "morphology.db"))


def _verified(directory: Path) -> bool:
    return all(
        (directory / name).is_file() and sha256((directory / name).read_bytes()).hexdigest() == digest
        for name, digest in EXPECTED.items()
    )


def ensure_db(directory: Path = DEFAULT_DIR) -> Path:
    """Download the pinned database into `directory` unless a verified copy is already there."""
    if _verified(directory):
        return directory / "morphology.db"
    print(f"Downloading the CAMeL calima-msa-r13 database to {directory} …", flush=True)
    with urlopen(URL, timeout=120) as response:
        archive = ZipFile(io.BytesIO(response.read()))
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest in EXPECTED.items():
        contents = archive.read(name)
        actual = sha256(contents).hexdigest()
        if actual != digest:
            raise RuntimeError(f"Checksum mismatch for {name}: expected {digest}, got {actual}. Nothing was installed.")
        (directory / name).write_bytes(contents)
    print("Database verified.", flush=True)
    return directory / "morphology.db"


if __name__ == "__main__":
    ensure_db()
