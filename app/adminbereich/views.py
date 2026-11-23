from accounts.models import Lehrkraft, Zugangscode
from archiv.models import Fach
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import admin_erforderlich
from .forms import FachErstellenForm, LehrkraftFaecherForm, ZugangscodeErstellenForm


@admin_erforderlich
def dashboard(request):
    kontext = {
        "anzahl_ausstehend": Lehrkraft.objects.filter(status=Lehrkraft.Status.AUSSTEHEND).count(),
        "anzahl_lehrkraefte": Lehrkraft.objects.count(),
        "anzahl_faecher": Fach.objects.count(),
        "anzahl_codes": Zugangscode.objects.count(),
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
                request,
                f"Zugangscode erstellt: {klartext_code} "
                "(wird nur jetzt angezeigt – bitte sofort notieren).",
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
