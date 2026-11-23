from accounts.models import Lehrkraft
from archiv.models import Fach
from config.forms import TailwindFormMixin
from django import forms


class FachErstellenForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Fach
        fields = ["name", "kuerzel"]


class LehrkraftFaecherForm(forms.ModelForm):
    class Meta:
        model = Lehrkraft
        fields = ["faecher"]
        widgets = {"faecher": forms.CheckboxSelectMultiple}


class ZugangscodeErstellenForm(TailwindFormMixin, forms.Form):
    fach = forms.ModelChoiceField(queryset=Fach.objects.all(), label="Fach")
    bezeichnung = forms.CharField(label="Bezeichnung", max_length=200)
    ablaufdatum = forms.DateField(
        label="Ablaufdatum", widget=forms.DateInput(attrs={"type": "date"})
    )
