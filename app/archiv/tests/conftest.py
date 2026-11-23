import datetime
from types import SimpleNamespace

import pytest
from accounts.models import Lehrkraft, Zugangscode
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from archiv.models import Aufgabe, Fach, Klausur, Teilaufgabe
from archiv.sichtbarkeit import NACHSCHREIBMODUS_SESSION_KEY


def dummy_pdf(name="klausur.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 Dummy", content_type="application/pdf")


@pytest.fixture
def fach_mathe(db):
    return Fach.objects.create(name="Mathematik", kuerzel="M")


@pytest.fixture
def fach_deutsch(db):
    return Fach.objects.create(name="Deutsch", kuerzel="D")


@pytest.fixture
def klausur_haupttermin(fach_mathe):
    return Klausur.objects.create(
        fach=fach_mathe,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante="A",
        titel="Analysis",
        pdf=dummy_pdf("haupttermin.pdf"),
    )


@pytest.fixture
def klausur_nachschreibtermin(fach_mathe):
    return Klausur.objects.create(
        fach=fach_mathe,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.NACHSCHREIBTERMIN,
        variante="A",
        titel="Analysis (Nachschreiber)",
        pdf=dummy_pdf("nachschreiber.pdf"),
    )


@pytest.fixture
def klausur_anderes_fach(fach_deutsch):
    return Klausur.objects.create(
        fach=fach_deutsch,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante="",
        titel="Lyrik",
        pdf=dummy_pdf("deutsch.pdf"),
    )


def erstelle_aufgabe(klausur, nummer=1):
    return Aufgabe.objects.create(
        klausur=klausur, nummer=nummer, kontext="Kontext", seite_von=1, seite_bis=2
    )


def erstelle_teilaufgabe(aufgabe, bezeichnung="1a"):
    return Teilaufgabe.objects.create(
        aufgabe=aufgabe,
        bezeichnung=bezeichnung,
        text="Text",
        seite=1,
        anforderungsbereich=Teilaufgabe.Anforderungsbereich.I,
    )


@pytest.fixture
def sus_request(fach_mathe):
    zugangscode, _klartext = Zugangscode.erstellen(
        fach=fach_mathe,
        bezeichnung="SuS-Code",
        ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
    )
    return SimpleNamespace(sus_zugangscode=zugangscode, user=AnonymousUser(), session={})


@pytest.fixture
def lehrkraft_request_factory(db):
    def _erstellen(faecher=(), nachschreibmodus=False, ist_admin=False):
        lehrkraft = Lehrkraft.objects.create_user(
            email=f"lehrkraft-{Lehrkraft.objects.count()}@schule.de",
            password="s3hrGeheim!",
            status=Lehrkraft.Status.AKTIV,
            ist_admin=ist_admin,
        )
        lehrkraft.faecher.set(faecher)
        session = {}
        if nachschreibmodus:
            session[NACHSCHREIBMODUS_SESSION_KEY] = True
        return SimpleNamespace(sus_zugangscode=None, user=lehrkraft, session=session)

    return _erstellen


@pytest.fixture
def anonymer_request():
    return SimpleNamespace(sus_zugangscode=None, user=AnonymousUser(), session={})
