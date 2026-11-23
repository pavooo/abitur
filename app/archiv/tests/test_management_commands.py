import pytest
from django.core.management import call_command

from archiv.models import Teilaufgabe

from .conftest import erstelle_aufgabe, erstelle_teilaufgabe


@pytest.mark.django_db
def test_aktualisiere_suchvektoren_befuellt_alle_teilaufgaben(klausur_haupttermin):
    teilaufgabe = erstelle_teilaufgabe(erstelle_aufgabe(klausur_haupttermin))
    Teilaufgabe.objects.filter(pk=teilaufgabe.pk).update(such_vektor=None)
    assert Teilaufgabe.objects.get(pk=teilaufgabe.pk).such_vektor is None

    call_command("aktualisiere_suchvektoren")

    assert Teilaufgabe.objects.get(pk=teilaufgabe.pk).such_vektor is not None
