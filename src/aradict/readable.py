"""Turn one CAMeL analysis into what a learner reads: a whole-word English gloss, grammar
labels, and the word split into its prefix, stem and suffix parts.

The parts come from the analysis's Buckwalter segmentation (`bw`), for example
وَ/CONJ+بِ/PREP+كِتاب/NOUN+هُم/POSS_PRON_3MP. Wording is built from those parts and the
stem's own senses rather than from CAMeL's composite gloss (`and_+_by;with+book+their`),
so attached words land in English word order.
"""

from __future__ import annotations

import re

# Harakat, tanween, sukun, hamza marks and the dagger alif. Shadda is not among them: it
# doubles a letter, so it counts as one.
MARKS = "ً-ِْ-ٰٕ"
# Words for the proclitics, keyed by the analysis feature that names them.
PROCLITICS = {
    "wa_conj": "and", "wa_part": "and", "wa_sub": "while", "fa_conj": "so",
    "bi_prep": "by/with", "li_prep": "for/to", "ka_prep": "like",
    "la_emph": "indeed", "la_rc": "surely", "sa_fut": "will", "Al_det": "the",
}
# Which feature a prefix part's tag stands for.
PREFIX_FEATURE = {
    "CONJ": "prc2", "SUB_CONJ": "prc2", "PART": "prc2",
    "PREP": "prc1", "FUT_PART": "prc1", "EMPHATIC_PART": "prc1", "RC_PART": "prc1",
    "DET": "prc0",
}

PERSONS = ("1s", "1p", "2ms", "2fs", "2d", "2mp", "2fp", "3ms", "3fs", "3d", "3mp", "3fp")
POSSESSIVE = dict(zip(PERSONS, (
    "my", "our", "your (m.)", "your (f.)", "your (both)", "your (m. pl.)", "your (f. pl.)",
    "his/its", "her/its", "their (both)", "their", "their (f.)",
)))


def parts(a: dict) -> list[tuple[str, str]]:
    """CAMeL's segmentation as (text, tag) pairs. Case endings are left out: they belong to the
    part before them. Parts with no written form, such as a silent subject marker, are left out."""
    pieces = (piece.rsplit("/", 1) for piece in a["bw"].split("+"))
    return [(text, tag) for text, tag in pieces if text != "(null)" and not tag.startswith("CASE_")]


def _stem_index(pcs: list[tuple[str, str]], a: dict) -> int:
    return next((k for k, (text, _) in enumerate(pcs) if text == a["stem"]), 0)


def _person(tag: str) -> str | None:
    """The person code in a pronoun tag: POSS_PRON_3MP gives "3mp"."""
    found = re.search(r"[123][MF]?[SDP]$", tag)
    return found.group().lower() if found else None


OBJECT = dict(zip(PERSONS, (
    "me", "us", "you (m.)", "you (f.)", "you both", "you (m. pl.)", "you (f. pl.)",
    "him/it", "her/it", "them both", "them", "them (f.)",
)))
ADDRESSEE = {"2ms": "to one man", "2fs": "to one woman", "2d": "to two people", "2mp": "to a group", "2fp": "to a group of women"}
SUBJECT = dict(zip(PERSONS, (
    "I", "we", "you (m.)", "you (f.)", "you both", "you (m. pl.)", "you (f. pl.)",
    "he/it", "she/it", "they both", "they", "they (f.)",
)))


def _agreement(a: dict) -> str:
    """Person, gender and number as a code like "3mp"; first person and duals have no gender."""
    per, gen, num = a["per"], a["gen"], a["num"]
    return per + num if per == "1" or num == "d" else per + gen + num


def _verb(sense: str, a: dict, future: bool) -> str:
    """Put the verb in its tense where English needs no lexicon: only "be" (the passive) is
    conjugated, other verbs keep their base form ("he/it write")."""
    if sense != "be" and not sense.startswith("be "):
        return f"will {sense}" if future else sense
    singular = a["per"] + a["num"] in ("1s", "3s")
    if a["asp"] == "p":
        be = "was" if singular else "were"
    elif future:
        be = "will be"
    else:
        be = "am" if a["per"] + a["num"] == "1s" else "is" if singular else "are"
    return be + sense[2:]


IRREGULAR_PLURALS = {"man": "men", "woman": "women", "child": "children", "person": "people", "foot": "feet", "tooth": "teeth"}


