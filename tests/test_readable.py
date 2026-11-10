"""Readable results: whole-word gloss, grammar and segments, checked against the real database."""

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


def test_stem_glosses_that_already_combine_words_read_as_one_phrase(real):
    assert "with that" in glosses(real, "بأن")  # CAMeL: with_+_that
    assert "with/by you (f.)" in glosses(real, "بك")  # with;by_+_you_[fem.sg.], pronoun already included


def sample_words(db_path, every: int = 40) -> list[str]:
    """Every nth stem of the database, bare and with common attached parts."""
    stems, in_stems = [], False
    with db_path.open(encoding="utf-8") as db:
        for line in db:
            if line.startswith("###"):
                in_stems = line.startswith("###STEMS###")
            elif in_stems and line.strip():
                stems.append(line.split("\t", 1)[0])
    return [w for stem in stems[::every] for w in (stem, "و" + stem, "بال" + stem, stem + "ها", "س" + "ي" + stem)]


def test_no_raw_tags_underscores_or_plus_signs_in_any_gloss(real, real_db):
    bad = [(w, r.gloss) for w in sample_words(real_db) for r in real.lookup_ar(w) if any(c in r.gloss for c in "_+[]<>")]
    assert bad == []
