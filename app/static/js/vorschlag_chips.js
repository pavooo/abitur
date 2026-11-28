// Macht Vorschlags-Chips (Anforderungsbereich, Themen) klickbar: ein Klick setzt bzw.
// toggelt das zugehörige Formularfeld im selben <form>. Übernimmt nie selbstständig
// etwas – die Lehrkraft klickt jeden Vorschlag bewusst an (CLAUDE.md, Abschnitt
// Regelbasierte Vorschläge: "nie ungefragt übernommen").
document.addEventListener("click", (ev) => {
  const setztChip = ev.target.closest("[data-setzt-feld]");
  if (setztChip) {
    const form = setztChip.closest("form");
    const input = form?.querySelector(
      `[name="${setztChip.dataset.setztFeld}"][value="${setztChip.dataset.setztWert}"]`
    );
    if (input) {
      input.checked = true;
    }
    return;
  }

  const toggeltChip = ev.target.closest("[data-toggelt-feld]");
  if (toggeltChip) {
    const form = toggeltChip.closest("form");
    const input = form?.querySelector(
      `[name="${toggeltChip.dataset.toggeltFeld}"][value="${toggeltChip.dataset.toggeltWert}"]`
    );
    if (input) {
      input.checked = !input.checked;
    }
  }
});