def _plural(sense: str) -> str:
    """English plural of a noun sense, inflecting the word before any bracketed note."""
    head, paren, note = sense.partition(" (")
    *rest, word = head.split(" ")
    if word in IRREGULAR_PLURALS:
        word = IRREGULAR_PLURALS[word]
    elif word.endswith("y") and word[-2:-1] not in ("a", "e", "i", "o", "u"):
        word = word[:-1] + "ies"
    elif word.endswith(("ss", "x", "z", "ch", "sh")):
        word += "es"
    elif word.endswith("s"):
        pass  # CAMeL often glosses a singular stem with a plural sense ("law;statutes")
    else:
        word += "s"  # ponytail: regular rules plus a few irregulars; extend IRREGULAR_PLURALS as glosses need
    return " ".join(rest + [word]) + paren + note


def _noun(sense: str, a: dict, suffixes: list[str]) -> str:
    """Number and gender that English shows on the noun itself: "two schools", "teacher (f.)"."""
    if a["num"] == "d":
        sense = "two " + _plural(sense)
    elif a["num"] == "p" and a["form_num"] == "p":  # sound plural; a broken plural's stem gloss is already plural
        sense = _plural(sense)
    feminine_ending = any(tag.startswith("NSUFF_FEM") for tag in suffixes)
    if feminine_ending and not re.sub(f"[{MARKS}]", "", a["lex"]).endswith("ة"):
        sense += " (f.)"  # a woman, from a masculine headword: مُدَرِّسَة from مُدَرِّس
    return sense


def _composite(stemgloss: str) -> bool:
    """A few stems (بِكِ, لا يَزال, اللَّتَيْنِ) carry attached words or agreement in their own gloss:
    with;by_+_you_[fem.sg.]. Their gloss already reads as the whole word."""
    return "_+_" in stemgloss or "[" in stemgloss


TAG_WORDS = {"masc": "m.", "fem": "f.", "pl": "pl.", "du": "dual", "Egy": "Egyptian"}


def _tag_note(match: re.Match) -> str:
    """CAMeL's bracketed agreement tags as a readable note: [fem.pl.] gives " (f. pl.)"."""
    words = [TAG_WORDS[t] for t in match.group(1).split(".") if t in TAG_WORDS]
    return f" ({' '.join(words)})" if words else ""


def senses(stemgloss: str) -> list[str]:
    """The stem's senses, with CAMeL's bracketed tags ([fem.pl.], <verb>) made readable or dropped."""
    text = re.sub(r"_?\[([^\]]*)\]", _tag_note, re.sub(r"_?<[^>]*>", "", stemgloss))
    if "_+_" in text:  # one phrase whose parts list alternatives: with;by_+_you
        return [text.replace(";", "/").replace("_+_", " ").replace("_", " ")]
    return [s.strip() for s in text.replace("_", " ").split(";") if s.strip()]


def gloss(a: dict) -> str:
    """The whole word in English, for example "and by/with their book"."""
    pcs = parts(a)
    k = _stem_index(pcs, a)
    prefixes = [tag for _, tag in pcs[:k] if tag in PREFIX_FEATURE]
    # Conjunctions and prepositions lead the whole sense list; the article, the future and
    # pronouns belong to each sense.
    before = [PROCLITICS[a[PREFIX_FEATURE[tag]]] for tag in prefixes if tag not in ("DET", "FUT_PART")]
    suffixes = [tag for _, tag in pcs[k + 1:]]
    possessive = next((POSSESSIVE[_person(tag)] for tag in suffixes if tag.startswith("POSS_PRON")), None)
    obj = next((OBJECT[_person(tag)] for tag in suffixes if "SUFF_DO" in tag or tag.startswith("PRON_")), None)
    command = a["pos"] == "verb" and a["asp"] == "c"
    phrases = []
    # A dual or sound plural written without its ن is the first word of a construct: "the two schools of".
    construct = not possessive and any(tag.startswith("NSUFF") and tag.endswith("_POSS") for tag in suffixes)
    if _composite(a["stemgloss"]):
        return " ".join(before + ["; ".join(senses(a["stemgloss"]))])
    for sense in senses(a["stemgloss"]):
        if command:
            sense = f"{sense}!"
        elif a["pos"] == "verb":
            sense = " ".join(filter(None, (SUBJECT.get(_agreement(a)), _verb(sense, a, "FUT_PART" in prefixes))))
        else:
            if a["pos"] == "noun":
                sense = _noun(sense, a, suffixes)
            if possessive:
                sense = f"{possessive} {sense}"
            elif "DET" in prefixes:
                sense = f"the {sense}"
            elif construct:
                sense = f"the {sense} of"
        phrases.append(f"{sense} {obj}" if obj else sense)
    after = [f"({ADDRESSEE[_agreement(a)]})"] if command and _agreement(a) in ADDRESSEE else []
    return " ".join(before + ["; ".join(phrases)] + after)
