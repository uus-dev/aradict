"""PROTOTYPE, throwaway. Dumps real CAMeL calima-msa-r13 analyses, roughly collapsed into readings, into index.html.

Usage: python dump.py path/to/calima-msa-r13/morphology.db WORD [WORD ...]
Needs camel-tools 1.6 (no torch). Glosses are hand-cleaned in HAND below; everything else is the database's own output.
"""
import sys, json, re
from collections import defaultdict
from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer

db = MorphologyDB(sys.argv[1], flags='a'); ana = Analyzer(db, backoff='NONE')
WORDS = sys.argv[2:]

# lemma frequency percentile, related-form counts, root family sizes (from the stem table)
lex_lp, forms, fam = {}, defaultdict(set), defaultdict(set)
for stem, entries in db.stem_hash.items():
    for cat, f in entries:
        lex_lp[(f['lex'], f['pos'])] = float(f.get('lex_logprob', -99))
        forms[(f['lex'], f['pos'])].add(f.get('diac', stem))
        if f.get('root'):
            fam[f['root']].add((f['lex'], f['pos']))
known = sorted(v for v in lex_lp.values() if v > -99)

def pct(lp):  # share of lemmas at least this frequent
    if lp <= -99: return None
    import bisect
    return round(100 * (1 - bisect.bisect_left(known, lp) / len(known)), 1)

DIAC = re.compile('[ً-ِْٰ]')  # keep shadda
def measure(lex, root, pos):
    if pos != 'verb' or not root: return None
    r = root.split('.')
    if len(r) != 3 or '#' in r: return None  # ponytail: weak/hamza roots need the full pattern table (#5); unavailable beats wrong
    a, b, c = [x if x != '#' else '.' for x in r]
    s = DIAC.sub('', lex.replace('ٱ', 'ا'))
    for name, t in [('I', f'{a}{b}{c}'), ('II', f'{a}{b}ّ{c}'), ('III', f'{a}ا{b}{c}'), ('IV', f'أ{a}{b}{c}'),
                    ('V', f'ت{a}{b}ّ{c}'), ('VI', f'ت{a}ا{b}{c}'), ('VII', f'ان{a}{b}{c}'), ('VIII', f'ا{a}ت{b}{c}'),
                    ('IX', f'ا{a}{b}{c}ّ'), ('X', f'است{a}{b}{c}')]:
        if re.fullmatch(t, s): return name
    return None

MARK = re.compile('[\u064b-\u0650\u0652-\u0655\u0670]')  # harakat; shadda counts as a unit (it doubles a letter)
units = lambda t: len(MARK.sub('', t))
trailing = lambda t: len(t) - len(t.rstrip(''.join(chr(c) for c in list(range(0x64b, 0x651)) + list(range(0x652, 0x656)) + [0x670])))

TAGS = {'CONJ': 'and', 'SUB_CONJ': 'while', 'PART': 'particle', 'FUT_PART': 'will (future)', 'DET': 'the',
        'IV3MP': 'they (m.), subject prefix', 'IV1S': 'I, subject prefix', 'IV3MS': 'he, subject prefix',
        'IVSUFF_SUBJ:MP_MOOD:I': 'plural subject, indicative', 'PVSUFF_SUBJ:3MS': 'he/it, subject ending',
        'CVSUFF_SUBJ:2MS': 'you (m.), command ending', 'NSUFF_FEM_SG': 'feminine ending',
        'POSS_PRON_1S': 'my', 'POSS_PRON_3MP': 'their', 'PRON_1S': 'me'}
PREP = {'bi_prep': 'by/with', 'li_prep': 'for/to', 'ka_prep': 'like'}

def tag_label(tag, a):
    if tag == 'PREP' and a['prc1'] in PREP: return PREP[a['prc1']]
    if tag.startswith('NSUFF_FEM_DU'): return 'dual ending'
    return TAGS.get(tag, tag)

