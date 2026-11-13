"""The Wiktionary layer (#20): the pinned kaikki.org extraction, the dataset built from it, and
its join to the CAMeL lemmas, checked against the real data."""

import sqlite3
from contextlib import closing
from hashlib import sha256

import pytest

from aradict import wiktionary
from aradict.data import EXPECTED
from aradict.dictionary import Dictionary


@pytest.fixture(scope="module")
def real(real_db, real_wiktionary):
    return Dictionary(real_db, real_wiktionary)


def senses(entry) -> list[str]:
    """Each numbered sense's gloss."""
    return [sense.gloss for sense in entry.senses]


def test_a_sense_keeps_the_register_label_wiktionary_gives_it(real_wiktionary):
    # جِدَّة "newness" is obsolete in Wiktionary, which says so only in the sense's tags: the #20
    # build kept the text alone, like 893 other labelled senses (PRD, Wiktionary layer, Register).
    newness = next(e for e in wiktionary.entries(real_wiktionary, "جِدَّة", "noun") if e.senses[0].gloss == "newness, recency")
    assert [(s.gloss, s.labels) for s in newness.senses[:2]] == [("newness, recency", ("obsolete",)), ("novelty", ("obsolete",))]


def test_wiktionarys_own_qualifiers_are_labels_not_text(real_wiktionary):
    [kattaba] = wiktionary.entries(real_wiktionary, "كَتَّب", "verb")
    assert (kattaba.senses[0].gloss, kattaba.senses[0].labels) == ("to cause to write, to make someone write", ("transitive", "causative"))


def test_sub_senses_stay_under_their_sense(real_wiktionary):
    [kataba] = wiktionary.entries(real_wiktionary, "كَتَب", "verb")
    write, produce, record = kataba.senses
    assert write.gloss.startswith("to mark (symbols, shapes")
    assert [s.gloss for s in write.subsenses] == ["to draw (figures)", "to cut (figures)"]
    assert len(produce.subsenses) == 2
    assert record.gloss == "to put down in writing, to write down; to record; to register; to track"
    assert [s.gloss for s in record.subsenses][-1] == "to bequeath"


def test_a_lemma_lists_its_wiktionary_senses_but_not_its_relations(real):
    [entry] = real.wiktionary("كِتاب", "noun").entries
    assert entry.word == "كِتَاب"
    assert {"book", "letter, note, paper, piece of writing, message", "a marriage contract."} <= set(senses(entry))
    # "verbal noun of كَتَبَ" says how the word relates to another, not what it means.
    assert not [s for s in senses(entry) if "verbal noun" in s]
    assert entry.url == "https://en.wiktionary.org/wiki/كتاب#Arabic"


def test_a_lemma_joins_its_own_entry_not_one_spelled_with_the_same_letters(real):
    # كُتّاب "Quran school", not كِتَاب "book" and not كُتَّاب "plural of كَاتِب", whose only sense is a relation.
    [entry] = real.wiktionary("كُتّاب", "noun").entries
    assert (entry.word, senses(entry)) == ("كُتَّاب", ["a traditional school for teaching Qur'an"])
    assert ("كَتَاتِيب", ("plural",)) in entry.forms


def test_homographs_from_different_etymologies_stay_apart(real):
    # CAMeL stores قال with no marks; Wiktionary has قَالَ "say" (ق و ل) and قَالَ "nap" (ق ي ل).
    say, nap = real.wiktionary("قال", "verb").entries
    assert (say.word, say.root, senses(say)[0]) == ("قَالَ", "ق و ل", "to say")
    assert (nap.word, nap.root, senses(nap)[0]) == ("قَالَ", "ق ي ل", "To nap.")


def test_a_lemma_joins_the_homograph_its_glosses_match(real):
    # CAMeL glosses قال "say; tell" (and "said"), which Wiktionary's قَالَ "to say" has and قَالَ "to nap" doesn't.
    found = real.wiktionary("قال", "verb")
    assert found.joined is found.entries[0] and senses(found.joined)[0] == "to say"
    # جِدَّة "newness; novelty", not جِدَّة "bank, side, edge of a water body".
    found = real.wiktionary("جِدَّة", "noun")
    assert len(found.entries) == 2 and senses(found.joined)[0] == "newness, recency"


def test_a_lemma_whose_glosses_pick_no_homograph_keeps_them_all(real):
    # CAMeL glosses جَزْر "slaughter; ebb", one of each of its homographs.
    found = real.wiktionary("جَزْر", "noun")
    assert len(found.entries) > 1 and found.joined is None
    # جَدّ "grandfather; good luck": more of its words are in Wiktionary's جَدّ "good luck, good fortune",
    # but جَدّ "grandfather, ancestor" has one too.
    found = real.wiktionary("جَدّ", "noun")
    assert len(found.entries) == 2 and found.joined is None


def test_a_lemma_with_one_entry_joins_it_whatever_its_glosses(real):
    found = real.wiktionary("كُتّاب", "noun")  # CAMeL: "kuttab (village school)"; Wiktionary: "a traditional school …"
    assert found.joined is found.entries[0]


def test_a_verb_joins_its_own_measure_only(real):
    # CAMeL's كَتَب leaves off the final vowel of Wiktionary's كَتَبَ; كَتَّبَ (measure II) is another verb.
    assert [(e.word, e.root) for e in real.wiktionary("كَتَب", "verb").entries] == [("كَتَبَ", "ك ت ب")]
    assert [e.word for e in real.wiktionary("كَتَّب", "verb").entries] == ["كَتَّبَ"]


