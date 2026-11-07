# Data license findings: Aratools GPL redistributable package

Checked: 2026-11-07. This is an engineering read of the license texts and provenance, not legal advice.

## Verdict

**AraDict can use the package, under GPL version 2 only.**

- Six of the files are Tim Buckwalter's *Buckwalter Arabic Morphological Analyzer 1.0* (BAMA 1.0) lexicon. LDC released it under GPLv2.
- The seventh file is an Aratools annotation layer derived from that lexicon. It points to the same license.

There are three catches:

1. The license is **v2 only**, not "v2 or later". That limits which licenses AraDict's own code and bundled dependencies can use.
2. The annotation layer is a **2015 snapshot**. It is much thinner than what the live Aratools site shows today, which affects the parity expectations in the PRD.
3. The live site's presentation logic (composed glosses, descriptions of prefix and suffix POS) is **not in the package**. AraDict has to build that itself.

## What is in the package

Package: `GPL.Redistributable.zip`, 2,613,964 bytes, SHA-256 `97d5bba0124f56c934473046994f379714a4d43d59e43e96b094d98ba4385991`, last modified 2024-09-25.

| File | Entries | Origin | License statement in file |
|---|---|---|---|
| `dictprefixes` | 299 | BAMA 1.0, unmodified | GPL "version 2"; © 2002 QAMUS LLC, © 2002 Trustees of the University of Pennsylvania |
| `dictsuffixes` | 618 | BAMA 1.0, unmodified | same |
| `dictstems` | 82,158 stems / 38,600 lemmas | BAMA 1.0 plus 4 one-line fixes | same |
| `tableab` (prefix–stem) | 1,648 | BAMA 1.0, unmodified | same |
| `tableac` (prefix–suffix) | 598 | BAMA 1.0, unmodified | same |
| `tablebc` (stem–suffix) | 1,285 | BAMA 1.0, unmodified | same |
| `aratools/stems.x` | 82,160 rows | Aratools annotation layer, dated 2015-06-28 | "Derived from work copyright Qamus LLC and Trustees of the University of Pennsylvania. Additions copyright A. Lynum. See gpl.txt for license details." |
| `gpl.txt` | | GNU GPL text, **Version 2, June 1991** | |
| `GPL.redistributable.txt` | | Aratools README | names the six BAMA files as the GPL components and points to LDC, a hunspell patch, and the nongnu aramorph project as other sources |

### Provenance checks

- **Counts match the LDC catalog.** The entry and lemma counts are exactly those in the LDC catalog entry for BAMA 1.0 (LDC2002L49). That entry states the release is under GNU GPL version 2.
- **Five files match an independent copy byte for byte.** The pyaramorph 0.2 package on PyPI (license GPLv2) carries its own copy of BAMA 1.0. Five of the six files are byte-identical to it.
- **`dictstems` differs in four lines.** Each change fixes a morphological-category typo that otherwise makes a stem unreachable through the compatibility tables:
  - `IV_0_Passyu` → `IV_0_Pass_yu` (ntdY)
  - `#mnTwq` → `mnTwq` (an entry that was commented out is re-enabled)
  - `IV_Pass` → `IV_Pass_yu` (ntqd)
  - `IV_0Pass_yu` → `IV_0_Pass_yu` (ntwY)
- **The license is v2 only.** Every BAMA file header and the LDC readme say "as published by the Free Software Foundation version 2", with no "or later" clause.
- **`stems.x` lines up with the BAMA stems.** All 82,158 BAMA stem rows appear in `stems.x` in the same order (same form, vocalized form, and category). `stems.x` is an annotation layer on top of `dictstems`, not a separate lexicon.

## What `stems.x` adds

There are 14 tab-separated columns:

1. numeric stem id (the same id space as the live API's `id.stem`)
2. unvocalized form
3. vocalized form
4. BAMA category
5. category id
6. gloss
7. Buckwalter POS
8. short POS
9. plain-English POS ("Perfect tense verb")
10. lemma id
11. root (Buckwalter transliteration)
12. measure
13. unused (empty in every row)
14. unused (empty in every row)

### Coverage in the published snapshot

- **Root:** present on 72,502 of 82,160 rows (88%).
- **Measure:** present on 6,178 of 31,797 verb rows (19.4%). It appears on the first row of a verb lemma only. Only measures I, II, III, V, and VI occur; there is no IV, VII, VIII, IX, or X. For example, استخدم (Form X) has no measure in the package, but the live site shows "X".
- **Missing entirely:** composed whole-word glosses ("and by/with their book"), plain-English descriptions of prefixes and suffixes ("Conjunction, preposition, …, suffixed possessive pronoun (3. person, male, plural)"), and information tags. These come from Aratools' private `aratools-core` code. Its license is not published.

**Gap to the live site.** The Aratools blog says that since 2024-11-05 every verb has a measure. The live API returns measures such as IV, VII, VIII, and X. So the published package is older than the data the live site and apps use.

## Implications for AraDict

1. **License AraDict's code so that it is compatible with GPLv2-only.**
   - Simplest: **GPL-2.0-or-later** for AraDict code, with the data files kept under GPL-2.0-only and their original notices intact. Any combined distribution is then GPLv2.
   - Not compatible with GPLv2-only: GPL-3.0-only, AGPL-3.0, and Apache-2.0. Such code must not end up in one distributed work with the data, for example a browser bundle that embeds the lexicon.
   - Permissive licenses (MIT/BSD) are compatible.
2. **Committing the data to the public repo counts as distribution, and that is fine.** Keep `gpl.txt` and the copyright headers. Any file AraDict changes (gloss fixes, added measures) must carry a prominent notice of the change and its date (GPLv2 §2(a)). A change log in the data directory satisfies this.
3. **Server-side lookup creates no source obligation. Client-side lookup does.** GPLv2 has no network clause. Serving lookups from a server is not distribution. Shipping the lexicon to browsers (offline or client-side lookup) is distribution, so the corresponding source must be offered. That is easy if the repo is public and GPL-licensed.
4. **Proprietary use needs a separate license.** The LDC catalog sends commercial licensing to QAMUS LLC. Selling the service is allowed under the GPL. A closed-source AraDict, for example a proprietary native app that embeds the data, would need a QAMUS license.
5. **Measures must be derived (or the current data obtained).** With 19% verb coverage, the PRD's measure display and the "root ordered by measure I–X" requirement can't be met from the package alone. There are two options:
   - **Derive measures** from the vocalized stem pattern and the root. This is deterministic for most verbs; for example `{isotaCoCaC` gives Form X. It's a well-bounded task and can be checked against the live site's output for a sample.
   - **Ask the author** (A. Lynum, support@aratools.com) for the current `stems.x` under GPLv2. The apps ship this data, and GPLv2 §3 entitles anyone who receives those binaries to the corresponding source.
   
   Recommendation: derive measures first, and ask the author in parallel.
6. **Build the presentation layer independently.** Compose glosses and POS descriptions from the BAMA prefix and suffix entries, which have their own glosses and POS tags. Don't copy `aratools-core` output strings. This supports the PRD rule that test assertions are written by hand rather than taken from captured live responses.
7. **Expected values in the PRD's reference cases.** Cases that depend on post-2015 data, such as measure X for استخدم or the full root-ordering list for كتب, hold only once measures are derived. Mark them so.

## Sources

- LDC catalog entry for BAMA 1.0 (LDC2002L49): https://catalog.ldc.upenn.edu/LDC2002L49
- LDC BAMA 1.0 readme: https://catalog.ldc.upenn.edu/docs/LDC2002L49/readme.txt
- pyaramorph 0.2 (independent BAMA 1.0 copy, GPLv2): https://pypi.org/project/pyaramorph
- Aratools GPL package: https://aratools-public.ams3.cdn.digitaloceanspaces.com/GPL.Redistributable.zip
- Aratools blog post on measure coverage (2024-11-05): https://aratools.mataroa.blog/blog/improved-verb-formmeasure-coverage/
