"""The dictionary contract, checked against the real pinned database."""

import re
import time
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
    assert sorted(first_sense(r.gloss) for r in real.lookup_ar("كتب")) == ["books", "he/it was written", "he/it wrote"]


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
    assert [first_sense(r.gloss) for r in real.lookup_ar("كَتَبَ")] == ["he/it wrote"]
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
    assert unranked(fixture.lookup_en("book")) == unranked(real.lookup_en("book"))


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


def test_text_keeps_every_token_in_order_with_its_kind_and_offset(real):
    passage = "كتب، 3 BBC\nقخغثص"
    tokens = real.analyze_text(passage)
    assert [(t.text, t.kind) for t in tokens] == [
        ("كتب", "word"), ("،", "punctuation"), (" ", "space"), ("3", "number"), (" ", "space"),
        ("BBC", "foreign"), ("\n", "space"), ("قخغثص", "unknown"),
    ]
    assert all(passage[t.start:t.end] == t.text for t in tokens)
    assert tokens[0].readings == tuple(real.lookup_ar("كتب")) and tokens[-1].readings == ()


def test_text_diacritics_filter_their_own_token(real):
    vocalized, bare = real.analyze_text("كَتَبَ كتب")[::2]
    assert [first_sense(r.gloss) for r in vocalized.readings] == ["he/it wrote"]
    assert len(bare.readings) == 3


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


def letters(arabic: str) -> str:
    return re.sub("[ً-ٰٟ]", "", arabic)


def test_arabizi_without_vowels_reads_as_the_bare_letters(real):
    assert real.arabizi("ktb") == "كتب"


def test_arabizi_vowels_are_marks_or_long_letters_as_the_database_confirms(real):
    # The reference leaves "i" in Latin and always writes "a" as ا.
    assert real.arabizi("kitab") == "كِتاب"
    assert real.arabizi("katab") == "كَتَب"
    # The typed vowel filters like a vowel mark, as About promises: كِتاب "book", not كُتّاب "writers".
    assert [r.lemma for r in real.lookup_ar(real.arabizi("kitab"))] == ["كِتاب"]


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


def forms(readings) -> list[tuple[str, str]]:
    return [(unicodedata.normalize("NFC", r.form), r.gloss) for r in readings]


def test_related_forms_share_the_lemma_and_part_of_speech(real):
    # A noun's singular and plural, each in its dictionary form with its own meaning.
    assert forms(real.related("كِتاب", "noun")) == [("كِتاب", "book"), ("كُتُب", "books")]
    # A verb's perfect and imperfect, active and passive, each in its "he" form.
    verb = real.related("كَتَب", "verb")
    assert [r.form for r in verb] == ["كَتَبَ", "كُتِبَ", "يَكْتُب", "يُكْتَب"]
    assert {(r.lemma, r.pos, r.root, r.measure) for r in verb} == {("كَتَب", "verb", "ك.ت.ب", "I")}
    # A hollow verb's imperfect is يَقُول; the short stem of لَمْ يَقُلْ is not a form of its own.
    assert [r.form for r in real.related("قال", "verb")] == ["قالَ", "قُلْ", "قِيلَ", "يُقال", "يَقُول"]
    # A noun stored without its feminine ending is listed with it, and with its plural ending.
    assert ("كِتابات", "writings; essays") in forms(real.related("كِتابَة", "noun"))
    assert real.related("كِتاب", "verb") == [] and real.related("قخغثص", "noun") == []


