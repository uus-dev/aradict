"""The Wiktionary layer (#20): the pinned kaikki.org extraction, the dataset built from it, and
its join to the CAMeL lemmas, checked against the real data."""

import sqlite3
import unicodedata
from contextlib import closing
from hashlib import sha256

import pytest

from aradict import wiktionary
from aradict.data import EXPECTED
from aradict.dictionary import Dictionary
from aradict.wiktionary import Form, Relation


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
    assert Form("كَتَاتِيب", ("plural",), "katātīb") in entry.forms


# --- Forms, pronunciation and relations (#23) ----------------------------------------------------

def test_an_entry_keeps_its_relations_apart_from_its_meanings_with_their_labels(real):
    # Wiktionary's كِتَاب is an obsolete verbal noun of كَتَبَ (PRD, Wiktionary layer, Register).
    [kitab] = real.wiktionary("كِتاب", "noun").entries
    assert kitab.relations == (
        Relation("verbal noun of", "كَتَبَ", "kataba", ("Measure I", "obsolete")),
        Relation("verbal noun of", "كَاتَبَ", "kātaba", ("Measure III",)),
    )
    assert "book" in senses(kitab)


def test_an_entry_whose_senses_are_all_relations_is_kept(real_wiktionary):
    # كُتُب "plural of كِتَاب", which the #20 build left out. A label the relation's own words
    # already say ("Classical Arabic spelling of") isn't repeated.
    [kutub] = wiktionary.entries(real_wiktionary, "كُتُب", "noun")
    assert (kutub.senses, kutub.relations) == ((), (Relation("plural of", "كِتَاب", "kitāb", ()),))
    [classical] = wiktionary.entries(real_wiktionary, "كِتٰب", "noun")
    assert classical.relations == (Relation("Classical Arabic spelling of", "كِتَاب", "kitāb", ()),)


def test_a_relation_to_two_words_is_of_the_same_kind_for_both(real):
    [farigh] = real.wiktionary("فارِغ", "adj").entries
    assert {r.kind for r in farigh.relations} == {"active participle of"} and len(farigh.relations) == 2


def test_a_lemma_wiktionary_has_only_as_a_relation_joins_that_entry(real):
    # Wiktionary's إِقَالَة is only "verbal noun of أَقَالَ"; it is CAMeL's lemma إِقالَة, and gives its root (#26).
    found = real.wiktionary("إِقالَة", "noun")
    assert found.joined.relations == (Relation("verbal noun of", "أَقَالَ", "ʔaqāla", ("Measure IV",)),)
    assert real.filled_root("إِقالَة", "noun", "ق.#.ل") == "ق.ي.ل"


def test_an_entry_keeps_its_plurals_gender_and_verbal_nouns_with_their_transliteration(real):
    [kitab] = real.wiktionary("كِتاب", "noun").entries
    assert kitab.forms[:2] == (Form("كِتَاب", ("canonical", "masculine"), None), Form("كُتُب", ("plural",), "kutub"))
    [kataba] = real.wiktionary("كَتَب", "verb").entries
    assert [f.form for f in kataba.forms if "noun-from-verb" in f.tags] == ["كِتَابَة", "كَتْب", "كِتَاب"]


def test_a_label_on_one_side_of_a_relation_shows_on_the_other(real):
    # كِتَاب says it is an obsolete verbal noun of كَتَبَ; كَتَبَ's list of verbal nouns says so too, in Wiktionary's order.
    [kataba] = real.wiktionary("كَتَب", "verb").entries
    assert [(f.form, f.tags) for f in kataba.forms if "noun-from-verb" in f.tags] == [
        ("كِتَابَة", ("noun-from-verb",)), ("كَتْب", ("noun-from-verb",)), ("كِتَاب", ("noun-from-verb", "obsolete")),
    ]


def test_an_entry_keeps_its_transliteration_and_pronunciations(real):
    [kitab] = real.wiktionary("كِتاب", "noun").entries
    assert kitab.romanization == "kitāb"
    assert kitab.ipa[0] == ("/ki.taːb/", "")  # Modern Standard Arabic's has no place
    assert ("[keˈtæːb]", "Egypt") in kitab.ipa and ("[kteːb]", "Lebanese Arabic") in kitab.ipa