def segments(a):
    parts = [p.rsplit('/', 1) for p in a['bw'].split('+')]
    parts = [(t, tag) for t, tag in parts if not tag.startswith('CASE_') and t != '(null)']
    si = next((k for k, (t, tag) in enumerate(parts) if t == a['stem']), 0)
    diac, pos, cuts = a['diac'], 0, []
    for k, (t, tag) in enumerate(parts):  # align each bw piece onto the real spelling by letter count
        start, need = pos, units(t)
        while need and pos < len(diac):
            if not MARK.match(diac[pos]): need -= 1
            pos += 1
        n = trailing(t)
        while n and pos < len(diac) and MARK.match(diac[pos]): pos += 1; n -= 1
        if k == len(parts) - 1: pos = len(diac)
        cuts.append({'text': diac[start:pos], 'tag': tag, 'label': None if k == si else tag_label(tag, a)})
    return {'prefix': cuts[:si], 'stem': cuts[si:si + 1], 'suffix': cuts[si + 1:]}

PER = {('1', 's'): 'I', ('1', 'p'): 'we', ('2', 's'): 'you', ('2', 'd'): 'you two', ('2', 'p'): 'you all',
       ('3', 's'): 'he/it', ('3', 'd'): 'they two', ('3', 'p'): 'they'}
def grammar(a):
    g = {'noun': ['noun'], 'verb': ['verb'], 'adj': ['adjective'], 'prep': ['preposition']}.get(a['pos'], [a['pos']])
    if a['pos'] == 'verb':
        g += [{'p': 'perfect (past)', 'i': 'imperfect (present/future)', 'c': 'imperative'}[a['asp']],
              {'a': 'active', 'p': 'passive'}[a['vox']]]
        subj = PER.get((a['per'], a['num']), '')
        if a['per'] == '3' and a['num'] == 's': subj = 'he/it' if a['gen'] == 'm' else 'she'
        g.append(f"subject: {subj}" + (' (m.)' if a['gen'] == 'm' and a['per'] == '2' else ''))
    elif a['pos'] in ('noun', 'adj'):
        g += [{'m': 'masculine', 'f': 'feminine'}.get(a['gen'], ''),
              {'s': 'singular', 'd': 'dual', 'p': 'plural'}.get(a['num'], '')]
        if a['num'] == 'p' and a['form_num'] == 's': g[-1] = 'broken plural'
    return [x for x in g if x]

# Hand-cleaned whole-word glosses. Issue #4 must produce wording like this automatically; until then the
# prototype marks every one of these as hand-cleaned so it can't oversell what the formatter will deliver.
HAND = {
    'كِتاب|كُتُب': 'books', 'كَتَب|كَتَبَ|a': 'he wrote', 'كَتَب|كُتِبَ|p': 'it was written; it was destined',
    'كِتاب|وَبِكِتابهم': 'and by/with their book', 'كاتِب|وَبِكُتّابهم': 'and by/with their writers; their authors',
    'كُتّاب|وَبِكُتّابهم': 'and by/with their kuttab (Quran school)',
    'كَتَب|سَيَكْتُبُونَ|a': 'they will write', 'كَتَب|سَيُكْتَبُونَ|p': 'they will be written',
    'أَكْتَب|سَيُكْتَبُونَ|p': 'they will be dictated', 'أَكْتَب|سَيُكْتِبُونَ|a': 'they will dictate; they will make (someone) write',
    'ٱِسْتَخْدَم|أَسْتَخْدِم|a': 'I use; I employ', 'ٱِسْتَخْدَم|أُسْتَخْدَم|p': 'I am used; I am employed',
    'ٱِسْتَخْدَم|اُسْتُخْدِمَ|p': 'it was used; it was employed', 'ٱِسْتَخْدَم|اِسْتَخْدَمَ|a': 'he used; he employed',
    'ٱِسْتَخْدَم|اِسْتَخْدِمْ|a': 'use! (said to one man)',
    'مَدْرَسَة|مَدْرَسَتِي': 'my school', 'مَدْرَسَة|مَدْرَسَتَيْ': 'the two schools of', 'مَدْرَسَة|مَدْرَسَتَيَّ': 'my two schools',
    'مُدَرِّس|مُدَرِّسَتِي': 'my teacher (f.)', 'مُدَرِّس|مُدَرِّسَتَيْ': 'the two teachers (f.) of', 'مُدَرِّس|مُدَرِّسَتَيَّ': 'my two teachers (f.)',
    'إِلَى|إِلَى': 'to; towards', 'إِلَى|إِلَيَّ': 'to me', 'وَلِي|أَلِي|a': 'I follow; I come after',
    'آلِيّ|آلِيّ': 'mechanical; automatic', 'آل|آلِي': 'my family; my clan', 'آلَى|آلَى|a': 'he promised; he swore an oath',
}
import unicodedata
nfd = lambda t: unicodedata.normalize('NFD', t)  # shadda/vowel order differs between sources
HAND = {nfd(k): v for k, v in HAND.items()}
def hand_gloss(a):
    for k in (f"{a['lex']}|{a['diac']}|{a['vox']}", f"{a['lex']}|{a['diac']}"):
        if nfd(k) in HAND: return HAND[nfd(k)]
    return None

