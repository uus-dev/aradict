# Spike: CAMeL Tools against the PRD's reference cases

Run on 2026-11-07 with camel-tools 1.6.0 on Python 3.13, against `calima-msa-r13` 0.4.0 (SHA-256 `195bc25a…dd70`). Torch and transformers were left out, because the analyzer and generator don't need them. The spike script was throwaway and is not committed.

## Verdict

**CAMeL is a good fit for the core.** It gives the right readings for every reference case, and it already handles most of the spelling variants the PRD asks for. It is fast enough to run as a simple server process.

AraDict still has to build four things on top:

1. diacritic filtering;
2. collapsing raw analyses into the readings a user sees;
3. turning CAMeL's composite gloss into natural English;
4. a rule layer for verb moods and imperatives in the Milestone 3 conjugation tables.

None of these blocks the plan.

## Reference cases

| Input | Raw analyses | Distinct readings¹ | Notes |
|---|---|---|---|
| كتب | 8 | 3 | he wrote, it was written, books (the same three readings as Aratools). The 8 raw analyses include case-ending variants of كُتُب. |
| وبكتابهم | 36 | 9 | book, kuttab and authors × three readings of وَ ("and", "while", and a bare particle). Aratools shows 3. The gloss is already composite: `and_+_by;with+book+their`. |
| سيكتبون | 4 | 4 | Measures I and IV, active and passive, the same as Aratools. |
| استخدم | 5 | 5 | Measure X, including the imperative "use". The pattern ٱِسْتَ1ْ2َ3 gives X directly. |
| مدرستي | 10 | 6 | school or teacher, each as "my", dual, and "my two". The gloss "two school" has the same flaw as Aratools. |
| الى | 11 | 6 | Includes إِلَى "to; towards". Also آلي "mechanical", آل + my, and آلَى "promise". |
| root ك.ت.ب | — | 32 lemma+POS pairs | All measures present (I, III, IV, VI, VII, VIII, X) with patterns. |

¹ Grouped by lemma, POS, clitics, and agreement. Case and mood endings are ignored.

## Normalization and diacritics

| Behaviour | CAMeL default | What AraDict must add |
|---|---|---|
| Tatweel (كـتـب) | handled; same results as كتب | nothing |
| Final ه for ة (مدرسه) | handled; same results as مدرسة | nothing (the PRD's "rank the exact match first" still applies) |
| Bare ا vs أ/إ/آ | **symmetric**: اكل, أكل and آكل give identical results | a filter that keeps only matching hamza when the input has a hamza, to meet the PRD's one-way rule |
| Persian ی / ک | **not** handled: كتابی gives 1 odd analysis, كتابي gives 13 | map ی→ي and ک→ك before analysis |
| Input diacritics | **ignored**: كَتَبَ gives the same 8 analyses as كتب | the diacritic filter: drop analyses whose vocalization conflicts with a typed diacritic |
| Unknown words | `backoff='NONE'` returns nothing; `NOAN_PROP` guesses a proper noun | use NONE; show the unknown-word state |

## Presentation work the data doesn't do for us

- **Collapsing readings.** Raw analyses repeat each reading for every case or mood ending. They also split the conjunction وَ into three readings (conjunction, "while", particle). The Word view should show one row per reading, so `وبكتابهم` would show 3 rows (or 3 rows with "and/while" folded together), not 36 analyses.
- **Gloss wording.** CAMeL glosses use underscores, `+` separators, and bracketed tags (`books+[def.acc.]`, `write+he;it_<verb>`). AraDict needs a formatter to produce "and by/with their book" and "he/it wrote", and to drop or translate the case tags. All the needed material is in the analysis: proclitics, enclitic, aspect, person, gender, and number.

## Milestone 3 generator check (lemma كَتَب and كِتاب)

- **Nouns: complete.** Every case (nominative, accusative, genitive) × state (indefinite, definite) × number (singular, dual, plural) generated correctly. For example كِتاباً, الكِتابَيْنِ, الكُتُبِ. The definite form needs `prc0:Al_det`.
- **Perfect tense: complete.** كَتَبَ, كَتَبَت, كَتَبْتَ, كَتَبْتُ, كَتَبُوا, كَتَبْنَ, كَتَبا, كَتَبْنا.
- **Imperfect: partly.** The database codes most persons with an unmarked mood (يَكْتُب, تَكْتُب, أَكْتُب, no final vowel). Indicative is generated only where the suffix differs (تَكْتُبِينَ, يَكْتُبانِ, يَكْتُبُونَ). Subjunctive and jussive come back empty.
- **Imperative: empty** for كَتَب, though the analyzer does know some imperative stems (for example استخدم).
- **Consequence:** conjugation tables need a small, deterministic rule layer. It adds the ending vowels (ُ / َ / ْ) to unmarked forms, swaps نَ-suffixed forms for their subjunctive/jussive counterparts, and builds the imperative from the jussive. Where Milestone 2 has a Wiktionary conjugation table, it can serve as a cross-check or fallback. Without the rule layer, most verb table cells would be empty.

## Performance (laptop, Apple silicon)

- Loading the database for analysis and generation: 0.9 s.
- Analysis: **0.27 ms per word**, uncached, over 500 words of news text.
- Peak memory: about 430 MB with both analysis and generation loaded. A 1 GB server instance is enough. Analysis alone should be lower; not measured.

## Suggested PRD adjustments

1. **Word UI:** state that case and mood endings aren't shown as separate results, and that readings differing only in how a proclitic is read (وَ as "and" or "while") are shown as one row.
2. **Conjugation tables (Milestone 3):** replace "Cells the generator cannot produce are shown empty" with "mood endings and imperatives are produced by a rule layer over the generator's output and checked against Wiktionary; cells still unknown are shown empty".
3. **Arabic matching:** note that tatweel and final ه/ة are handled by the analyzer, and that the hamza one-way rule, diacritic filtering, and Persian letters are AraDict's own pre- and post-processing.
