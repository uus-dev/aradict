"""The dictionary contract, checked against the real pinned database."""

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


def test_fixture_database_matches_real_for_its_lemmas(real, fixture_db):
    fixture = Dictionary(fixture_db)
    for word in ("كتب", "وبكتابهم", "سيكتبون"):
        assert fixture.lookup_ar(word) == real.lookup_ar(word)


def test_missing_database_fails_loudly(tmp_path):
    with pytest.raises(RuntimeError, match="No morphology database"):
        Dictionary(tmp_path / "missing.db")
