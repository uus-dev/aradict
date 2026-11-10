// Recent lookups and remembered preferences, kept only in this browser's localStorage and never
// sent to the server. Storage can be blocked, full or hold anything, so every access is wrapped:
// without it nothing outlasts the page, and lookup works the same.

const read = (key) => {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
};
const write = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
};

// Preferences: every control marked data-remember keeps its last state on this device. That is
// the diacritics switch and the history size now; the direction switch (#9) and the autocomplete
// toggle (#8) only need the attribute. A URL with parameters names its own view, so there the
// search form keeps the state the server rendered from it, and the next lookups follow the page.
const PREFS = "aradict.prefs";
const storedPrefs = read(PREFS);
const prefs = storedPrefs && typeof storedPrefs === "object" ? storedPrefs : {};
for (const control of document.querySelectorAll("[data-remember]")) {
  const value = prefs[control.name];
  if (value !== undefined && !(control.form && location.search)) {
    if (control.type === "checkbox") control.checked = value === true;
    else control.value = value;
  }
  control.addEventListener("change", () => {
    prefs[control.name] = control.type === "checkbox" ? control.checked : control.value;
    write(PREFS, prefs);
  });
}

// History.
const panel = document.getElementById("history");
const list = panel.querySelector("ol");
const size = panel.querySelector("[name=history-size]");

// An entry is the URL of a view on this site, which encodes the query, its options and any root
// or related-forms view, so opening it shows exactly what was shown. Anything else, such as a
// blank query, is not an entry.
const entry = (url) => {
  const view = URL.parse(url, location.href);
  return view?.origin === location.origin && view.searchParams.get("q")?.trim()
    ? `${view.pathname}?${view.searchParams}`
    : null;
};

const KEY = "aradict.history";
const stored = read(KEY);
let entries = (Array.isArray(stored) ? stored : []).map(entry).filter(Boolean);

const params = (url) => new URL(url, location.href).searchParams;
const query = (url) => params(url).get("q").trim();

// Text in its own language: Arabic script is marked as Arabic (an Arabizi or English query is not).
const span = (text) => {
  const node = document.createElement("span");
  node.textContent = text;
  if (/[\u0600-\u06ff]/.test(text)) Object.assign(node, { className: "ar", lang: "ar", dir: "rtl" });
  return node;
};

// What an entry says: the query; that it was English (book is also Arabizi), or else that
// diacritics were ignored where that changes the result, which is only when the query has vowel
// marks (the same marks as dictionary.py's MARK); and the root's words or the lemma's forms shown
// in place of its results, so that they read differently from the lookup itself. Entries that say
// the same are one view, so a sorted root view is too.
const label = (url) => {
  const view = params(url);
  const root = view.get("root");
  const related = view.get("related");
  const link = document.createElement("a");
  link.href = url;
  link.append(span(query(url)));
  if (view.get("lang") === "en") link.append(" · English");
  else if (view.get("diacritics") === "off" && /[\u064b-\u065f\u0670]/.test(query(url))) link.append(" · diacritics ignored");
  if (root) link.append(" · root ", span(root.split(".").map((letter) => (letter === "#" ? "◌" : letter)).join(" ")));
  else if (related) link.append(" · forms of ", span(related));
  return link;
};
const title = (url) => label(url).textContent;

const render = () => {
  list.replaceChildren(...entries.map((url) => {
    const item = document.createElement("li");
    item.append(label(url));
    return item;
  }));
};

// How many entries to keep: what the size field says, or its default when it says nothing usable.
const limit = () => (size.valueAsNumber >= 0 ? Math.floor(size.valueAsNumber) : Number(size.defaultValue));
const save = () => {
  entries = entries.slice(0, limit()); // drops the oldest
  write(KEY, entries);
  render();
};
size.addEventListener("change", save);
panel.querySelector("button").addEventListener("click", () => {
  entries = [];
  save();
});

// A view is listed once, newest first, and two views that would read the same are one entry
// (كتب with diacritics ignored or not), which keeps the newer one. Typing a word looks up each
// prefix on the way (ك, كت, كتب): a typed lookup that extends the previous typed lookup replaces
// it, so the word is kept once. Any other lookup (Enter, a switch, a link, a reload) and any
// blank query in between start a new entry.
let typing = false;
const record = (url, typed = false) => {
  const view = entry(url);
  const extend = typed && typing && view && entries.length && query(view).startsWith(query(entries[0]));
  typing = typed && !!view;
  if (!view) return;
  entries = [view, ...entries.slice(extend ? 1 : 0).filter((e) => title(e) !== title(view))];
  save();
};

record(location.href); // a view opened from a link, a reload, Back or a plain form submission
// A live lookup, just before htmx puts its URL in the browser history.
document.body.addEventListener("htmx:beforeHistoryUpdate", ({ detail }) => {
  const trigger = detail.requestConfig.triggeringEvent;
  record(detail.history.path, trigger?.type === "input" && trigger.target.name === "q");
});
render();
panel.hidden = false;