def test_a_pronunciation_kaikki_copies_from_another_entry_on_the_page_is_left_out(real_wiktionary):
    # kaikki.org gives كَتْب (katb) the pronunciation of كَتَبَ, /ka.ta.ba/, which its romanization says isn't its own.
    [katb] = wiktionary.entries(real_wiktionary, "كَتْب", "noun")
    assert (katb.romanization, katb.ipa) == ("katb", ())


@pytest.mark.parametrize("ipa, romanization", [
    ("/ki.taːb/", "kitāb"), ("/d͡ʒa.maːl/", "jamāl"), ("/ʕa.ra.biː/", "ʕarabiyy"), ("/ʔin.ɡliː.zijj/", "ʔinglīziyy"),
    ("/aʃ.ʃarq al.ʔaw.satˤ/", "aš-šarq al-ʔawsaṭ"), ("/tˤibː/", "ṭibb"), ("/ħad͡ʒ.d͡ʒa.ra/", "ḥajjara"),
])
def test_a_pronunciation_fits_the_entrys_romanization(ipa, romanization):
    assert wiktionary.says(ipa, romanization)


def test_a_pronunciation_of_another_word_does_not_fit():
    assert not wiktionary.says("/ka.ta.ba/", "katb") and not wiktionary.says("/qa.mar/", "qamara")


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


def test_a_lemma_whose_glosses_pick_no_homograph_or_several_keeps_them_all(real):
    # CAMeL glosses جَزْر "slaughter; ebb", one of each of its homographs: it picks both.
    found = real.wiktionary("جَزْر", "noun")
    assert len(real.picked("جَزْر", "noun")) == len(found.entries) == 2 and found.joined is None
    # جَدّ "grandfather; good luck; grandmother": no homograph says "grandmother", so none is picked.
    found = real.wiktionary("جَدّ", "noun")
    assert real.picked("جَدّ", "noun") == [] and len(found.entries) == 2 and found.joined is None


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
    ("الَّذِي", "اَلَّذِي"),  # a vowel on an opening bare ا, which either source may write
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


# --- Roots filled from Wiktionary (#26) ---------------------------------------------------------

def test_camels_gloss_picks_the_homograph_that_fills_an_open_root(real):
    # CAMeL's قال (ق.#.ل) "said" matches two Wiktionary entries: قَالَ "to say" (ق و ل) and "to nap" (ق ي ل).
    assert [e.root for e in real.picked("قال", "verb")] == ["ق و ل"]
    assert real.filled_root("قال", "verb", "ق.#.ل") == "ق.و.ل"


def test_an_open_root_is_filled_where_the_entries_agree(real):
    assert real.filled_root("قاوَل", "verb", "ق.#.ل") == "ق.و.ل"
    assert real.filled_root("أَقال", "verb", "ق.#.ل") == "ق.ي.ل"  # the same open root, another letter
    assert real.filled_root("أَكَل", "verb", "#.ك.ل") == "ء.ك.ل"  # a hamza
    assert real.filled_root("مُقِيم", "noun", "ق.#.م") is None  # Wiktionary gives this entry no root, and relates it to no word
    assert real.filled_root("كَتَب", "verb", "ك.ت.ب") is None  # nothing open


def test_a_lemma_whose_wiktionary_entries_disagree_on_the_root_keeps_it_open(real):
    # مَقال's entries are of ق و ل and ق ي ل, and CAMeL's "article; essay" picks neither.
    assert real.picked("مَقال", "noun") == [] and real.filled_root("مَقال", "noun", "ق.#.ل") is None
    # CAMeL's سائِل joins two of Wiktionary's nouns: "liquid" (س ي ل) and "questioner" (س ء ل).
    assert {e.root for e in real.picked("سائِل", "noun")} == {"س ي ل", "س ء ل"}
    assert real.filled_root("سائِل", "noun", "س.#.ل") is None
    # CAMeL's هال "frighten" is Wiktionary's ه و ل, but no entry says its "pour".
    assert real.picked("هال", "verb") == [] and real.filled_root("هال", "verb", "ه.#.ل") is None


