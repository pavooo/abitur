import json
from pathlib import Path
from uuid import uuid4

from archiv.models import Aufgabe, Bereich, Klausur, Teilaufgabe, Thema
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import json_script
from django.views.decorators.http import require_POST

from . import option_c as option_c_modul
from . import pdf_text, vollstaendigkeit, vorschlaege
from .forms import (
    AufgabeForm,
    MetadatenForm,
    PdfUploadForm,
    TeilaufgabeDetailForm,
    TeilaufgabeErstellenForm,
)

_BEARBEITBARE_STATUS = (Klausur.Status.ENTWURF, Klausur.Status.ABGELEHNT)


def _hole_bearbeitbare_klausur(request, pk):
    """404 statt 403, wenn die Klausur nicht existiert, nicht der anfragenden Lehrkraft
    gehört oder nicht mehr in Bearbeitung ist: freigegebene Klausuren dürfen nur noch
    Admins bearbeiten, eingereichte stehen bis zur Admin-Entscheidung fest (CLAUDE.md,
    Abschnitt Lehrkraft-Editor). Standard ist verweigern."""
    return get_object_or_404(
        Klausur.objects.filter(ersteller=request.user, status__in=_BEARBEITBARE_STATUS),
        pk=pk,
    )


def _bearbeiten_url_name(klausur) -> str | None:
    if klausur.status not in (Klausur.Status.ENTWURF, Klausur.Status.ABGELEHNT):
        return None
    return "editor:schritt2" if klausur.pdf else "editor:schritt1"


def _hole_bereich(klausur, bereich_pk):
    """Erfasst sowohl Aufgabe- als auch Teilaufgabe-Bereiche."""
    return get_object_or_404(
        Bereich.objects.filter(
            models.Q(aufgabe__klausur=klausur) | models.Q(teilaufgabe__aufgabe__klausur=klausur)
        ),
        pk=bereich_pk,
    )


def _hole_bereich_ziel(klausur, request):
    """Liest aus dem POST-Body, ob der neue/geänderte Bereich zu einer Aufgabe oder
    einer Teilaufgabe gehört (genau eines von beidem, siehe `Bereich`-Constraint)."""
    aufgabe_id = request.POST.get("aufgabe")
    teilaufgabe_id = request.POST.get("teilaufgabe")
    if bool(aufgabe_id) == bool(teilaufgabe_id):
        raise Http404("Es muss genau ein Ziel (Aufgabe oder Teilaufgabe) angegeben werden.")
    if aufgabe_id:
        return get_object_or_404(Aufgabe, pk=aufgabe_id, klausur=klausur), None
    teilaufgabe = get_object_or_404(Teilaufgabe, pk=teilaufgabe_id, aufgabe__klausur=klausur)
    return None, teilaufgabe


def _seitenbereich_aktualisieren(aufgabe) -> None:
    """Hält `Aufgabe.seite_von`/`seite_bis` synchron zu ihren Bereichen (siehe
    CLAUDE.md, Abschnitt Lehrkraft-Editor): im Editor nicht manuell erfasst, sondern
    aus dem Min/Max der markierten Seiten abgeleitet. Ohne Bereiche wieder leer."""
    grenzen = aufgabe.bereiche.aggregate(von=models.Min("seite"), bis=models.Max("seite"))
    aufgabe.seite_von = grenzen["von"]
    aufgabe.seite_bis = grenzen["bis"]
    aufgabe.save(update_fields=["seite_von", "seite_bis"])


