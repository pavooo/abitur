from editor.vorschlaege.operatoren import lade_operatoren, schlage_anforderungsbereich_vor


class TestLadeOperatoren:
    def test_laedt_mathematik_liste(self):
        operatoren = lade_operatoren("Mathematik")

        assert operatoren["begründen"] == "II"
        assert operatoren["beurteilen"] == "III"
        assert operatoren["angeben"] == "I"

    def test_unbekanntes_fach_liefert_leeres_dict(self):
        assert lade_operatoren("Nichtvorhandenesfach") == {}


class TestSchlageAnforderungsbereichVor:
    OPERATOREN = {
        "angeben": "I",
        "begründen": "II",
        "stellung nehmen": "III",
        "kritisch stellung nehmen": "III",
    }

    def test_findet_operator_im_text(self):
        ergebnis = schlage_anforderungsbereich_vor(
            "Begründen Sie Ihre Entscheidung.", self.OPERATOREN
        )

        assert ergebnis == {"operator": "begründen", "anforderungsbereich": "II"}

    def test_bevorzugt_laengeren_operator(self):
        ergebnis = schlage_anforderungsbereich_vor(
            "Bitte kritisch Stellung nehmen zu dieser These.", self.OPERATOREN
        )

        assert ergebnis["operator"] == "kritisch stellung nehmen"

    def test_ohne_treffer_liefert_none(self):
        assert schlage_anforderungsbereich_vor("Ein Text ohne Operator.", self.OPERATOREN) is None
