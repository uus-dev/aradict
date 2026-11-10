"""Turn one CAMeL analysis into what a learner reads: a whole-word English gloss, grammar
labels, and the word split into its prefix, stem and suffix parts.

The parts come from the analysis's Buckwalter segmentation (`bw`), for example
وَ/CONJ+بِ/PREP+كِتاب/NOUN+هُم/POSS_PRON_3MP. Wording is built from those parts and the
stem's own senses rather than from CAMeL's composite gloss (`and_+_by;with+book+their`),
so attached words land in English word order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Harakat, tanween, sukun, hamza marks and the dagger alif. Shadda is not among them: it
# doubles a letter, so it counts as one.
MARKS = "\u064b-\u0650\u0652-\u0655\u0670"
SHADDA = "\u0651"
_MARK = re.compile(f"[{MARKS}]")
_LETTER_VARIANTS = str.maketrans("ٱأإآىة", "اااايت")  # one letter, however CAMeL's parts and spelling write it

# Words for attached particles, keyed by tag and bare letters (a tag alone where it is unambiguous).
# The last row is for function words a few stored stems carry at their end (مِمّا, بَعْدَما).
PARTICLES = {
    "CONJ و": "and", "PART و": "and", "SUB_CONJ و": "while", "CONJ ف": "so",
    "PREP ب": "by/with", "PREP ل": "for/to", "PREP ك": "like",
    "EMPHATIC_PART": "indeed", "RC_PART": "surely", "FUT_PART": "will", "DET": "the",
    "NEG_PART": "not", "INTERROG_PART": "question",
    "SUB_CONJ ما": "that", "REL_PRON ما": "what", "INTERROG_PRON م": "what", "REL_PRON من": "whom", "INTERROG_PRON من": "whom",
}

PERSONS = ("1s", "1p", "2ms", "2fs", "2d", "2mp", "2fp", "3ms", "3fs", "3d", "3mp", "3fp")
SUBJECT = dict(zip(PERSONS, (
    "I", "we", "you (m.)", "you (f.)", "you both", "you (m. pl.)", "you (f. pl.)",
    "he/it", "she/it", "they both", "they", "they (f.)",
)))
OBJECT = dict(zip(PERSONS, (
    "me", "us", "you (m.)", "you (f.)", "you both", "you (m. pl.)", "you (f. pl.)",
    "him/it", "her/it", "them both", "them", "them (f.)",
)))
POSSESSIVE = dict(zip(PERSONS, (
    "my", "our", "your (m.)", "your (f.)", "your (both)", "your (m. pl.)", "your (f. pl.)",
    "his/its", "her/its", "their (both)", "their", "their (f.)",
)))
ADDRESSEE = {"2ms": "to one man", "2fs": "to one woman", "2d": "to two people", "2mp": "to a group", "2fp": "to a group of women"}

POS = {
    "noun": "noun", "noun_prop": "proper noun", "noun_num": "number", "noun_quant": "quantifier",
    "adj": "adjective", "adj_comp": "comparative adjective", "adj_num": "ordinal number",
    "adv": "adverb", "adv_interrog": "interrogative adverb", "adv_rel": "relative adverb",
    "pron": "pronoun", "pron_dem": "demonstrative pronoun", "pron_exclam": "exclamatory pronoun",
    "pron_interrog": "interrogative pronoun", "pron_rel": "relative pronoun",
    "verb": "verb", "verb_pseudo": "pseudo-verb", "prep": "preposition",
    "conj": "conjunction", "conj_sub": "subordinating conjunction", "interj": "interjection",
    "part": "particle", "part_det": "determiner", "part_focus": "focus particle", "part_fut": "future particle",
    "part_interrog": "interrogative particle", "part_neg": "negative particle", "part_restrict": "restrictive particle",
    "part_verb": "verbal particle", "part_voc": "vocative particle",
    "abbrev": "abbreviation", "digit": "digit", "latin": "Latin script", "punc": "punctuation",
}
VOICE = {"a": "active", "p": "passive"}
PERSON = {"1": "1st person", "2": "2nd person", "3": "3rd person"}
GENDER = {"m": "masculine", "f": "feminine"}
NUMBER = {"s": "singular", "d": "dual", "p": "plural"}
ASPECT = {"p": "perfect (past)", "i": "imperfect (present/future)", "c": "imperative"}
MOOD = {"i": "indicative", "s": "subjunctive", "j": "jussive"}
STATE = {"i": "indefinite", "d": "definite", "c": "construct state"}
CASE = {"n": "nominative", "a": "accusative", "g": "genitive"}


# --- Grammar -------------------------------------------------------------------------------

def tags(a: dict) -> tuple[str, ...]:
    """Short labels: part of speech, then voice and agreement where the word has them."""
    agreement = " ".join(filter(None, (
        PERSON.get(a["per"]), None if a["per"] == "1" else GENDER.get(a["gen"]), NUMBER.get(a["num"]),
    )))
    return tuple(filter(None, (POS.get(a["pos"], a["pos"]), VOICE.get(a["vox"]), agreement)))


def _fixed(analyses: list[dict], feature: str, names: dict[str, str]) -> str | None:
    """A feature the spelling fixes: every analysis folded into the reading has a known value.
    A caseless or moodless analysis ("u") means the spelling leaves it open."""
    values = {a[feature] for a in analyses}
    return " or ".join(name for code, name in names.items() if code in values) if values <= names.keys() else None


def grammar(analyses: list[dict]) -> str:
    """The rest of the grammar in plain English: aspect, mood, state, case, broken plural."""
    a = analyses[0]
    states = {x["stt"] for x in analyses}
    details = [
        ASPECT.get(a["asp"]),
        a["asp"] == "i" and (mood := _fixed(analyses, "mod", MOOD)) and f"{mood} mood",
        # A bare noun is indefinite or construct alike; only a single state says something.
        len(states) == 1 and STATE.get(states.pop()),
        (case := _fixed(analyses, "cas", CASE)) and f"{case} case",
        a["num"] == "p" and a["form_num"] == "s" and "broken plural",
    ]
    return ", ".join(d for d in details if d)


# --- Parts ---------------------------------------------------------------------------------

def parts(a: dict) -> list[tuple[str, str]]:
    """CAMeL's segmentation as (text, tag) pairs. Case endings are left out: they belong to the
    part before them. Parts with no written form, such as a silent subject marker, are left out."""
    pieces = (piece.rsplit("/", 1) for piece in a["bw"].split("+"))
    return [(text, tag) for text, tag in pieces if text != "(null)" and not tag.startswith("CASE_")]


def _letters(text: str) -> str:
    return _MARK.sub("", text).translate(_LETTER_VARIANTS)


def _particle(text: str, tag: str) -> str | None:
    return PARTICLES.get(f"{tag} {_letters(text)}") or PARTICLES.get(tag)


def _affix(text: str, tag: str) -> bool:
    return bool(_particle(text, tag) or re.match(r"IV\d|(POSS_)*PRON_\d", tag) or "SUFF" in tag)


def _stem(pcs: list[tuple[str, str]], a: dict) -> tuple[int, range]:
    """The stem part, and the parts that spell the database's stem entry. That is usually the
    stem alone, but a few entries are stored with their clitics (ما زِلْتُ, بِكِ, بِاللّٰهِ)."""
    stored = _letters(a["stem"])
    span = next(
        (range(i, i + 1) for i, (text, _) in enumerate(pcs) if text == a["stem"]),
        next((range(j, m) for j in range(len(pcs)) for m in range(j + 1, len(pcs) + 1)
              if _letters("".join(text for text, _ in pcs[j:m])) == stored), range(len(pcs))),
    )
    return next((i for i in span if not _affix(*pcs[i])), span.start), span


def _person(tag: str) -> str | None:
    """The person code in a pronoun or subject tag: POSS_PRON_3MP gives "3mp"."""
    found = re.search(r"[123][MF]?[SDP]", tag)
    return found.group().lower() if found else None


def _agreement(a: dict) -> str:
    """Person, gender and number as a code like "3mp"; first person and duals have no gender."""
    per, gen, num = a["per"], a["gen"], a["num"]
    return per + num if per == "1" or num == "d" else per + gen + num


def _label(i: int, k: int, text: str, tag: str, a: dict) -> str:
    """What one part means, for the Word parts chips."""
    if word := _particle(text, tag):
        return word
    if i == k:
        return senses(a["stemgloss"])[0]
    # Some stems stored with their clitics have no agreement features; their tags still have it.
    subject = SUBJECT.get(_person(tag) or _agreement(a))
    if "SUFF_SUBJ" in tag:
        return ", ".join(filter(None, (subject, "command ending" if a["asp"] == "c" else "subject ending")))
    if tag.startswith("IV"):
        return ", ".join(filter(None, (subject, "subject prefix")))
    if "POSS_PRON" in tag:
        return POSSESSIVE[_person(tag)]
    if "SUFF_DO" in tag or tag.startswith("PRON_"):
        return OBJECT[_person(tag)]
    if tag.startswith("NSUFF"):
        if "_DU" in tag:
            return "dual ending"
        if "_PL" in tag:
            return "feminine plural ending" if "FEM" in tag else "plural ending"
        return "feminine ending"
    return "prefix" if i < k else "suffix"


@dataclass(frozen=True)
class Segment:
    text: str  # this part's slice of the vocalized form; the slices join up to the form
    role: str  # "prefix", "stem" or "suffix"
    label: str  # what the part means: "and", "their", "dual ending"
    spelling: str  # the part written on its own; differs from text only where two parts share a letter


def segments(a: dict) -> tuple[Segment, ...]:
    """The vocalized form cut into its parts, each labelled with its meaning.

    Each part's letters are matched against the spelling in turn. A letter the spelling leaves
    out (the alif of ال after لِ) is skipped. Where one written letter stands for the last letter
    of one part and the first of the next (تَيْ + يَ written تَيَّ with a shadda, أ + ا written آ),
    the word shows that letter in the later part, and each part's `spelling` keeps its own copy.
    """
    pcs = parts(a)
    k, _ = _stem(pcs, a)
    # Put each shadda straight after its letter (letter, shadda, vowel), so a doubled letter is one unit.
    form = re.sub(f"([{MARKS}]+){SHADDA}", lambda m: SHADDA + m.group(1), a["diac"])
    starts, merged, pos, last, used = [], [], 0, -1, -1
    for i, (text, _) in enumerate(pcs):
        starts.append(pos)
        merged.append(False)
        for letter in _MARK.sub("", text):
            while pos < len(form) and _MARK.match(form[pos]):
                pos += 1
            if pos < len(form) and _letters(letter) == _letters(form[pos]):
                last, pos = pos, pos + 1
            elif last != used and (form[pos:pos + 1] == SHADDA and _letters(letter) == _letters(form[last])
                                   or form[last] == "آ" and _letters(letter) == "ا"):
                # One written letter stands for two: a doubled letter, or hamza and alif as madda.
                if last < starts[i]:
                    starts[i], merged[i] = last, True
                used, pos = last, pos + (form[pos:pos + 1] == SHADDA)
            # Otherwise the spelling leaves this letter out.
        next_starts_with_mark = i + 1 < len(pcs) and _MARK.match(pcs[i + 1][0])
        while pos < len(form) and _MARK.match(form[pos]) and not next_starts_with_mark:
            pos += 1  # vowels after this part's last letter, such as a case ending, belong to it
    cuts = [form[start:end] for start, end in zip(starts, starts[1:] + [len(form)])]
    shares = [merged[i] or merged[i + 1:i + 2] == [True] for i in range(len(pcs))]
    return tuple(
        Segment(
            cut, "prefix" if i < k else "stem" if i == k else "suffix", _label(i, k, text, tag, a),
            text.replace("ٱ", "ا") if shares[i] else cut,
        )
        for i, ((text, tag), cut) in enumerate(zip(pcs, cuts))
    )


# --- Gloss ---------------------------------------------------------------------------------

TAG_WORDS = {"masc": "m.", "fem": "f.", "pl": "pl.", "du": "dual", "Egy": "Egyptian"}
IRREGULAR_PLURALS = {"man": "men", "woman": "women", "child": "children", "person": "people", "foot": "feet", "tooth": "teeth"}


def _tag_note(match: re.Match) -> str:
    """CAMeL's bracketed agreement tags as a readable note: [fem.pl.] gives " (f. pl.)"."""
    words = [TAG_WORDS[t] for t in match.group(1).split(".") if t in TAG_WORDS]
    return f" ({' '.join(words)})" if words else ""