def test_root_family_lists_verbs_by_measure_then_nouns_and_adjectives(real):
    family = real.root_family("ك.ت.ب")
    assert {r.root for r in family} == {"ك.ت.ب"}
    verbs = [r for r in family if r.pos == "verb"]
    assert family[:len(verbs)] == verbs  # verbs first
    assert list(dict.fromkeys(r.measure for r in verbs)) == ["I", "III", "IV", "VI", "VII", "VIII", "X"]
    assert {r.pos for r in family[len(verbs):]} == {"noun", "adj", "noun_prop"}
    # Then each lemma's forms together, the lemmas in alphabetical order by their letters.
    lemmas = list(dict.fromkeys(r.lemma for r in family[len(verbs):]))
    assert lemmas[:3] == ["ٱِسْتِكْتاب", "ٱِكْتِتاب", "كاتِب"] and lemmas[-2:] == ["مُكْتَتِب", "مَكْتُوب"]
    assert forms(r for r in family if r.lemma == "كِتاب") == [("كِتاب", "book"), ("كُتُب", "books")]
    assert ("مَكْتَبَة", "library; bookstore") in forms(family)
    assert len({(r.lemma, r.pos) for r in family}) == 32
    # A root with an unresolved radical is a root like any other.
    assert {r.lemma for r in real.root_family("ق.#.ل")} >= {"قال", "قَوْل", "مَقال"}
    assert real.root_family("NTWS") == [] and real.root_family("ق.خ.غ") == []


# --- English → Arabic -----------------------------------------------------------------------

def lemmas(readings) -> list[str]:
    return list(dict.fromkeys(r.lemma for r in readings))


def test_english_book_finds_kitab_and_sifr(real):
    found = real.lookup_en("book")
    assert {"كِتاب", "سِفْر"} <= set(lemmas(found))
    assert real.lookup_en("Book ") == found  # case and surrounding whitespace don't matter


def test_english_phrase_matches_whole_not_its_first_word(real):
    phrase = lemmas(real.lookup_en("piece of writing"))
    assert phrase == ["كِتابَة"]  # essay; piece of writing
    assert "كِتابَة" not in lemmas(real.lookup_en("piece"))
    assert "قِطْعَة" in lemmas(real.lookup_en("piece"))  # the reference matches "piece of writing" by "piece"


def test_english_inflected_forms_find_their_base_form(real):
    assert {"كِتاب", "سِفْر"} <= set(lemmas(real.lookup_en("books")))
    # The plural كُتُب is glossed "books" itself; the lemma's own form comes first.
    assert [r.form for r in real.lookup_en("books") if r.lemma == "كِتاب"] == ["كِتاب", "كُتُب"]
    assert [r.form for r in real.lookup_en("wrote")] == ["كَتَبَ"]
    assert "كَتَب" in lemmas(real.lookup_en("writes"))


def test_english_inflects_as_the_glosses_do(real):
    # The third person of "focus" is "focuses", as the glosses write it ("he/it focuses").
    verbs = [r for r in real.lookup_en("focus") if r.pos == "verb"]
    assert verbs and real.lookup_en("focuses") == verbs


def test_english_finds_each_word_once_and_verbs_in_citation_form(real):
    found = real.lookup_en("eat")
    assert len({(r.form, r.gloss) for r in found}) == len(found)
    # أَكَل has stems أَكَل, أْكُل and كُل, all glossed "eat": shown once, as the perfect "he/it ate".
    assert [(r.form, first_sense(r.gloss)) for r in found if r.lemma == "أَكَل"] == [("أَكَلَ", "he/it ate")]
    assert {r.tags for r in found} == {("verb", "active", "3rd person masculine singular")}


def test_english_most_frequent_first(real):
    frequencies = [r.frequency for r in real.lookup_en("eat")]
    known = [f for f in frequencies if f is not None]
    assert known == sorted(known, reverse=True) and frequencies[len(known):] == [None] * (len(frequencies) - len(known))


def test_english_ignores_bracketed_annotations(real):
    assert "حَلُوم" in lemmas(real.lookup_en("cheese"))  # glossed "(Egyptian)_cheese"
    assert real.lookup_en("egyptian cheese") == []


def test_english_unknown_or_blank_finds_nothing(real):
    assert real.lookup_en("xyzzy") == []
    assert real.lookup_en("  ") == []
