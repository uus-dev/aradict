"""The dictionary contract, checked against the real pinned database."""

import unicodedata
from dataclasses import replace

import pytest

from aradict.dictionary import MARK, Dictionary


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
    # مُدَرِّسُهُ "his teacher" is spelled exactly مدرسه, so its lemma ranks above the more
    # frequent مَدْرَسَة "school", and takes along its other reading, مُدَرِّسَة "teacher (fem.)".
    # The database writes shadda before kasra, so compare in NFC.
    readings = real.lookup_ar("مدرسه")
    assert [unicodedata.normalize("NFC", r.lemma) for r in readings] == ["مُدَرِّس", "مُدَرِّس", "مَدْرَسَة"]
    assert MARK.sub("", readings[0].form) == "مدرسه"


def test_several_words_analyse_the_first(real):
    assert real.lookup_ar(" كتب  كتاب ") == real.lookup_ar("كتب")


def test_non_arabic_input_has_no_readings(real):
    # The analyzer invents a "foreign", "digit" or "punc" reading for these; none is a dictionary entry.
    for word in ("hello", "123", "كتب123", "؟"):
        assert real.lookup_ar(word) == [], word


def test_fixture_database_matches_real_for_its_lemmas(real, fixture_db):
    fixture = Dictionary(fixture_db)
    # Except each lemma's frequency rank, which counts all the lemmas a database holds.
    unranked = lambda readings: [replace(r, top_percent=None) for r in readings]
    for word in ("كتب", "وبكتابهم", "سيكتبون"):
        assert unranked(fixture.lookup_ar(word)) == unranked(real.lookup_ar(word))


def test_missing_database_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="No morphology database"):
        Dictionary(tmp_path / "missing.db")


def test_istakhdam_is_measure_x(real):
    assert {r.measure for r in real.lookup_ar("استخدم")} == {"X"}


def test_sayaktubun_reads_in_measures_i_and_iv(real):
    assert sorted((r.lemma, r.measure) for r in real.lookup_ar("سيكتبون")) == [
        ("أَكْتَب", "IV"), ("أَكْتَب", "IV"), ("كَتَب", "I"), ("كَتَب", "I"),
    ]


# Three-letter verb lemmas that get no measure, and why.
UNMAPPED_VERBS = {
    # The database merges a Form III and a Form IV verb into one lemma.
    "آتَى", "آسَى", "آلَف", "آنَس",
    # Form VIII and Form IX are spelled the same.
    "ٱِقْتَتّ",
    # The root does not fit the lemma.
    "ٱِنْبَغَى", "جَثا", "حابَى", "ذَرا", "رَبَّى", "تَصَدَّى", "ضَفا", "مَهَن", "مَهُن", "ٱِمْتَهَن", "ٱِسْتَماح",
    "ٱِسْتَمَل", "تَأَرْجَح", "طَأْمَن", "تَطَأْمَن", "طَمْأَن", "تَطَمْأَن", "تَحَنْجَل", "عَمَّن",
    # Not a verb, though the database tags it as one.
    "آمِين", "آهاً", "حَبَّذا", "حَذارِ", "مادام", "راوَنْد", "ٱِرْتِعاشَة", "مُعاوَنَة", "هَلُمَّ", "هَيْهات",
}


def test_measure_coverage_of_three_letter_verbs(real, real_db):
    from camel_tools.morphology.database import MorphologyDB

    stems = MorphologyDB(str(real_db), "a").stem_hash.values()
    roots = {f["lex"]: f["root"] for entries in stems for _, f in entries if f["pos"] == "verb"}
    # The database writes shadda before the vowel; compare in NFC.
    measures = {unicodedata.normalize("NFC", lemma): real.measure(lemma, root) for lemma, root in roots.items() if root.count(".") == 2}
    unmapped = {lemma for lemma, m in measures.items() if m is None}
    print(f"\nMeasures for {len(measures) - len(unmapped)} of {len(measures)} three-letter verb lemmas "
          f"({1 - len(unmapped) / len(measures):.1%}); {len(roots)} verb lemmas in all")
    assert unmapped == UNMAPPED_VERBS
    # Forms XI and XII are rare; a few verbs add a fourth letter to three root letters (تَمَرْكَز,
    # سَيْطَر) and conjugate as quadriliterals.
    assert set(measures.values()) - {None} == {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "QI", "QII"}
    assert [measures[lemma] for lemma in ("قال", "دَعا", "رَمَى", "وَصَل", "أَخَذ", "قَرَأ", "رَدّ", "آمَن", "آخَذ", "ٱِتَّخَذ", "ٱِطَّلَع", "ٱِخْتار", "ٱِسْتَقام", "تَمَرْكَز", "سَيْطَر", "ٱِحْمَرّ")] == [
        "I", "I", "I", "I", "I", "I", "I", "IV", "III", "VIII", "VIII", "VIII", "X", "QII", "QI", "IX",
    ]


def test_roots_keep_unresolved_radicals_and_drop_malformed_ones(real):
    assert {r.root for r in real.lookup_ar("قال") if r.lemma == "قال"} == {"ق.#.ل"}  # the view shows ◌ for #
    # The database stores لَيْسَ's root as "لسن", not as dotted letters; that is no root at all.
    assert {(r.root, r.measure) for r in real.lookup_ar("ليس") if r.lemma == "لَيْسَ"} == {(None, None)}


def test_default_order_is_stable_grouped_by_lemma_and_most_frequent_first(real):
    # مؤدي and مواتي: the database stores two lemmas spelled alike, one without a frequency.
    for word in ("كتب", "سيكتبون", "علم", "اكل", "طرق", "سابقي", "مؤدي", "مواتي"):
        readings = real.lookup_ar(word)
        assert readings == real.lookup_ar(word), word
        lemmas = [(r.lemma, r.pos) for r in readings]
        assert lemmas == sorted(lemmas, key=lemmas.index), word  # each lemma's readings sit together
        best = [max(-99 if r.frequency is None else r.frequency for r in readings if (r.lemma, r.pos) == lemma) for lemma in lemmas]
        assert best == sorted(best, reverse=True), word
    assert [r.lemma for r in real.lookup_ar("سيكتبون")] == ["كَتَب", "كَتَب", "أَكْتَب", "أَكْتَب"]


def test_readings_place_their_lemma_among_all_lemmas_by_frequency(real):
    # The share of lemmas with a frequency that are at least as frequent as this one.
    top = {r.lemma: r.top_percent for r in real.lookup_ar("سيكتبون")}
    assert top == {"كَتَب": pytest.approx(5.2, abs=0.05), "أَكْتَب": None}
    assert [r.top_percent for r in real.lookup_ar("استخدم")][0] == pytest.approx(7.2, abs=0.05)
