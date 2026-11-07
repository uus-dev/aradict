# AraDict

A modern, mobile-friendly Arabic–English dictionary for Modern Standard Arabic. You can paste any inflected word, with or without vowel marks, and see every possible reading, with its vocalized form, its English meaning, the grammar, its root, and its verb measure. From any reading you can explore the root and related forms. You can also analyze whole passages word by word.

**Status:** specification stage. There is no application code yet.

## Documents

- [PRD.md](PRD.md): the product requirements, also tracked as [issue #1](https://github.com/uus-dev/aradict/issues/1).
- [DATA-SOURCES.md](DATA-SOURCES.md): the survey of dictionary data and analyzers, and why CAMeL Tools plus Wiktionary was chosen.
- [DATA-LICENSE-FINDINGS.md](DATA-LICENSE-FINDINGS.md): the license and provenance check of the Aratools GPL data package.

## License

Copyright (C) 2026 the AraDict contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 2 of the License, or (at your option) any later version. See [LICENSE](LICENSE) for the full GPL version 2 text.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY, without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

Dictionary data that AraDict will use is not stored in this repository and keeps its own licenses:

- The CAMeL Tools MSA morphology database (`calima-msa-r13`) is licensed under GPL version 2. It is derived from the Buckwalter Arabic Morphological Analyzer 1.0, portions (c) 2002 QAMUS LLC and (c) 2002 Trustees of the University of Pennsylvania.
- English Wiktionary content (planned for Milestone 2) is licensed under CC BY-SA 4.0 and GFDL. It is kept as a separate dataset and credited wherever it is shown.
