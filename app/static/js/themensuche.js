// Client-seitiges Suchfeld über der Themenbaum-Auswahl (CLAUDE.md, Abschnitt
// Regelbasierte Vorschläge: "manuelle Themenauswahl: Baumansicht + Suchfeld"). Ein
// Knoten bleibt sichtbar, wenn er selbst zum Suchbegriff passt oder mindestens ein
// Kind-Knoten passt (daher Verarbeitung in umgekehrter Dokumentreihenfolge: Blätter
// zuerst, damit beim Erreichen eines Eltern-Knotens dessen Kinder schon bewertet sind).
document.addEventListener("input", (ev) => {
  const feld = ev.target.closest("[data-themensuche]");
  if (!feld) {
    return;
  }
  const baum = document.getElementById(feld.dataset.themensuche);
  if (!baum) {
    return;
  }
  const begriff = feld.value.trim().toLowerCase();
  const knoten = Array.from(baum.querySelectorAll("li[data-suchtext]")).reverse();

  knoten.forEach((li) => {
    const eigenerTreffer = !begriff || li.dataset.suchtext.includes(begriff);
    const kindTreffer = Array.from(li.querySelectorAll("li")).some(
      (kind) => kind.style.display !== "none"
    );
    li.style.display = eigenerTreffer || kindTreffer ? "" : "none";
  });
});
