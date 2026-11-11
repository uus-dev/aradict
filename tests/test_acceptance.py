"""The release gate's data acceptance checks (#17)."""

from aradict.acceptance import approx, malformed, overpluralized, singular_after_two


def test_counts_are_rounded_to_two_figures_for_a_learner():
    assert [approx(n) for n in (38353, 35336, 4470, 1126, 45, 7)] == ["38,000", "35,000", "4,500", "1,100", "45", "7"]


def test_well_formed_arabic_passes():
    # Shadda with a vowel, the dagger alif, tanween on alif, alif wasla, hamza seats.
    for text in ("كِتاب", "هٰذا", "مَدْرَسَتَيَّ", "شُكْراً", "ٱِسْتَخْدَم", "إِلَى", "سَأَلَ", "يُؤْمِن"):
        assert malformed(text) is None, text


def test_malformed_arabic_says_what_is_wrong():
    assert malformed("كتابx") == "Latin letters"
    assert malformed("كتاب1") == "other characters"
    assert malformed("کتاب") == "other characters"  # Persian kaf
    assert malformed("َكتب") == "a mark with no letter"
    assert malformed("كَُتب") == "clashing marks on one letter"
    assert malformed("كّّتب") == "clashing marks on one letter"


def test_a_singular_noun_after_two_is_the_two_school_defect():
    for sense in ("two school", "my two school", "two period of times", "and two point of views"):
        assert singular_after_two(sense), sense
    for sense in ("two schools", "the two schools of", "two periods of time", "two men", "two teachers (f.)", "school", "two wounded"):
        assert not singular_after_two(sense), sense


def test_adjective_senses_given_a_plural_ending_are_found():
    for sense in ("two firmly establisheds", "two taking overs", "two ruling outs (f.)"):
        assert overpluralized(sense), sense
    for sense in ("two needs", "two beds", "two schools", "two hot springs"):
        assert not overpluralized(sense), sense
