// Bereichsmarkierung im Lehrkraft-Editor (CLAUDE.md, Abschnitt Lehrkraft-Editor):
// zeigt das Klausur-PDF seitenweise per PDF.js an und erlaubt, Rechtecke für die
// aktuell ausgewählte Aufgabe zu ziehen, zu verschieben, in der Größe zu ändern und
// zu löschen. Bewusst Vanilla JS, kein Build-Framework (siehe CLAUDE.md).

function csrfToken() {
  return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

async function postForm(url, daten) {
  const body = new URLSearchParams(daten);
  const antwort = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "X-CSRFToken": csrfToken(),
    },
    body,
  });
  if (!antwort.ok) {
    throw new Error(`Anfrage fehlgeschlagen (${antwort.status})`);
  }
  return antwort.json();
}

function clamp(wert) {
  return Math.min(1, Math.max(0, wert));
}

class Bereichsmarkierung {
  constructor(wurzel) {
    this.wurzel = wurzel;
    this.pdfUrl = wurzel.dataset.pdfUrl;
    this.erstellenUrl = wurzel.dataset.bereichErstellenUrl;
    this.aktualisierenUrlVorlage = wurzel.dataset.bereichAktualisierenUrlVorlage;
    this.loeschenUrlVorlage = wurzel.dataset.bereichLoeschenUrlVorlage;
    this.pdfjsUrl = wurzel.dataset.pdfjsUrl;
    this.pdfjsWorkerUrl = wurzel.dataset.pdfjsWorkerUrl;
    this.teilaufgabenPanelUrl = wurzel.dataset.teilaufgabenPanelUrl || null;
    this.seitenContainer = wurzel.querySelector("#pdf-seiten");
    this.bereiche = JSON.parse(document.getElementById("bereiche-daten").textContent);
    // Format "aufgabe:<id>" oder "teilaufgabe:<id>" – welches Formularfeld beim
    // Anlegen eines Bereichs an den Server geschickt wird, hängt davon ab (Schritt 2
    // markiert Aufgaben, Schritt 3 Teilaufgaben, siehe `editor/views.py`).
    this.aktivesZiel = null;

    // Event-Delegation statt direkter Listener: das Aufgaben-/Teilaufgaben-Panel wird
    // per HTMX ausgetauscht, ein auf `document` registrierter Listener bleibt dabei
    // unabhängig vom DOM-Austausch gültig.
    document.addEventListener("change", (ev) => {
      if (ev.target.matches('input[name="aktives-ziel"]')) {
        this.aktivesZiel = ev.target.value;
      }
    });

    this._laden();
  }

  _zielFeld() {
    const [feld, id] = this.aktivesZiel.split(":");
    return { feld, id };
  }

  async _nachBereichsAenderung(antwort) {
    if (antwort.teilaufgabe && this.teilaufgabenPanelUrl) {
      const panelAntwort = await fetch(this.teilaufgabenPanelUrl);
      const panel = document.getElementById("teilaufgaben-panel");
      if (panel && panelAntwort.ok) {
        panel.outerHTML = await panelAntwort.text();
        // `outerHTML` ersetzt den Knoten per roher HTML-Textzuweisung – HTMX bekommt
        // davon nichts mit und würde die neuen hx-post-Formulare sonst nie verkabeln
        // (sie würden beim Absenden auf normales GET zurückfallen). `htmx.process`
        // verkabelt den frischen Teilbaum explizit nach.
        const neuesPanel = document.getElementById("teilaufgaben-panel");
        if (neuesPanel && window.htmx) {
          window.htmx.process(neuesPanel);
        }
      }
    }
  }

  async _laden() {
    // Dynamischer Import statt eines statischen `import`-Statements mit festem Pfad:
    // nur so landet die von Django/WhiteNoise ggf. gehashte static-URL (`{% static %}`)
    // im geladenen Modulpfad, nicht ein hartkodierter `/static/...`-Pfad.
    const pdfjsLib = await import(this.pdfjsUrl);
    pdfjsLib.GlobalWorkerOptions.workerSrc = this.pdfjsWorkerUrl;

    const dokument = await pdfjsLib.getDocument({ url: this.pdfUrl }).promise;
    for (let nummer = 1; nummer <= dokument.numPages; nummer++) {
      const seite = await dokument.getPage(nummer);
      await this._seiteRendern(seite, nummer);
    }
  }

