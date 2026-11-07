# Data sources survey: what AraDict can build on

Checked: 2026-11-07. This is an engineering read of licenses and contents, not legal advice. It follows on from `DATA-LICENSE-FINDINGS.md`, which covers the Aratools GPL package.

## Verdict

AraDict doesn't need to be limited to what Aratools has. The recommended stack:

1. **Core analyzer and lexicon:** the CAMeL Tools `calima-msa-r13` morphology database, licensed GPL v2. It is built on the same Buckwalter 1.0 base as Aratools, with much more annotation on every stem. It replaces the Aratools package outright.
2. **Rich entries and modern vocabulary:** English Wiktionary, using the kaikki.org extraction, licensed CC BY-SA 4.0 / GFDL. It is kept as a **separate** dataset and linked at runtime.
3. **Reading in context (Text view):** CAMeL Tools disambiguators. The MLE model is GPL v2; the BERT model is MIT.
4. **Example sentences:** Tatoeba Arabic–English pairs, licensed CC BY 2.0 FR.

Everything below in "Rejected or deferred" is either paid and not redistributable, or has an unverified license.

## 1. CAMeL Tools `calima-msa-r13`: recommended core

- **What it is.** The NYU Abu Dhabi CAMeL Lab's MSA morphology database, "derived from Aramorph 1.2.1", the Java port of Buckwalter 1.0. The package carries a GPL **version 2** notice and the full GPLv2 text.
  - The CAMeL Tools code (analyzer, generator, reinflector, tokenizers, transliterators) is **MIT**.
  - Package: `morphology_db_calima-msa-r13-0.4.0.zip`, from camel-tools-data release 2022.03.21. The database file is 40.5 MB, SHA-256 `195bc25a…dd70`.
  - The camel-tools-data repo is still active; its latest release is dated 2026-06-08.
- **Size.**
  - 72,734 stem entries (Arabic script, alif-normalized), covering 39,820 distinct lemma+POS pairs and 4,924 roots.
  - 452 prefix entries and 828 suffix entries, which are more detailed than Buckwalter's 299/618 splits.
  - The same three compatibility tables (1,648 / 1,285 / 598 entries).
- **Features present on 100% of stems:**

  | Group | Features |
  |---|---|
  | Form and identity | vocalized form, lemma, Buckwalter tag, English gloss, POS (fine-grained, e.g. `noun_prop`, `adj_comp`) |
  | **Morphology** | root, pattern (vowel template) |
  | Inflection | person, aspect, voice, mood, state, case |
  | Gender and number | form-based and **functional**, which handles broken plurals correctly |
  | **Other annotation** | rationality, CAPHI phonetic transcription, **lemma and POS log-probabilities (frequency)**, UD and CATiB6 POS, 7 tokenization schemes |
- **What this fixes compared with the Aratools package:**
  - **Verb measures (I–X).** Derivable from `pattern` for every verb. A rough 30-line heuristic already mapped 90.2% of the 9,172 verb lemmas, for example ٱِسْتَ1ْ2َ3 → X. Most of the remainder are four-letter verbs (QI/QII), which fall outside I–X anyway. The Aratools package covers 19% of verb rows.
  - **Roots on every stem** (Aratools: 88%).
  - **Frequency-ranked results and autocomplete** from `lex_logprob`.
  - **Pronunciation display** from CAPHI.
  - **Correct gender and number for broken plurals.**
  - **Conjugation and declension tables** through CAMeL's generator. This is a new feature the reference doesn't have.
- **Known gaps:**
  - The lexical coverage and glosses are still Buckwalter's from 2002. Glosses use `_` for spaces.
  - 38% of stems have `#` placeholders in the root for weak or hamza radicals (for example `ش.#.ش` for شاشة). These need resolving from Wiktionary or a rule set.
  - Words from after about 2010 are missing (see the probe below).
- **Licence fit:** the same GPL v2 regime as the Aratools package, so nothing new is needed beyond what `DATA-LICENSE-FINDINGS.md` already covers.
- **Architecture consequence:** CAMeL Tools is Python. Either the backend runs Python, or AraDict reimplements the lookup (the database format is plain text and documented) in its own stack. The second keeps the analyzer and data GPL-only, with no MIT-code dependency needed.

## 2. English Wiktionary via kaikki.org: recommended enrichment layer

- **What it is.** A structured extraction of English Wiktionary's Arabic entries.
  - Wiktionary text is dual-licensed under **CC BY-SA 4.0** and **GFDL 1.1 or later**.
  - The kaikki.org extraction is dated 2026-10-30, from the 2026-10-01 dump. It is JSONL, 828 MB for Arabic.
- **Size, from the Wiktionary API:**
  - 23,650 Arabic lemma pages: 14,356 nouns, 5,862 verbs, 3,994 adjectives.
  - 157,911 non-lemma (inflected form) pages.
  - 750 entries with audio pronunciation.
  
  That is fewer lemmas than Buckwalter, but each entry is far richer.
- **What an entry has** (sampled: كتاب):
  - vocalized headword, transliteration, and IPA, including regional variants;
  - root;
  - plurals (كُتُب; كَتَاتِيب for كُتَّاب) and gender;
  - **numbered senses** (8 for كتاب, including "book", "letter", "Scripture", "marriage contract");
  - etymology, derived terms (كِتَابِيّ، كُتَيِّب), declension forms, and descendants.
