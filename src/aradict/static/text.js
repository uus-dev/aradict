// Live analysis is htmx, declared on the form; this adds its loading and failure states.
// Token details are native popovers and work without this script. Here they open under the
// chosen word on wide screens; narrow screens show them as a bottom sheet (style.css) and
// scroll the word above it.
const form = document.getElementById("analyse");
const status = document.getElementById("status");
const failure = document.getElementById("failure");
const narrow = matchMedia("(max-width: 640px)");
let word; // the button that opened the details: a word written twice shares them

form.addEventListener("htmx:beforeRequest", () => {
  status.textContent = "Analysing…";
});
const fail = () => {
  // An older passage must not read as current; Retry posts the kept text again.
  document.getElementById("analysis").replaceChildren(failure.content.cloneNode(true));
  status.textContent = failure.dataset.status;
};
form.addEventListener("htmx:responseError", fail);
form.addEventListener("htmx:sendError", fail);

const place = (pop) => {
  pop.style.inset = pop.style.margin = pop.style.maxHeight = "";
  if (narrow.matches || !word?.isConnected) return;
  const r = word.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  const left = Math.min(Math.max(16, r.left + r.width / 2 - w / 2), innerWidth - w - 16);
  const above = r.top - h - 6;
  const below = r.bottom + h + 6 <= innerHeight - 12 || above < 12;
  const top = below ? r.bottom + 6 : above;
  pop.style.margin = "0";
  pop.style.inset = `${top}px auto auto ${left}px`;
  // ponytail: when neither side fits, it scrolls inside rather than moving off the word.
  if (below) pop.style.maxHeight = `${Math.max(200, innerHeight - top - 12)}px`;
};

document.addEventListener("click", (event) => {
  word = event.target.closest(".tok") ?? word;
});
document.addEventListener("toggle", (event) => {
  const pop = event.target;
  if (!pop.classList?.contains("tok-pop")) return;
  for (const tok of document.querySelectorAll(`.tok[popovertarget="${pop.id}"]`)) tok.classList.remove("on");
  if (event.newState !== "open") return;
  word?.classList.add("on");
  place(pop);
  if (narrow.matches) word?.scrollIntoView({ block: "nearest" });
}, true); // toggle does not bubble

const replace = () => {
  const pop = document.querySelector(".tok-pop:popover-open");
  if (pop) place(pop);
};
addEventListener("scroll", replace, { passive: true });
addEventListener("resize", replace);
