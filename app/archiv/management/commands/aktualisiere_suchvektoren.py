from django.core.management.base import BaseCommand

from archiv.models import Teilaufgabe
from archiv.suche import such_vektor_aktualisieren


class Command(BaseCommand):
    help = (
        "Baut den Suchvektor aller Teilaufgaben neu auf. Nötig nach einem Import, der "
        "vor der Einführung der Suchvektor-Signals lief, oder nach nachträglichen "
        "Änderungen an Themen-Namen/Synonymen (die nicht automatisch nachgezogen werden)."
    )

    def handle(self, *args, **options):
        teilaufgaben = Teilaufgabe.objects.select_related("aufgabe").prefetch_related("themen")
        anzahl = 0
        for teilaufgabe in teilaufgaben:
            such_vektor_aktualisieren(teilaufgabe)
            anzahl += 1
        self.stdout.write(self.style.SUCCESS(f"{anzahl} Suchvektoren aktualisiert."))