out = {}
for w in WORDS:
    raw = ana.analyze(w)
    groups = {}
    for a in raw:
        prc2 = 'wa' if a['prc2'].startswith('wa_') else a['prc2']  # وَ as and/while/particle -> one reading
        k = (a['lex'], a['pos'], a['prc3'], prc2, a['prc1'], a['prc0'], a['enc0'], a['vox'], a['asp'], a['per'], a['gen'], a['num'])
        g = groups.setdefault(k, {'analyses': [], 'prc2_readings': set(), 'case_forms': set()})
        g['analyses'].append(a); g['prc2_readings'].add(a['prc2']); g['case_forms'].add(a['diac'])
    readings = []
    for k, g in groups.items():
        a = next((x for x in g['analyses'] if x['prc2'] in ('wa_conj', '0') and x['cas'] in ('u', 'na')), g['analyses'][0])
        seg = segments(a)
        form = a['diac']
        readings.append({
            'form': form, 'segments': seg, 'lemma': a['lex'], 'pos': a['pos'],
            'gloss': hand_gloss(a), 'gloss_raw': a['gloss'], 'stemgloss': a['stemgloss'],
            'root': a.get('root') or None, 'pattern': a.get('pattern'), 'measure': measure(a['lex'], a.get('root'), a['pos']),
            'freq_top_pct': pct(float(a.get('lex_logprob', -99))),
            'grammar': grammar(a), 'feats': {f: a.get(f) for f in ['asp', 'vox', 'per', 'gen', 'num', 'form_gen', 'form_num', 'rat', 'prc3', 'prc1', 'prc0', 'enc0']},
            'prc2_readings': sorted(g['prc2_readings']), 'case_forms': sorted(g['case_forms']),
            'raw_count': len(g['analyses']),
            'related_count': len(forms[(a['lex'], a['pos'])]) - 1,
            'root_family_count': len(fam.get(a.get('root'), ())),
        })
    # PRD order: group by lemma, most frequent lemma first, stable within
    readings.sort(key=lambda r: (-(r['freq_top_pct'] is not None), r['freq_top_pct'] if r['freq_top_pct'] is not None else 999, r['lemma'], r['form']))
    out[w] = {'raw_count': len(raw), 'readings': readings}
missing = [(w, r['lemma'], r['form']) for w, v in out.items() for r in v['readings'] if not r['gloss']]
assert not missing, missing
import os
html = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
page = open(html, encoding='utf-8').read()
a, b = page.index('/*DATA*/') + len('/*DATA*/'), page.index('/*END*/')
open(html, 'w', encoding='utf-8').write(page[:a] + 'window.DATA = ' + json.dumps(out, ensure_ascii=False) + ';' + page[b:])
print(f"wrote {len(out)} words into {html}")
