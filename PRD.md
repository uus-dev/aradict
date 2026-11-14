# AraDict: Arabic–English Dictionary Web App

## Problem Statement

Readers of Modern Standard Arabic, especially learners and people reading news, need to understand an inflected word without first identifying its dictionary headword. A plain bilingual word list misses attached prefixes and suffixes, grammatical information, roots, and relationships among words. Readers also need to inspect a passage word by word while retaining its context. The long-used Aratools website offers much of this useful information, but its dense desktop-first presentation makes frequent lookup and mobile reading harder than necessary.

AraDict will be an independently built, modern, mobile-friendly dictionary that preserves this depth of information while making lookup faster and results easier to understand. The goal is a daily-use tool, not a marketing page or a visual copy of Aratools. This is a product specification for AraDict, not a request to copy Aratools branding, source code, or unverified dictionary data.

## Solution

Build a responsive Arabic–English dictionary for Modern Standard Arabic.

- **Lookup.** Users look up Arabic surface forms and English glosses. Results update as the user types.
- **Analyses.** Users see every possible analysis of a word. Each analysis shows:
  - the vocalized form, with the prefix, stem, and suffix visually distinguished;
  - an English gloss for the whole word that includes the meaning of attached prefixes and suffixes;
  - part of speech, root, and verb measure.
- **Diacritics as a filter.** Diacritics the user types narrow the analyses to those consistent with them.
- **Word families.** From any result, users can move to its related forms or to all entries sharing its root.
- **Text.** Users can paste Arabic text and inspect each token's possible analyses in place.
- **Input.** The interface supports Arabic input through an on-screen keyboard and Arabizi (Latin/SMS-style) transliteration.
- **History, states, and layout.** The app keeps a device-local history of recent lookups, gives clear loading and empty states, supports the keyboard throughout, and renders right-to-left Arabic readably alongside left-to-right English.
- **Data.** The first release is built on the CAMeL Tools Arabic morphology database (GPL v2). It gives every stem a root, a vowel pattern (from which the verb measure is derived), and a frequency, so results and suggestions can be ranked by how common a word is.
- **Later milestones.** Milestone 2 adds English Wiktionary entries as a separate, credited layer: multiple meanings, plurals and verbal nouns, pronunciation, and newer vocabulary. Milestone 3 adds verb conjugation and noun/adjective declension tables generated from the morphology database.

Launch as a web application whose home view opens directly on Word lookup, with Text and About/Help available from concise navigation. Keep the search field and current query clear throughout the lookup flow. Present candidate analyses in a visual hierarchy that foregrounds Arabic form and English meaning, then exposes the full grammatical detail without hiding it. Use a mobile-first layout that works with touch, small screens, and the on-screen keyboard. Describe mobile web use honestly; do not imply that AraDict has native apps. Dictionary content must come from a source whose license and attribution requirements have been verified before release.

## User Stories

### Discover and navigate

1. As a first-time visitor, I want to understand what AraDict does from the home page, so that I can choose the right tool.
2. As an Arabic learner, I want a direct route to word lookup, so that I can check a word quickly.
3. As a reader, I want a direct route to text analysis, so that I can inspect a passage without entering words one by one.
4. As a returning visitor, I want navigation among Word (home), Text, and About/Help, so that I can change tasks without losing orientation.
5. As a mobile visitor, I want the same core lookup and text tools in a responsive layout, so that I can use AraDict on my phone.
6. As a visitor, I want each view and each lookup state (query, lookup direction, and any root or related-forms view) to have a stable, shareable URL, so that browser navigation, bookmarks, and shared links reproduce what I saw.
7. As a visitor, I want the current view identified in navigation, so that I know where I am.
8. As a visitor, I want accurate product scope and data attribution, so that I know what AraDict can and cannot provide.

### Enter and find words

9. As an Arabic reader, I want to paste or type an Arabic word as written in my text, so that I do not need to reduce it to a stem first.
10. As an Arabic reader, I want lookup to handle common attached prefixes and suffixes, so that inflected forms return useful analyses.
11. As an Arabic reader, I want any diacritics I type to narrow results to the analyses consistent with them, while undiacritized input returns every analysis, so that I can be exactly as precise as my source text.
12. As an Arabic reader, I want to turn diacritic filtering off, so that I can see every analysis even when my input carries vowel marks.
13. As an Arabic reader, I want hamza, alif, ya/alif maqsura, ta marbuta, shadda, tanween, tatweel (kashida), and Persian/Urdu look-alike letters handled predictably, so that orthographic differences do not cause misleading failures.
14. As an Arabic reader, I want a word-final ه also tried as ة, so that a common informal spelling such as مدرسه still finds "school".
15. As a user who enters several words in the word field, I want to be told that only one word is looked up and offered the Text view, so that words are never silently dropped.
16. As a user without an Arabic hardware keyboard, I want an on-screen keyboard with the standard Arabic layout and a shift layer for diacritics, hamza seats, and lam-alif forms, so that I can enter any Arabic character.
17. As a user without an Arabic keyboard, I want to type Arabizi (for example "ktb", "mar7aba", "3arabi") in Arabic lookup mode and have it converted to Arabic script before lookup, so that I can search with a Latin keyboard.
18. As an Arabizi user, I want to see the Arabic produced from my Latin input, so that I can check what was actually looked up.
19. As a user, I want results to update as I type, with Enter running the lookup immediately, so that searching feels instant and needs no pointer.
20. As a user, I want a clear action for the current query, so that I can start a new lookup quickly.
21. As a user, I want optional autocomplete in supported lookup modes that suggests vocalized dictionary forms, most common first, so that I can find a word with less typing.
22. As a user, I want choosing a suggestion to put its vocalized form in the field and show that exact analysis, and I want duplicate suggestions removed, so that suggestions are precise and uncluttered.
23. As a user, I want autocomplete to keep helping after I type an attached prefix (for example وكتا), so that suggestions do not silently disappear.
24. As a keyboard user, I want to navigate and choose suggestions with arrow keys and Enter, so that autocomplete is accessible.
25. As a user, I want to turn autocomplete off and have that choice remembered, so that suggestions do not interrupt my input.
26. As a user, I want the lookup direction stated beside the field, so that I know which language to enter.
27. As an English speaker, I want to switch to English-to-Arabic lookup, so that I can find candidate Arabic entries from an English word.
28. As an English-to-Arabic user, I want a multi-word query such as "piece of writing" matched as a phrase rather than by its first word, so that results match what I asked.
29. As an English-to-Arabic user, I want inflected English forms to find their base meaning (for example "books" finds "book" entries), so that I do not have to guess the dictionary form.
30. As an English-to-Arabic user, I want duplicate entries removed and verbs shown in citation form, so that the result list is short and useful.
31. As an English-to-Arabic user, I want coverage limits shown, so that I do not mistake a missing reverse result for proof that no translation exists.
32. As a user, I want changing direction to update field labels and result context, so that stale results cannot be mistaken for results in the new direction.
33. As a user, I want blank input to remain an intentional empty state, so that no confusing lookup occurs.
34. As a user, I want an explicit no-results state for a completed query that suggests next steps (check spelling, remove diacritics, use Arabizi, or switch direction), so that I can tell it apart from loading or a network failure and know what to try.
35. As a user, I want a recoverable error state when lookup fails, so that I can retry without retyping.

