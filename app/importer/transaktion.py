from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe, Thema
from django.core.files import File
from django.db import transaction

from .models import Importprotokoll
from .paket import EntpacktesPaket, KlausurEintrag
from .vorschaubilder import vorschaubilder_erzeugen


def importiere_paket(paket: EntpacktesPaket, *, lehrkraft, paketname: str) -> Importprotokoll:
    """Führt den eigentlichen Import durch. Geht davon aus, dass das Paket bereits
    über `vorschau.berechne_vorschau()` geprüft wurde und `hat_fehler` False ist –
    diese Funktion validiert nicht erneut fachlich.

    Das Importprotokoll wird in jedem Fall persistiert (auch bei Fehlschlag), die
    eigentlichen Datenänderungen laufen in einer einzigen Transaktion (alles oder
    nichts). Seitenvorschaubilder entstehen erst nach erfolgreichem Commit.
    """
    protokoll = Importprotokoll.objects.create(
        lehrkraft=lehrkraft,
        paketname=paketname,
        ergebnis=Importprotokoll.Ergebnis.FEHLGESCHLAGEN,
    )

    importierte_klausuren = []
    try:
        with transaction.atomic():
            anzahl_neu = 0
            anzahl_aktualisiert = 0

            if paket.taxonomie is not None:
                _taxonomie_importieren(paket.taxonomie)

            for eintrag in paket.klausuren:
                klausur, wurde_erstellt = _klausur_importieren(eintrag, protokoll)
                importierte_klausuren.append(klausur)
                if wurde_erstellt:
                    anzahl_neu += 1
                else:
                    anzahl_aktualisiert += 1
    except Exception as exc:
        protokoll.fehlermeldung = str(exc)
        protokoll.save(update_fields=["fehlermeldung"])
        return protokoll

    protokoll.ergebnis = Importprotokoll.Ergebnis.ERFOLGREICH
    protokoll.anzahl_neu = anzahl_neu
    protokoll.anzahl_aktualisiert = anzahl_aktualisiert
    protokoll.save(update_fields=["ergebnis", "anzahl_neu", "anzahl_aktualisiert"])

    warnungen = []
    for klausur in importierte_klausuren:
        try:
            vorschaubilder_erzeugen(klausur)
        except Exception as exc:
            # Vorschaubilder sind kein Grund, den Import als fehlgeschlagen zu werten.
            warnungen.append(f"{klausur}: Vorschaubilder konnten nicht erzeugt werden ({exc}).")
    if warnungen:
        protokoll.fehlermeldung = "\n".join(warnungen)
        protokoll.save(update_fields=["fehlermeldung"])

    return protokoll


def _taxonomie_importieren(taxonomie: dict) -> None:
    """Flache Themen-Liste, jedes Thema verweist per `eltern` auf die Kennung
    seines Elternthemas. Zweistufig: erst alle Knoten upserten, dann die
    `eltern`-Verweise auflösen – damit die Reihenfolge in der JSON-Liste keine
    Rolle spielt."""
    fach = Fach.objects.get(kuerzel=taxonomie["fach"])
    knoten_liste = taxonomie.get("themen", [])

    for knoten in knoten_liste:
        Thema.objects.update_or_create(
            fach=fach,
            kennung=knoten["kennung"],
            defaults={
                "name": knoten["name"],
                "synonyme": knoten.get("synonyme", []),
                "kursniveau": knoten.get("kursniveau", Thema.Kursniveau.ALLE),
            },
        )

    for knoten in knoten_liste:
        eltern_kennung = knoten.get("eltern")
        eltern = (
            Thema.objects.get(fach=fach, kennung=eltern_kennung)
            if eltern_kennung is not None
            else None
        )
        Thema.objects.filter(fach=fach, kennung=knoten["kennung"]).update(eltern=eltern)


def _klausur_importieren(eintrag: KlausurEintrag, protokoll: Importprotokoll):
    daten = eintrag.daten
    fach = Fach.objects.get(kuerzel=daten["fach"])

    klausur, wurde_erstellt = Klausur.objects.update_or_create(
        fach=fach,
        jahr=daten["jahr"],
        kursart=daten["kursart"],
        termin=daten["termin"],
        variante=daten.get("variante", ""),
        defaults={
            "titel": daten["titel"],
            "hilfsmittel": daten["hilfsmittel"],
            "importprotokoll": protokoll,
        },
    )

    with open(eintrag.pdf_pfad, "rb") as datei:
        klausur.pdf.save(f"{eintrag.id}.pdf", File(datei), save=False)
    if eintrag.ewh_pdf_pfad is not None:
        with open(eintrag.ewh_pdf_pfad, "rb") as datei:
            klausur.erwartungshorizont_pdf.save(f"{eintrag.id}-ewh.pdf", File(datei), save=False)
    klausur.save()

    # Bei Aktualisierung: Aufgaben (und kaskadierend Teilaufgaben) vollständig ersetzen,
    # statt sie zu duplizieren (siehe CLAUDE.md, Abschnitt Import-Regeln).
    klausur.aufgaben.all().delete()

    for aufgabe_daten in daten["aufgaben"]:
        seite_von, seite_bis = aufgabe_daten["seiten"]
        aufgabe = Aufgabe.objects.create(
            klausur=klausur,
            nummer=aufgabe_daten["nummer"],
            kontext=aufgabe_daten.get("kontext", ""),
            seite_von=seite_von,
            seite_bis=seite_bis,
            pruefungsteil=aufgabe_daten["pruefungsteil"],
            aufgabenbereich=aufgabe_daten.get(
                "aufgabenbereich", Aufgabe.Aufgabenbereich.KEINE_ANGABE
            ),
        )
        for teilaufgabe_daten in aufgabe_daten["teilaufgaben"]:
            teilaufgabe = Teilaufgabe.objects.create(
                aufgabe=aufgabe,
                bezeichnung=teilaufgabe_daten["bezeichnung"],
                text=teilaufgabe_daten["text"],
                seite=teilaufgabe_daten["seite"],
                punkte=teilaufgabe_daten.get("punkte"),
                anforderungsbereich=teilaufgabe_daten["anforderungsbereich"],
                operatoren=teilaufgabe_daten.get("operatoren", []),
                begruendung=teilaufgabe_daten.get("begruendung", ""),
            )
            kennungen = teilaufgabe_daten.get("themen", [])
            if kennungen:
                themen = Thema.objects.filter(fach=fach, kennung__in=kennungen)
                teilaufgabe.themen.set(themen)

    return klausur, wurde_erstellt
