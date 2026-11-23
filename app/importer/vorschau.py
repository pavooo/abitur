import dataclasses

from archiv.models import Fach, Klausur, Thema

from .paket import EntpacktesPaket, KlausurEintrag


@dataclasses.dataclass
class KlausurVorschauZeile:
    id: str
    titel: str
    fach_kuerzel: str
    jahr: int | None
    kursart: str
    termin: str
    variante: str
    status: str  # "neu" | "aktualisiert" | "fehler"
    fehler: list[str]


@dataclasses.dataclass
class VorschauErgebnis:
    allgemeine_fehler: list[str]
    zeilen: list[KlausurVorschauZeile]
    taxonomie_themen_anzahl: int

    @property
    def hat_fehler(self) -> bool:
        gibt_es_fehlerzeile = any(zeile.status == "fehler" for zeile in self.zeilen)
        return bool(self.allgemeine_fehler) or gibt_es_fehlerzeile


def berechne_vorschau(paket: EntpacktesPaket) -> VorschauErgebnis:
    fach_kuerzel = paket.manifest["fach"]
    allgemeine_fehler = []

    if not Fach.objects.filter(kuerzel=fach_kuerzel).exists():
        allgemeine_fehler.append(
            f"Unbekanntes Fach-Kürzel {fach_kuerzel!r} (manifest.json). "
            "Bitte zuerst im Adminbereich anlegen."
        )

    if paket.taxonomie is not None:
        if paket.taxonomie["fach"] != fach_kuerzel:
            allgemeine_fehler.append(
                f"Fach {paket.taxonomie['fach']!r} in taxonomie.json weicht vom Paket-Fach "
                f"{fach_kuerzel!r} (manifest.json) ab."
            )
        allgemeine_fehler.extend(_taxonomie_fehler(paket.taxonomie, fach_kuerzel))

    zeilen = [_zeile_fuer(eintrag, fach_kuerzel, paket.taxonomie) for eintrag in paket.klausuren]

    taxonomie_themen_anzahl = 0
    if paket.taxonomie is not None:
        taxonomie_themen_anzahl = len(_kennungen_aus_taxonomie(paket.taxonomie))

    return VorschauErgebnis(
        allgemeine_fehler=allgemeine_fehler,
        zeilen=zeilen,
        taxonomie_themen_anzahl=taxonomie_themen_anzahl,
    )


def _kennungen_aus_taxonomie(taxonomie: dict) -> set:
    return {knoten["kennung"] for knoten in taxonomie.get("themen", [])}


def _taxonomie_fehler(taxonomie: dict, fach_kuerzel: str) -> list[str]:
    """Prüft die Taxonomie selbst: fertig/geprüft (nicht Entwurf) und alle
    `eltern`-Verweise lösbar – entweder innerhalb desselben Pakets oder bereits
    als Thema in der Datenbank vorhanden."""
    fehler = []

    if taxonomie.get("status") == "entwurf":
        fehler.append(
            "taxonomie.json hat den Status 'entwurf' – die App importiert nur fertige, "
            "geprüfte Daten."
        )

    knoten_mit_zu_pruefen = [k["kennung"] for k in taxonomie.get("themen", []) if "zu_pruefen" in k]
    if knoten_mit_zu_pruefen:
        fehler.append(
            "taxonomie.json enthält noch zu prüfende Themen (zu_pruefen): "
            + ", ".join(sorted(knoten_mit_zu_pruefen))
        )

    kennungen_im_paket = _kennungen_aus_taxonomie(taxonomie)
    bekannte_kennungen = set(
        Thema.objects.filter(fach__kuerzel=fach_kuerzel).values_list("kennung", flat=True)
    )
    for knoten in taxonomie.get("themen", []):
        eltern = knoten.get("eltern")
        if eltern is not None and eltern not in kennungen_im_paket | bekannte_kennungen:
            fehler.append(f"Thema {knoten['kennung']!r}: unbekanntes Eltern-Thema {eltern!r}.")

    return fehler


def _bekannte_themen_kennungen(fach: Fach, taxonomie: dict | None) -> set:
    kennungen = set(Thema.objects.filter(fach=fach).values_list("kennung", flat=True))
    if taxonomie is not None:
        kennungen |= _kennungen_aus_taxonomie(taxonomie)
    return kennungen


def _zeile_fuer(
    eintrag: KlausurEintrag, manifest_fach_kuerzel: str, taxonomie: dict | None
) -> KlausurVorschauZeile:
    daten = eintrag.daten
    fehler = list(eintrag.schema_fehler)

    if fehler:
        return KlausurVorschauZeile(
            id=eintrag.id,
            titel=daten.get("titel", eintrag.id),
            fach_kuerzel=daten.get("fach", "?"),
            jahr=daten.get("jahr"),
            kursart=daten.get("kursart", "?"),
            termin=daten.get("termin", "?"),
            variante=daten.get("variante", ""),
            status="fehler",
            fehler=fehler,
        )

    if daten["fach"] != manifest_fach_kuerzel:
        fehler.append(
            f"Fach {daten['fach']!r} der Klausur weicht vom Paket-Fach "
            f"{manifest_fach_kuerzel!r} (manifest.json) ab."
        )

    fach = Fach.objects.filter(kuerzel=daten["fach"]).first()
    if fach is None:
        fehler.append(f"Unbekanntes Fach-Kürzel: {daten['fach']!r}.")

    nummern = [aufgabe["nummer"] for aufgabe in daten["aufgaben"]]
    if len(nummern) != len(set(nummern)):
        fehler.append("Aufgaben-Nummern sind nicht eindeutig innerhalb der Klausur.")

    for aufgabe in daten["aufgaben"]:
        seite_von, seite_bis = aufgabe["seiten"]
        if seite_von > seite_bis:
            fehler.append(
                f"Aufgabe {aufgabe['nummer']}: Seitenbereich {aufgabe['seiten']} ist ungültig."
            )

        bezeichnungen = [t["bezeichnung"] for t in aufgabe["teilaufgaben"]]
        if len(bezeichnungen) != len(set(bezeichnungen)):
            fehler.append(
                f"Aufgabe {aufgabe['nummer']}: Teilaufgaben-Bezeichnungen sind nicht eindeutig."
            )

    if fach is not None:
        bekannte_kennungen = _bekannte_themen_kennungen(fach, taxonomie)
        for aufgabe in daten["aufgaben"]:
            for teilaufgabe in aufgabe["teilaufgaben"]:
                for kennung in teilaufgabe.get("themen", []):
                    if kennung not in bekannte_kennungen:
                        fehler.append(
                            f"Teilaufgabe {teilaufgabe['bezeichnung']}: "
                            f"unbekannte Themen-Kennung {kennung!r}."
                        )

    status = "fehler"
    if not fehler and fach is not None:
        existiert = Klausur.objects.filter(
            fach=fach,
            jahr=daten["jahr"],
            kursart=daten["kursart"],
            termin=daten["termin"],
            variante=daten.get("variante", ""),
        ).exists()
        status = "aktualisiert" if existiert else "neu"

    return KlausurVorschauZeile(
        id=eintrag.id,
        titel=daten["titel"],
        fach_kuerzel=daten["fach"],
        jahr=daten["jahr"],
        kursart=daten["kursart"],
        termin=daten["termin"],
        variante=daten.get("variante", ""),
        status=status,
        fehler=fehler,
    )
