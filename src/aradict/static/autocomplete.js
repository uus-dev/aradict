// Autocomplete for the Word field, following the WAI-ARIA combobox pattern with list
// autocomplete: the field keeps focus and points at the active suggestion. Choosing one puts
// its vocalized form in the field and submits the form, so the live lookup shows it and
// pushes its URL as Enter does. Without JavaScript there is neither the list nor its switch.
const form = document.getElementById("search");
const input = form.elements.q;

const list = document.createElement("ul");
list.id = "suggestions";
list.className = "suggestions";
list.setAttribute("role", "listbox");
list.setAttribute("aria-label", "Suggestions");
list.lang = "ar";
list.dir = "rtl";
list.hidden = true;
input.after(list);

// Unnamed, so the switch is never part of the lookup URL. Persisting it is #13.
const toggle = Object.assign(document.createElement("input"), { type: "checkbox", checked: true });
const toggleLabel = document.createElement("label");
toggleLabel.className = "option";
toggleLabel.append(toggle, " Show suggestions");
form.append(toggleLabel);

let request = new AbortController();
let active = -1;

const setActive = (index) => {
  [...list.children].forEach((option, i) => option.setAttribute("aria-selected", i === index));
  active = index;
  if (index < 0) {
    input.removeAttribute("aria-activedescendant");
  } else {
    input.setAttribute("aria-activedescendant", list.children[index].id);
    list.children[index].scrollIntoView({ block: "nearest" });
  }
};

const close = () => {
  request.abort();
  list.hidden = true;
  list.replaceChildren();
  setActive(-1);
  if (toggle.checked) input.setAttribute("aria-expanded", "false");
};

const suggest = async () => {
  request.abort(); // the list stays until the new suggestions replace it
  if (!toggle.checked || !input.value.trim()) return close();
  request = new AbortController();
  const { signal } = request;
  let forms;
  try {
    // The form's own fields, so suggestions follow the diacritics switch.
    const response = await fetch(`/suggest?${new URLSearchParams(new FormData(form))}`, { signal });
    forms = response.ok ? await response.json() : [];
  } catch {
    return; // superseded, switched off, or offline: the lookup itself reports failures
  }
  if (signal.aborted) return;
  if (!forms.length || document.activeElement !== input) return close();
  setActive(-1);
  list.replaceChildren(...forms.map((text, i) => {
    const option = document.createElement("li");
    option.id = `suggestion-${i}`;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    option.textContent = text;
    return option;
  }));
  Object.assign(list.style, {
    top: `${input.offsetTop + input.offsetHeight}px`,
    left: `${input.offsetLeft}px`,
    width: `${input.offsetWidth}px`,
  });
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
};

const choose = (option) => {
  input.value = option.textContent;
  close();
  form.requestSubmit();
};

const setSwitch = () => {
  close();
  const aria = { role: "combobox", "aria-autocomplete": "list", "aria-controls": list.id, "aria-expanded": "false" };
  for (const [name, value] of Object.entries(aria)) {
    if (toggle.checked) input.setAttribute(name, value);
    else input.removeAttribute(name);
  }
};
setSwitch();

// The switch only changes suggestions; it must not reach the form's live lookup.
toggle.addEventListener("input", (event) => event.stopPropagation());
toggle.addEventListener("change", setSwitch);

input.addEventListener("input", suggest);
input.addEventListener("blur", close);
form.addEventListener("submit", close);

input.addEventListener("keydown", (event) => {
  const count = list.children.length;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    if (list.hidden) {
      if (event.key === "ArrowDown") suggest();
      return;
    }
    event.preventDefault();
    const step = event.key === "ArrowDown" ? 1 : -1;
    setActive(active < 0 ? (step > 0 ? 0 : count - 1) : (active + step + count) % count);
  } else if (event.key === "Enter" && !list.hidden && active >= 0) {
    event.preventDefault();
    choose(list.children[active]);
  } else if (event.key === "Escape" && !list.hidden) {
    event.preventDefault();
    close(); // the lookup of the typed text stays
  }
});

list.addEventListener("mousedown", (event) => event.preventDefault()); // keep focus in the field
list.addEventListener("click", (event) => {
  const option = event.target.closest("[role=option]");
  if (option) choose(option);
});
