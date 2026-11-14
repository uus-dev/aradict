# AraDict

A modern, mobile-friendly Arabic–English dictionary for Modern Standard Arabic. You can paste any inflected word, with or without vowel marks, and see every possible reading, with its vocalized form, its English meaning, the grammar, its root, and its verb measure. From any reading you can explore the root and related forms. You can also analyze whole passages word by word.

**Status:** early development. Arabic word lookup works end to end; the rest of [Milestone 1](https://github.com/uus-dev/aradict/milestone/1) is in progress.

## Run locally

You need [uv](https://docs.astral.sh/uv/). From a fresh clone, one command installs everything, downloads and verifies the dictionary database (about 40 MB, into `data/`), and starts the app at http://127.0.0.1:8000:

```sh
uv run aradict
```

To use a database stored elsewhere, set `ARADICT_DB_PATH` to its `morphology.db`. Set `PORT` to use another port.

### Wiktionary senses (optional)

Entries can also show English Wiktionary's senses, plurals, gender, verbal nouns, relations and pronunciation. They come from a pinned kaikki.org extraction, kept as a dataset of its own. One command downloads the extraction (about 870 MB, into `data/wiktionary/`), checks it against its pinned SHA-256 and builds the dataset (`data/wiktionary/wiktionary.db`):

```sh
uv run python -m aradict.wiktionary
```

To build from a copy you already downloaded, pass its path: `uv run python -m aradict.wiktionary path/to/kaikki.org-dictionary-Arabic.jsonl`. To use a dataset stored elsewhere, set `ARADICT_WIKTIONARY_PATH`. Without the dataset, the app works as before.

kaikki.org replaces the extraction at the same URL when it publishes a new one. The build then stops and says how to move the pin in `src/aradict/wiktionary.py`.

When a new version of AraDict keeps more from the extraction, the app refuses a dataset an older version built and says so at startup. Run the same command again to rebuild it.

## Test

```sh
uv run playwright install chromium
uv run pytest
```

Contract tests run against the real database and the real Wiktionary dataset. App and browser tests use a small database that `tests/make_fixture_db.py` builds from it, keeping only a few lemmas, and a small Wiktionary dataset that `tests/make_fixture_wiktionary.py` builds for the same lemmas. Tests that need data you haven't downloaded are skipped.

## Documents

- [PRD.md](PRD.md): the product requirements, also tracked as [issue #1](https://github.com/uus-dev/aradict/issues/1).
- [DATA-SOURCES.md](DATA-SOURCES.md): the survey of dictionary data and analyzers, and why CAMeL Tools plus Wiktionary was chosen.
- [DATA-LICENSE-FINDINGS.md](DATA-LICENSE-FINDINGS.md): the license and provenance check of the Aratools GPL data package.

## License

Copyright (C) 2026 the AraDict contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 2 of the License, or (at your option) any later version. See [LICENSE](LICENSE) for the full GPL version 2 text.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY, without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

Dictionary data is not stored in this repository and keeps its own licenses:

- The CAMeL Tools MSA morphology database (`calima-msa-r13`) is licensed under GPL version 2. It is derived from the Buckwalter Arabic Morphological Analyzer 1.0, portions (c) 2002 QAMUS LLC, (c) 2002 Trustees of the University of Pennsylvania, and portions (c) 2006 Jon Dehdari.
- English Wiktionary content, from kaikki.org's extraction, is licensed under CC BY-SA 4.0 and GFDL. It is kept as a separate dataset, never merged with the GPL data, and credited wherever it is shown.

Bundled assets keep their own licenses: [htmx](https://htmx.org/) 2.0.11 under the Zero-Clause BSD license, and the [Scheherazade New](https://software.sil.org/scheherazade/) font by SIL under the SIL Open Font License. Their license texts are in `src/aradict/static/vendor/`.