def test_a_filled_root_holds_every_lemma_filled_to_it_and_the_open_roots_others_apart(real):
    family = real.root_family("ق.و.ل")
    # With the verbal nouns of قَالَ, تَقَوَّلَ and قَاوَلَ, whose roots they take (wiktionary_root).
    assert {r.lemma for r in family} == {"قال", "قاوَل", "مَقُولَة", "قَوْل", "تَقَوُّل", "مُقاوَلَة"}
    assert {r.root for r in family} == {"ق.#.ل"}  # each form keeps the root CAMeL gives it
    # إِقالَة's only entry says it is the "verbal noun of أَقَالَ" (#23), and gives the root ق ي ل; ٱِسْتِقالَة
    # "resignation" gives none, but is the verbal noun of اِسْتَقَالَ, of ق ي ل.
    assert {r.lemma for r in real.root_family("ق.ي.ل")} == {"أَقال", "ٱِسْتَقال", "مَقِيل", "قَيْلُولَة", "إِقالَة", "ٱِسْتِقالَة"}
    # The lemmas Wiktionary can't place are listed apart, as not confirmed; not those it places elsewhere.
    unconfirmed = {r.lemma for r in real.unconfirmed("ق.و.ل")}
    assert {"مَقال", "قَيْل"} <= unconfirmed and not {"قال", "أَقال", "قَيْلُولَة", "قَوْل"} & unconfirmed
    assert real.family_size("ق.و.ل") == len(family) + len(real.unconfirmed("ق.و.ل"))
    # CAMeL's open root keeps its whole family; a root no lemma is filled to (ق ء ل) has nothing apart.
    assert len(real.root_family("ق.#.ل")) == 42
    assert real.unconfirmed("ق.#.ل") == real.unconfirmed("ك.ت.ب") == real.unconfirmed("ق.ء.ل") == []


def test_an_entry_that_only_relates_its_word_to_another_takes_that_words_root(real):
    # Wiktionary's إِثَارَة is only "verbal noun of أَثَارَ", and gives no root of its own; أَثَارَ's is ث و ر.
    assert real.wiktionary("إِثارَة", "noun").joined.root is None
    assert real.filled_root("إِثارَة", "noun", "ث.#.ر") == "ث.و.ر"
    assert real.filled_root("آباء", "noun", "#.ب.#") == "ء.ب.و"  # "plural of أَب"
    # An entry with meanings of its own too: سِيَاحَة "tourism" is also "verbal noun of سَاحَ" (س ي ح).
    assert real.filled_root("سِياحَة", "noun", "س.#.ح") == "س.ي.ح"
    # The word is Wiktionary's headword as written: لِدَة is the verbal noun of the verb وَلَدَ (و ل د), not of the noun وَلَد.
    assert real.filled_root("لِدَة", "noun", "#.ل.د") == "و.ل.د"
    # Never guessed: إِهْدَاء is the verbal noun of أَهْدَأَ (ه د ء) and of أَهْدَى (ه د ي);
    # أَبْنَاء is the plural of اِبْن, which gives no root.
    assert real.filled_root("إِهْداء", "noun", "ه.د.#") is None
    assert real.filled_root("أَبْناء", "noun", "ب.ن.#") is None


def test_of_a_related_words_homographs_the_one_the_dictionarys_lemma_joins_gives_the_root(real):
    # قَوْل "speech" is the verbal noun of قَالَ; of Wiktionary's قَالَ "say" (ق و ل) and "nap" (ق ي ل),
    # CAMeL's قال "said" joins "say" (see picked).
    assert real.filled_root("قَوْل", "noun", "ق.#.ل") == "ق.و.ل"
    # نَيْل is the verbal noun of نَالَ, whose homographs are of ن و ل and ن ي ل; CAMeL's نال joins neither.
    assert real.filled_root("نَيْل", "noun", "ن.#.ل") is None


def test_a_root_wiktionary_gives_with_other_letters_is_not_used(real):
    assert real.wiktionary_root("سِوار", "noun", "س.#.ر") == "ش.ج.ر"
    assert real.filled_root("سِوار", "noun", "س.#.ر") is None


# --- Words only Wiktionary has (#24) -------------------------------------------------------------

