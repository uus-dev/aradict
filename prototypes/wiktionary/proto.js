// M1 Cloth Tab (visual-identity/m1.html) with the Wiktionary layer for #21.
// <html data-option="w1|w2|w3"> picks where Wiktionary's numbered senses sit:
//   w1  labelled rows in the entry head, above the readings
//   w2  a separate credited panel under the readings
//   w3  beside each reading, opened on demand like Word parts
//   w4  like w1, but the readings come first and all the senses follow them
//   w5  question order: which word (headword, how to say it, how common), what the typed word
//       means (readings), then everything about the headword, meanings first
const OPT = document.documentElement.dataset.option;
const W = window.WIKT, FAMILY = window.FAMILY;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const MARKS = /[ً-ْٰـ]/g;
const bare = s => s.replace(MARKS, '').trim();
const POS = { noun: 'Noun', verb: 'Verb', adj: 'Adjective', adv: 'Adverb', prep: 'Preposition', noun_prop: 'Proper noun', pron_rel: 'Relative pronoun' };
const KIND = { prefix: 'Prefix', stem: 'Stem', suffix: 'Suffix' };
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const senses = s => (s || '').split(';').map(x => x.replace(/_/g, ' ').trim()).filter(Boolean);
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const ar = t => `<span lang="ar" dir="rtl">${esc(t)}</span>`;
const arIn = t => esc(t).replace(/[؀-ۿ]+(?:\s+[؀-ۿ]+)*/g, m => `<span lang="ar" dir="rtl">${m}</span>`); // Arabic inside English text
const CHEV = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const EXT = '<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M5 2.5H2.5v7h7V7M7 2.5h2.5V5M9.5 2.5 5.5 6.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

// ponytail: band cut-offs are a design assumption; swap for the product's real thresholds
function freq(p) {
  if (p == null) return { n: 0, label: 'Frequency unknown', pct: '' };
  const [n, label] = p <= 5 ? [4, 'Very common'] : p <= 15 ? [3, 'Common'] : p <= 35 ? [2, 'Less common'] : [1, 'Rare'];
  return { n, label, pct: n === 1 ? '' : `top ${p < 1 ? 1 : Math.round(p)}% of words` };
}
const rootText = r => r ? r.split('.').map(c => c === '#' ? '◌' : c).join(' ') : null;
const rootHTML = t => esc(t).replace(/◌/g, '<span class="unk"><span class="sr" lang="en">unknown letter</span></span>');

function group(readings) {
  const m = new Map();
  for (const r of readings) {
    const k = r.lemma + '|' + r.pos;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(r);
  }
  return [...m.values()];
}

// The lemma's own meaning: senses of its active readings (passives only describe the form).
function lemmaMeaning(rs) {
  const act = rs.filter(r => !r.grammar.includes('passive'));
  return [...new Set((act.length ? act : rs).flatMap(r => senses(r.stemgloss)))].join('; ');
}

