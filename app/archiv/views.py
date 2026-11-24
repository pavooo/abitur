from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .dateien import datei_ausliefern, protokolliere_falls_nachschreibklausur, vorschaubild_pfad
from .models import Aufgabe, Fach, Klausur, Teilaufgabe, Thema
from .sichtbarkeit import NACHSCHREIBMODUS_SESSION_KEY, Termin, sichtbarkeitskontext_fuer
from .suche import volltext_filtern

TREFFER_PRO_SEITE = 20
TREFFER_OBERGRENZE = 300


def _ist_lehrkraft(request) -> bool:
    return request.sus_zugangscode is None and request.user.is_authenticated


def _nach_klausur_gruppieren(teilaufgaben):
    gruppen = {}
    for teilaufgabe in teilaufgaben:
        klausur = teilaufgabe.aufgabe.klausur
        gruppen.setdefault(klausur, []).append(teilaufgabe)
    return [{"klausur": klausur, "teilaufgaben": liste} for klausur, liste in gruppen.items()]


def _themenbaum(themen):
    """Baut den Themenbaum in Python aus der flachen Liste (eltern-Zeiger). Das
    Baum-Attribut heißt bewusst `baum_kinder`, nicht `kinder` – Letzteres ist
    bereits der Name des echten `related_name` auf `Thema.eltern` und würde bei
    Zuweisung einen Fehler auslösen (reverse FK-Manager ist nicht beschreibbar)."""
    je_id = {thema.id: thema for thema in themen}
    for thema in themen:
        thema.baum_kinder = []
    wurzeln = []
    for thema in themen:
        if thema.eltern_id and thema.eltern_id in je_id:
            je_id[thema.eltern_id].baum_kinder.append(thema)
        else:
            wurzeln.append(thema)
    return wurzeln


def suche(request):
    kontext = sichtbarkeitskontext_fuer(request)
    ist_lehrkraft = _ist_lehrkraft(request)
    nachschreibmodus_aktiv = request.session.get(NACHSCHREIBMODUS_SESSION_KEY, False)
    g = request.GET

    queryset = (
        Teilaufgabe.objects.sichtbar_fuer(request)
        .select_related("aufgabe__klausur__fach")
        .prefetch_related("themen")
    )
    queryset = volltext_filtern(queryset, g.get("q", ""))

    if g.get("fach"):
        queryset = queryset.filter(aufgabe__klausur__fach_id=g["fach"])
    if g.get("jahr"):
        queryset = queryset.filter(aufgabe__klausur__jahr=g["jahr"])
    if g.get("kursart"):
        queryset = queryset.filter(aufgabe__klausur__kursart=g["kursart"])
    if g.get("thema"):
        queryset = queryset.in_thema(g["thema"])
    if g.get("anforderungsbereich"):
        queryset = queryset.filter(anforderungsbereich=g["anforderungsbereich"])

    nur_hilfsmittelfrei = g.get("nur_hilfsmittelfrei") == "1"
    nur_mit_hilfsmitteln = g.get("nur_mit_hilfsmitteln") == "1"
    if nur_hilfsmittelfrei:
        queryset = queryset.filter(aufgabe__pruefungsteil=Aufgabe.Pruefungsteil.HILFSMITTELFREI)
    elif nur_mit_hilfsmitteln:
        queryset = queryset.filter(aufgabe__pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN)

    # Hilfsmittel (CAS/TR) ist nur für Aufgaben mit Hilfsmitteln aussagekräftig –
    # bei "nur hilfsmittelfrei" wird der Filter ignoriert (sonst verschwänden
    # hilfsmittelfreie Treffer der TR-Variante, nur weil "CAS" gewählt ist,
    # obwohl Prüfungsteil A zwischen CAS/TR-Varianten identisch ist). Ohne
    # explizite Wahl ist "CAS" voreingestellt (Standardwert laut Anforderung).
    hilfsmittel_wert = g["hilfsmittel"] if "hilfsmittel" in g else Klausur.Hilfsmittel.CAS
    if hilfsmittel_wert and not nur_hilfsmittelfrei:
        queryset = queryset.filter(aufgabe__klausur__hilfsmittel=hilfsmittel_wert)

    # Termin-Filter nur für Lehrkräfte im aktivierten Nachschreibmodus (CLAUDE.md,
    # Abschnitt Suche) – sichtbar_fuer() würde SuS ohnehin nie Nachschreibtermine
    # liefern, dieser Filter engt nur innerhalb des ohnehin Sichtbaren weiter ein.
    if ist_lehrkraft and nachschreibmodus_aktiv and g.get("termin"):
        queryset = queryset.filter(aufgabe__klausur__termin=g["termin"])

    gruppen = _nach_klausur_gruppieren(queryset[:TREFFER_OBERGRENZE])
    paginator = Paginator(gruppen, TREFFER_PRO_SEITE)
    seite_obj = paginator.get_page(g.get("seite", 1))

    jahre = (
        Klausur.objects.sichtbar_fuer(request)
        .order_by("-jahr")
        .values_list("jahr", flat=True)
        .distinct()
    )

    kontext_daten = {
        "seite_obj": seite_obj,
        "g": g,
        "hilfsmittel_wert": hilfsmittel_wert,
        "ist_lehrkraft": ist_lehrkraft,
        "nachschreibmodus_aktiv": nachschreibmodus_aktiv,
        "faecher": Fach.objects.filter(id__in=kontext.fach_ids) if ist_lehrkraft else None,
        "jahre": jahre,
        "kursarten": Klausur.Kursart.choices,
        "anforderungsbereiche": Teilaufgabe.Anforderungsbereich.choices,
        "hilfsmittel_choices": Klausur.Hilfsmittel.choices,
        "termine": Termin.choices,
    }
    template = "archiv/_treffer_liste.html" if request.htmx else "archiv/suche.html"
    return render(request, template, kontext_daten)