def senses(stemgloss: str) -> list[str]:
    """The stem's senses, with CAMeL's bracketed tags ([fem.pl.], <verb>) made readable or dropped."""
    text = re.sub(r"_?\[([^\]]*)\]", _tag_note, re.sub(r"_?<[^>]*>", "", stemgloss))
    # "more;most_tractable" and "of;from_Irbid" pair two words inside one sense.
    text = re.sub(r"\b(more|most|of|from|to|for|with|by);(?=(more|most|of|from|to|for|with|by)_)", r"\1/", text)
    if "_+_" in text:  # one phrase whose parts list alternatives: with;by_+_you
        return [text.replace(";", "/").replace("_+_", " ").replace("_", " ")]
    return [s.strip() for s in text.replace("_", " ").split(";") if s.strip()]


def _composite(stemgloss: str) -> bool:
    """A few stems (بِكِ, لا يَزال, اللَّتَيْنِ) carry attached words or agreement in their own gloss:
    with;by_+_you_[fem.sg.]. Their gloss already reads as the whole stored stem."""
    return "_+_" in stemgloss or "[" in stemgloss


# Common irregular English verbs. "lie" is left out: "lay" and "lied" are both right, by sense.
IRREGULAR_PAST = dict(pair.split(":") for pair in """
    abide:abode arise:arose awake:awoke bear:bore beat:beat become:became befall:befell beget:begot
    begin:began behold:beheld bend:bent bet:bet bid:bid bind:bound bite:bit bleed:bled blow:blew
    break:broke breed:bred bring:brought broadcast:broadcast build:built burst:burst buy:bought
    cast:cast catch:caught choose:chose cling:clung come:came cost:cost creep:crept cut:cut
    deal:dealt dig:dug do:did draw:drew drink:drank drive:drove dwell:dwelt eat:ate fall:fell
    feed:fed feel:felt fight:fought find:found flee:fled fling:flung fly:flew forbid:forbade
    forecast:forecast foresee:foresaw foretell:foretold forget:forgot forgive:forgave forsake:forsook
    freeze:froze get:got give:gave go:went grind:ground grow:grew hang:hung have:had hear:heard
    hide:hid hit:hit hold:held hurt:hurt keep:kept kneel:knelt know:knew lay:laid lead:led
    leap:leapt leave:left lend:lent let:let light:lit lose:lost make:made mean:meant meet:met
    mislead:misled mistake:mistook misunderstand:misunderstood outdo:outdid overcome:overcame
    overhear:overheard override:overrode overrun:overran oversee:oversaw overtake:overtook
    overthrow:overthrew partake:partook pay:paid put:put quit:quit read:read rebuild:rebuilt
    redo:redid repay:repaid retell:retold rewrite:rewrote rid:rid ride:rode ring:rang rise:rose
    run:ran say:said see:saw seek:sought sell:sold send:sent set:set shake:shook shed:shed
    shine:shone shoot:shot shrink:shrank shut:shut sing:sang sink:sank sit:sat slay:slew sleep:slept
    slide:slid sling:slung slit:slit smite:smote speak:spoke speed:sped spend:spent spin:spun
    spit:spat split:split spread:spread spring:sprang stand:stood steal:stole stick:stuck sting:stung
    stink:stank stride:strode strike:struck string:strung strive:strove swear:swore sweep:swept
    swim:swam swing:swung take:took teach:taught tear:tore tell:told think:thought throw:threw
    thrust:thrust tread:trod undergo:underwent understand:understood undertake:undertook undo:undid
    uphold:upheld upset:upset wake:woke wear:wore weave:wove weep:wept win:won wind:wound
    withdraw:withdrew withhold:withheld withstand:withstood wring:wrung write:wrote
""".split())
# Verbs of more than one syllable that double their last consonant (stress on the last syllable).
DOUBLE_FINAL = set("""
    abhor acquit admit allot annul commit compel confer control defer deter dispel emit equip excel
    expel extol impel incur infer occur omit outwit patrol permit prefer propel rebel recur refer
    regret remit repel submit transfer transmit
""".split())


