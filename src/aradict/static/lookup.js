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
