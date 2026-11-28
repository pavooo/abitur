from accounts.models import Lehrkraft, Zugangscode
from archiv.models import Fach, Klausur, NachschreibZugriff
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.views.decorators.http import require_POST
from importer.models import Importprotokoll
from importer.paket import PaketFehler, entpacken
from importer.staging import neues_token, staging_aufraeumen, staging_verzeichnis
from importer.transaktion import importiere_paket
from importer.vorschau import berechne_vorschau

from .decorators import admin_erforderlich
from .forms import (
    AblehnenForm,
    FachErstellenForm,
    ImportUploadForm,
    LehrkraftFaecherForm,
    ZugangscodeErstellenForm,
)

STAGING_TOKEN_SESSION_KEY = "import_staging_token"
STAGING_PAKETNAME_SESSION_KEY = "import_staging_paketname"


def _klartext_code_nachricht(bezeichnung, klartext_code, *, hinweis_zusatz=""):
    return format_html(
        'Zugangscode für „{}“: <code class="rounded bg-slate-100 px-2 py-1 font-mono">{}</code> '
        '<button type="button" data-copy="{}" class="ml-2 underline">Kopieren</button> '
        "(wird nur jetzt angezeigt – bitte sofort notieren{}).",
        bezeichnung,
        klartext_code,
        klartext_code,
        hinweis_zusatz,
    )


@admin_erforderlich
def dashboard(request):
    kontext = {
        "anzahl_ausstehend": Lehrkraft.objects.filter(status=Lehrkraft.Status.AUSSTEHEND).count(),
        "anzahl_lehrkraefte": Lehrkraft.objects.count(),
        "anzahl_faecher": Fach.objects.count(),
        "anzahl_codes": Zugangscode.objects.count(),
        "anzahl_zur_freigabe": Klausur.objects.sichtbar_fuer(request)
        .filter(status=Klausur.Status.EINGEREICHT)
        .count(),
    }
    return render(request, "adminbereich/dashboard.html", kontext)


@admin_erforderlich
def lehrkraft_liste(request):
    lehrkraefte = Lehrkraft.objects.prefetch_related("faecher").all()
    return render(request, "adminbereich/lehrkraft_liste.html", {"lehrkraefte": lehrkraefte})


@admin_erforderlich
def lehrkraft_detail(request, pk):
    lehrkraft = get_object_or_404(Lehrkraft, pk=pk)

    if request.method == "POST":
        aktion = request.POST.get("aktion")
        if aktion == "freischalten":
            lehrkraft.status = Lehrkraft.Status.AKTIV
            lehrkraft.save(update_fields=["status"])
            messages.success(request, f"{lehrkraft.email} wurde freigeschaltet.")
        elif aktion == "sperren":
            lehrkraft.status = Lehrkraft.Status.GESPERRT
            lehrkraft.save(update_fields=["status"])
            messages.success(request, f"{lehrkraft.email} wurde gesperrt.")
        elif aktion == "admin_umschalten":
            lehrkraft.ist_admin = not lehrkraft.ist_admin
            lehrkraft.save(update_fields=["ist_admin"])
            messages.success(request, f"Admin-Recht für {lehrkraft.email} aktualisiert.")
        elif aktion == "faecher_speichern":
            faecher_form = LehrkraftFaecherForm(request.POST, instance=lehrkraft)
            if faecher_form.is_valid():
                faecher_form.save()
                messages.success(request, f"Fächer für {lehrkraft.email} aktualisiert.")
        return redirect("adminbereich:lehrkraft_detail", pk=lehrkraft.pk)

    faecher_form = LehrkraftFaecherForm(instance=lehrkraft)
    return render(
        request,
        "adminbereich/lehrkraft_detail.html",
        {"lehrkraft": lehrkraft, "faecher_form": faecher_form},
    )


@admin_erforderlich
def fach_liste(request):
    if request.method == "POST":
        form = FachErstellenForm(request.POST)
        if form.is_valid():
            fach = form.save()
            messages.success(request, f"Fach „{fach.name}“ wurde angelegt.")
            return redirect("adminbereich:fach_liste")
    else:
        form = FachErstellenForm()

    faecher = Fach.objects.all()
    return render(request, "adminbereich/fach_liste.html", {"faecher": faecher, "form": form})