def _teilaufgabe_vorschlaege_aktualisieren(teilaufgabe, klausur) -> dict:
    """Extrahiert Text aus den Bereichen der Teilaufgabe (inkl. OCR-Fallback bei
    Scans), speichert Text und Seite und berechnet die regelbasierten Vorschläge für
    Anforderungsbereich und Themen (CLAUDE.md, Abschnitt Regelbasierte Vorschläge).
    Wird nach jeder Bereichsänderung einer Teilaufgabe aufgerufen."""
    bereiche = list(teilaufgabe.bereiche.all())
    if bereiche:
        with pdf_text.dokument_mit_textebene_oeffnen(Path(klausur.pdf.path)) as dokument:
            text = pdf_text.text_fuer_bereiche(dokument, bereiche)
        seite = min(bereich.seite for bereich in bereiche)
    else:
        text, seite = "", None

    teilaufgabe.text = text
    teilaufgabe.seite = seite
    teilaufgabe.save(update_fields=["text", "seite"])

    operatoren = vorschlaege.lade_operatoren(klausur.fach.name)
    anforderungsbereich_vorschlag = vorschlaege.schlage_anforderungsbereich_vor(text, operatoren)
    themen_vorschlaege = vorschlaege.schlage_themen_vor(
        text, Thema.objects.filter(fach=klausur.fach)
    )

    return {
        "teilaufgabe": teilaufgabe.pk,
        "text": text,
        "seite": seite,
        "anforderungsbereich_vorschlag": anforderungsbereich_vorschlag,
        "themen_vorschlaege": themen_vorschlaege,
    }


def _bereich_als_dict(bereich) -> dict:
    return {
        "id": bereich.pk,
        "aufgabe": bereich.aufgabe_id,
        "teilaufgabe": bereich.teilaufgabe_id,
        "seite": bereich.seite,
        "x0": bereich.x0,
        "y0": bereich.y0,
        "x1": bereich.x1,
        "y1": bereich.y1,
    }


@login_required
def meine_klausuren(request):
    """Zeigt einer Lehrkraft ihre eigenen Klausuren mit Status und ggf.
    Ablehnungskommentar (CLAUDE.md, Abschnitt Lehrkraft-Editor). Filtert bewusst direkt
    über `ersteller`, nicht über `sichtbar_fuer`: Letzteres regelt, was generell sichtbar
    ist, hier geht es nur um die eigenen Klausuren der anfragenden Lehrkraft – das kann
    nie Inhalte anderer Lehrkräfte offenlegen."""
    klausuren = (
        Klausur.objects.filter(ersteller=request.user)
        .select_related("fach")
        .order_by("-erstellt_am")
    )
    eintraege = [
        {"klausur": klausur, "bearbeiten_url_name": _bearbeiten_url_name(klausur)}
        for klausur in klausuren
    ]
    return render(request, "editor/meine_klausuren.html", {"eintraege": eintraege})


@login_required
def schritt1(request, pk=None):
    klausur = _hole_bearbeitbare_klausur(request, pk) if pk is not None else None

    if request.method == "POST":
        form = MetadatenForm(request.POST, instance=klausur, lehrkraft=request.user)
        if form.is_valid():
            klausur = form.save(commit=False)
            if klausur.pk is None:
                klausur.status = Klausur.Status.ENTWURF
                klausur.ersteller = request.user
            klausur.save()
            return redirect("editor:schritt2", pk=klausur.pk)
    else:
        form = MetadatenForm(instance=klausur, lehrkraft=request.user)

    return render(request, "editor/schritt1_metadaten.html", {"form": form, "klausur": klausur})


