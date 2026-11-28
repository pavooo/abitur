from editor.vorschlaege.teilaufgaben import erkenne_teilaufgaben


class TestErkenneTeilaufgaben:
    def test_erkennt_buchstaben_marker(self):
        text = (
            "a) Bestimmen Sie die Nullstellen von f.\n"
            "b) Untersuchen Sie das Monotonieverhalten von f."
        )

        vorschlaege = erkenne_teilaufgaben(text)

        assert [v["bezeichnung"] for v in vorschlaege] == ["a", "b"]
        assert vorschlaege[0]["text"] == "Bestimmen Sie die Nullstellen von f."
        assert vorschlaege[1]["text"] == "Untersuchen Sie das Monotonieverhalten von f."

    def test_erkennt_nummerierte_marker(self):
        text = "1.1 Bestimmen Sie f'(x).\n1.2 Berechnen Sie f'(2)."

        vorschlaege = erkenne_teilaufgaben(text)

        assert [v["bezeichnung"] for v in vorschlaege] == ["1.1", "1.2"]

    def test_erkennt_punkteangabe(self):
        text = "a) Zeigen Sie die Behauptung. (6 Punkte)\nb) Begründen Sie Ihr Ergebnis. (3 P.)"

        vorschlaege = erkenne_teilaufgaben(text)

        assert vorschlaege[0]["punkte"] == 6
        assert vorschlaege[1]["punkte"] == 3

    def test_ohne_punkteangabe_ist_punkte_none(self):
        text = "a) Bestimmen Sie die Nullstellen von f."

        vorschlaege = erkenne_teilaufgaben(text)

        assert vorschlaege[0]["punkte"] is None

    def test_ohne_marker_liefert_leere_liste(self):
        assert erkenne_teilaufgaben("Ein Fließtext ohne jede Markierung.") == []

    def test_text_vor_erstem_marker_wird_ignoriert(self):
        text = "Betrachtet wird die Funktion f.\na) Bestimmen Sie f'(x)."

        vorschlaege = erkenne_teilaufgaben(text)

        assert len(vorschlaege) == 1
        assert vorschlaege[0]["bezeichnung"] == "a"

    def test_marker_mitten_im_satz_wird_nicht_erkannt(self):
        # "f(1.2)" steht nicht am Zeilenanfang und darf keinen Marker auslösen.
        text = "Berechnen Sie f(1.2) für die gegebene Funktion."

        assert erkenne_teilaufgaben(text) == []
