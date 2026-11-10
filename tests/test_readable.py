"""Readable results: whole-word gloss, grammar and segments, checked against the real database."""

import re
from unicodedata import normalize

import pytest

from aradict.dictionary import Dictionary


@pytest.fixture(scope="module")
def real(real_db):
    return Dictionary(real_db)


def glosses(real, word: str) -> set[str]:
    return {r.gloss for r in real.lookup_ar(word)}


def test_proclitics_go_in_front_and_possessives_before_the_noun(real):
    assert glosses(real, "وبكتابهم") == {
        "and by/with their book",
        "and by/with their authors; their writers",
        "and by/with their kuttab (village school); their Quran school",
    }


def test_verbs_get_their_subject_and_future(real):
    assert glosses(real, "سيكتبون") == {
        "they will write",
        "they will be written; they will be fated; they will be destined",
        "they will dictate; they will make write",
        "they will be dictated",
    }


def test_perfect_verbs_read_as_subject_and_verb(real):
    # English past tense ("wrote") is out of scope; the grammar line says the verb is perfect.
    assert glosses(real, "كتب") == {
        "he/it write",
        "he/it was written; he/it was fated; he/it was destined",
        "books",
    }


def test_measure_x_verbs_including_the_imperative(real):
    assert glosses(real, "استخدم") == {
        "he/it utilize; he/it employ; he/it operate",
        "he/it was used; he/it was utilized; he/it was employed",
        "use! (to one man)",
        "I utilize; I employ; I operate",
        "I am used; I am utilized; I am employed",
    }


def test_pronoun_suffixes_become_objects_or_possessives(real):
    assert glosses(real, "الى") == {
        "to; towards",
        "to me; towards me",
        "my family; my clan",
        "mechanical; automatic",
        "he/it promise; he/it take an oath",
        "I follow; I come after",
    }


def test_duals_construct_forms_and_feminine_persons(real):
    assert glosses(real, "مدرستي") == {
        "my school",
        "the two schools of",
        "my two schools",
        "my instructor (f.); my teacher (f.)",
        "the two instructors (f.) of; the two teachers (f.) of",
        "my two instructors (f.); my two teachers (f.)",
    }


def test_wa_reads_as_and_even_when_every_analysis_has_a_case_ending(real):
    # The dual construct has no caseless analysis; وَ still reads "and", not "while".
    assert glosses(real, "ومدرستي") >= {"and the two schools of", "and my two schools"}


def test_senses_already_plural_are_not_pluralized_again(real):
    assert "my two laws; my two statutes; my two regulations" in glosses(real, "قانوني")


def test_article_and_sound_plurals(real):
    assert "the book" in glosses(real, "الكتاب")
    assert glosses(real, "مدرسون") == {"instructors; teachers"}
    assert glosses(real, "مدرسات") == {"instructors (f.); teachers (f.)"}


def test_case_tags_are_dropped_and_agreement_tags_made_readable(real):
    # CAMeL's composite glosses read "the+books+[def.acc.]" and "which;who;whom_[fem.du.]".
    assert "the books" in glosses(real, "الكتب")
    assert glosses(real, "اللتين") == {"which; who; whom (f. dual)"}


def test_paired_function_words_stay_inside_one_sense(real):
    # CAMeL writes "more;most_tractable;more;most_flexible" and "of;from_Irbid".
    assert "more/most tractable; more/most flexible" in glosses(real, "أسلس")
    assert "of/from Irbid" in glosses(real, "إربدي")


def test_stem_glosses_that_already_combine_words_read_as_one_phrase(real):
    assert "with that" in glosses(real, "بأن")  # CAMeL: with_+_that
    assert "with/by you (f.)" in glosses(real, "بك")  # with;by_+_you_[fem.sg.], pronoun already included
    # بِاللّٰهِ is stored with its بِ, and its gloss "by God" already says so.
    assert glosses(real, "بالله") == {"by God; Allah"}
    assert glosses(real, "وبالله") == {"and by God; Allah"}


def grammar(real, word: str) -> dict[str, tuple]:
    """Each reading's short tags and grammar description, keyed by form and lemma."""
    return {f"{r.form} {r.lemma}": (r.tags, r.grammar) for r in real.lookup_ar(word)}


def test_verbs_are_described_by_aspect_voice_mood_and_subject(real):
    ktb = grammar(real, "كتب")
    assert ktb["كَتَبَ كَتَب"] == (("verb", "active", "3rd person masculine singular"), "perfect (past)")
    assert ktb["كُتِبَ كَتَب"] == (("verb", "passive", "3rd person masculine singular"), "perfect (past)")
    assert grammar(real, "سيكتبون")["سَيَكْتُبُونَ كَتَب"] == (
        ("verb", "active", "3rd person masculine plural"),
        "imperfect (present/future), indicative mood",
    )
    assert grammar(real, "استخدم")["اِسْتَخْدِمْ ٱِسْتَخْدَم"][1] == "imperative"
    assert grammar(real, "استخدم")["أَسْتَخْدِم ٱِسْتَخْدَم"][0][2] == "1st person singular"  # no gender in the 1st person