def _past(verb: str) -> str:
    """The English simple past: write → wrote, use → used, try → tried, stop → stopped, add → added."""
    if verb in IRREGULAR_PAST:
        return IRREGULAR_PAST[verb]
    if verb.endswith("e"):
        return verb + "d"
    if verb.endswith("y") and verb[-2:-1] not in ("a", "e", "i", "o", "u"):
        return verb[:-1] + "ied"
    if verb.endswith("c"):
        return verb + "ked"  # panic → panicked
    if verb in DOUBLE_FINAL or re.fullmatch(r"[^aeiou]*[aeiou][^aeiouwxy]", verb):
        return verb + verb[-1] + "ed"  # one syllable ending in one vowel and one consonant
    return verb + "ed"


def _verb(sense: str, a: dict, future: bool) -> str:
    """Put the verb in its tense: "will" for the future, the English past for the perfect, and
    "be" (the passive) by person. The imperfect keeps the base form ("they write")."""
    first, _, rest = sense.partition(" ")
    if first != "be":
        if future:
            return f"will {sense}"
        return " ".join(filter(None, (_past(first), rest))) if a["asp"] == "p" else sense
    singular = a["per"] + a["num"] in ("1s", "3s")
    if a["asp"] == "p":
        be = "was" if singular else "were"
    elif future:
        be = "will be"
    else:
        be = "am" if a["per"] + a["num"] == "1s" else "is" if singular else "are"
    return be + sense[2:]


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
    if feminine_ending and not _letters(a["lex"]).endswith("ت"):
        sense += " (f.)"  # a woman, from a masculine headword: مُدَرِّسَة from مُدَرِّس
    return sense


