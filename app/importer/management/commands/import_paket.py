import tempfile
from pathlib import Path

from accounts.models import Lehrkraft
from django.core.management.base import BaseCommand, CommandError

from ...paket import PaketFehler, entpacken
from ...transaktion import importiere_paket
from ...vorschau import berechne_vorschau


class Command(BaseCommand):
    help = (
        "Importiert ein Zerlegung-Paket (ZIP) – für den Erstbestand, "
        "gleiche Logik wie der Adminbereich."
    )

    def add_arguments(self, parser):
        parser.add_argument("zip_pfad", type=Path)
        parser.add_argument(
            "--lehrkraft",
            required=True,
            metavar="E-MAIL",
            help="E-Mail-Adresse einer existierenden Admin-Lehrkraft (für das Importprotokoll).",
        )

    def handle(self, *args, **options):
        zip_pfad: Path = options["zip_pfad"]
        if not zip_pfad.exists():
            raise CommandError(f"Datei nicht gefunden: {zip_pfad}")

        try:
            lehrkraft = Lehrkraft.objects.get(email=options["lehrkraft"])
        except Lehrkraft.DoesNotExist as exc:
            raise CommandError(
                f"Keine Lehrkraft mit E-Mail {options['lehrkraft']!r} gefunden."
            ) from exc
        if not lehrkraft.ist_admin:
            raise CommandError(f"{lehrkraft.email} hat kein Admin-Recht.")

        with tempfile.TemporaryDirectory() as tmp_verzeichnis:
            try:
                paket = entpacken(zip_pfad, Path(tmp_verzeichnis) / "inhalt")
            except PaketFehler as exc:
                raise CommandError(str(exc)) from exc

            vorschau = berechne_vorschau(paket)
            if vorschau.hat_fehler:
                self.stdout.write(
                    self.style.ERROR("Paket enthält Fehler, Import wird abgebrochen:")
                )
                for fehler in vorschau.allgemeine_fehler:
                    self.stdout.write(f"  - {fehler}")
                for zeile in vorschau.zeilen:
                    for fehler in zeile.fehler:
                        self.stdout.write(f"  - {zeile.id}: {fehler}")
                raise CommandError("Import abgebrochen.")

            protokoll = importiere_paket(paket, lehrkraft=lehrkraft, paketname=zip_pfad.name)

        if protokoll.ergebnis == protokoll.Ergebnis.ERFOLGREICH:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import erfolgreich: {protokoll.anzahl_neu} neu, "
                    f"{protokoll.anzahl_aktualisiert} aktualisiert."
                )
            )
            if protokoll.fehlermeldung:
                self.stdout.write(self.style.WARNING(protokoll.fehlermeldung))
        else:
            raise CommandError(f"Import fehlgeschlagen: {protokoll.fehlermeldung}")
