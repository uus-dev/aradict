// Live lookup itself is htmx, declared on the search form. This adds the states htmx can't
// render from a response: loading, before the response arrives, and failure, when there is
// no usable response. The input is never touched, so Retry looks up the same word again.
const form = document.getElementById("search");
const query = form.elements.q;
const clear = form.querySelector(".clear");
const status = document.getElementById("status");
const results = document.getElementById("results");
const failure = document.getElementById("failure");

form.addEventListener("htmx:beforeRequest", () => {
  status.textContent = "Looking up…";
});

const fail = () => {
  results.replaceChildren(failure.content.cloneNode(true));
  status.textContent = failure.dataset.status;
  document.getElementById("arabizi").hidden = true; // found each time: every live lookup replaces this element
};
form.addEventListener("htmx:responseError", fail); // the server answered with an error
form.addEventListener("htmx:sendError", fail); // the server couldn't be reached

// Clear is a link to "/" without JavaScript. Here it empties the field in place and looks up
// the blank query, which shows the empty start and pushes "/".
const showClear = () => {
  clear.hidden = !query.value;
};
query.addEventListener("input", showClear);
clear.addEventListener("click", (event) => {
  event.preventDefault();
  query.value = "";
  showClear();
  query.focus();
  form.requestSubmit();
});

// The direction switch. Switching empties the field, sets its language, and looks up at once
// rather than after the typing delay: the request supersedes any lookup from the other
// direction still on its way, and the blank query shows the direction's start and pushes its URL.
// Without JavaScript the switch applies to the next lookup.
const english = form.elements.lang;
english.addEventListener("input", (event) => {
  event.stopPropagation(); // not the form's delayed live lookup
  Object.assign(query, english.checked ? { lang: "en", dir: "ltr" } : { lang: "ar", dir: "auto" });
  form.querySelector(`label[for="${query.id}"]`).textContent = english.checked ? "English word" : "Arabic word";
  query.value = "";
  showClear();
  query.focus();
  form.requestSubmit();
});
// history.js restores a remembered direction after this runs, without an event. On the home
// page that can be English, which is a page of its own: load it in place of this one.
addEventListener("DOMContentLoaded", () => {
  if (english.checked && query.lang !== "en") {
    const options = new URLSearchParams(new FormData(form));
    options.delete("q");
    location.replace(`/?${options}`);
  }
});