def gloss(a: dict) -> str:
    """The whole word in English, for example "and by/with their book"."""
    pcs = parts(a)
    _, stored = _stem(pcs, a)
    # Parts stored with the stem are already in its gloss; only the parts around it add words.
    if _composite(a["stemgloss"]):
        before = [w for text, tag in pcs[:stored.start] if (w := _particle(text, tag))]
        return " ".join(before + ["; ".join(senses(a["stemgloss"]))])
    prefixes = [tag for _, tag in pcs[:stored.start]]
    suffixes = [tag for _, tag in pcs[stored.stop:]]
    # Conjunctions and prepositions lead the whole sense list; the article, the future and
    # pronouns belong to each sense.
    before = [w for text, tag in pcs[:stored.start] if tag not in ("DET", "FUT_PART") and (w := _particle(text, tag))]
    possessive = next((POSSESSIVE[_person(tag)] for tag in suffixes if "POSS_PRON" in tag), None)
    obj = next((OBJECT[_person(tag)] for tag in suffixes if "SUFF_DO" in tag or tag.startswith("PRON_")), None)
    # A dual or sound plural written without its ن is the first word of a construct: "the two schools of".
    construct = not possessive and any(tag.startswith("NSUFF") and tag.endswith("_POSS") for tag in suffixes)
    command = a["pos"] == "verb" and a["asp"] == "c"
    phrases = []
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