@login_required
def schritt2(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)

    if request.method == "POST":
        form = PdfUploadForm(request.POST, request.FILES, hat_bereits_pdf=bool(klausur.pdf))
        if form.is_valid():
            if form.cleaned_data["pdf"] is not None:
                klausur.pdf.save(f"{uuid4().hex}.pdf", form.cleaned_data["pdf"], save=False)
            if form.cleaned_data["erwartungshorizont_pdf"] is not None:
                klausur.erwartungshorizont_pdf.save(
                    f"{uuid4().hex}-ewh.pdf",
                    form.cleaned_data["erwartungshorizont_pdf"],
                    save=False,
                )
            klausur.save()
            # Zurück auf Schritt 2 (nicht automatisch weiter zu Schritt 3): die Aufgaben-
            # und Bereichsmarkierung findet hier auf derselben Seite statt, sobald das
            # PDF hochgeladen ist.
            return redirect("editor:schritt2", pk=klausur.pk)
    else:
        form = PdfUploadForm(hat_bereits_pdf=bool(klausur.pdf))

    kontext = {"form": form, "klausur": klausur}
    if klausur.pdf:
        alle_bereiche = Bereich.objects.filter(aufgabe__klausur=klausur)
        kontext["aufgaben"] = klausur.aufgaben.prefetch_related("bereiche").order_by("nummer")
        kontext["aufgabe_form"] = AufgabeForm(klausur=klausur)
        kontext["bereiche_script"] = json_script(
            [_bereich_als_dict(b) for b in alle_bereiche], "bereiche-daten"
        )
    return render(request, "editor/schritt2_pdf.html", kontext)


