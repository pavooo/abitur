from archiv.models import Aufgabe, Klausur, Teilaufgabe, Thema
from archiv.sichtbarkeit import Termin
from config.forms import TailwindFormMixin
from django import forms

from . import pdf_sicherheit


class MetadatenForm(TailwindFormMixin, forms.ModelForm):
    # Eigenes Feld statt des automatisch generierten: RadioSelect statt Dropdown, damit
    # ohne Auswahl sichtbar nichts vorausgewählt ist (CLAUDE.md: Termin hat keinen
    # Standardwert, im Zweifel nie Haupttermin annehmen).
    termin = forms.ChoiceField(label="Termin", choices=Termin.choices, widget=forms.RadioSelect)

    class Meta:
        model = Klausur
        fields = ["fach", "jahr", "kursart", "termin", "variante", "hilfsmittel", "titel"]

    def __init__(self, *args, lehrkraft, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fach"].queryset = lehrkraft.faecher.all()

    def clean(self):
        cleaned = super().clean()
        schluessel_felder = ("fach", "jahr", "kursart", "termin")
        if not all(cleaned.get(feld) for feld in schluessel_felder):
            return cleaned

        bestehende = Klausur.objects.filter(
            fach=cleaned["fach"],
            jahr=cleaned["jahr"],
            kursart=cleaned["kursart"],
            termin=cleaned["termin"],
            variante=cleaned.get("variante", ""),
        )
        if self.instance.pk:
            bestehende = bestehende.exclude(pk=self.instance.pk)
        if bestehende.exists():
            raise forms.ValidationError(
                "Achtung: Für diese Kombination aus Fach, Jahr, Kursart, Termin und "
                "Variante existiert bereits eine Klausur."
            )
        return cleaned


class AufgabeForm(TailwindFormMixin, forms.ModelForm):
    """`klausur` ist bewusst kein Formularfeld, sondern ein Konstruktor-Argument: Felder,
    die nicht im Formular stehen, schließt Django bei `ModelForm.validate_unique()`
    grundsätzlich von Eindeutigkeitsprüfungen aus (auch wenn `instance.klausur` längst
    gesetzt ist) – die Prüfung auf doppelte Nummer je Klausur muss daher hier manuell
    erfolgen. Seitenbereich wird nicht erfasst, sondern automatisch aus den Bereichen der
    Aufgabe abgeleitet (siehe `editor/views.py`)."""

    class Meta:
        model = Aufgabe
        fields = ["nummer", "kontext", "pruefungsteil", "aufgabenbereich"]

    def __init__(self, *args, klausur, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.klausur = klausur
        self._klausur = klausur

    def clean_nummer(self):
        nummer = self.cleaned_data["nummer"]
        bestehende = Aufgabe.objects.filter(klausur=self._klausur, nummer=nummer)
        if self.instance.pk:
            bestehende = bestehende.exclude(pk=self.instance.pk)
        if bestehende.exists():
            raise forms.ValidationError(f"Aufgabe {nummer} existiert in dieser Klausur bereits.")
        return nummer


class TeilaufgabeErstellenForm(TailwindFormMixin, forms.ModelForm):
    """Legt eine Teilaufgabe nur mit ihrer Bezeichnung an (z. B. „1a“). Text, Seite,
    Anforderungsbereich usw. folgen erst, sobald Bereiche markiert sind (siehe
    `TeilaufgabeDetailForm` und `editor/views.py`)."""

    class Meta:
        model = Teilaufgabe
        fields = ["bezeichnung"]

    def __init__(self, *args, aufgabe, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.aufgabe = aufgabe
        self._aufgabe = aufgabe

    def clean_bezeichnung(self):
        bezeichnung = self.cleaned_data["bezeichnung"]
        bestehende = Teilaufgabe.objects.filter(aufgabe=self._aufgabe, bezeichnung=bezeichnung)
        if self.instance.pk:
            bestehende = bestehende.exclude(pk=self.instance.pk)
        if bestehende.exists():
            raise forms.ValidationError(f"Teilaufgabe {bezeichnung} existiert bereits.")
        return bezeichnung


class TeilaufgabeDetailForm(TailwindFormMixin, forms.ModelForm):
    """Die übrigen Angaben einer Teilaufgabe. `operatoren` ist im Modell ein
    Array-Feld ohne passendes Standard-Widget, daher als kommagetrennter Text
    erfasst und beim Speichern in eine Liste zerlegt. Themen werden als
    Checkbox-Baum gerendert (siehe `editor/_themenbaum.html`), nicht als Django-
    Standard-Widget – das Feld bleibt aber ein normales `ModelMultipleChoiceField`,
    sodass das Formular selbst unverändert funktioniert."""

    operatoren_text = forms.CharField(
        label="Operatoren",
        required=False,
        help_text="Durch Komma getrennt, z. B. „ermitteln, begründen“.",
    )

    class Meta:
        model = Teilaufgabe
        fields = ["text", "punkte", "anforderungsbereich", "themen"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4}),
            "anforderungsbereich": forms.RadioSelect,
            "themen": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, fach, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["anforderungsbereich"].required = False
        self.fields["themen"].queryset = Thema.objects.filter(fach=fach).order_by("kennung")
        if self.instance.pk:
            self.fields["operatoren_text"].initial = ", ".join(self.instance.operatoren)

    def clean_operatoren_text(self):
        roh = self.cleaned_data.get("operatoren_text", "")
        return [teil.strip() for teil in roh.split(",") if teil.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.operatoren = self.cleaned_data["operatoren_text"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PdfUploadForm(TailwindFormMixin, forms.Form):
    pdf = forms.FileField(label="Klausur-PDF", required=False)
    erwartungshorizont_pdf = forms.FileField(
        label="Erwartungshorizont-PDF (optional)", required=False
    )

    def __init__(self, *args, hat_bereits_pdf=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._hat_bereits_pdf = hat_bereits_pdf

    def clean_pdf(self):
        datei = self.cleaned_data.get("pdf")
        if datei is None:
            if not self._hat_bereits_pdf:
                raise forms.ValidationError("Das Klausur-PDF ist Pflicht.")
            return None
        self._pruefe(datei)
        return datei

    def clean_erwartungshorizont_pdf(self):
        datei = self.cleaned_data.get("erwartungshorizont_pdf")
        if datei is None:
            return None
        self._pruefe(datei)
        return datei

    @staticmethod
    def _pruefe(datei):
        try:
            pdf_sicherheit.pruefe_pdf(datei)
        except pdf_sicherheit.PdfPruefungFehler as exc:
            raise forms.ValidationError(str(exc)) from exc