def themenbrowser(request):
    kontext = sichtbarkeitskontext_fuer(request)
    themen = list(Thema.objects.filter(fach_id__in=kontext.fach_ids).order_by("kennung"))
    wurzelthemen = _themenbaum(themen)

    ausgewaehlte_kennung = request.GET.get("thema", "")
    seite_obj = None
    if ausgewaehlte_kennung:
        queryset = (
            Teilaufgabe.objects.sichtbar_fuer(request)
            .in_thema(ausgewaehlte_kennung)
            .select_related("aufgabe__klausur__fach")
            .prefetch_related("themen")
            .order_by("-aufgabe__klausur__jahr")
        )
        gruppen = _nach_klausur_gruppieren(queryset[:TREFFER_OBERGRENZE])
        paginator = Paginator(gruppen, TREFFER_PRO_SEITE)
        seite_obj = paginator.get_page(request.GET.get("seite", 1))

    kontext_daten = {
        "wurzelthemen": wurzelthemen,
        "ausgewaehlte_kennung": ausgewaehlte_kennung,
        "seite_obj": seite_obj,
        "g": request.GET,
    }
    template = "archiv/_treffer_liste.html" if request.htmx else "archiv/themenbrowser.html"
    return render(request, template, kontext_daten)


def klausur_detail(request, pk):
    klausur = get_object_or_404(
        Klausur.objects.select_related("fach").sichtbar_fuer(request), pk=pk
    )
    protokolliere_falls_nachschreibklausur(request, klausur)
    aufgaben = klausur.aufgaben.prefetch_related("teilaufgaben__themen").all()
    return render(
        request,
        "archiv/klausur_detail.html",
        {"klausur": klausur, "aufgaben": aufgaben, "ist_lehrkraft": _ist_lehrkraft(request)},
    )


def klausur_datei(request, pk, art):
    klausur = get_object_or_404(Klausur.objects.sichtbar_fuer(request), pk=pk)

    if art == "pdf":
        datei_feld = klausur.pdf
    elif art == "erwartungshorizont":
        if not _ist_lehrkraft(request) or not klausur.erwartungshorizont_pdf:
            raise Http404("Erwartungshorizont nicht verfügbar.")
        datei_feld = klausur.erwartungshorizont_pdf
    else:
        raise Http404("Unbekannte Dateiart.")

    protokolliere_falls_nachschreibklausur(request, klausur)
    pfad = Path(datei_feld.path)
    return datei_ausliefern(pfad, pfad.name, content_type="application/pdf")


def vorschaubild(request, pk, seite):
    klausur = get_object_or_404(Klausur.objects.sichtbar_fuer(request), pk=pk)
    protokolliere_falls_nachschreibklausur(request, klausur)
    pfad = vorschaubild_pfad(klausur, seite)
    return datei_ausliefern(pfad, pfad.name, content_type="image/png")


@login_required
@require_POST
def nachschreibmodus_umschalten(request):
    aktuell = request.session.get(NACHSCHREIBMODUS_SESSION_KEY, False)
    request.session[NACHSCHREIBMODUS_SESSION_KEY] = not aktuell

    ziel = request.POST.get("weiter_zu", "")
    if not url_has_allowed_host_and_scheme(
        ziel, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        ziel = reverse("archiv:suche")
    return redirect(ziel)