  async _seiteRendern(seite, nummer) {
    const viewport = seite.getViewport({ scale: 1.5 });

    const wrapper = document.createElement("div");
    wrapper.className = "relative mb-4 border border-slate-200";
    wrapper.style.width = `${viewport.width}px`;
    wrapper.style.height = `${viewport.height}px`;

    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    wrapper.appendChild(canvas);

    const overlay = document.createElement("div");
    overlay.className = "absolute inset-0";
    wrapper.appendChild(overlay);

    this.seitenContainer.appendChild(wrapper);

    await seite.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;

    this._overlayInteraktivMachen(overlay, nummer);
    this.bereiche
      .filter((bereich) => bereich.seite === nummer)
      .forEach((bereich) => this._rechteckZeichnen(overlay, bereich));
  }

  _styleAusKoordinaten(element, bereich) {
    element.style.left = `${bereich.x0 * 100}%`;
    element.style.top = `${bereich.y0 * 100}%`;
    element.style.width = `${(bereich.x1 - bereich.x0) * 100}%`;
    element.style.height = `${(bereich.y1 - bereich.y0) * 100}%`;
  }

  _rechteckZeichnen(overlay, bereich) {
    const element = document.createElement("div");
    element.className = "group absolute border-2 border-indigo-600 bg-indigo-600/10";
    this._styleAusKoordinaten(element, bereich);

    const loeschenButton = document.createElement("button");
    loeschenButton.type = "button";
    loeschenButton.textContent = "×";
    loeschenButton.title = "Bereich löschen";
    loeschenButton.className =
      "absolute -right-2 -top-2 hidden h-5 w-5 rounded-full bg-red-600 text-xs " +
      "leading-5 text-white group-hover:block";
    loeschenButton.addEventListener("mousedown", (ev) => ev.stopPropagation());
    loeschenButton.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const antwort = await postForm(
        this.loeschenUrlVorlage.replace(/\/0\/loeschen\/$/, `/${bereich.id}/loeschen/`),
        {}
      );
      element.remove();
      this.bereiche = this.bereiche.filter((eintrag) => eintrag.id !== bereich.id);
      await this._nachBereichsAenderung(antwort);
    });
    element.appendChild(loeschenButton);

    const griff = document.createElement("div");
    griff.className = "absolute -bottom-1 -right-1 h-3 w-3 cursor-nwse-resize bg-indigo-600";
    element.appendChild(griff);

    this._verschiebbarMachen(element, overlay, bereich);
    this._groessenveraenderbarMachen(griff, overlay, bereich, element);

    overlay.appendChild(element);
  }

  _aktualisierenUrlFuer(bereich) {
    return this.aktualisierenUrlVorlage.replace(/\/0\/$/, `/${bereich.id}/`);
  }

  async _aufServerAktualisieren(bereich) {
    const antwort = await postForm(this._aktualisierenUrlFuer(bereich), {
      x0: bereich.x0,
      y0: bereich.y0,
      x1: bereich.x1,
      y1: bereich.y1,
    });
    await this._nachBereichsAenderung(antwort);
  }

  _verschiebbarMachen(element, overlay, bereich) {
    element.addEventListener("mousedown", (ev) => {
      if (ev.target !== element) {
        return; // Löschen-Button und Resize-Griff haben eigene Handler.
      }
      ev.stopPropagation();
      ev.preventDefault();
      const rahmen = overlay.getBoundingClientRect();
      const start = { x0: bereich.x0, y0: bereich.y0, x1: bereich.x1, y1: bereich.y1 };
      const startX = ev.clientX;
      const startY = ev.clientY;

      const bewegen = (moveEv) => {
        const dx = (moveEv.clientX - startX) / rahmen.width;
        const dy = (moveEv.clientY - startY) / rahmen.height;
        const breite = start.x1 - start.x0;
        const hoehe = start.y1 - start.y0;
        bereich.x0 = clamp(start.x0 + dx);
        bereich.x1 = clamp(bereich.x0 + breite);
        bereich.y0 = clamp(start.y0 + dy);
        bereich.y1 = clamp(bereich.y0 + hoehe);
        this._styleAusKoordinaten(element, bereich);
      };
      const loslassen = async () => {
        document.removeEventListener("mousemove", bewegen);
        document.removeEventListener("mouseup", loslassen);
        await this._aufServerAktualisieren(bereich);
      };
      document.addEventListener("mousemove", bewegen);
      document.addEventListener("mouseup", loslassen);
    });
  }

  _groessenveraenderbarMachen(griff, overlay, bereich, element) {
    griff.addEventListener("mousedown", (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
      const rahmen = overlay.getBoundingClientRect();

      const bewegen = (moveEv) => {
        bereich.x1 = clamp((moveEv.clientX - rahmen.left) / rahmen.width);
        bereich.y1 = clamp((moveEv.clientY - rahmen.top) / rahmen.height);
        this._styleAusKoordinaten(element, bereich);
      };
      const loslassen = async () => {
        document.removeEventListener("mousemove", bewegen);
        document.removeEventListener("mouseup", loslassen);
        await this._aufServerAktualisieren(bereich);
      };
      document.addEventListener("mousemove", bewegen);
      document.addEventListener("mouseup", loslassen);
    });
  }

  _overlayInteraktivMachen(overlay, seite) {
    overlay.addEventListener("mousedown", (ev) => {
      if (ev.target !== overlay) {
        return; // Klick auf ein bestehendes Rechteck, nicht auf den leeren Hintergrund.
      }
      if (!this.aktivesZiel) {
        window.alert("Bitte zuerst links eine Aufgabe bzw. Teilaufgabe auswählen.");
        return;
      }

      const rahmen = overlay.getBoundingClientRect();
      const startX = clamp((ev.clientX - rahmen.left) / rahmen.width);
      const startY = clamp((ev.clientY - rahmen.top) / rahmen.height);

      const vorschau = document.createElement("div");
      vorschau.className = "absolute border-2 border-dashed border-indigo-600";
      overlay.appendChild(vorschau);

      const aktuellesRechteck = (x, y) => ({
        x0: Math.min(startX, x),
        x1: Math.max(startX, x),
        y0: Math.min(startY, y),
        y1: Math.max(startY, y),
      });

      const bewegen = (moveEv) => {
        const x = clamp((moveEv.clientX - rahmen.left) / rahmen.width);
        const y = clamp((moveEv.clientY - rahmen.top) / rahmen.height);
        this._styleAusKoordinaten(vorschau, aktuellesRechteck(x, y));
      };

      const loslassen = async (upEv) => {
        document.removeEventListener("mousemove", bewegen);
        document.removeEventListener("mouseup", loslassen);
        vorschau.remove();

        const x = clamp((upEv.clientX - rahmen.left) / rahmen.width);
        const y = clamp((upEv.clientY - rahmen.top) / rahmen.height);
        const { x0, x1, y0, y1 } = aktuellesRechteck(x, y);
        if (x1 - x0 < 0.01 || y1 - y0 < 0.01) {
          return; // Zu klein, vermutlich nur ein Klick ohne Ziehen.
        }

        const { feld, id } = this._zielFeld();
        const formDaten = { seite, x0, y0, x1, y1 };
        formDaten[feld] = id;
        const neuerBereich = await postForm(this.erstellenUrl, formDaten);
        this.bereiche.push(neuerBereich);
        this._rechteckZeichnen(overlay, neuerBereich);
        await this._nachBereichsAenderung(neuerBereich);
      };
      document.addEventListener("mousemove", bewegen);
      document.addEventListener("mouseup", loslassen);
    });
  }
}

document.querySelectorAll("[data-bereichsmarkierung]").forEach((wurzel) => {
  new Bereichsmarkierung(wurzel);
});
