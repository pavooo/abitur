from types import SimpleNamespace

from editor.vorschlaege.themen import normalisiere, schlage_themen_vor


def _thema(pk, kennung, name, synonyme=()):
    return SimpleNamespace(pk=pk, kennung=kennung, name=name, synonyme=list(synonyme))


class TestNormalisiere:
    def test_kleinschreibung_und_umlaute(self):
        assert normalisiere("Äußere Ableitung") == "aeussere ableitung"


class TestSchlageThemenVor:
    def test_findet_thema_ueber_namen(self):
        themen = [_thema(1, "analysis.diff.wendepunkt", "Wendepunkte")]

        vorschlaege = schlage_themen_vor("Bestimmen Sie die Wendepunkte von f.", themen)

        assert [v["kennung"] for v in vorschlaege] == ["analysis.diff.wendepunkt"]

    def test_findet_thema_ueber_synonym(self):
        themen = [
            _thema(
                1,
                "analysis.fkt.ganzrational",
                "Ganzrationale Funktionen",
                synonyme=["Polynom", "Polynomfunktion"],
            )
        ]

        vorschlaege = schlage_themen_vor("Gegeben ist die Polynomfunktion f.", themen)

        assert [v["kennung"] for v in vorschlaege] == ["analysis.fkt.ganzrational"]

    def test_wortstamm_toleranz(self):
        themen = [_thema(1, "analysis.diff", "Ableitung")]

        # "Ableitungsregel" teilt sich mit "Ableitung" den Stamm "ablei".
        vorschlaege = schlage_themen_vor("Wenden Sie die Ableitungsregel an.", themen)

        assert [v["kennung"] for v in vorschlaege] == ["analysis.diff"]

    def test_ignoriert_umlaute_und_grossschreibung(self):
        themen = [_thema(1, "analysis.extrema", "Äußere Ableitung")]

        vorschlaege = schlage_themen_vor("bestimmen sie die AEUSSERE ableitung", themen)

        assert [v["kennung"] for v in vorschlaege] == ["analysis.extrema"]

    def test_kein_treffer_liefert_leere_liste(self):
        themen = [_thema(1, "stochastik.binomial", "Binomialverteilung")]

        assert schlage_themen_vor("Ein völlig anderer Text.", themen) == []

    def test_sortiert_nach_relevanz(self):
        themen = [
            _thema(1, "analysis.fkt", "Funktionen"),
            _thema(2, "analysis.fkt.ganzrational", "Ganzrationale Funktionen"),
        ]

        vorschlaege = schlage_themen_vor(
            "Untersuchen Sie die ganzrationale Funktion auf Nullstellen.", themen
        )

        assert vorschlaege[0]["kennung"] == "analysis.fkt.ganzrational"

    def test_begrenzt_auf_max_anzahl(self):
        themen = [_thema(i, f"thema.{i}", "Funktionen") for i in range(10)]

        vorschlaege = schlage_themen_vor("Untersuchen Sie die Funktionen.", themen, max_anzahl=3)

        assert len(vorschlaege) == 3