@pytest.mark.parametrize("word", ["تغريدة", "تغريدات", "والتغريدات", "بالتغريدة", "للتغريدات", "تغريدتها", "تغريداتهم", "تَغْرِيدَة"])
def test_a_word_only_wiktionary_has_is_found_from_the_forms_its_entry_lists(real, word):
    # CAMeL reads تغريدة only as تَغْرِيد "his twittering"; Wiktionary's تَغْرِيدَة "a tweet" lists its
    # plural, definite and case forms. Attached words are stripped as Milestone 1 strips them.
    [tweet] = [e for e in real.wiktionary_only(word) if e.word == "تَغْرِيدَة"]
    assert "a tweet" in senses(tweet)


def words(real, word: str, **options) -> set[str]:
    return {e.word for e in real.wiktionary_only(word, **options)}


def test_finding_a_word_by_its_forms_follows_the_lookups_letter_and_diacritic_rules(real):
    assert "تَغْرِيدَة" in words(real, "تغريده")  # a final ه also finds ة
    assert "تَغْرِيدَة" not in words(real, "تُغْرِيدَة")  # a vowel none of its forms has
    assert "تَغْرِيدَة" in words(real, "تُغْرِيدَة", filter_diacritics=False)
    # A bare ا finds any hamza; a typed one must match. No lemma joins Wiktionary's إِنْتَرْنَت "Internet": CAMeL's is إِنْتِرْنِت.
    assert words(real, "انترنت") == words(real, "إنترنت") == {"إِنْتَرْنَت"} and words(real, "أنترنت") == set()
    assert words(real, "قخغثص") == set()


def test_an_entry_is_only_wiktionarys_unless_a_lemma_joins_it(real):
    # The count of words only Wiktionary has (acceptance.wiktionary_only) rests on this.
    [kitab] = real.wiktionary("كِتاب", "noun").entries
    say, nap = real.wiktionary("قال", "verb").entries
    [tweet] = [e for e in real.wiktionary_only("تغريدة") if e.word == "تَغْرِيدَة"]
    assert real.joined(kitab) and real.joined(say)
    assert not real.joined(nap) and not real.joined(tweet)  # a homograph CAMeL's gloss leaves out is Wiktionary's own (#22)
    # Homographs a gloss can't tell apart all stay under the lemma (جَزْر), so each is joined.
    assert all(real.joined(e) for e in real.wiktionary("جَزْر", "noun").entries)


def test_only_the_words_no_lemma_of_the_dictionary_joins_are_found(real):
    # كتب is CAMeL's كَتَب and كُتُب (of كِتاب). Wiktionary also has كَتَّبَ "cause to write" and two entries
    # that only relate a word to another, كَتْب "verbal noun of كَتَبَ" and كِتٰب, a Classical spelling of كِتَاب;
    # كُتُب "plural of كِتَاب" is CAMeL's reading too, which the page decides (views).
    assert words(real, "كتب") == {"كَتَّبَ", "كَتْب", "كُتُب", "كِتٰب"}


def test_autocomplete_offers_words_only_wiktionary_has_after_the_dictionarys_own(real):
    offered = real.suggest("تغري")
    assert "تَغْرِيدَة" in offered and offered.index("تَغْرِيدَة") > offered.index("تَغْرِيد")
    assert "تَغْرِيدَة" not in real.suggest("تغ")  # the dictionary's fill the list


def test_a_verbs_participles_and_verbal_nouns_are_not_its_spellings(real):
    # كَتَبَ's conjugation lists كَاتِب and مَكْتُوب, and its headword line كِتَابَة: each is a word of its own.
    assert not {e for w in ("كاتب", "مكتوب", "كتابة") for e in real.wiktionary_only(w) if e.word == "كَتَبَ"}


def test_a_word_found_whole_is_not_also_looked_for_without_its_attached_words(real):
    # ولد is وَلَد "boy" and وَلَدَ "give birth to"; و + لد would add the entries spelled لد.
    assert all(wiktionary.key(e.word) != "لد" for e in real.wiktionary_only("ولد"))
    # وبعد is و + بعد, with an entry of its own; و + ب + عد would add عَادَ "return" and وَعَدَ "promise".
    assert {"عَادَ", "وَعَدَ"}.isdisjoint(words(real, "وبعد"))


