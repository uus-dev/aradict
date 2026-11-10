"""The dictionary contract, checked against the real pinned database."""

import unicodedata

import pytest

from aradict.dictionary import Dictionary


@pytest.fixture(scope="module")
def real(real_db):
    return Dictionary(real_db)


def first_sense(gloss: str) -> str:
    return gloss.split("+")[0].split(";")[0]


def test_ktb_has_three_readings(real):
    assert sorted(first_sense(r.gloss) for r in real.lookup_ar("كتب")) == ["be written", "books", "write"]


def test_clitics_and_case_endings_collapse(real):
    # 36 raw analyses: three lemmas, each with three readings of وَ and several case endings.
    readings = real.lookup_ar("وبكتابهم")
    assert sorted(r.lemma for r in readings) == sorted(["كِتاب", "كاتِب", "كُتّاب"])


def test_most_frequent_lemma_first(real):
    readings = real.lookup_ar("وبكتابهم")
    assert readings[0].lemma == "كِتاب"
    assert readings[-1].frequency is None  # كُتّاب has no frequency in the database


def test_unknown_word_has_no_readings(real):
    assert real.lookup_ar("قخغثص") == []


def test_typed_diacritics_filter_readings(real):
    assert [first_sense(r.gloss) for r in real.lookup_ar("كَتَبَ")] == ["write"]
    assert len(real.lookup_ar("كَتَبَ", filter_diacritics=False)) == 3


def test_fully_vowelled_spellings_agree_with_the_database(real):
    # The database leaves the fatha before a long ا unwritten (كِتاب) and puts tanween fath on the ا.
    assert [r.lemma for r in real.lookup_ar("كِتَابٌ")] == ["كِتاب"]
    assert "كِتاب" in [r.lemma for r in real.lookup_ar("كِتَابًا")]
    assert "كِتاب" in [r.lemma for r in real.lookup_ar("كِتَاباً")]


def test_bare_alif_matches_every_hamza_form(real):
    forms = [r.form for r in real.lookup_ar("اكل")]
    assert "أَكَلَ" in forms and "آكَلَ" in forms


def test_typed_hamza_keeps_only_that_hamza(real):
    forms = [r.form for r in real.lookup_ar("أكل")]
    assert "أَكَلَ" in forms
    assert [f for f in forms if not f.startswith("أ")] == []  # no آكَلَ, آكِل or آكُل


def test_hamza_rule_holds_with_diacritic_filter_off(real):
    assert "آكَلَ" not in [r.form for r in real.lookup_ar("أكل", filter_diacritics=False)]


def test_alif_maqsura_is_tolerated(real):
    assert "إِلَى" in [r.form for r in real.lookup_ar("الى")]


def test_alif_maqsura_and_ya_keep_frequency_order(real):
    # Only a final ه/ة ranks the typed spelling first; for علي the frequent preposition عَلَى
    # ("on", and عَلَيَّ "on me") still outranks the name عَلِيّ.
    assert "عَلَى" in [r.form for r in real.lookup_ar("علي")][:2]


def test_tatweel_is_ignored(real):
    assert real.lookup_ar("كـتـب") == real.lookup_ar("كتب")


def test_persian_look_alikes_read_as_arabic(real):
    assert real.lookup_ar("كتابی") == real.lookup_ar("كتابي") != []
    assert real.lookup_ar("کتب") == real.lookup_ar("كتب")


def test_decomposed_hamza_reads_as_the_composed_letter(real):
    assert real.lookup_ar("\u0627\u0654" "كل") == real.lookup_ar("أكل")


def test_final_ha_finds_ta_marbuta_after_exact_spellings(real):
    # مُدَرِّسُهُ "his teacher" is spelled exactly مدرسه, so it ranks above the more frequent
    # مَدْرَسَة "school"; مُدَرِّسَة "teacher (fem.)" keeps its frequency rank after school.
    # The database writes shadda before kasra, so compare in NFC.
    lemmas = [unicodedata.normalize("NFC", r.lemma) for r in real.lookup_ar("مدرسه")]
    assert lemmas == ["مُدَرِّس", "مَدْرَسَة", "مُدَرِّس"]


def test_several_words_analyse_the_first(real):
    assert real.lookup_ar(" كتب  كتاب ") == real.lookup_ar("كتب")


def test_non_arabic_input_has_no_readings(real):
    # The analyzer invents a "foreign", "digit" or "punc" reading for these; none is a dictionary entry.
    for word in ("hello", "123", "كتب123", "؟"):
        assert real.lookup_ar(word) == [], word


def test_fixture_database_matches_real_for_its_lemmas(real, fixture_db):
    fixture = Dictionary(fixture_db)
    for word in ("كتب", "وبكتابهم", "سيكتبون"):
        assert fixture.lookup_ar(word) == real.lookup_ar(word)


def test_missing_database_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="No morphology database"):
        Dictionary(tmp_path / "missing.db")


def test_suggestions_complete_a_stem_most_frequent_first(real):
    # كِتاب "book" (-3.5), كُتّاب "writers" from two lemmas (-3.9, shown once), كَتائِب "battalions"
    # (-4.2), and كِتابَة "writing" (-4.4), whose stem is كِتاب with the feminine ة attached.
    suggestions = real.suggest("كتا")
    assert suggestions[:4] == ["كِتاب", "كُتّاب", "كَتائِب", "كِتابَة"]
    assert len(suggestions) == len(set(suggestions))


def test_suggestions_keep_an_attached_prefix(real):
    suggestions = real.suggest("وكتا")
    assert suggestions[:2] == ["وَكِتاب", "وَكُتّاب"]
    assert all(s.startswith("وَ") for s in suggestions)
    # Completions of the whole typed word come before those that read part of it as a prefix:
    # الكت completes إِلِكْترُونِيّ "electronic" as well as الكِتاب "the book".
    suggestions = real.suggest("الكت")
    assert suggestions.index("إِلِكْترُونِيّ") < suggestions.index("الكِتاب")


def test_typed_diacritics_and_hamza_filter_suggestions(real):
    assert real.suggest("كُتّا") == ["كُتّاب"]  # the damma and shadda leave out كِتاب
    assert "كِتاب" in real.suggest("كُتّا", filter_diacritics=False)
    assert real.suggest("وَكُتّا") == ["وَكُتّاب"]  # marks on the prefix count too
    assert real.suggest("وِكتا") == []
    assert "إِلَى" in real.suggest("ال")  # a bare ا completes any hamza form
    assert {s[0] for s in real.suggest("أك")} == {"أ"}  # a typed hamza keeps only its own


def test_looking_up_a_suggestion_shows_that_reading(real):
    for typed in ("كتا", "وكتا", "مدر", "يكت", "الكت", "ك"):
        for suggestion in real.suggest(typed):
            assert suggestion in [r.form for r in real.lookup_ar(suggestion)], (typed, suggestion)


def test_suggestions_are_capped_and_need_arabic_letters(real):
    assert len(real.suggest("ك")) == 25
    for text in ("", "  ", "قخغ", "hello", "123"):
        assert real.suggest(text) == [], text
