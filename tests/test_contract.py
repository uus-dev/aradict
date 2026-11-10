"""The dictionary contract, checked against the real pinned database."""

import re
import time
import unicodedata

import pytest

from aradict.dictionary import Dictionary


@pytest.fixture(scope="module")
def real(real_db):
    return Dictionary(real_db)


def first_sense(gloss: str) -> str:
    return gloss.split(";")[0]


def test_ktb_has_three_readings(real):
    assert sorted(first_sense(r.gloss) for r in real.lookup_ar("كتب")) == ["books", "he/it was written", "he/it write"]


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
    assert [first_sense(r.gloss) for r in real.lookup_ar("كَتَبَ")] == ["he/it write"]
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


def letters(arabic: str) -> str:
    return re.sub("[ً-ٰٟ]", "", arabic)


def test_arabizi_without_vowels_reads_as_the_bare_letters(real):
    assert real.arabizi("ktb") == "كتب"


def test_arabizi_vowels_are_marks_or_long_letters_as_the_database_confirms(real):
    # The reference leaves "i" in Latin and always writes "a" as ا.
    assert real.arabizi("kitab") == "كِتاب"
    assert real.arabizi("katab") == "كَتَب"


def test_arabizi_digits_stand_for_letters_and_final_vowels_for_letters(real):
    assert letters(real.arabizi("mar7aba")) == "مرحبا"
    assert letters(real.arabizi("3arabi")) == "عربي"


@pytest.mark.parametrize("arabizi, arabic", [
    ("shams", "شمس"), ("khubz", "خبز"), ("5ubz", "خبز"), ("ghurfa", "غرفة"), ("thaqafa", "ثقافة"), ("dhikr", "ذكر"),
    ("9alb", "قلب"), ("su2al", "سؤال"), ("2akl", "أكل"),  # 2 is a hamza
    ("mudarris", "مدرس"), ("allah", "الله"),  # a doubled consonant is a shadda or two letters
    ("kbeer", "كبير"), ("saa3a", "ساعة"), ("beit", "بيت"), ("mustashfa", "مستشفى"),
    ("shukran", "شكرا"),  # a final "an" may be tanween: شُكْراً
    ("al-kitab", "الكتاب"),
])
def test_arabizi_spelling_conventions(real, arabizi, arabic):
    assert letters(real.arabizi(arabizi)) == arabic


def test_arabizi_picks_the_spelling_with_the_most_frequent_lemma(real):
    # s may be س or ص, h ه or ح: صَباح "morning" outranks سَبّاح "swimmer".
    assert letters(real.arabizi("sabah")) == "صباح"


def test_arabizi_needs_a_known_word(real):
    assert real.arabizi("zzz") is None  # Arabizi letters, but no Arabic word
    assert real.arabizi("xbox") is None  # x stands for no Arabic letter
    assert real.arabizi("كتب") is None  # Arabic script is not Arabizi
    assert real.arabizi(" ") is None


def test_arabizi_reads_the_first_word(real):
    assert real.arabizi(" kitab  kabir ") == real.arabizi("kitab")


def test_arabizi_answers_quickly_however_long_the_word(real):
    start = time.perf_counter()
    real.arabizi("kitab" * 20)
    assert time.perf_counter() - start < 2