@login_required
@require_POST
def aufgabe_erstellen(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    form = AufgabeForm(request.POST, klausur=klausur)
    if form.is_valid():
        form.save()
        form = AufgabeForm(klausur=klausur)
    return render(
        request,
        "editor/_aufgaben_bereich_panel.html",
        {
            "klausur": klausur,
            "aufgaben": klausur.aufgaben.prefetch_related("bereiche").order_by("nummer"),
            "aufgabe_form": form,
        },
    )


@login_required
@require_POST
def aufgabe_loeschen(request, pk, aufgabe_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    aufgabe = get_object_or_404(Aufgabe, pk=aufgabe_pk, klausur=klausur)
    aufgabe.delete()
    return render(
        request,
        "editor/_aufgaben_bereich_panel.html",
        {
            "klausur": klausur,
            "aufgaben": klausur.aufgaben.prefetch_related("bereiche").order_by("nummer"),
            "aufgabe_form": AufgabeForm(klausur=klausur),
        },
    )


@login_required
@require_POST
def bereich_erstellen(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    aufgabe, teilaufgabe = _hole_bereich_ziel(klausur, request)
    try:
        seite = int(request.POST["seite"])
        koordinaten = {feld: float(request.POST[feld]) for feld in ("x0", "y0", "x1", "y1")}
    except (KeyError, ValueError):
        return JsonResponse({"fehler": "Ungültige Koordinaten."}, status=400)

    bereich = Bereich.objects.create(
        aufgabe=aufgabe, teilaufgabe=teilaufgabe, seite=seite, **koordinaten
    )
    antwort = _bereich_als_dict(bereich)
    if aufgabe is not None:
        _seitenbereich_aktualisieren(aufgabe)
    else:
        antwort.update(_teilaufgabe_vorschlaege_aktualisieren(teilaufgabe, klausur))
    return JsonResponse(antwort)


@login_required
@require_POST
def bereich_aktualisieren(request, pk, bereich_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    bereich = _hole_bereich(klausur, bereich_pk)
    try:
        koordinaten = {feld: float(request.POST[feld]) for feld in ("x0", "y0", "x1", "y1")}
    except (KeyError, ValueError):
        return JsonResponse({"fehler": "Ungültige Koordinaten."}, status=400)

    for feld, wert in koordinaten.items():
        setattr(bereich, feld, wert)
    bereich.save()

    antwort = _bereich_als_dict(bereich)
    if bereich.teilaufgabe_id is not None:
        antwort.update(_teilaufgabe_vorschlaege_aktualisieren(bereich.teilaufgabe, klausur))
    elif bereich.aufgabe_id is not None:
        _seitenbereich_aktualisieren(bereich.aufgabe)
    return JsonResponse(antwort)


@login_required
@require_POST
def bereich_loeschen(request, pk, bereich_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    bereich = _hole_bereich(klausur, bereich_pk)
    aufgabe, teilaufgabe = bereich.aufgabe, bereich.teilaufgabe
    bereich.delete()

    antwort = {"geloescht": True}
    if aufgabe is not None:
        _seitenbereich_aktualisieren(aufgabe)
    elif teilaufgabe is not None:
        antwort.update(_teilaufgabe_vorschlaege_aktualisieren(teilaufgabe, klausur))
    return JsonResponse(antwort)


def _themenbaum(themen):
    """Baut aus der flachen Themenliste eines Fachs einen Baum (siehe
    `archiv.views._themenbaum`, hier dupliziert, da `editor` nicht von privaten
    Hilfsfunktionen aus `archiv` abhängen soll). Hängt zusätzlich `.suchtext` an
    (Name + Synonyme, normalisiert) für das clientseitige Suchfeld."""
    je_id = {thema.id: thema for thema in themen}
    for thema in themen:
        thema.baum_kinder = []
        thema.suchtext = vorschlaege.normalisiere(" ".join([thema.name, *thema.synonyme]))
    wurzeln = []
    for thema in themen:
        if thema.eltern_id and thema.eltern_id in je_id:
            je_id[thema.eltern_id].baum_kinder.append(thema)
        else:
            wurzeln.append(thema)
    return wurzeln


def _teilaufgaben_panel_kontext(klausur) -> dict:
    aufgaben = klausur.aufgaben.prefetch_related(
        "teilaufgaben__bereiche", "teilaufgaben__themen"
    ).order_by("nummer")
    themen = list(Thema.objects.filter(fach=klausur.fach).order_by("kennung"))
    wurzelthemen = _themenbaum(themen)
    operatoren = vorschlaege.lade_operatoren(klausur.fach.name)

    teilaufgabe_erstellen_formulare = {
        aufgabe.pk: TeilaufgabeErstellenForm(aufgabe=aufgabe) for aufgabe in aufgaben
    }

    # Pro Teilaufgabe gebündelt (Formular, bereits ausgewählte Themen, Vorschläge),
    # damit das Template nur einen einzigen Dict-Zugriff pro Teilaufgabe braucht.
    teilaufgaben_daten = {}
    for aufgabe in aufgaben:
        for teilaufgabe in aufgabe.teilaufgaben.all():
            vorschlag = None
            if teilaufgabe.text:
                vorschlag = {
                    "anforderungsbereich": vorschlaege.schlage_anforderungsbereich_vor(
                        teilaufgabe.text, operatoren
                    ),
                    "themen": vorschlaege.schlage_themen_vor(teilaufgabe.text, themen),
                }
            teilaufgaben_daten[teilaufgabe.pk] = {
                "form": TeilaufgabeDetailForm(
                    instance=teilaufgabe,
                    fach=klausur.fach,
                    auto_id=f"id_teilaufgabe_{teilaufgabe.pk}_%s",
                ),
                "ausgewaehlte_ids": {thema.pk for thema in teilaufgabe.themen.all()},
                "vorschlag": vorschlag,
            }

    return {
        "klausur": klausur,
        "aufgaben": aufgaben,
        "wurzelthemen": wurzelthemen,
        "teilaufgabe_erstellen_formulare": teilaufgabe_erstellen_formulare,
        "teilaufgaben_daten": teilaufgaben_daten,
    }


def _teilaufgaben_panel_rendern(request, klausur):
    return render(request, "editor/_teilaufgaben_panel.html", _teilaufgaben_panel_kontext(klausur))


@login_required
def teilaufgaben_panel_fragment(request, pk):
    """GET-Variante des Panels, damit die Bereichsmarkierung (`bereichsmarkierung.js`)
    nach einer Bereichsänderung an einer Teilaufgabe – Text-/Vorschlags-Update – das
    Panel per HTMX neu anfordern kann, ohne die PDF-Ansicht neu zu rendern."""
    klausur = _hole_bearbeitbare_klausur(request, pk)
    return _teilaufgaben_panel_rendern(request, klausur)


@login_required
@require_POST
def teilaufgabe_erstellen(request, pk, aufgabe_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    aufgabe = get_object_or_404(Aufgabe, pk=aufgabe_pk, klausur=klausur)
    form = TeilaufgabeErstellenForm(request.POST, aufgabe=aufgabe)
    if form.is_valid():
        form.save()
    return _teilaufgaben_panel_rendern(request, klausur)


@login_required
@require_POST
def teilaufgabe_aktualisieren(request, pk, teilaufgabe_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    teilaufgabe = get_object_or_404(Teilaufgabe, pk=teilaufgabe_pk, aufgabe__klausur=klausur)
    form = TeilaufgabeDetailForm(request.POST, instance=teilaufgabe, fach=klausur.fach)
    if form.is_valid():
        form.save()
        messages.success(request, f"Teilaufgabe {teilaufgabe.bezeichnung} gespeichert.")
    return _teilaufgaben_panel_rendern(request, klausur)


@login_required
@require_POST
def teilaufgabe_loeschen(request, pk, teilaufgabe_pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    teilaufgabe = get_object_or_404(Teilaufgabe, pk=teilaufgabe_pk, aufgabe__klausur=klausur)
    teilaufgabe.delete()
    return _teilaufgaben_panel_rendern(request, klausur)


@login_required
def schritt3(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    kontext = _teilaufgaben_panel_kontext(klausur)

    if klausur.aufgaben.exists():
        alle_bereiche = Bereich.objects.filter(
            models.Q(aufgabe__klausur=klausur) | models.Q(teilaufgabe__aufgabe__klausur=klausur)
        )
        kontext["bereiche_script"] = json_script(
            [_bereich_als_dict(b) for b in alle_bereiche], "bereiche-daten"
        )
    return render(request, "editor/schritt3_teilaufgaben.html", kontext)


@login_required
def schritt4(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    pruefung = vollstaendigkeit.pruefe(klausur)

    if request.method == "POST":
        if not pruefung.ist_vollstaendig:
            messages.error(request, "Einreichen nicht möglich: Es gibt noch offene Pflichtangaben.")
        else:
            klausur.status = Klausur.Status.EINGEREICHT
            klausur.save(update_fields=["status"])
            messages.success(
                request, f"„{klausur.titel}“ wurde eingereicht und wartet auf die Freigabe."
            )
            return redirect("editor:meine_klausuren")

    return render(
        request,
        "editor/schritt4_pruefen.html",
        {"klausur": klausur, "aktueller_schritt": 4, "pruefung": pruefung},
    )


@login_required
def option_c(request, pk):
    klausur = _hole_bearbeitbare_klausur(request, pk)
    ergebnis = None
    json_text = ""

    if request.method == "POST":
        json_text = request.POST.get("json_text", "")
        bestaetigt = request.POST.get("konflikte_bestaetigt") == "1"
        ergebnis = option_c_modul.validiere(json_text, klausur=klausur)

        if ergebnis.gueltig and (not ergebnis.konflikte or bestaetigt):
            option_c_modul.uebernehmen(klausur, ergebnis.daten)
            messages.success(request, "Aufgaben und Teilaufgaben aus dem JSON übernommen.")
            return redirect("editor:schritt3", pk=klausur.pk)

    return render(
        request,
        "editor/option_c.html",
        {
            "klausur": klausur,
            "prompt": option_c_modul.erzeuge_prompt(klausur),
            "beispiel_json": json.dumps(option_c_modul.BEISPIEL_JSON, ensure_ascii=False, indent=2),
            "ergebnis": ergebnis,
            "json_text": json_text,
        },
    )


@login_required
def option_c_format(request):
    """Formatbeschreibung ist bewusst fachunabhängig und erfordert keine eigene
    Klausur – rein informativ (keine Klausurdaten werden ausgegeben), aber wie jede
    Seite im Editor nur für angemeldete Lehrkräfte (Standard ist verweigern)."""
    return render(
        request,
        "editor/option_c_format.html",
        {"beispiel_json": json.dumps(option_c_modul.BEISPIEL_JSON, ensure_ascii=False, indent=2)},
    )