def test_nouns_are_described_by_number_state_and_case_where_the_spelling_fixes_them(real):
    assert grammar(real, "كتب")["كُتُب كِتاب"] == (("noun", "masculine plural"), "broken plural")
    mdrsty = grammar(real, "مدرستي")
    assert mdrsty["مَدْرَسَتَيْ مَدْرَسَة"] == (("noun", "feminine dual"), "construct state, accusative or genitive case")
    assert mdrsty["مَدْرَسَتِي مَدْرَسَة"] == (("noun", "feminine singular"), "construct state")
    # The bare word can be any case or state, so neither is claimed.
    assert grammar(real, "كتاب")["كِتاب كِتاب"] == (("noun", "masculine singular"), "")
    assert grammar(real, "الى")["إِلَى إِلَى"] == (("preposition",), "")


def segments(real, word: str, form: str, lemma: str | None = None) -> list[tuple[str, str, str]]:
    r = next(r for r in real.lookup_ar(word) if nfc(r.form) == nfc(form) and lemma in (None, r.lemma))
    return [(nfc(s.text), s.role, s.label) for s in r.segments]


def nfc(text: str) -> str:
    """CAMeL writes shadda before or after a vowel; compare spellings in one canonical order."""
    return normalize("NFC", text)


def test_segments_label_each_attached_part(real):
    assert segments(real, "وبكتابهم", "وَبِكِتابهم") == [
        ("وَ", "prefix", "and"), ("بِ", "prefix", "by/with"), ("كِتاب", "stem", "book"), ("هم", "suffix", "their"),
    ]
    assert segments(real, "سيكتبون", "سَيَكْتُبُونَ") == [
        ("سَ", "prefix", "will"), ("يَ", "prefix", "they, subject prefix"),
        ("كْتُب", "stem", "write"), ("ُونَ", "suffix", "they, subject ending"),
    ]
    assert segments(real, "كتب", "كَتَبَ") == [("كَتَب", "stem", "write"), ("َ", "suffix", "he/it, subject ending")]
    assert segments(real, "كتب", "كُتُب") == [("كُتُب", "stem", "books")]


def test_stems_stored_with_their_clitics_still_split_into_parts(real):
    # The database stores ما زِلْتُ "I am still" as one stem; its parts still show.
    assert segments(real, "مازلت", "مازِلْتُ") == [
        ("ما", "prefix", "not"), ("زِلْ", "stem", "not stop/cease I (I continue)"), ("تُ", "suffix", "I, subject ending"),
    ]


def test_a_letter_the_spelling_drops_does_not_shift_the_parts(real):
    # لِ + ال + كِتاب is written لِلكِتاب: the alif of ال is not written.
    assert segments(real, "للكتاب", "لِلكِتاب") == [
        ("لِ", "prefix", "for/to"), ("ل", "prefix", "the"), ("كِتاب", "stem", "book"),
    ]


def test_two_parts_sharing_a_doubled_letter(real):
    # The dual ending تَيْ and "my" يَ are written تَيَّ: one ي with a shadda stands for both.
    # In the word the doubled letter goes to the later part; each part's own spelling keeps its letter.
    r = next(r for r in real.lookup_ar("مدرستي") if nfc(r.form) == nfc("مَدْرَسَتَيَّ") and r.lemma == "مَدْرَسَة")
    assert [(nfc(s.text), nfc(s.spelling), s.role, s.label) for s in r.segments] == [
        ("مَدْرَس", "مَدْرَس", "stem", "school"),
        ("َتَ", "َتَيْ", "suffix", "dual ending"),
        ("يَّ", "يَ", "suffix", "my"),
    ]
    # The same rule when the stem and a suffix share the letter: إِلَي + يَ is written إِلَيَّ.
    assert segments(real, "الى", "إِلَيَّ") == [("إِلَ", "stem", "to"), ("يَّ", "suffix", "me")]


def sample_words(db_path, every: int = 40) -> list[str]:
    """Every nth stem of the database, bare and with common attached parts."""
    stems, in_stems = [], False
    with db_path.open(encoding="utf-8") as db:
        for line in db:
            if line.startswith("###"):
                in_stems = line.startswith("###STEMS###")
            elif in_stems and line.strip():
                stems.append(line.split("\t", 1)[0])
    return [w for stem in stems[::every] for w in (stem, "و" + stem, "بال" + stem, stem + "ها", "سي" + stem)]


@pytest.fixture(scope="module")
def sample(real, real_db):
    """About 9,000 lookups across the database, for checks that must hold for every reading."""
    return [(word, r) for word in sample_words(real_db) for r in real.lookup_ar(word)]


def test_no_raw_tags_underscores_or_plus_signs_in_any_gloss(sample):
    assert [(w, r.gloss) for w, r in sample if any(c in r.gloss for c in "_+[]<>")] == []


def test_segments_always_spell_the_whole_form(sample):
    for word, r in sample:
        roles = "".join({"prefix": "p", "stem": "s", "suffix": "x"}[s.role] for s in r.segments)
        assert nfc("".join(s.text for s in r.segments)) == nfc(r.form), (word, r.segments)
        assert re.fullmatch("p*sx*", roles), (word, r.form, r.segments)
        assert all(s.text and s.label and "_" not in s.label for s in r.segments), (word, r.form, r.segments)