# --- English lookup of Wiktionary's senses (#25) ----------------------------------------------------

def english(real, query: str) -> list[str]:
    """The headwords of the entries only Wiktionary has that an English lookup finds."""
    return [e.word for e in real.lookup(query, english=True).wiktionary]


def lemmas(real, query: str) -> list[str]:
    """The lemmas an English lookup finds, in order, their marks in one order (NFC) as the literals here are compared."""
    return list(dict.fromkeys(unicodedata.normalize("NFC", r.lemma) for r in real.lookup_en(query)))


def test_english_finds_a_word_only_wiktionary_has(real):
    # تَغْرِيدَة "chirp, tweet; a tweet", which the dictionary doesn't have.
    assert "تَغْرِيدَة" in english(real, "tweet")


def test_english_finds_a_lemma_by_a_sense_only_its_wiktionary_entry_has(real):
    # The dictionary glosses كِتاب "book"; Wiktionary's كِتَاب, which it joins, also says "a marriage contract.".
    assert "كِتاب" in lemmas(real, "marriage contract") and "كِتاب" in lemmas(real, "a marriage contract")
    assert "كِتَاب" not in english(real, "marriage contract")  # the lemma's entry, not one of Wiktionary's own
    assert "كِتاب" not in lemmas(real, "marriage")  # a phrase is matched whole


def test_english_shows_each_lemma_once_the_dictionarys_matches_first(real):
    # Both sources say كِتاب is "book". The dictionary's matches keep their order; then the lemmas only their
    # Wiktionary entries call a book (سِجِلّ "scroll, book", حَجَزَ "to book", مُصْحَف "volume, tome, book");
    # then the words only Wiktionary has (نَمْق).
    found = real.lookup("book", english=True)
    assert lemmas(real, "book") == ["كِتاب", "سِفْر", "سِجِلّ", "حَجَز", "مُصْحَف"]
    assert len(set(found.readings)) == len(found.readings)
    assert [e.word for e in found.wiktionary] == ["نَمْق"] and not any(real.joined(e) for e in found.wiktionary)


def test_english_shows_a_lemma_with_no_citation_form_by_its_forms(real):
    # The dictionary has the noun ساكِن only as its plural سُكّان "residents"; Wiktionary's ساكِن says "inhabitant".
    assert [r.form for r in real.lookup_en("inhabitant") if (r.lemma, r.pos) == ("ساكِن", "noun")] == ["سُكّان"]


def test_english_finds_wiktionarys_senses_by_the_rules_of_the_dictionarys_glosses(real):
    assert english(real, "Tweet ") == english(real, "tweet")  # case and surrounding whitespace don't matter
    assert "تَغْرِيدَة" in english(real, "tweets")  # an inflected form finds its base form
    assert unicodedata.normalize("NFC", "غَرَّد") in lemmas(real, "tweeted")  # Wiktionary's غَرَّدَ "to tweet", which the dictionary's غَرَّد joins
    # سِجِلّ "register (unit of computer memory)": the bracketed note is not what it is found by.
    assert "سِجِلّ" in lemmas(real, "register") and "سِجِلّ" not in lemmas(real, "unit of computer memory")


def test_english_does_not_search_wiktionarys_labels_or_relations(real):
    # كَتَّبَ is "(transitive, causative) to cause to write"; جِدَّة "newness" is labelled obsolete.
    assert "كَتَّب" not in lemmas(real, "causative") and "كَتَّبَ" not in english(real, "causative")
    assert "جِدَّة" not in lemmas(real, "obsolete") and "جِدَّة" not in english(real, "obsolete")
    # كُتُب is only "plural of كِتَاب", which relates it to another word rather than saying what it means.
    assert real.lookup("plural of", english=True).wiktionary == ()


def test_english_lists_the_words_only_wiktionary_has_by_how_early_their_entry_says_it(real):
    # قَالَ "To nap." and طِنْفَسَة "carpet of fine piles, pile rug, nap" say it in their first sense, سِنَة in its second
    # ("drowsiness"; "slumber; nap"); Wiktionary lists سِنَة first.
    assert english(real, "nap") == ["قَالَ", "طِنْفَسَة", "سِنَة"]


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