@admin_erforderlich
def zugangscode_liste(request):
    if request.method == "POST":
        form = ZugangscodeErstellenForm(request.POST)
        if form.is_valid():
            zugangscode, klartext_code = Zugangscode.erstellen(
                fach=form.cleaned_data["fach"],
                bezeichnung=form.cleaned_data["bezeichnung"],
                ablaufdatum=form.cleaned_data["ablaufdatum"],
            )
            messages.success(
                request, _klartext_code_nachricht(zugangscode.bezeichnung, klartext_code)
            )
            return redirect("adminbereich:zugangscode_liste")
    else:
        form = ZugangscodeErstellenForm()

    zugangscodes = Zugangscode.objects.select_related("fach").all()
    return render(
        request,
        "adminbereich/zugangscode_liste.html",
        {"zugangscodes": zugangscodes, "form": form},
    )


@admin_erforderlich
@require_POST
def zugangscode_sperren_umschalten(request, pk):
    zugangscode = get_object_or_404(Zugangscode, pk=pk)
    zugangscode.gesperrt = not zugangscode.gesperrt
    zugangscode.save(update_fields=["gesperrt"])
    if zugangscode.gesperrt:
        messages.success(request, f"Zugangscode „{zugangscode.bezeichnung}“ wurde gesperrt.")
    else:
        messages.success(request, f"Zugangscode „{zugangscode.bezeichnung}“ wurde entsperrt.")
    return redirect("adminbereich:zugangscode_liste")


@admin_erforderlich
@require_POST
def zugangscode_neu_generieren(request, pk):
    zugangscode = get_object_or_404(Zugangscode, pk=pk)
    klartext_code = zugangscode.code_neu_generieren()
    messages.success(
        request,
        _klartext_code_nachricht(
            zugangscode.bezeichnung,
            klartext_code,
            hinweis_zusatz="; der alte Code ist ab sofort ungültig",
        ),
    )
    return redirect("adminbereich:zugangscode_liste")


@admin_erforderlich
def freigabe_liste(request):
    klausuren = (
        Klausur.objects.select_related("fach", "ersteller")
        .sichtbar_fuer(request)
        .filter(status=Klausur.Status.EINGEREICHT)
    )
    return render(request, "adminbereich/freigabe_liste.html", {"klausuren": klausuren})


@admin_erforderlich
def freigabe_detail(request, pk):
    # `sichtbar_fuer` beschränkt dies automatisch auf die Fächer des Admins (siehe
    # CLAUDE.md, Abschnitt Lehrkraft-Editor) – ein Admin kann so keine Klausur
    # fachfremder Lehrkräfte freigeben oder ablehnen.
    klausur = get_object_or_404(
        Klausur.objects.select_related("fach", "ersteller").sichtbar_fuer(request), pk=pk
    )
    ablehnen_form = AblehnenForm()

    if request.method == "POST":
        aktion = request.POST.get("aktion")
        if klausur.status != Klausur.Status.EINGEREICHT:
            messages.error(
                request, "Nur eingereichte Klausuren können freigegeben oder abgelehnt werden."
            )
            return redirect("adminbereich:freigabe_liste")

        if aktion == "freigeben":
            klausur.status = Klausur.Status.FREIGEGEBEN
            klausur.ablehnungskommentar = ""
            klausur.save(update_fields=["status", "ablehnungskommentar"])
            messages.success(request, f"„{klausur.titel}“ wurde freigegeben.")
            return redirect("adminbereich:freigabe_liste")
        elif aktion == "ablehnen":
            ablehnen_form = AblehnenForm(request.POST)
            if ablehnen_form.is_valid():
                klausur.status = Klausur.Status.ABGELEHNT
                klausur.ablehnungskommentar = ablehnen_form.cleaned_data["kommentar"]
                klausur.save(update_fields=["status", "ablehnungskommentar"])
                messages.success(request, f"„{klausur.titel}“ wurde abgelehnt.")
                return redirect("adminbereich:freigabe_liste")

    aufgaben = klausur.aufgaben.prefetch_related("teilaufgaben__themen").all()
    return render(
        request,
        "adminbereich/freigabe_detail.html",
        {"klausur": klausur, "aufgaben": aufgaben, "ablehnen_form": ablehnen_form},
    )