@pytest.mark.parametrize("camel, wiktionary_spelling", [
    ("كِتاب", "كِتَاب"),  # CAMeL leaves the fatha before a long ا unwritten
    ("كُتّاب", "كُتَّاب"),  # also after a shadda
    ("كَتَب", "كَتَبَ"),  # and a verb's final vowel
    ("أَشَعّ", "أَشَعَّ"),  # also on a doubled letter
    ("مُسْتَوَى", "مُسْتَوًى"),  # tanween fath on a final ى
    ("إِنْجلِيزِيّ", "إِنْجْلِيزِيّ"),  # sukun, written or not
    ("ٱِسْتَخْدَم", "اِسْتَخْدَمَ"),  # alif wasla
    ("أَيْضاً", "أَيْضًا"),  # tanween fath after or before its ا
    ("مُدَرِّس", "مُدَرِّس"),  # shadda and kasra in either order
])
def test_the_join_evens_out_how_the_two_sources_spell_a_lemma(camel, wiktionary_spelling):
    assert wiktionary.spelling(camel) == wiktionary.spelling(wiktionary_spelling)


def test_the_join_keeps_lemmas_with_other_vowels_apart():
    assert wiktionary.spelling("كِتاب") != wiktionary.spelling("كُتَّاب")
    assert wiktionary.spelling("كَتَب") != wiktionary.spelling("كَتَّبَ")


def test_a_headword_wiktionary_leaves_unvocalized_matches_on_its_letters(real):
    assert [e.word for e in real.wiktionary("آيَة", "noun_prop").entries] == ["آية"]


def test_the_part_of_speech_must_agree(real):
    assert real.wiktionary("كِتاب", "verb").entries == []


def test_without_the_dataset_a_lemma_has_no_wiktionary_entries(fixture_db, tmp_path):
    assert Dictionary(fixture_db).wiktionary("كِتاب", "noun") == ([], None)
    assert Dictionary(fixture_db, tmp_path / "missing.db").wiktionary("كِتاب", "noun") == ([], None)


def test_no_wiktionary_text_appears_in_the_gpl_data_files(real_db, real_wiktionary):
    # CC BY-SA text can't be merged with GPL v2-only data (PRD, Wiktionary layer): after the
    # build, the CAMeL files are still exactly as pinned, and the dataset is a file of its own.
    assert all(sha256((real_db.parent / name).read_bytes()).hexdigest() == digest for name, digest in EXPECTED.items())
    assert real_wiktionary.resolve().parent != real_db.resolve().parent
    # Senses long enough to be Wiktionary's own words: either source may say "book" or "to say".
    quoted = [text for lemma, pos in (("كِتاب", "noun"), ("كُتّاب", "noun"), ("قال", "verb"))
              for entry in wiktionary.entries(real_wiktionary, lemma, pos) for sense in entry.senses
              for text in (sense.gloss, *(sub.gloss for sub in sense.subsenses)) if len(text.split()) > 3]
    assert "a traditional school for teaching Qur'an" in quoted
    for path in real_db.parent.iterdir():
        data = path.read_bytes()
        assert [text for text in quoted if text.encode() in data] == [], path


KAIKKI_LINE = (
    '{"word": "كتاب", "pos": "noun", "forms": [{"form": "كِتَاب", "tags": ["canonical", "masculine"]}, {"form": "kitāb", "tags": ["romanization"]}],'
    ' "senses": [{"glosses": ["verbal noun of كَتَبَ"], "tags": ["form-of"], "form_of": [{"word": "كَتَبَ"}]}, {"glosses": ["book"]}]}\n'
)


def test_one_command_checks_the_extraction_against_the_pin_and_builds_the_dataset(tmp_path, monkeypatch):
    source, target = tmp_path / "kaikki.jsonl", tmp_path / "wiktionary.db"
    source.write_text(KAIKKI_LINE, encoding="utf-8")
    monkeypatch.setattr(wiktionary, "SHA256", sha256(source.read_bytes()).hexdigest())
    wiktionary.ensure_dataset(source, target)
    [entry] = wiktionary.entries(target, "كِتاب", "noun")
    assert (entry.word, senses(entry), entry.romanization) == ("كِتَاب", ["book"], "kitāb")


def test_a_dataset_an_older_build_wrote_is_refused_until_rebuilt(fixture_db, tmp_path):
    # #20's dataset kept each sense as bare text; reading it now would fail on every lookup.
    old = tmp_path / "wiktionary.db"
    with closing(sqlite3.connect(old)) as db:
        db.execute("CREATE TABLE entry (letters TEXT NOT NULL, pos TEXT NOT NULL, entry TEXT NOT NULL)")
    with pytest.raises(RuntimeError, match="python -m aradict.wiktionary"):
        Dictionary(fixture_db, old)


def test_an_extraction_that_does_not_match_the_pin_is_refused(tmp_path):
    source, target = tmp_path / "kaikki.jsonl", tmp_path / "wiktionary.db"
    source.write_text(KAIKKI_LINE, encoding="utf-8")
    with pytest.raises(RuntimeError, match="kaikki.org has probably published a newer extraction") as refused:
        wiktionary.ensure_dataset(source, target)
    assert "SHA256 in src/aradict/wiktionary.py" in str(refused.value)  # how to move the pin
    assert not target.exists()
