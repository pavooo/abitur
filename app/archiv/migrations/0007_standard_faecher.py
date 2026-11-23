from django.db import migrations

# Typische Fächer der gymnasialen Oberstufe in NRW mit gebräuchlichen Kürzeln.
# Kein Anspruch auf Vollständigkeit (z. B. selten unterrichtete Fächer wie
# Pädagogik oder weitere Fremdsprachen fehlen bewusst) – "typische" Fächer
# laut Anfrage, nicht jedes mögliche Fach.
STANDARD_FAECHER = [
    ("Deutsch", "D"),
    ("Mathematik", "M"),
    ("Englisch", "E"),
    ("Französisch", "F"),
    ("Latein", "L"),
    ("Spanisch", "S"),
    ("Biologie", "BI"),
    ("Chemie", "CH"),
    ("Physik", "PH"),
    ("Informatik", "IF"),
    ("Erdkunde", "EK"),
    ("Geschichte", "GE"),
    ("Sozialwissenschaften", "SW"),
    ("Philosophie", "PL"),
    ("Kunst", "KU"),
    ("Musik", "MU"),
    ("Sport", "SP"),
    ("Evangelische Religionslehre", "ER"),
    ("Katholische Religionslehre", "KR"),
]


def faecher_anlegen(apps, schema_editor):
    Fach = apps.get_model("archiv", "Fach")
    for name, kuerzel in STANDARD_FAECHER:
        # Weder Name noch Kürzel dürfen bereits (unter anderer Kombination)
        # existieren, sonst verletzt das Anlegen die Unique-Constraints – z. B.
        # wenn ein Admin ein Fach schon manuell mit abweichendem Kürzel angelegt
        # hat. In dem Fall wird dieses Fach übersprungen, nicht überschrieben
        # (CLAUDE.md: nicht still ändern).
        if Fach.objects.filter(name=name).exists() or Fach.objects.filter(kuerzel=kuerzel).exists():
            continue
        Fach.objects.create(name=name, kuerzel=kuerzel)


def faecher_entfernen(apps, schema_editor):
    Fach = apps.get_model("archiv", "Fach")
    kuerzel_liste = [kuerzel for _name, kuerzel in STANDARD_FAECHER]
    # Nur entfernen, wenn unbenutzt – ein Fach mit bereits zugeordneten
    # Klausuren/Lehrkräften/Zugangscodes wird durch PROTECT-FKs ohnehin nicht
    # gelöscht, der Versuch würde die Rückwärtsmigration sonst abbrechen lassen.
    Fach.objects.filter(kuerzel__in=kuerzel_liste, klausuren__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("archiv", "0006_trigram_extension"),
    ]

    operations = [
        migrations.RunPython(faecher_anlegen, faecher_entfernen),
    ]
