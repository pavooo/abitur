from django import forms

INPUT_CLASSES = (
    "mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm "
    "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
)

_WIDGETS_OHNE_INPUT_CLASSEN = (
    forms.CheckboxInput,
    forms.CheckboxSelectMultiple,
    forms.RadioSelect,
)


class TailwindFormMixin:
    """Versieht Formularfelder mit einheitlichen Tailwind-Klassen."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, _WIDGETS_OHNE_INPUT_CLASSEN):
                continue
            vorhandene_klassen = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{vorhandene_klassen} {INPUT_CLASSES}".strip()