@admin_erforderlich
def import_hochladen(request):
    alter_token = request.session.get(STAGING_TOKEN_SESSION_KEY)
    if alter_token:
        staging_aufraeumen(alter_token)
        del request.session[STAGING_TOKEN_SESSION_KEY]

    if request.method == "POST":
        form = ImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            hochgeladene_datei = form.cleaned_data["paket"]
            token = neues_token()
            staging_pfad = staging_verzeichnis(token)
            staging_pfad.mkdir(parents=True, exist_ok=True)
            zip_pfad = staging_pfad / "paket.zip"
            with open(zip_pfad, "wb") as ziel:
                for chunk in hochgeladene_datei.chunks():
                    ziel.write(chunk)

            try:
                paket = entpacken(zip_pfad, staging_pfad / "inhalt")
            except PaketFehler as exc:
                staging_aufraeumen(token)
                form.add_error(None, str(exc))
            else:
                vorschau = berechne_vorschau(paket)
                request.session[STAGING_TOKEN_SESSION_KEY] = token
                request.session[STAGING_PAKETNAME_SESSION_KEY] = hochgeladene_datei.name
                return render(
                    request,
                    "adminbereich/import_vorschau.html",
                    {"vorschau": vorschau, "paketname": hochgeladene_datei.name, "token": token},
                )
    else:
        form = ImportUploadForm()

    return render(request, "adminbereich/import_hochladen.html", {"form": form})


@admin_erforderlich
@require_POST
def import_bestaetigen(request):
    token = request.session.get(STAGING_TOKEN_SESSION_KEY)
    paketname = request.session.get(STAGING_PAKETNAME_SESSION_KEY, "paket.zip")
    gesendeter_token = request.POST.get("token")

    if not token or token != gesendeter_token:
        messages.error(
            request, "Der Importvorgang ist abgelaufen. Bitte das Paket erneut hochladen."
        )
        return redirect("adminbereich:import_hochladen")

    staging_pfad = staging_verzeichnis(token)
    try:
        paket = entpacken(staging_pfad / "paket.zip", staging_pfad / "inhalt")
        vorschau = berechne_vorschau(paket)
        if vorschau.hat_fehler:
            messages.error(request, "Das Paket enthält Fehler und wurde nicht importiert.")
            return redirect("adminbereich:import_hochladen")

        protokoll = importiere_paket(paket, lehrkraft=request.user, paketname=paketname)
    finally:
        staging_aufraeumen(token)
        request.session.pop(STAGING_TOKEN_SESSION_KEY, None)
        request.session.pop(STAGING_PAKETNAME_SESSION_KEY, None)

    if protokoll.ergebnis == Importprotokoll.Ergebnis.ERFOLGREICH:
        messages.success(
            request,
            f"Import erfolgreich: {protokoll.anzahl_neu} neu, "
            f"{protokoll.anzahl_aktualisiert} aktualisiert.",
        )
    else:
        messages.error(request, f"Import fehlgeschlagen: {protokoll.fehlermeldung}")
    return redirect("adminbereich:import_protokoll_liste")


@admin_erforderlich
def import_protokoll_liste(request):
    protokolle = Importprotokoll.objects.select_related("lehrkraft").all()
    return render(request, "adminbereich/import_protokoll_liste.html", {"protokolle": protokolle})


@admin_erforderlich
def nachschreib_protokoll_liste(request):
    zugriffe = NachschreibZugriff.objects.select_related(
        "lehrkraft", "klausur", "klausur__fach"
    ).all()
    return render(request, "adminbereich/nachschreib_protokoll_liste.html", {"zugriffe": zugriffe})
