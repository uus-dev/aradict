"""The release gate's data acceptance checks (#17)."""

from hashlib import sha256

from aradict.acceptance import approx, coverage, malformed, notices, overpluralized, singular_after_two
from aradict.dictionary import Dictionary
from aradict.views import about_page


def test_about_states_the_measured_coverage(real_db):
    from camel_tools.morphology.database import MorphologyDB

    measured = coverage(Dictionary(real_db), MorphologyDB(str(real_db), "a"))
    without_measure = sum(n for (_, derived), n in measured["measures"].items() if not derived)
    rootless = dict(measured["rootless_by_pos"])
    other = measured["rootless"] - rootless["noun_prop"] - rootless["noun"] - rootless["adj"]
    about = str(about_page())
    stated = about[about.index('id="coverage"'):about.index('id="typing"')]
    # Every figure the section states, as the database measures it today.
    for figure in (
        f"about {approx(measured['entries'])} entries",
        f"{approx(measured['lemmas'])} headwords",
        f"about {approx(measured['roots'])} roots",
        f"all but {approx(without_measure)} of about {approx(measured['verbs'])}",
        f"about 1 root in {round(measured['roots'] / measured['unresolved'])}",
        f"About {approx(measured['rootless'])} entries have no root: about {approx(rootless['noun_prop'])} proper nouns, "
        f"{approx(rootless['noun'])} other nouns, {approx(rootless['adj'])} adjectives and {approx(other)} of other parts of speech.",
    ):
        assert figure in stated


def test_attribution_privacy_statement_and_support_are_in_place(real_db):
    # The release gate (#17): every provenance, license, privacy and support check holds.
    failing = [what for what, holds in notices(real_db, sha256(real_db.read_bytes()).hexdigest()) if not holds]
    assert failing == []


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
