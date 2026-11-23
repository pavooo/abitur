function matheRendernIn(element) {
  if (window.renderMathInElement) {
    renderMathInElement(element, {
      delimiters: [{ left: "$", right: "$", display: false }],
      throwOnError: false,
    });
  }
}

document.addEventListener("DOMContentLoaded", function () {
  matheRendernIn(document.body);
});

document.body.addEventListener("htmx:afterSwap", function (event) {
  matheRendernIn(event.detail.target);
});