function grammarTags(r) {
  const g = r.grammar.slice(1).map(cap);
  for (const s of r.segments.suffix) if (/PRON/.test(s.tag) && s.label) g.push('Attached: ' + s.label);
  return g;
}
const gramHTML = r => {
  const g = grammarTags(r);
  return g.length ? `<ul class="gram">${g.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '<span class="nil">None marked</span>';
};

function formHTML(r) {
  const s = r.segments;
  const all = [...s.prefix, ...s.stem, ...s.suffix].map(p => p.text).join('');
  if (all !== r.form) return esc(r.form);
  return ['prefix', 'stem', 'suffix'].map(k => {
    const t = s[k].map(p => p.text).join('');
    return t ? `<span class="m-${k}">${esc(t)}</span>` : '';
  }).join('');
}

// Dictionary notation for parts: a tatweel shows where an affix joins its neighbour.
const NOJOIN = new Set([...'اأإآٱدذرزوؤةء']);
function joins(t) {
  const b = t.replace(MARKS, '');
  const c = b[b.length - 1];
  return !!c && /[ئ-ي]/.test(c) && !NOJOIN.has(c);
}
function partsHTML(r) {
  const seq = ['prefix', 'stem', 'suffix'].flatMap(k => r.segments[k].map(p => [k, p]));
  return `<ol class="pl" lang="ar" dir="rtl">${seq.map(([k, p], i) => {
    let t = p.text;
    if (k === 'prefix' && seq[i + 1] && joins(t)) t += 'ـ';
    if (k === 'suffix') {
      if (seq[i - 1] && joins(seq[i - 1][1].text)) t = 'ـ' + t;
      else if (/^[ً-ْٰ]/.test(t)) t = '◌' + t;
    }
    const label = p.label || (k === 'stem' ? senses(r.stemgloss).slice(0, 2).join(', ') : '');
    return `${i ? '<li class="plus" aria-hidden="true">+</li>' : ''}<li class="pt pt-${k}"><span class="pt-k" lang="en" dir="ltr">${KIND[k]}<span class="sr">: </span></span><span class="pt-ar">${esc(t)}</span><span class="pt-en" lang="en" dir="ltr">${esc(label)}</span></li>`;
  }).join('')}</ol>`;
}

function freqHTML(r) {
  const f = freq(r.freq_top_pct);
  return `<span class="bars" aria-hidden="true">${[1, 2, 3, 4].map(i => `<i${i <= f.n ? ' class="on"' : ''}></i>`).join('')}</span><span class="lv">${f.label}</span>${f.pct ? `<span class="pct">${f.pct}</span>` : ''}`;
}

/* ---------- Wiktionary ---------- */

// A group is one headword: CAMeL readings (rs) and the Wiktionary entry joined to them (wk).
// Joined by lemma + part of speech; entries with no CAMeL lemma follow as Wiktionary-only groups.
function groupsFor(w) {
  const k = bare(w), d = window.DATA[k];
  const gs = group(d ? d.readings : []).map(rs => ({ rs, wk: W.entries[(W.lemma[rs[0].lemma + '|' + rs[0].pos] || [])[0]] || null }));
  for (const id of W.only[k] || []) gs.push({ rs: [], wk: W.entries[id] });
  for (const g of gs) {
    const sib = gs.filter(h => h.wk && g.wk && h.wk.word === g.wk.word && h.wk.pos === g.wk.pos);
    if (sib.length > 1) g.hn = sib.indexOf(g) + 1;
  }
  return gs;
}
const alsoFor = w => (W.also[bare(w)] || []).map(id => W.entries[id]);

const WK_URL = p => `https://en.wiktionary.org/wiki/${encodeURIComponent(p)}#Arabic`;
function credit(pages) {
  const ps = [...new Set(pages)];
  return `<p class="credit">From Wiktionary, <a class="link" href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a> · ${ps.length > 1 ? 'Entries' : 'Entry'}: ${ps.map(p =>
    `<a class="link" href="${WK_URL(p)}" target="_blank" rel="noopener"><span lang="ar" dir="rtl">${esc(p)}</span><span class="sr"> on Wiktionary, opens in a new tab</span>${EXT}</a>`).join(', ')}</p>`;
}

const qTags = q => q.map(x => `<span class="q">${esc(cap(x))}</span>`).join('');
const senseLi = s => `<li>${qTags(s.q)}${arIn(s.t)}${s.note ? ` <span class="nt">(${arIn(s.note)})</span>` : ''}${s.sub && s.sub.length ? `<ol type="a">${s.sub.map(senseLi).join('')}</ol>` : ''}</li>`;
const sensesHTML = e => `<ol class="sn">${e.senses.map(senseLi).join('')}</ol>`;

// Plurals and verbal nouns open their own lookup.
const look = (a, tr, tags = []) => `<span class="fw"><a class="link" href="#word" data-look="${esc(a)}">${ar(a)}</a>${tr ? ` <span class="tr">${esc(tr)}</span>` : ''}${qTags(tags)}</span>`;
const forms = xs => xs.map(([a, tr]) => look(a, tr)).join('<span class="sep" aria-hidden="true"> · </span> ');

function pronHTML(e) {
  const reg = e.regional.length ? `<details class="reg"><summary>${CHEV}${e.regional.length} regional</summary><dl class="reg-l">${e.regional.map(([k, v]) => `<dt>${esc(k)}</dt><dd class="ipa">${esc(v)}</dd>`).join('')}</dl></details>` : '';
  return `<span class="say">${e.tr ? `<span class="tr">${esc(e.tr)}</span>` : ''}${e.ipa ? ` <span class="ipa">${esc(e.ipa)}</span>` : ''}</span>${reg}`;
}

// Root: CAMeL's root, with letters it leaves open (◌) filled from a matching Wiktionary root.
const fits = (c, w) => { const a = c.split(' '), b = w.split(' '); return a.length === b.length && a.every((x, i) => x === '◌' || x === b[i]); };
function rootInfo(g) {
  const c = rootText(g.rs[0]?.root), w = g.wk?.root || null;
  if (c && w && c.includes('◌') && fits(c, w)) return { text: w, camel: c };
  if (c) return { text: c };
  return w ? { text: w, fromWk: true } : null;
}
function rootLetters(info) {
  if (!info.camel) return rootHTML(info.text);
  const c = info.camel.split(' ');
  return info.text.split(' ').map((x, i) => c[i] === '◌' ? `<span class="fill">${esc(x)}<span class="sr" lang="en"> (filled from Wiktionary)</span></span>` : esc(x)).join(' ');
}
const filledNote = info => `<span class="fw">${ar(info.text.split(' ').filter((x, i) => info.camel.split(' ')[i] === '◌').join(' '))}</span> filled from Wiktionary; the core dictionary has <span class="fw" lang="ar" dir="rtl">${rootHTML(info.camel)}</span>`;

function rootTab(g) {
  const info = rootInfo(g);
  if (!info) return '';
  const n = rootModel(info.text).count;
  return `<a class="root-tab" href="#root:${encodeURIComponent(info.text)}" data-root="${esc(info.text)}">
    <span class="rt-k">Root</span><span class="rt-ar" lang="ar" dir="rtl">${rootLetters(info)}</span>
    <span class="rt-go"><span class="rt-u">${plural(n, 'word')}</span><span class="sr"> from this root</span>${CHEV}</span></a>`;
}

// Labelled rows for one Wiktionary entry. Form-of senses are relations ("Verbal noun of"), never meanings.
function wkRows(g, withSenses) {
  const e = g.wk, info = rootInfo(g);
  let h = '';
  const row = (k, v, cls = '') => { h += `<dt class="${cls}">${k}</dt><dd class="${cls}">${v}</dd>`; };
  if (withSenses && e.senses.length) row('Meanings', sensesHTML(e), 'wide');
  if (e.of.length) row(esc(e.of[0].rel), e.of.map(o => look(o.ar, o.tr, o.tags)).join('<span class="sep" aria-hidden="true"> · </span> '));
  if (e.plural.length) row(e.plural.length > 1 ? 'Plurals' : 'Plural', forms(e.plural));
  if (e.gender) row('Gender', `<ul class="gram"><li>${cap(e.gender)}</li></ul>`);
  if (e.vn.length) row(e.vn.length > 1 ? 'Verbal nouns' : 'Verbal noun', forms(e.vn));
  if (info?.camel) row('Root', filledNote(info));
  if (e.tr || e.ipa) row('Pronunciation', pronHTML(e));
  return h;
}
function wkBlock(g, withSenses, withCredit = true) {
  const rows = wkRows(g, withSenses);
  if (!rows && !withCredit) return '';
  return `<div class="wk"><dl class="facts">${rows}</dl>${withCredit ? credit([g.wk.page]) : ''}</div>`;
}
// W4: all of Wiktionary's senses after the readings, with the credit for the entry's Wiktionary content
const sensesAfter = g => OPT === 'w4' && g.rs.length && g.wk?.senses.length;
const wkAfter = g => `<section class="wk-after" aria-label="All meanings, from Wiktionary"><dl class="facts"><dt class="wide">All meanings</dt><dd class="wide">${sensesHTML(g.wk)}</dd></dl>${credit([g.wk.page])}</section>`;
const wkPanel = g => `<section class="wk-panel" aria-label="From Wiktionary">${credit([g.wk.page])}<dl class="facts">${wkRows(g, true)}</dl></section>`;
const onlyNote = '<p class="only-note">Only in Wiktionary: no frequency, measure or word parts.</p>';
// W3: the entry's numbered senses, opened beside one reading
const sensesBtn = (g, id) => g.wk?.senses.length ? `<button type="button" class="parts-btn" aria-expanded="false" aria-controls="sn-${id}">${CHEV}${plural(g.wk.senses.length, 'meaning')}</button>` : '';
const sensesPanel = (g, id) => g.wk?.senses.length ? `<div class="parts sns" id="sn-${id}" hidden><p class="sns-h">Meanings of ${ar(g.wk.word)} in Wiktionary</p>${sensesHTML(g.wk)}${credit([g.wk.page])}</div>` : '';

function tagsHTML(g) {
  const r = g.rs[0], pos = r ? r.pos : g.wk.pos;
  let h = `<span class="pos">${esc(POS[pos] || cap(pos.replace(/_/g, ' ')))}</span>`;
  if (r && r.pos === 'verb') h += r.measure ? `<span class="pos ms">Form ${esc(r.measure)}</span>` : '<span class="pos ms na">Measure unavailable</span>';
  if (g.hn) h += `<span class="pos ms">Homograph ${g.hn}</span>`;
  if (!r) h += '<span class="pos wko">Wiktionary only</span>';
  return h;
}

/* ---------- W5: question order ---------- */

// How to say the headword sits under it, as in a printed dictionary's headword line.
const sayLine = e => e && (e.tr || e.ipa) ? `<p class="say-line" lang="en" dir="ltr">${e.tr ? `<span class="tr">${esc(e.tr)}</span>` : ''}${e.ipa ? ` <span class="ipa">${esc(e.ipa)}</span>` : ''}</p>` : '';
const regional = e => `<details class="reg"><summary>${CHEV}${plural(e.regional.length, 'pronunciation')}</summary><dl class="reg-l">${e.regional.map(([k, v]) => `<dt>${esc(k)}</dt><dd class="ipa">${esc(v)}</dd>`).join('')}</dl></details>`;

// Everything about the headword, after the readings: what it means, then how it changes, then where it leads.
function w5Rows(g, brief) {
  const e = g.wk, r = g.rs[0], info = rootInfo(g);
  let h = '';
  const row = (k, v, cls = '') => { h += `<dt class="${cls}">${k}</dt><dd class="${cls}">${v}</dd>`; };
  const merged = r && g.rs.length > 1 && !e?.senses.length ? lemmaMeaning(g.rs) : '';
  if (merged) row('Meaning', `<span class="mean">${esc(merged)}</span>`);
  if (e?.senses.length) row('Meanings', sensesHTML(e), 'wide');
  if (e?.plural.length) row(e.plural.length > 1 ? 'Plurals' : 'Plural', forms(e.plural));
  if (e?.gender) row('Gender', `<ul class="gram"><li>${cap(e.gender)}</li></ul>`);
  if (e?.vn.length) row(e.vn.length > 1 ? 'Verbal nouns' : 'Verbal noun', forms(e.vn));
  if (e?.of.length) row(esc(e.of[0].rel), e.of.map(o => look(o.ar, o.tr, o.tags)).join('<span class="sep" aria-hidden="true"> · </span> '));
  if (!brief && r) row('Forms', r.related_count ? `<a class="link" href="#forms" data-forms="${esc(r.lemma)}">${plural(r.related_count, 'other form')}</a>` : '<span class="nil">No other forms</span>');
  if (info?.camel) row('Root', filledNote(info));
  if (!brief && e?.regional.length) row('Regional', regional(e));
  return h;
}
function aboutW5(g, brief) {
  const rows = w5Rows(g, brief);
  if (!rows) return '';
  return `<section class="about-w5" aria-label="About ${esc(g.rs[0] ? g.rs[0].lemma : g.wk.word)}"><dl class="facts">${rows}</dl>${g.wk ? credit([g.wk.page]) : ''}</section>`;
}
function entryW5(g, n) {
  const r = g.rs[0], e = g.wk;
  return `<li class="entry" aria-labelledby="hw-${n}">
    <div class="eh">
      <div class="lemma">
        <div class="hwb"><h2 class="hw" id="hw-${n}" lang="ar" dir="rtl">${esc(r ? r.lemma : e.word)}</h2>${sayLine(e)}</div>
        <span class="tags">${tagsHTML(g)}</span>
      </div>
      ${rootTab(g)}
      ${r ? `<dl class="facts"><dt>Frequency</dt><dd class="freq">${freqHTML(r)}</dd></dl>` : ''}
    </div>
    ${r ? `<ul class="readings" aria-label="Readings under ${esc(r.lemma)}">${g.rs.map((x, i) => readingHTML(x, g, `${n}-${i}`)).join('')}</ul>` : ''}
    ${aboutW5(g, false)}
    ${r ? '' : onlyNote}
  </li>`;
}
function wgW5(g) {
  const r = g.rs[0], e = g.wk;
  const li = x => `<li><div><p class="gloss">${esc(x.gloss)}</p>${gramHTML(x)}</div><p class="form" lang="ar" dir="rtl">${formHTML(x)}</p></li>`;
  return `<section class="wg" aria-label="${esc(r ? r.lemma : e.word)}">
    ${rootTab(g)}
    <div class="wg-h"><div class="hwb"><h3 class="hw" lang="ar" dir="rtl">${esc(r ? r.lemma : e.word)}</h3>${sayLine(e)}</div><span class="tags">${tagsHTML(g)}</span></div>
    ${r ? `<ul class="wl">${g.rs.map(li).join('')}</ul>` : ''}
    ${aboutW5(g, true)}
    ${r ? '' : onlyNote}
  </section>`;
}

/* ---------- Word view ---------- */

function readingHTML(r, g, id) {
  return `<li class="rd">
    <p class="form" lang="ar" dir="rtl">${formHTML(r)}</p>
    <dl class="facts">
      <dt>Meaning</dt><dd class="gloss">${esc(r.gloss)}</dd>
      <dt>Grammar</dt><dd>${gramHTML(r)}</dd>
    </dl>
    <div class="rd-btns">
      <button type="button" class="parts-btn" aria-expanded="false" aria-controls="pt-${id}">${CHEV}Word parts<span class="sr"> of ${esc(r.form)}</span></button>
      ${OPT === 'w3' ? sensesBtn(g, id) : ''}
    </div>
    <div class="parts" id="pt-${id}" hidden>${partsHTML(r)}</div>
    ${OPT === 'w3' ? sensesPanel(g, id) : ''}
  </li>`;
}

function entryHTML(g, n) {
  if (OPT === 'w5') return entryW5(g, n);
  const r = g.rs[0], e = g.wk;
  // W1 shows Wiktionary's numbered senses in the head, so CAMeL's merged lemma meaning steps aside.
  const meaning = r && g.rs.length > 1 && !((OPT === 'w1' || OPT === 'w4') && e?.senses.length) ? lemmaMeaning(g.rs) : '';
  const inHead = e && (OPT !== 'w2');
  return `<li class="entry" aria-labelledby="hw-${n}">
    <div class="eh${inHead ? ' has-wk' : ''}${r ? '' : ' no-facts'}">
      <div class="lemma">
        <h2 class="hw" id="hw-${n}" lang="ar" dir="rtl">${esc(r ? r.lemma : e.word)}</h2>
        <span class="tags">${tagsHTML(g)}</span>
      </div>
      ${rootTab(g)}
      ${r ? `<dl class="facts">
        <dt>Frequency</dt><dd class="freq">${freqHTML(r)}</dd>
        <dt>Forms</dt><dd>${r.related_count ? `<a class="link" href="#forms" data-forms="${esc(r.lemma)}">${plural(r.related_count, 'other form')}</a>` : '<span class="nil">No other forms</span>'}</dd>
        ${meaning ? `<dt>Meaning</dt><dd class="mean">${esc(meaning)}</dd>` : ''}
      </dl>` : ''}
      ${inHead ? wkBlock(g, OPT === 'w1' || !r, !sensesAfter(g)) : ''}
    </div>
    ${r ? `<ul class="readings" aria-label="Readings under ${esc(r.lemma)}">${g.rs.map((x, i) => readingHTML(x, g, `${n}-${i}`)).join('')}</ul>` : onlyNote}
    ${sensesAfter(g) ? wkAfter(g) : ''}
    ${e && OPT === 'w2' ? wkPanel(g) : ''}
  </li>`;
}

function alsoHTML(es, cls = 'box also') {
  if (!es.length) return '';
  return `<section class="${cls}" aria-label="Also in Wiktionary">
    <h2>Also in Wiktionary</h2>
    <p class="also-sub">Listed there as forms of other words, so they have no meanings of their own.</p>
    <ul>${es.map(e => `<li><p>${e.tr ? `<span class="tr">${esc(e.tr)}</span>: ` : ''}${e.of.map(o => `${esc(o.rel)} ${look(o.ar, o.tr, o.tags)}`).join('; ')}</p><p class="form" lang="ar" dir="rtl">${esc(e.word)}</p></li>`).join('')}</ul>
    ${credit(es.map(e => e.page))}
  </section>`;
}

function noneHTML(w) {
  return `<div class="box none">
    <h2>No entry for ${ar(w)}</h2>
    <p>The dictionary has no reading for this word. You could:</p>
    <ul>
      <li>Check the spelling.</li>
      <li>Type it without vowel marks.</li>
      <li>Try it without attached parts, such as ${ar('و')}, ${ar('ب')} or ${ar('ال')} at the start, or ${ar('ها')}, ${ar('هم')} at the end.</li>
    </ul>
    <p>Recent loanwords are often missing from the dictionary.</p>
  </div>`;
}

function statusText(w, gs, also) {
  const nr = gs.reduce((n, g) => n + g.rs.length, 0), nh = gs.filter(g => g.rs.length).length;
  const more = gs.length - nh + also.length;
  return `<strong>${plural(nr, 'reading')}</strong> for ${ar(w)}, under ${plural(nh, 'headword')}${more ? `, and ${more} more ${more === 1 ? 'entry' : 'entries'} from Wiktionary` : ''}`;
}

const q = $('#q'), results = $('#results'), status = $('#status');
let lastWord = '';
function lookup(w) {
  w = w.trim();
  q.value = w;
  lastWord = w;
  if (!w) {
    status.textContent = '';
    results.innerHTML = '<div class="box empty">Type or paste an Arabic word above, or pick one of the examples.</div>';
    return;
  }
  const gs = groupsFor(w), also = alsoFor(w);
  if (!gs.length && !also.length) {
    status.innerHTML = `<strong>No readings</strong> for ${ar(w)}`;
    $('#legend').hidden = true;
    results.innerHTML = noneHTML(w);
    return;
  }
  $('#legend').hidden = false;
  status.innerHTML = statusText(w, gs, also);
  results.innerHTML = `<ol class="entries">${gs.map(entryHTML).join('')}</ol>${alsoHTML(also)}`;
  if ((location.hash.split(':')[0] || '#word') === '#word') history.replaceState(null, '', '#word:' + encodeURIComponent(w));
}
$('#sf').addEventListener('submit', e => { e.preventDefault(); lookup(q.value); });
$('#ex').innerHTML = ['كتاب', 'كتب', 'قال', 'تغريدة']
  .map(w => `<li><button type="button" class="chip" lang="ar" dir="rtl">${w}</button></li>`).join('');
$('#ex').addEventListener('click', e => { const b = e.target.closest('.chip'); if (b) lookup(b.textContent); });

/* ---------- Root view ---------- */

// PRD order: by measure, then part of speech (verbs first), then lemma.
const MEAS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'];
const POS_ORDER = ['verb', 'noun', 'adj', 'adv', 'noun_prop', 'prep', 'pron_rel'];
const byRoot = (a, b) => ((MEAS.indexOf(a.measure) + 1 || 99) - (MEAS.indexOf(b.measure) + 1 || 99))
  || (POS_ORDER.indexOf(a.pos) - POS_ORDER.indexOf(b.pos)) || a.ar.localeCompare(b.ar, 'ar');

// The words under a root. When Wiktionary fills a letter CAMeL left open, only words Wiktionary
// places under the filled root are confirmed; the rest of CAMeL's family stays unconfirmed.
function rootModel(text) {
  const keys = Object.keys(FAMILY);
  const exact = keys.find(k => rootText(k) === text);
  const loose = exact ? null : keys.find(k => rootText(k).includes('◌') && fits(rootText(k), text));
  const joined = new Set(Object.values(W.lemma).flat());
  const wkOf = x => W.entries[(W.lemma[x.lemma + '|' + x.pos] || [])[0]];
  const main = [], unconf = [], pages = [];
  for (const x of FAMILY[exact || loose] || []) {
    const row = { ar: x.lemma, pos: x.pos, measure: x.measure, gloss: x.gloss };
    const wr = wkOf(x)?.root;
    if (exact) main.push(row);
    else if (wr === text) { main.push(row); pages.push(wkOf(x).page); }
    else if (!wr) unconf.push(row);
  }
  for (const e of Object.values(W.entries)) {
    if (e.root !== text || joined.has(e.id)) continue;
    main.push({ ar: e.word, pos: e.pos, measure: null, wk: e,
      gloss: e.senses.length ? e.senses.map(s => s.t).join('; ') : e.of.map(o => `${o.rel} ${o.ar}`).join('; ') });
    pages.push(e.page);
  }
  main.sort(byRoot); unconf.sort(byRoot);
  return { text, camel: loose ? rootText(loose) : null, main, unconf, pages, count: main.length + unconf.length };
}

const rvRow = x => `<li class="rv-r">
  <p class="rv-g"><span class="tags"><span class="pos">${esc(POS[x.pos] || cap(x.pos.replace(/_/g, ' ')))}</span>${x.measure ? `<span class="pos ms">Form ${x.measure}</span>` : ''}${x.wk ? '<span class="pos wko">Wiktionary</span>' : ''}</span>
    ${x.gloss ? arIn(x.gloss) : '<span class="nil">No gloss</span>'}</p>
  <p class="rv-ar"><a class="link" href="#word" data-look="${esc(x.ar)}" lang="ar" dir="rtl">${esc(x.ar)}</a></p>
</li>`;

function renderRoot(text) {
  const m = rootModel(text), info = m.camel ? { text, camel: m.camel } : { text };
  const fromWk = !m.camel && !Object.keys(FAMILY).some(k => rootText(k) === text);
  $('#rv').innerHTML = `<article class="entry rv" aria-labelledby="rv-h">
    <div class="eh">
      <div class="lemma"><h1 class="hw" id="rv-h" lang="ar" dir="rtl">${rootLetters(info)}</h1><span class="tags"><span class="pos">Root</span></span></div>
      <dl class="facts">
        <dt>Words</dt><dd>${m.unconf.length ? `${m.main.length} confirmed, ${m.unconf.length} not confirmed` : plural(m.count, 'word')}</dd>
        ${m.camel ? `<dt>Letters</dt><dd>${filledNote(info)}</dd>` : fromWk ? '<dt>Letters</dt><dd>From Wiktionary</dd>' : ''}
      </dl>
    </div>
    <ol class="rv-l">${m.main.map(rvRow).join('')}</ol>
    ${m.unconf.length ? `<h2 class="rv-sub">Also under <span lang="ar" dir="rtl">${rootHTML(m.camel)}</span> in the core dictionary, letter not confirmed</h2><ol class="rv-l">${m.unconf.map(rvRow).join('')}</ol>` : ''}
    ${m.pages.length ? `<div class="rv-foot">${credit(m.pages)}</div>` : ''}
  </article>`;
}
$('#rvBack').addEventListener('click', () => history.length > 1 ? history.back() : (location.hash = '#word'));

/* ---------- Shared clicks: word parts, meanings, lookups, roots ---------- */

function openWord(w) {
  const k = bare(w);
  if (!window.DATA[k] && !W.only[k]) return toast(`${ar(w)} opens its own lookup here.`);
  if (wp.matches(':popover-open')) wp.hidePopover();
  location.hash = '#word';
  lookup(w);
  scrollTo({ top: 0, behavior: 'instant' });
}
document.addEventListener('click', e => {
  const pb = e.target.closest('.parts-btn');
  if (pb) {
    const open = pb.getAttribute('aria-expanded') !== 'true';
    pb.setAttribute('aria-expanded', open);
    document.getElementById(pb.getAttribute('aria-controls')).hidden = !open;
    return;
  }
  const a = e.target.closest('a[data-look], a.root-tab, a[data-forms]');
  if (!a) return;
  e.preventDefault();
  if (a.dataset.look) return openWord(a.dataset.look);
  if (a.dataset.forms) return toast(`All forms of ${ar(a.dataset.forms)} open here.`);
  if (wp.matches(':popover-open')) wp.hidePopover();
  location.hash = '#root:' + encodeURIComponent(a.dataset.root);
  scrollTo({ top: 0, behavior: 'instant' });
});

let toastT;
function toast(html) {
  const t = $('#toast');
  t.innerHTML = html;
  t.classList.add('on');
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.remove('on'), 3200);
}

