document.addEventListener("click", function (event) {
  var knopf = event.target.closest("[data-copy]");
  if (!knopf) return;
  navigator.clipboard.writeText(knopf.dataset.copy).then(function () {
    var original = knopf.textContent;
    knopf.textContent = "Kopiert!";
    setTimeout(function () {
      knopf.textContent = original;
    }, 1500);
  });
});
