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
    # get_or_create statt create: "Mathematik"/"M" ist eines der durch
    # Migration 0007 automatisch angelegten Standardfächer.
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="M", defaults={"name": "Mathematik"})
    return fach


@pytest.fixture
def fach_deutsch(db):
    fach, _erstellt = Fach.objects.get_or_create(kuerzel="D", defaults={"name": "Deutsch"})
    return fach


@pytest.fixture
def klausur_haupttermin(fach_mathe):
    return Klausur.objects.create(
        fach=fach_mathe,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante="A",
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
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
        hilfsmittel=Klausur.Hilfsmittel.TR,
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
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=dummy_pdf("deutsch.pdf"),
    )


def erstelle_klausur(fach, *, status=Klausur.Status.FREIGEGEBEN, ersteller=None, variante=""):
    """Für Tests rund um den Freigabe-Status (siehe CLAUDE.md, Abschnitt Lehrkraft-Editor).
    Variante muss je Test eindeutig sein, da Fach+Jahr+Kursart+Termin+Variante eindeutig ist."""
    return Klausur.objects.create(
        fach=fach,
        jahr=2024,
        kursart=Klausur.Kursart.LK,
        termin=Klausur.Termin.HAUPTTERMIN,
        variante=variante,
        titel="Analysis",
        hilfsmittel=Klausur.Hilfsmittel.TR,
        pdf=dummy_pdf(f"status-{status}-{variante}.pdf"),
        status=status,
        ersteller=ersteller,
    )


def erstelle_aufgabe(klausur, nummer=1):
    return Aufgabe.objects.create(
        klausur=klausur,
        nummer=nummer,
        kontext="Kontext",
        seite_von=1,
        seite_bis=2,
        pruefungsteil=Aufgabe.Pruefungsteil.MIT_HILFSMITTELN,
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


@pytest.fixture
def sus_client(client, fach_mathe):
    """Django-Test-Client mit gültiger SuS-Zugangscode-Session (für View-Tests,
    im Gegensatz zu `sus_request`, das nur die reine Sichtbarkeitslogik testet)."""
    zugangscode, _klartext = Zugangscode.erstellen(
        fach=fach_mathe,
        bezeichnung="SuS-Code",
        ablaufdatum=timezone.localdate() + datetime.timedelta(days=30),
    )
    session = client.session
    session["sus_zugangscode_id"] = zugangscode.pk
    session.save()
    return client


@pytest.fixture
def lehrkraft_client_factory(client):
    def _erstellen(faecher=(), nachschreibmodus=False, ist_admin=False):
        lehrkraft = Lehrkraft.objects.create_user(
            email=f"lehrkraft-client-{Lehrkraft.objects.count()}@schule.de",
            password="s3hrGeheim!",
            status=Lehrkraft.Status.AKTIV,
            ist_admin=ist_admin,
        )
        lehrkraft.faecher.set(faecher)
        client.force_login(lehrkraft)
        if nachschreibmodus:
            session = client.session
            session[NACHSCHREIBMODUS_SESSION_KEY] = True
            session.save()
        return client

    return _erstellen
