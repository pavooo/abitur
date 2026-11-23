"""Volltextsuche auf Teilaufgaben-Ebene (siehe CLAUDE.md, Abschnitt Suche).

Der Suchvektor einer Teilaufgabe wird aus Text, Aufgabenkontext sowie Namen und
Synonymen ihrer Themen gebildet. Die Pflege übernehmen Signals (`signals.py`) bei
jedem Speichern einer Teilaufgabe bzw. jeder Änderung ihrer Themen-Zuordnung.
"""

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramWordSimilarity,
)
from django.db.models import F, Q, Value

SUCH_KONFIGURATION = "german"


def such_text_fuer(teilaufgabe) -> str:
    themen = list(teilaufgabe.themen.all())
    namen = [thema.name for thema in themen]
    synonyme = [synonym for thema in themen for synonym in thema.synonyme]
    return " ".join([teilaufgabe.text, teilaufgabe.aufgabe.kontext, *namen, *synonyme])


def such_vektor_aktualisieren(teilaufgabe) -> None:
    text = such_text_fuer(teilaufgabe)
    type(teilaufgabe).objects.filter(pk=teilaufgabe.pk).update(
        such_vektor=SearchVector(Value(text), config=SUCH_KONFIGURATION)
    )


def volltext_filtern(queryset, text: str):
    """Kombiniert Volltextsuche (inkl. Themennamen/Synonyme über such_vektor) mit
    Trigram-Wortähnlichkeit auf dem Teilaufgabentext zur Tippfehlertoleranz.

    `TrigramWordSimilarity` (Postgres `word_similarity()`) vergleicht den Suchbegriff
    mit der best passenden Teilzeichenkette des Texts, statt mit dem gesamten Text
    (wie `TrigramSimilarity`/`similarity()`) – sonst verwässert ein einzelner Tippfehler
    in einem langen Satz die Ähnlichkeit und bleibt unter jeder sinnvollen Schwelle."""
    text = (text or "").strip()
    if not text:
        return queryset

    query = SearchQuery(text, config=SUCH_KONFIGURATION)
    return (
        queryset.annotate(
            rang=SearchRank(F("such_vektor"), query),
            aehnlichkeit=TrigramWordSimilarity(text, "text"),
        )
        .filter(Q(such_vektor=query) | Q(aehnlichkeit__gt=0.4))
        .order_by("-rang", "-aehnlichkeit")
    )