/* ---------- On-screen keyboard (Arabic 101 rows, physical left-to-right order) ---------- */
const ROWS = [
  [['ذ','dhal'],['ض','ḍad'],['ص','ṣad'],['ث','tha'],['ق','qaf'],['ف','fa'],['غ','ghayn'],['ع','ʿayn'],['ه','ha'],['خ','kha'],['ح','ḥa'],['ج','jim'],['د','dal']],
  [['ش','shin'],['س','sin'],['ي','ya'],['ب','ba'],['ل','lam'],['ا','alif'],['ت','ta'],['ن','nun'],['م','mim'],['ك','kaf'],['ط','ṭa']],
  [['ئ','ya with hamza above'],['ء','hamza'],['ؤ','waw with hamza above'],['ر','ra'],['لا','lam alif'],['ى','alif maqsura'],['ة','ta marbuta'],['و','waw'],['ز','zay'],['ظ','ẓa']],
];
const SHIFT = [
  [['ّ','shadda'],['َ','fatha'],['ً','fathatan'],['ُ','damma'],['ٌ','dammatan'],['ِ','kasra'],['ٍ','kasratan'],['ْ','sukun']],
  [['أ','alif with hamza above'],['إ','alif with hamza below'],['آ','alif with madda'],['لأ','lam alif with hamza above'],['لإ','lam alif with hamza below'],['لآ','lam alif with madda'],['ـ','tatweel']],
  [['،','Arabic comma'],['؛','Arabic semicolon'],['؟','Arabic question mark']],
];
const kbd = $('#kbd'), kbBtn = $('#kbBtn');
let shifted = false;
function drawKbd() {
  const rows = shifted ? SHIFT : ROWS;
  kbd.innerHTML = rows.map(row => `<div class="kr">${row.map(([c, n]) =>
    `<button type="button" class="key" data-c="${c}" aria-label="${n}"><span lang="ar">${/^[ً-ْ]$/.test(c) ? '◌' + c : c}</span></button>`).join('')}</div>`).join('') +
    `<div class="kr">
      <button type="button" class="key fn shift" data-fn="shift" aria-pressed="${shifted}">Shift</button>
      <button type="button" class="key fn space" data-fn="space" aria-label="Space">Space</button>
      <button type="button" class="key fn del" data-fn="del" aria-label="Delete">⌫</button>
      <button type="button" class="key fn hide" data-fn="hide" aria-label="Hide keyboard">Hide</button>
    </div>
    <p class="kbd-note">${shifted ? 'Vowel marks, hamza seats and punctuation, for one key' : 'Shift for vowel marks, hamza seats and punctuation'}</p>`;
}
function setKbd(open) {
  kbd.hidden = !open;
  kbBtn.setAttribute('aria-expanded', open);
  if (open) { q.setAttribute('inputmode', 'none'); drawKbd(); }
  else { q.removeAttribute('inputmode'); shifted = false; }
  q.focus();
}
kbBtn.addEventListener('click', () => setKbd(kbd.hidden));
kbd.addEventListener('pointerdown', e => { if (e.target.closest('.key')) e.preventDefault(); }); // keep the caret in the field
kbd.addEventListener('click', e => {
  const k = e.target.closest('.key');
  if (!k) return;
  const fn = k.dataset.fn;
  if (fn === 'hide') return setKbd(false);
  if (fn === 'shift') { shifted = !shifted; drawKbd(); return refocusKey('shift'); }
  let s = q.selectionStart ?? q.value.length, en = q.selectionEnd ?? s;
  if (fn === 'del') {
    if (s === en && s > 0) s -= 1;
    q.setRangeText('', s, en, 'end');
  } else {
    q.setRangeText(fn === 'space' ? ' ' : k.dataset.c, s, en, 'end');
    if (shifted && !fn) { shifted = false; drawKbd(); }
  }
  q.dispatchEvent(new Event('input', { bubbles: true }));
  if (document.activeElement === document.body || kbd.contains(document.activeElement) === false) q.focus();
});
function refocusKey(fn) { if (kbd.contains(document.activeElement) || document.activeElement === document.body) $(`.key[data-fn="${fn}"]`, kbd)?.focus(); }