### Understand dictionary results

36. As a learner, I want all plausible analyses for my input, so that ambiguity is visible rather than silently resolved.
37. As a learner, I want each result's vocalized Arabic form, so that I can distinguish words sharing consonantal spelling.
38. As a learner, I want an English gloss for the whole word, including attached conjunctions, prepositions, articles, and pronouns (for example "and by/with their book"), so that I understand the word as written, not only its stem.
39. As a learner, I want the prefix, stem, and suffix of each vocalized form visually distinguished, so that I can see how the word is built.
40. As a learner, I want part-of-speech and available morphology details, so that I can interpret a form in context.
41. As a learner, I want root information when available, so that I can connect related vocabulary.
42. As a learner, I want verb measure/form when available, so that I can recognize derivational patterns.
43. As a learner, I want missing root or measure fields shown as unavailable, so that absence is not rendered as corrupt text or an invented value.
44. As a user, I want a stable, readable default result order, with analyses grouped by lemma and the most common words first, so that repeated lookups are predictable and the likely reading is near the top.
45. As a learner, I want analyses that share the same gloss (for example a noun's singular and plural) grouped into one result, so that the list is shorter without hiding any form.
46. As a user, I want to sort long result lists, such as a root's word family, by visible columns, so that I can scan them.
47. As a user, I want Arabic and English text displayed with correct direction and alignment, so that mixed-script rows remain legible.
48. As a user, I want long glosses and morphology labels to wrap cleanly on a narrow screen, so that no result is hidden.
49. As a user, I want result controls to have descriptive accessible names, so that assistive technology can distinguish actions.

### Explore word families

50. As a learner, I want to open related forms from a result (the other forms of the same lemma and part of speech, such as a noun's singular and plural or a verb's perfect and imperfect), so that I can compare closely connected entries.
51. As a learner, I want to open all entries sharing a result's root, ordered by verb measure (I–X), then verbs before nouns and adjectives, then lemma, so that I can explore its word family in a predictable order.
52. As a learner, I want a result whose root has alternatives (for example الو/الي) to offer each alternative root, so that weak roots remain explorable.
53. As a learner, I want the active related-word or root filter shown clearly, so that I know why results changed.
54. As a learner, I want to dismiss that filter and return to my prior lookup, so that exploration does not erase my original context.
55. As a user, I want root navigation offered only when a result has a valid root, so that dead-end controls do not appear.
56. As a user, I want related-word navigation offered only when related entries exist, so that controls have meaningful outcomes.
57. As a user, I want browser Back to restore the previous lookup or exploration state, so that navigation follows normal web expectations.

### Analyze text in context

58. As a reader, I want to paste an Arabic sentence or short passage, so that I can inspect unfamiliar words in context.
59. As a reader, I want the analyzed text to preserve word order, punctuation, line breaks, numbers, and non-Arabic text, so that I can still follow the passage.
60. As a reader, I want each analyzable token to be interactive, so that I can inspect it without leaving the text.
61. As a reader, I want each token to show all available analyses, so that ambiguity remains visible.
62. As a reader, I want token details to show form, gloss, part of speech, and available root or measure, so that the detail is consistent with Word lookup.
63. As a reader, I want diacritics already present in the passage to narrow that token's analyses, so that vocalized texts give precise readings.
64. As a reader, I want to open a token's full Word lookup, including root and related-form navigation, so that I can dig deeper from the text.
65. As a touch user, I want to open token details by tap, so that the feature works without hover.
66. As a keyboard user, I want to focus and open token details with keyboard controls, so that I can analyze text without a pointer.
67. As a reader, I want an unknown token distinguished from an empty or failed analysis, so that I understand coverage limits.
68. As a reader, I want to edit or replace the passage and get updated analysis, so that I can investigate another sentence.
69. As a reader, I want long passages to fail gracefully at a documented limit, so that the page remains responsive.
70. As a reader, I want inserted text treated as data, so that pasted markup cannot alter the page or run code.

### History

71. As a returning user, I want a list of my recent lookups, so that I can revisit words without retyping them.
72. As a user, I want to set how many history entries are kept and to clear the history, so that I control what is remembered.
73. As a privacy-conscious user, I want history stored only on my device, so that no account or server-side record is needed.

### Help, trust, and accessibility

74. As a new user, I want concise guidance on entering Arabic, including hamza forms and diacritics, on the on-screen keyboard and on common phone keyboards, so that I can start without device-specific setup instructions that may be outdated.
75. As a visitor, I want to know what language variety and corpus AraDict covers, so that I can judge whether a result is relevant.
76. As a visitor, I want source attribution and license notices, so that I can inspect provenance.
77. As a visitor, I want a working support or feedback channel, so that I can report incorrect results or bugs.
78. As a visitor, I want an honest statement about native app availability, so that I do not confuse third-party store listings with AraDict apps.
79. As a screen-reader user, I want semantic navigation, labeled fields, result headers, and announced status changes, so that I can complete a lookup.
80. As a keyboard-only user, I want visible focus, operable navigation, lookup, sorting, and token details, so that every core flow is usable.
81. As a low-vision user, I want scalable Arabic and English text with sufficient contrast, so that I can read dense results.
82. As a user on a slow connection, I want loading feedback and no stale result substitution, so that I know which query a result belongs to.
83. As a privacy-conscious user, I want a clear statement of data handling and no account requirement, so that I can decide what text to submit.

### Daily-use experience

84. As a returning user, I want Word lookup ready on the home view, so that I can search without passing through promotional content.
85. As a frequent user, I want the current query and lookup direction visible while reading results, so that I never lose context.
86. As a mobile user, I want the search input to remain usable when my device keyboard is open, so that I can refine a query without fighting the layout.
87. As a mobile user, I want to scan each result without sideways scrolling, so that I can compare analyses with one hand.
88. As a learner, I want Arabic form and English meaning easy to identify first, so that detailed grammar does not obscure the answer I came for.
89. As an advanced learner, I want every available grammatical detail retained and accessible, so that a simpler layout does not remove dictionary depth.
90. As a learner, I want person, gender, number, tense, voice, and other available tags shown clearly, so that I can distinguish similar analyses.
91. As a user exploring roots, I want to return to my original search in one action, so that investigation remains quick.
92. As a mobile reader, I want text-token details in a dismissible panel that fits the viewport, so that I can inspect a word and resume reading.
93. As a user, I want results to appear without distracting motion or layout jumps, so that repeated lookup feels stable.
94. As a user, I want visual styling that clearly distinguishes Arabic text, translations, grammar, and actions, so that I can scan results without decoding a dense table.
95. As a user, I want large enough Arabic type and comfortable line spacing, so that vowels and shadda remain legible.

### Richer entries (Milestone 2: Wiktionary)

96. As a learner, I want every meaning of a word listed separately (for example كتاب as "book", "letter", "scripture", "marriage contract"), so that I can choose the sense that fits my text.
97. As a learner, I want a noun's plural forms and gender, and a verb's verbal nouns, shown with the entry, so that I learn the forms that go with the word.
98. As a learner, I want a pronunciation guide (transliteration and IPA) for a word, so that I can say it correctly.
99. As a reader of current Arabic, I want words that entered the language recently (for example تغريدة "tweet") to be found, including in their inflected forms, so that modern texts are covered.
100. As a visitor, I want content taken from Wiktionary clearly credited and linked to its source entry, so that I know where it comes from and can read more.
101. As a user, I want a word that is only in one source to still show everything that source knows, so that a gap in one source never hides a result.
107. As a learner looking up an English word, I want meanings that only Wiktionary gives (for example "tweet" or "marriage contract") to find their Arabic words too, so that English lookup reaches the same entries as Arabic lookup. (Added in Milestone 2, #25; numbered after the Milestone 3 stories.)

### Conjugation and declension (Milestone 3)

102. As a learner, I want a full conjugation table for any verb result (perfect; imperfect in indicative, subjunctive and jussive; imperative; active and passive; all persons), so that I can see every form of the verb.
103. As a learner, I want a declension table for any noun or adjective result (cases, definite and indefinite states, singular, dual and plural), so that I can see how it inflects.
104. As a learner, I want the form I looked up highlighted in its table, so that I can see where it fits.
105. As a learner, I want to open any form in a table as its own lookup, so that I can explore from the table.
106. As a mobile user, I want conjugation and declension tables readable on a narrow screen without sideways scrolling, so that I can use them on my phone.

## Implementation Decisions

- **Scope and information architecture:**
  - Word lookup is the home view and the primary task. Text and About/Help are secondary views.
  - Explanatory content stays brief and sits below or beside the primary search, never in front of it.
  - About/Help documents Arabic input (including hamza and diacritics), Arabizi, data provenance, coverage limits, privacy, and support.
  - Responsive web use is in scope. Native iOS and Android apps, app-store links presented as AraDict products, and device keyboard installation guides are not.
- **Experience direction:** Design for an established user's repeated, short lookup sessions. Preserve all available dictionary detail while reducing visual density. Arabic form and English gloss are the primary scan targets; POS and morphology form the next level; root and measure are clearly labeled actions or metadata. Choose an original visual identity for AraDict. Do not treat the reference site's table layout or branding as a design specification.
- **Mobile interaction:**
  - Design from narrow touch screens upward.
  - These must remain usable with the device keyboard open: search input, direction switch, clear action, results, root/related actions, history, and text-token details.
  - Use a readable stacked result layout when columns no longer fit. Core content must not require horizontal scrolling.
  - Keep touch targets distinct, and avoid disclosure that only works on hover.
- **Terminology:**

  | Term | Meaning |
  |---|---|
  | *surface form* | user input |
  | *analysis* | one possible morphological interpretation |
  | *segment* | the prefix, stem, or suffix part of an analysis |
  | *entry* | a dictionary record |
  | *lemma* | the dictionary headword that groups an entry's forms |
  | *related forms* | other entries with the same lemma and part of speech |
  | *gloss* | an English meaning |
  | *root* | Arabic root |
  | *measure* | a verb's derived form (I–X) |
  | *pattern* | a stem's vowel template, with the root letters as numbered slots (for example ٱِسْتَ1ْ2َ3) |
  | *Arabizi* | Latin/SMS-style spelling of Arabic |

  These are proposed domain terms; the repository has no glossary or ADRs.
- **Dictionary source:**
  - **Core (license verified):** the CAMeL Tools MSA morphology database `calima-msa-r13`, licensed GPL v2. It is derived from Aramorph 1.2.1, the Java port of the Buckwalter Arabic Morphological Analyzer 1.0. It has 72,734 stem entries covering about 39,800 lemmas. Every stem has a root, pattern, English gloss, fine-grained POS, functional gender and number, and frequency. Details and checks are in `DATA-SOURCES.md`.
  - Pin the database version and checksum. Download it at build or deploy time, and do not commit it to the repository.
  - The Aratools GPL package is no longer the data source. It remains useful only as a reference for expected behaviour (see `DATA-LICENSE-FINDINGS.md`).
  - **Known gaps in the core:**
    - The vocabulary and glosses date from about 2002. Glosses use underscores for spaces, which the presentation layer replaces.
    - Newer words such as "tweet", "podcast" and "Instagram" are missing. Milestone 2 addresses this.
  - Record the source and version in the data pipeline, and carry the required attribution through to About/Help.
  - Do not scrape the live lookup endpoint as a production dependency.
- **Architecture and licensing:**
  - The backend is Python and uses CAMeL Tools (MIT) for analysis and, in Milestone 3, generation.
  - Lookups run on the server. The lexicon is never shipped to the browser, so serving the site is not distribution under the GPL.
  - AraDict's own code is licensed GPL-2.0-or-later, so any combined distribution with the GPL v2-only data, including the public repository, stays compatible.
  - Any changes AraDict makes to GPL data (gloss fixes, additions) live in AraDict's own files with a dated change note, as GPL v2 §2(a) requires.
- **Frontend:** server-rendered HTML from the same Python app, with no separate frontend framework or second runtime.
  - **Stack:** FastAPI renders every page, so word, root, and related-forms URLs return complete HTML. That gives fast first paint on phones, working links and previews, and search-engine-indexable entries.
  - **Views in Python:** markup is written with htpy (MIT), a small typed HTML-builder library, instead of a template language. The whole app is then Python, type checking catches markup mistakes, and view components are plain functions that can be tested on their own.
  - **Rejected alternatives:**
    - Python UI frameworks (Reflex, NiceGUI, Streamlit, Flet and similar) keep per-visitor state on the server and render content with JavaScript or a canvas. That hurts shareable URLs, search indexing, accessibility, and right-to-left control. Reflex also brings back a Node build.
    - FastHTML is pre-1.0 and replaces FastAPI with its own conventions.
    - Python in the browser (Pyodide/PyScript) means a multi-megabyte runtime on phones and would ship the GPL data to every visitor.
  - **Live behaviour:** htmx (0BSD license) provides live lookup and URL updates. Input is debounced, newer requests replace older ones, and the URL is pushed for each lookup, so shareable URLs and Back work. Basic lookup also works without JavaScript, as a plain form submission.
  - **Interactive widgets:** small vanilla JavaScript modules, with no component library:
    - the autocomplete combobox, following the WAI-ARIA combobox pattern (native `datalist` can't match typed letters against vocalized suggestions);
    - the on-screen Arabic keyboard;
    - local history and preferences;
    - text-token details using the native Popover API.
  - **Styling:** plain CSS with logical properties for RTL/LTR, light and dark themes from system settings, and no CSS build step. Arabic text uses self-hosted Scheherazade New (regular and bold) under the SIL Open Font License. Diacritics must remain legible at mobile sizes. Latin text uses self-hosted Source Sans 3, also under the SIL Open Font License. No font or asset is loaded from a third party. The visual identity is design M1 Cloth Tab from #14: framed entry boxes, labelled fields, grammar as small boxed tags, the root on a green tab above each entry, and compact text and controls. Theme colours are plain tokens redefined in a dark-scheme media query; the CSS `light-dark()` function is not used.
  - **Trade-off accepted:** the accessible combobox and popovers are hand-built rather than taken from a component library. In return there is one language, one deployable, and no frontend build chain. Revisit only if the interactive parts outgrow small modules.
- **Coverage claim:** The reference site advertises more than 80,000 stems. AraDict must state its own measured coverage. Do not reuse that number unless the selected AraDict corpus supports it.
- **Shared dictionary boundary:**
  - All user-facing modes use one dictionary application contract for these operations: Arabic lookup, English lookup, autocomplete, Arabizi transliteration, token analysis, related forms, root exploration, Wiktionary enrichment (Milestone 2), and conjugation and declension (Milestone 3).
  - This keeps normalization, morphology, ordering, and provenance consistent across the Word and Text views.
  - The Python backend implements the contract. Its internal storage remains an implementation choice.
- **Core data shape:**
  - An analysis includes:
    - stable entry identity and the source surface form;
    - the vocalized form where available;
    - **segments**: prefix, stem, and suffix, each with surface and vocalized form, so that the UI can distinguish them visually;
    - a whole-word composed gloss and the stem's own glosses;
    - part of speech as both a code and a plain-English description;
    - lemma and available morphological tags;
    - optional root, which may hold alternatives;
    - pattern and frequency;
    - optional measure (derived from the pattern for verbs);
    - relation identifiers that tell the UI whether related-form and root navigation exist;
    - provenance.
  - Missing information stays null or absent rather than guessed.
  - A lookup response identifies the query, mode, completion status, and ordered analyses.
  - Text analysis returns ordered tokens with their original text spans. Each token is typed (word, unknown word, punctuation, whitespace including line breaks, number, or non-Arabic text), and word tokens carry their analyses.
- **Measures and roots from the core data:**
  - Derive the verb measure from the stem's pattern using a template table: I–X for three-letter roots, and QI–QIV for four-letter roots. A rough first heuristic already mapped 90% of verb lemmas. The table must also cover the remaining weak and hamzated patterns.
  - About 38% of stems have an unresolved weak or hamza radical in the root (shown as `#` in the data). Display those radicals with a neutral placeholder and keep the root navigable. Milestone 2 fills them from Wiktionary where available.
- **Frequency ranking:** use the database's lemma frequency to order results within the default grouping, and to order autocomplete suggestions.
- **Arabic matching:**
  - Normalize Unicode consistently for matching while preserving the user's original text and the corpus's display form.
  - Normalization must not collapse distinct entries in display, or invent a unique analysis when several remain possible.
  - **Diacritics are a filter, not noise.** Undiacritized input matches every analysis of its letters. Each diacritic the user types must agree with an analysis's vocalization, or that analysis is dropped. Filtering is on by default and can be switched off.
  - Defined behaviour, fixture-tested, with the reference baseline for comparison:

    | Input | Reference behaviour (observed) | AraDict decision |
    |---|---|---|
    | bare ا vs أ/إ/آ | bare alif matches hamza forms; hamzated input matches only itself | keep |
    | ى vs ي | tolerant (الى finds إلى) | keep |
    | tatweel ـ | not handled; lookup fails | strip before matching |
    | word-final ه for ة | not tried | try both; rank the exact match first |
    | Persian/Urdu ی, ک | ی tolerated | map both to Arabic equivalents |
    | several words in the Word field | only the first word is analysed, silently | analyse the first word, show a notice, offer the Text view |
    | Latin letters in Arabic mode | "Invalid word" error | treat as Arabizi (see below) |
- **Arabizi:**
  - In Arabic mode, input containing no Arabic letters is transliterated before lookup. Common digit conventions apply (2→ء, 3→ع, 5→خ, 7→ح, 9→ق), as do the multi-letter mappings (sh, kh, gh, th, dh).
  - Short vowels are optional, and long vowels map to their letters only where the analyser confirms a match.
  - Generate a ranked set of candidate Arabic spellings, keep those the analyser recognizes, and show the chosen Arabic next to the input.
  - The reference dev implementation maps naively: it leaves "i" untransliterated and always turns "a" into a long alif. Do not copy that behaviour.
- **English lookup:**
  - Search English gloss/index data and return Arabic entries with the same result fields.
  - Matching rules:
    - matches whole gloss senses (gloss lists split on ";"), ignoring bracketed annotations, letter case, and surrounding whitespace;
    - matches multi-word queries as phrases;
    - matches inflected English forms to their base form;
    - removes duplicates;
    - shows verbs in citation form.
  - The reference matches only the first word of a phrase and returns duplicates. AraDict deliberately differs.
  - Mark this direction as limited if the selected corpus is incomplete.
- **Autocomplete:**
  - Suggestions come from a stem prefix index, are filtered by any diacritics typed, are deduplicated by vocalized form, are ordered by frequency, and are capped at a small number (the reference uses 25).
  - When the input begins with a recognized attached prefix, complete the stem and keep the typed prefix. The reference returns nothing in this case.
  - Autocomplete is shown only when the selected mode has a supported suggestion index. The on/off preference persists on the device.
- **Word UI:**
  - **Input and lookup:**
    - Provide the input, live lookup, optional autocomplete, a clear control, a direction switch, the on-screen keyboard, and Arabizi feedback.
    - Lookup runs as the user types, debounced at about 150 ms, and Enter runs it immediately.
    - Query changes cancel or supersede earlier responses. The UI never shows a previous query's results as current.
  - **Results:**
    - Show a result list with the segment-distinguished vocalized form, whole-word gloss, full available POS/morphology, root, and measure.
    - Group analyses that share an identical gloss into one result that lists all their vocalized forms.
    - Analyses that differ only in a case or mood ending, or only in how a proclitic is read (for example وَ as "and" or "while"), are shown as one result. The spike found that otherwise وبكتابهم would show 36 rows for 3 readings.
    - The default order groups by lemma, with the most frequent lemmas first.
    - Results are laid out as one entry per lemma. Each entry shows the lemma, its part of speech, measure, root, frequency, and the related-forms action once, then lists the readings of the typed word that belong to it. This keeps readings with the same vocalized form but different lemmas (for example سَيُكْتَبُونَ from كَتَب and from أَكْتَب) visibly apart. The layout was chosen with the round 1 prototype in #14.
    - Each reading's prefix, stem, and suffix, each labelled with its meaning, can be shown on demand by tap, click, or keyboard. They are hidden by default.
    - Word results keep this grouping and are not column-sortable.
    - Desktop and mobile layouts may present results differently, but no available field is dropped just to fit the screen.
  - **On-screen keyboard:** the standard Arabic (101) layout, with a shift layer for harakat, hamza seats, and lam-alif forms.
- **Family navigation:**
  - Related-form and root actions replace the result set while keeping the originating query, and display a dismissible context chip or an equivalent control.
  - **Related forms:** entries sharing the result's lemma and part of speech.
  - **Root view:** all entries with that root, ordered by measure, then part of speech (verbs first), then lemma, then form.
  - Root and related-form lists can be sorted by their visible columns, with a defined, stable secondary order and an accessible sort state.
  - Roots with alternatives offer each alternative.
  - Browser history restores prior states.
  - Suppress actions when the corresponding data is absent.
- **History:**
  - Recent lookups (query, direction, and any root or related view) are stored only on the device.
  - The number of entries kept is configurable, with a sensible default, and the history can be cleared.
  - History is never sent to a server.
- **Wiktionary layer (Milestone 2):**
  - Import English Wiktionary's Arabic entries from a pinned, dated kaikki.org extraction, checked by SHA-256 like the core database, into a separate dataset. It is refreshed by moving the pin and rebuilding; a scheduled refresh waits until the site is hosted.
  - Wiktionary text is CC BY-SA 4.0 / GFDL, which is not compatible with GPL v2-only. It is therefore never merged into a file or database with the GPL data. The two are joined at request time by vocalized lemma and part of speech.
  - From Wiktionary, show numbered senses, plurals and gender, verbal nouns, and transliteration and IPA. Use it to fill unresolved root radicals.
  - Words found only in Wiktionary are looked up through its inflected-form entries. They are shown as entries without the morphology fields the core would provide.
  - English lookup also searches Wiktionary's senses, with the same matching rules as the core glosses. A lemma both sources match appears once, and results from Wiktionary carry the credit.
  - Every view that shows Wiktionary content credits it ("From Wiktionary, CC BY-SA 4.0") with a link to the source entry. Adapted Wiktionary text stays under CC BY-SA.
  - **Presentation** (design W5, chosen in #21): an entry answers its questions in order.
    1. Which word it is: the root tab, the headword with its part of speech and measure, its transliteration and IPA under it, and its frequency.
    2. What the typed word means: each reading's meaning, grammar and word parts.
    3. Everything about the headword:
       - all its meanings, numbered;
       - its plural, gender and verbal nouns;
       - its relations ("verbal noun of …");
       - its other forms;
       - regional pronunciations;
       - the credit.
    - Token details in the Text view follow the same order, but leave out frequency, other forms and regional pronunciations.
    - A word only Wiktionary has goes straight from its headword line to its meanings.
    - When a reading's lemma is common (in the top 10% of lemmas by frequency), Wiktionary's other entries for the word fold under one closed "N more entries from Wiktionary" disclosure, together with those that only relate it to another word. Rare words and senses (من "aphid") then don't push the common reading's neighbours down. They are folded, never dropped. A word whose readings are less common or have no frequency (تغريدة) shows them open.
    - An English lookup shows its first 25 entries, with a link to show all of them: "male given name" has 344.
  - **Register.** AraDict covers Modern Standard Arabic, as its CAMeL core does. Aratools does too: both are built on the Buckwalter lexicon of MSA news text. Wiktionary also records Classical, obsolete, archaic, rare and dialectal uses. About 4% of its senses carry such a label (2,051 of 47,111 in the pinned extraction), for example كِتاب as an obsolete verbal noun of كَتَبَ, where MSA uses كِتابة.
    - Every sense, form and relation that Wiktionary labels this way is shown with its label, never without it.
    - A label on one side of a relation also shows on the other side: كَتَبَ's list of verbal nouns marks كِتاب as obsolete, too.
    - These uses are labelled, not hidden, so that a reader of older texts can still find them.
- **Conjugation and declension tables (Milestone 3):**
  - Generate tables from the lemma using CAMeL Tools' generator over the core database:
    - verbs: perfect; imperfect (indicative, subjunctive, jussive); imperative; active and passive; all persons;
    - nouns and adjectives: case × state × number.
  - A small rule layer completes the generator's output. It adds mood endings (indicative, subjunctive, jussive) to the forms the database leaves unmarked, and builds imperatives from the jussive. The spike found the generator alone leaves most of those cells empty.
  - Tables are checked against Wiktionary's conjugation tables where Milestone 2 has them. Cells that are still unknown are shown empty, never guessed.
  - The looked-up form is highlighted, and each cell opens its own lookup.
  - On narrow screens, tables are split into sections (for example by tense or by number) so that no sideways scrolling is needed.
- **URLs:**
  - The query, direction, and root or related-forms state are encoded in the URL, so that links and browser history reproduce the view.
  - Pasted passages are never placed in URLs.
- **Text UI:**
  - Accept pasted or typed Arabic text.
  - Tokenize without losing punctuation, line breaks, numbers, non-Arabic text, or offsets, and render words in their original order.
  - A token opens a dismissible detail surface that works with pointer, touch, keyboard, and screen reader. The surface shows multiple analyses, explicit unknown-token states, and a way into the full Word lookup.
  - Diacritics in the passage filter that token's analyses.
  - The initial release limits input to a documented size and returns a clear validation message when the limit is exceeded.
- **Status and errors:** Distinguish initial empty, loading, results, no results, invalid/too-long input, and service failure. Announce status accessibly. Preserve user input on failure and provide Retry. Avoid silent empty tables after a completed no-result lookup.
- **Accessibility and layout:** Support mixed RTL/LTR text, semantic headings, labels, table headers where tables are used, focus order, visible focus, touch targets, and responsive result presentation. Target WCAG 2.2 AA for the web app. Avoid interaction that requires hover alone. Test common mobile and desktop widths, browser text zoom, and Arabic diacritic legibility.
- **Privacy and operations:** No account, advertising, or user profile in this scope. Define retention and logging before release; do not log submitted passages by default. Expose only the documented dictionary operations, validate input, escape rendered text, and rate-limit public endpoints if server backed. Use operational telemetry that does not include query text unless separately justified and disclosed.
- **Performance:** Lookup and token detail should respond promptly on representative devices and corpus size. Establish measured latency and passage-size budgets against the selected data source before release; do not claim reference-site performance as an AraDict guarantee.
- **Release gate:** Corpus rights for the core data are verified (GPL v2; see `DATA-SOURCES.md`). Do not publish corpus-backed production behavior until attribution, coverage description, privacy statement, and support destination are settled. Milestone 2 also requires the Wiktionary credit to be in place. These are required product inputs, not assumed from Aratools.

## Testing Decisions

- **Principle:**
  - Test externally observable behavior and real dictionary outcomes, not component internals or framework state.
  - Lexical correctness can only be shown against real data. A hand-made fixture corpus shows that the UI renders data, not that the analyzer is right.
- **Seams:** two seams, the fewest that cover both concerns.
  1. **Dictionary contract (morphology seam).** Exercise the shared dictionary contract in-process against the pinned CAMeL core database. This seam carries the bulk of the cases:
     - analysis enumeration;
     - normalization and diacritic filtering;
     - whole-word gloss composition;
     - English matching;
     - autocomplete;
     - Arabizi;
     - related and root ordering;
     - tokenization.
     
     Running these many input-to-analysis cases through a browser would be slow and brittle.
  2. **Browser journeys (UX seam).** Exercise Word (home), Text, and About/Help through browser-visible journeys, using Playwright for Python so that both seams share one test toolchain (pytest), against a small deterministic, redistribution-safe fixture corpus. The corpus contains ambiguous unvocalized forms, affixed forms, English gloss matches, multiple roots and measures, root alternatives, missing metadata, and unknown tokens.
  
  No prior test conventions exist in this repository.
- **Reference behaviour cases (dictionary contract):**
  - **Expected analyses for Arabic input:**
    - كتب → 3 analyses (he/it wrote · he/it was written · books)
    - كَتَبَ → 1 analysis with filtering, 3 without
    - وبكتابهم → 3 analyses with whole-word glosses of the form "and by/with their …"
    - سيكتبون → 4 analyses across measures I and IV
    - استخدم → measure X analyses
    - مدرستي → includes dual and first-person possessive analyses
    - اكل → includes the أكل and آكل analyses; أكل excludes آكل
    - الى → includes إلى
  - **Family, English, and autocomplete:**
    - root كتب → ordered I, III, IV, VI, VII, VIII, X, then nouns
    - English "book" → كِتاب and سِفْر
    - autocomplete كتا → vocalized stems beginning كتا
  - **Intentional differences from the reference** each get their own case: tatweel, word-final ه, several words, English phrases and duplicates, Latin input, and autocomplete after a prefix.
  - Write these assertions by hand and keep them small. Do not commit full captured responses from the live site, because parts of its presentation output may come from non-GPL code.
- **Word journeys:**
  - Arabic lookup of a surface form, with multiple analyses.
  - Display of gloss, POS, root, and measure, with segments visually distinguished.
  - Identical-gloss grouping.
  - English direction.
  - Live update while typing, plus Enter.
  - Autocomplete on and off where supported.
  - Arabizi with its visible transliteration.
  - Clear, stable sorting of root and related-form lists.
  - No results with next-step guidance.
  - Request failure.
  - Superseded queries.
- **Morphology journeys:** a small set of browser checks confirming that clitic handling, diacritic filtering, and normalization surface correctly in the UI. Exhaustive cases live at the dictionary contract seam. Assert that displayed forms stay faithful to the source and that ambiguity is retained.
- **Exploration journeys:**
  - Related and root navigation.
  - Root ordering.
  - Root alternatives.
  - The context indicator and dismiss-to-return.
  - Behaviour when the root is absent.
  - Browser Back/Forward restoration.
  - Shareable URLs.
- **Milestone 2 journeys:**
  - A word with several Wiktionary senses shows them all.
  - A plural and a verbal noun appear with their entry.
  - A Wiktionary-only word (for example تغريدة) is found from an inflected form.
  - Every view showing Wiktionary content shows the credit and link.
  - No Wiktionary text appears in the GPL data files.
- **Milestone 3 journeys:**
  - Generated tables match Wiktionary's tables for one sample verb of each measure, and for a sound noun, a broken-plural noun, and a diptote noun.
  - The looked-up form is highlighted, and a cell opens its lookup.
  - Tables need no sideways scrolling on a narrow screen.
- **History journeys:**
  - A lookup appears in history.
  - Selecting an entry restores the view.
  - The size limit is enforced.
  - Clearing empties the history.
  - Nothing is sent to the server.
- **Text journeys:**
  - Token order, with punctuation, line breaks, numbers, and non-Arabic text preserved.
  - Multiple analyses per token.
  - Diacritic filtering within a passage.
  - Unknown tokens.
  - Detail activation by touch/click and by keyboard.
  - Opening a token in Word lookup.
  - Long-input validation.
  - Safe rendering of pasted markup.
- **Accessibility journeys:** Verify labeled controls, status announcements, keyboard-only completion of core flows, visible focus, RTL/LTR readability, zoom, and responsive layout at narrow and wide widths. Automated accessibility checks supplement manual screen-reader review.
- **Daily-use UX journeys:** From a fresh load, complete a word lookup immediately. On narrow screens, repeat lookup with the device keyboard open, compare ambiguous analyses without sideways scrolling, open and dismiss root/related views, and inspect and dismiss text-token details. Confirm that full grammatical detail remains available on both mobile and desktop. Review visual hierarchy with representative Arabic learner tasks rather than judging only a static screenshot.
- **Data acceptance:**
  - Before release, run a documented corpus validation pass for:
    - duplicate identities;
    - broken relations;
    - empty required fields;
    - malformed Arabic;
    - provenance and license notices;
    - measured coverage;
    - measure-derivation coverage for verbs (target: every three-letter verb gets one of I–X);
    - the number of roots with unresolved radicals.
  - Include the defects already known in the reference data:
    - misspelled grammar labels ("genetive", "possesive");
    - ungrammatical dual glosses ("two school");
    - root fields holding alternatives ("الو/الي");
    - proper nouns without roots.
  - Use a linguist-reviewed sample for morphology quality. UI tests alone cannot establish lexical accuracy.
- **Performance acceptance:** Measure lookup and passage analysis on representative mobile hardware and the selected corpus. Set pass/fail thresholds from product requirements before implementation is considered complete.

## Out of Scope

- Native iOS or Android apps, offline native dictionaries, app-store purchasing, app extensions, and device keyboard setup walkthroughs.
- User accounts, synchronized history, favorites, flashcards, spaced repetition, and personalization. Device-local lookup history is in scope.
- Machine translation of full sentences or promises of a single context-correct interpretation. Text view provides token-level dictionary analyses.
- Audio pronunciation, OCR, and browser extensions.
- Context-aware disambiguation (choosing the right analysis from surrounding words). CAMeL Tools has models for this; revisit after Milestone 3 if users ask for it.
- Example sentences. Tatoeba was evaluated: its roughly 30,000 Arabic–English pairs give thin coverage, and each sentence needs its own credit.
- A public developer API, third-party integration, and automatic import of Aratools' proprietary code, branding, images, or unverified data.
- Publishing a news/blog system. About/Help may link to an AraDict updates channel if one exists.

## Further Notes

### Evidence and scope

**Production site** — inspected the live [Aratools site](https://www.aratools.com/) across the Main, Word, Text, Mobile, and About tabs on 7 November 2026, including the JSON API it calls.

- *Word tab:*
  - Arabic/English direction, autocomplete, and an on-screen Arabic keyboard.
  - A results table that can be sorted by any column and defaults to sorting by form.
  - Lookup runs on every keystroke; the Lookup button adds nothing.
  - Diacritics in the input filter the results.
  - Latin input in Arabic mode returns an "Invalid word" error.
- *Text tab:* accepts a passage and shows per-token analyses in hover popovers. Unknown words are marked, and line breaks and punctuation are kept. The server returns markup and script that the page inserts directly.
- *Mobile and About tabs:* store links, keyboard help, support details, and a link to the GPL redistributable package.

**Preview web app** — inspected the linked [preview web app](https://dev.aratools.com/) across all routes, including its client code and API calls.

- *Word view:*
  - Related-word and root actions with dismissible context chips.
  - Prefix and suffix segments shown in a distinct color.
  - Rows with the same gloss merged.
  - **Arabizi mode** when the input has no Arabic letters: a transliteration endpoint is called and its output shown as a chip. Its mapping is naive.
- *Text view:* updates as the text changes and shows token details in hover/focus tooltips; touch requires a long-press. Its tokenizer drops punctuation, line breaks, and non-Arabic text.
- *Status:* the [October 2026 announcement](https://aratools.mataroa.blog/blog/upcoming-release-and-new-web-app/) describes this preview as the place where features are tested first. Treat preview behavior as product inspiration, not as a claim that it is on the current production site.

**Native apps** — the official [Google Play listing](https://play.google.com/store/apps/details?id=com.aratools.dictionaryProd) and [Apple App Store listing](https://apps.apple.com/us/app/aratools-arabic-english/id329068883) describe additional native features: Arabizi input, related-word links, combined related words, color-accented prefixes and suffixes, and configurable history size. These listings inform the boundary of this spec and the history and grouping requirements. They do not give AraDict rights to reuse their assets.

**GPL package** — the zip (about 2.6 MB) contains:
- Buckwalter-style `dictprefixes`, `dictstems`, and `dictsuffixes`;
- the compatibility tables `tableab`, `tableac`, and `tablebc`;
- the GPL texts;
- an Aratools extension file (about 9 MB).

It is GPL v2 Buckwalter 1.0 data plus a 2015 annotation file, and it is no longer the planned data source (see `DATA-LICENSE-FINDINGS.md`).

**Data sources** — a survey of alternatives (`DATA-SOURCES.md`) chose:
- the CAMeL Tools `calima-msa-r13` database as the core;
- English Wiktionary as the Milestone 2 layer.

It rejected SAMA 3.1 and BAMA 2.0 (paid LDC licenses that don't allow redistribution), Qabas (license unclear), and several Arabic-only or license-incompatible analyzers.

**CAMeL spike** — a run of CAMeL Tools against the reference cases (`SPIKE-CAMEL.md`) confirmed the expected readings and showed analysis at about 0.27 ms per word. It also listed what AraDict must add: diacritic filtering, the hamza rule, Persian letters, grouping of readings, gloss wording, and the conjugation rule layer.

**Repository and goal**
- The repository has no application code as of 7 November 2026. There are no modules, glossary, ADRs, or prior tests to preserve. The core corpus (CAMeL), the backend (Python, FastAPI), and the frontend (server-rendered pages written in Python with htpy, plus htmx and small vanilla JavaScript modules) are now decided.
- The product owner's clarified goal is an independent, better-looking and easier-to-use replacement for a dictionary they have used for years. Preserve the reference site's informational value; redesign the interaction and presentation for daily use, especially on mobile.

### Build readiness

- **Ready now:** design and implement the app shell, responsive live lookup flow, result hierarchy with segments and grouping, root/related navigation, history, and text interaction, using the deterministic fixture corpus.
- **Required before a real dictionary launch:**
  - Integrate the pinned CAMeL core database, and pass the reference behaviour cases.
  - Derive verb measures, and handle unresolved root radicals.
  - Measure coverage and quality, and publish the required attribution.
  
  Without these, a polished interface would not reproduce the information that makes the reference useful.
- **Design review before broad implementation:** Validate one desktop and one mobile interactive prototype with realistic ambiguous results and dense morphology. Preserve the full data set while testing the new hierarchy; do not approve a design from empty-state mockups alone.

### Milestones

1. **Milestone 1 (first release):** stories 1–95, built on the CAMeL core, including frequency ranking and derived measures.
2. **Milestone 2:** Wiktionary enrichment (stories 96–101 and 107).
3. **Milestone 3:** conjugation and declension tables (stories 102–106).

Deferred: context-aware disambiguation, example sentences, and audio.

### Success criteria

1. A user can start Arabic lookup on the home view and complete these flows on desktop and mobile web:
   - Arabic lookup, including Arabizi input;
   - English lookup;
   - root and related-forms exploration;
   - history recall;
   - passage token inspection.
2. Results explain ambiguity and coverage limits; no-result and failure states cannot be confused with successful empty output.
3. Core flows work with keyboard and assistive technology, and Arabic/English mixed text stays readable.
4. Every shipped entry has documented provenance and meets the selected corpus's license terms.
5. Mobile and desktop layouts show every available analysis field without making users scroll sideways or rely on hover.
6. Arabic lookup meets the reference behaviour cases, except for documented intentional differences: diacritic filtering, whole-word glosses, normalization, and root ordering.
7. Milestones 2 and 3 each pass their journeys in Testing Decisions before release.
