// The on-screen Arabic keyboard: the standard Arabic (101) layout, whose shift layer holds the
// harakat, the hamza seats and lam-alif. Every button with data-keyboard gets one: the attribute
// names the field the keys type into, and aria-controls the empty panel the keys are drawn in.
// A key inserts at the caret and fires an input event, so live lookup runs just as for typing.

// The letter and Latin cap of each key, row by row in physical order from the left.
const CAPS = ["`QWERTYUIOP[]", "ASDFGHJKL;'", "ZXCVBNM,./"];
const BASE = [
  ["ذ", "ض", "ص", "ث", "ق", "ف", "غ", "ع", "ه", "خ", "ح", "ج", "د"],
  ["ش", "س", "ي", "ب", "ل", "ا", "ت", "ن", "م", "ك", "ط"],
  ["ئ", "ء", "ؤ", "ر", "لا", "ى", "ة", "و", "ز", "ظ"],
];
// Shift: shadda, fatha, fathatan, damma, dammatan … / kasra, kasratan … / … sukun.
const SHIFT = [
  ["ّ", "َ", "ً", "ُ", "ٌ", "لإ", "إ", "‘", "÷", "×", "؛", "<", ">"],
  ["ِ", "ٍ", "]", "[", "لأ", "أ", "ـ", "،", "/", ":", '"'],
  ["~", "ْ", "}", "{", "لآ", "آ", "’", ",", ".", "؟"],
];
// Spoken names, after the Unicode character names. Other keys are named by their symbol.
const NAMES = {
  "ا": "alef", "ب": "beh", "ت": "teh", "ث": "theh", "ج": "jeem", "ح": "hah", "خ": "khah", "د": "dal", "ذ": "thal",
  "ر": "reh", "ز": "zain", "س": "seen", "ش": "sheen", "ص": "sad", "ض": "dad", "ط": "tah", "ظ": "zah", "ع": "ain",
  "غ": "ghain", "ف": "feh", "ق": "qaf", "ك": "kaf", "ل": "lam", "م": "meem", "ن": "noon", "ه": "heh", "و": "waw",
  "ي": "yeh", "ى": "alef maksura", "ة": "teh marbuta", "ء": "hamza", "أ": "alef with hamza above",
  "إ": "alef with hamza below", "آ": "alef with madda above", "ؤ": "waw with hamza above", "ئ": "yeh with hamza above",
  "لا": "lam alef", "لأ": "lam alef with hamza above", "لإ": "lam alef with hamza below", "لآ": "lam alef with madda above",
  "ً": "fathatan", "ٌ": "dammatan", "ٍ": "kasratan", "َ": "fatha", "ُ": "damma",
  "ِ": "kasra", "ّ": "shadda", "ْ": "sukun", "ـ": "tatweel",
  "،": "Arabic comma", "؛": "Arabic semicolon", "؟": "Arabic question mark",
};
const MARK = /^[ً-ْ]$/;

const key = (className, label, name) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  if (name) button.setAttribute("aria-label", name);
  return button;
};

for (const toggle of document.querySelectorAll("[data-keyboard]")) {
  const field = document.getElementById(toggle.dataset.keyboard);
  const panel = document.getElementById(toggle.getAttribute("aria-controls"));
  let shifted = false;
  let focused = false; // a field never focused has its caret at the start, not after the word it was loaded with
  field.addEventListener("focus", () => { focused = true; }, { once: true });

  // Replace the selection, or insert at the caret, and tell listeners the field changed.
  const type = (text) => {
    if (!focused) field.setSelectionRange(field.value.length, field.value.length);
    let { selectionStart: start, selectionEnd: end } = field;
    if (!text && start === end) { // Delete with no selection takes the character before the caret
      if (!start) return;
      start -= 1;
    }
    field.setRangeText(text, start, end, "end");
    field.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: text ? "insertText" : "deleteContentBackward", data: text || null }));
  };

  const letters = BASE.map((row, r) => row.map((_, i) => {
    const button = key("key", "");
    button.dataset.cap = CAPS[r][i];
    button.addEventListener("click", () => {
      type(button.value);
      if (shifted) shift(false); // one key from the shift layer, then back to the letters
    });
    return button;
  }));
  const shiftKey = key("key fn", "Shift");
  const shift = (on) => {
    shifted = on;
    shiftKey.setAttribute("aria-pressed", on);
    letters.forEach((row, r) => row.forEach((button, i) => {
      const ch = (on ? SHIFT : BASE)[r][i];
      button.value = ch;
      button.setAttribute("aria-label", NAMES[ch] ?? ch);
      const glyph = document.createElement("span");
      glyph.lang = "ar";
      glyph.dir = "rtl";
      glyph.textContent = MARK.test(ch) ? `◌${ch}` : ch;
      button.replaceChildren(glyph);
    }));
  };
  shiftKey.addEventListener("click", () => shift(!shifted));
  const deleteKey = key("key fn", "⌫", "Delete");
  deleteKey.addEventListener("click", () => type(""));
  const space = key("key fn space", "Space");
  space.addEventListener("click", () => type(" "));
  const hide = key("key fn", "Hide");

  const rows = [letters[0], letters[1], [shiftKey, ...letters[2], deleteKey], [hide, space]].map((keys) => {
    const row = document.createElement("div");
    row.className = "row";
    row.append(...keys);
    return row;
  });
  panel.append(...rows);
  panel.addEventListener("mousedown", (event) => event.preventDefault()); // keep focus, and the caret, in the field

  const show = (open) => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", open);
    // While the keys are on screen, a tap in the field moves the caret without raising the phone's own keyboard.
    if (open) field.setAttribute("inputmode", "none");
    else field.removeAttribute("inputmode");
    shift(false);
  };
  toggle.addEventListener("click", () => show(panel.hidden));
  hide.addEventListener("click", () => {
    show(false);
    toggle.focus();
  });
  show(false);
  toggle.hidden = false;
}