/* ---------- Text view ---------- */
const passage = $('#passage'), wp = $('#wp');
let cur = null;
function analyze(text) {
  const re = /[ء-ْٰٱ]+/g;
  let out = '', last = 0, m, n = 0;
  while ((m = re.exec(text))) {
    out += esc(text.slice(last, m.index));
    const w = m[0], known = groupsFor(w).length;
    out += `<button type="button" class="w${known ? '' : ' unknown'}" popovertarget="wp" data-w="${esc(w)}">${esc(w)}${known ? '' : '<span class="sr" lang="en"> (no entry)</span>'}</button>`;
    last = re.lastIndex; n++;
  }
  passage.innerHTML = out + esc(text.slice(last));
  $('#pb-n').textContent = `, ${plural(n, 'word')}`;
}
$('#tf').addEventListener('submit', e => { e.preventDefault(); analyze($('#ta').value); });

function wgHTML(g, n) {
  if (OPT === 'w5') return wgW5(g);
  const r = g.rs[0], e = g.wk, id = `p${n}`;
  const li = (x, i) => `<li><div><p class="gloss">${esc(x.gloss)}</p>${gramHTML(x)}${OPT === 'w3' && sensesBtn(g, `${id}-${i}`) ? `<div class="rd-btns">${sensesBtn(g, `${id}-${i}`)}</div>` : ''}</div><p class="form" lang="ar" dir="rtl">${formHTML(x)}</p>${OPT === 'w3' ? sensesPanel(g, `${id}-${i}`) : ''}</li>`;
  return `<section class="wg" aria-label="${esc(r ? r.lemma : e.word)}">
    ${rootTab(g)}
    <div class="wg-h">
      <h3 class="hw" lang="ar" dir="rtl">${esc(r ? r.lemma : e.word)}</h3>
      <span class="tags">${tagsHTML(g)}</span>
    </div>
    ${e && OPT !== 'w2' ? wkBlock(g, OPT === 'w1' || !r, !sensesAfter(g)) : ''}
    ${r ? `<ul class="wl">${g.rs.map(li).join('')}</ul>` : onlyNote}
    ${sensesAfter(g) ? wkAfter(g) : ''}
    ${e && OPT === 'w2' ? wkPanel(g) : ''}
  </section>`;
}
function panelHTML(w) {
  const gs = groupsFor(w), also = alsoFor(w), nr = gs.reduce((n, g) => n + g.rs.length, 0), more = gs.length - gs.filter(g => g.rs.length).length + also.length;
  const body = gs.length ? gs.map(wgHTML).join('') + alsoHTML(also, 'wg also')
    : `<p class="wp-none">This word isn’t in the dictionary. Recent loanwords are often missing; try it without attached parts.</p>`;
  return `<div class="wp-head"><h2 id="wp-h" lang="ar" dir="rtl">${esc(w)}</h2><p>${gs.length ? `<strong>${plural(nr, 'reading')}</strong>${more ? `, ${more} more from Wiktionary` : ''}` : '<strong>No entry</strong>'}</p></div>
    <div class="wp-body"${gs.length ? '' : ' style="padding:0;background:var(--leaf)"'}>${body}</div>
    <div class="wp-foot">
      ${gs.length ? `<button type="button" class="btn sm" data-open="${esc(w)}">Open in Word lookup</button>` : ''}
      <button type="button" class="btn sm primary" popovertarget="wp" popovertargetaction="hide">Close</button>
    </div>`;
}
function setWord(b) {
  cur?.classList.remove('is-open');
  cur = b;
  b.classList.add('is-open');
  wp.innerHTML = panelHTML(b.dataset.w);
}
passage.addEventListener('click', e => {
  const b = e.target.closest('.w');
  if (!b) return;
  const open = wp.matches(':popover-open');
  if (open && b !== cur) { e.preventDefault(); setWord(b); place(); } // switch words without closing
  else if (!open) setWord(b);
});
wp.addEventListener('toggle', e => {
  if (e.newState === 'open') {
    place();
    if (narrow.matches) { // keep the tapped word visible above the sheet
      const r = cur.getBoundingClientRect(), top = innerHeight - wp.offsetHeight - 20;
      if (r.bottom > top) scrollBy({ top: r.bottom - top, behavior: 'instant' });
    }
  }
  else { cur?.classList.remove('is-open'); cur = null; }
});
wp.addEventListener('click', e => {
  const o = e.target.closest('[data-open]');
  if (o) openWord(o.dataset.open);
});
const narrow = matchMedia('(max-width: 640px)');
function place() {
  if (!cur || !wp.matches(':popover-open')) return;
  wp.style.removeProperty('max-height');
  if (narrow.matches) return; // bottom sheet, placed by CSS
  const r = cur.getBoundingClientRect(), pw = wp.offsetWidth, ph = wp.offsetHeight, m = 12, gap = 8;
  // Prefer below the word; shrink (the body scrolls) rather than cover the text above.
  const below = innerHeight - r.bottom - gap - m, above = r.top - gap - m;
  const down = ph <= below || below >= 300 || below >= above;
  const h = Math.min(ph, down ? below : above);
  wp.style.maxHeight = h + 'px';
  wp.style.setProperty('--x', Math.max(m, Math.min(r.right - pw, innerWidth - pw - m)) + 'px');
  wp.style.setProperty('--y', (down ? r.bottom + gap : r.top - gap - h) + 'px');
}
addEventListener('resize', place);
addEventListener('scroll', place, { passive: true });