- **Value for AraDict:**
  - multiple senses where Buckwalter gives one gloss;
  - plurals and verbal nouns;
  - modern vocabulary (تغريدة "tweet" is a Wiktionary lemma; Buckwalter only has a proper name and "twittering;warbling");
  - IPA and audio;
  - the root for weak radicals (to fill CAMeL's `#` placeholders);
  - a check on generated conjugation tables.
- **License caution:** CC BY-SA 4.0 and GFDL are **not compatible with GPL v2-only**.
  - Never merge Wiktionary content and Buckwalter/CAMeL data into one distributed file or database. Keep them as separate datasets, joined at runtime by vocalized lemma. This is "mere aggregation" under the GPL.
  - On every page that shows Wiktionary content, attribute it ("From Wiktionary, CC BY-SA 4.0", with a link to the entry). Adapted Wiktionary text stays CC BY-SA.

## 3. CAMeL disambiguators: reading in context

- `disambig-mle-calima-msa-r13`: a maximum-likelihood model, **GPL v2**, 89 MB, built on the same database.
- `disambig-bert-unfactored-msa`: a BERT-based model, catalogue license **MIT**, release 2026-06-08. Check the license of any upstream model weights it pulls in before shipping.
- **Value:** the Text view could rank or highlight the *likely* analysis of each word in its sentence, instead of listing every reading equally. Aratools doesn't do this. The current PRD lists it as out of scope.
- **Cost:** a Python inference service on the server. BERT needs PyTorch and more memory. MLE is lightweight.

## 4. Tatoeba: example sentences

- About 30,852 unique Arabic–English sentence pairs, counted from the OPUS-derived Hugging Face mirror; the live Tatoeba export may be larger. Licensed CC BY 2.0 FR.
- Each sentence must be attributed to its author.
- **Value:** "Examples" under a result, matched by lemma, using the analyzer over the Arabic side.

## Probe: modern vocabulary in the Buckwalter base

These results come from the live Aratools API, which uses the same Buckwalter base.

| Word | Buckwalter analysis | Wiktionary |
|---|---|---|
| إنترنت | Internet | lemma |
| شاشة | screen | lemma |
| عولمة | globalization | (missing) |
| تغريدة | **not found** (only تغريد "twittering; warbling" exists) | lemma ("tweet") |
| كورونا | **wrong** ("they roll up; wind us") | (missing) |
| بودكاست | **not found** | (missing) |
| إنستغرام | **not found** | not checked |

The base covers news vocabulary up to about 2002 well. Newer terms need Wiktionary or AraDict's own additions. Any additions go into AraDict's own data file under GPL v2 with a change note.

## Rejected or deferred

| Source | Why not (now) |
|---|---|
| **SAMA 3.1** (LDC2010L01; 40,654 lemmas; the successor to BAMA 2.0) | LDC license agreement, members-only, fee required, not redistributable. CAMeL's `msa-s31` database requires it. |
| **BAMA 2.0** (LDC2004L02) | Under the LDC "BAMA Agreement", not GPL; members-only. |
| **Qabas** (Birzeit SinaLab; about 58K lemmas linked to 110 lexicons) | License unconfirmed: sources disagree between CC BY 4.0 and CC BY-NC 4.0. The site was unreachable on 2026-11-07. It has no English glosses of its own. Revisit later. |
| **ElixirFM** | Code is GPL v3, which is incompatible with GPLv2-only if combined; the lexicon license is not stated; the project is dormant. |
| **Arramooz / Qalsadi** (Taha Zerrouki) | GPL. Arabic-only (no English glosses). Could supply Arabic features such as transitivity; low priority. |
| **AlKhalil Morpho Sys 2** | License not stated on the project pages. Arabic-only output. |
| **Hans Wehr** and other commercial dictionaries | Copyrighted. Not usable. |
| **Aratools' current (post-2015) data** | Not published. It could be requested from the author under GPL v2 §3, but CAMeL already gives measures and roots, so this is now optional. |

## What this would change in the PRD

- **Dictionary source:** CAMeL `calima-msa-r13` instead of the Aratools package. Wiktionary becomes a separate enrichment layer with its own attribution rules.
- **New in scope (optional):**
  - conjugation and declension tables (CAMeL generator);
  - multiple senses, plurals, IPA and audio (Wiktionary);
  - frequency ranking (CAMeL);
  - example sentences (Tatoeba);
  - likely-reading highlighting in the Text view (CAMeL disambiguator; currently out of scope).
- **Reference test cases:** measure and root expectations become achievable from the data on day one.

## Sources

- CAMeL Tools (code, MIT): https://github.com/CAMeL-Lab/camel_tools
- CAMeL Tools data catalogue (per-package licenses): https://raw.githubusercontent.com/CAMeL-Lab/camel-tools-data/main/catalogue-1.6.json
- calima-msa-r13 package: https://github.com/CAMeL-Lab/camel-tools-data/releases/download/2022.03.21/morphology_db_calima-msa-r13-0.4.0.zip
- kaikki.org Arabic: https://kaikki.org/dictionary/Arabic/index.html
- Wiktionary copyrights: https://en.wiktionary.org/wiki/Wiktionary:Copyrights
- Wiktionary category API counts: https://en.wiktionary.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Arabic_lemmas
- SAMA 3.1: https://catalog.ldc.upenn.edu/LDC2010L01
- BAMA 2.0: https://catalog.ldc.upenn.edu/LDC2004L02
- Qabas paper: https://arxiv.org/html/2406.06598v1
- Tatoeba EN–AR mirror: https://huggingface.co/datasets/ymoslem/Tatoeba-EN-AR
- ElixirFM: https://github.com/otakar-smrz/elixir-fm
- Arramooz: https://github.com/linuxscout/arramooz
- AlKhalil: https://alkhalil.oujda-nlp-team.net/AlKhalil-MorphoSys.php