/* ---------- Views: #word[:word], #text, #root:letters, #about ---------- */
const VIEWS = ['word', 'text', 'root', 'about'];
function show() {
  let [view, arg] = location.hash.slice(1).split(':');
  if (!VIEWS.includes(view)) view = 'word';
  arg = arg ? decodeURIComponent(arg) : '';
  for (const v of VIEWS) $('#v-' + v).hidden = v !== view;
  $$('.nav a').forEach(a => a.dataset.view === view ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  if (view !== 'text' && wp.matches(':popover-open')) wp.hidePopover();
  if (view === 'root') renderRoot(arg || 'ق و ل');
  if (view === 'word' && arg && arg !== lastWord) lookup(arg);
  markReview();
}
addEventListener('hashchange', show);

// Review control: Auto removes data-theme so the system setting applies; options keep the screen.
function markReview() {
  const v = location.hash.slice(1).split(':')[0] || 'word';
  const s = v === 'text' || v === 'root' ? v : v === 'word' ? 'word' : '';
  const th = document.documentElement.dataset.theme || 'auto';
  $$('.review [data-screen]').forEach(b => b.setAttribute('aria-pressed', b.dataset.screen === s));
  $$('.review [data-theme]').forEach(b => b.setAttribute('aria-pressed', b.dataset.theme === th));
  $$('.review [data-opt]').forEach(a => {
    a.href = `${a.dataset.opt}.html${location.hash}`;
    a.dataset.opt === OPT ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
  });
}
$('.review').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  if (b.dataset.theme === 'auto') delete document.documentElement.dataset.theme;
  else if (b.dataset.theme) document.documentElement.dataset.theme = b.dataset.theme;
  if (b.dataset.screen === 'word') location.hash = '#word:' + encodeURIComponent(lastWord);
  if (b.dataset.screen === 'text') location.hash = '#text';
  if (b.dataset.screen === 'root') location.hash = '#root:' + encodeURIComponent('ق و ل');
  markReview();
});

analyze($('#ta').value);
if (!location.hash.startsWith('#word:')) lookup('كتاب');
show();
