from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("archiv", "0005_alter_klausur_hilfsmittel"),
    ]

    operations = [
        TrigramExtension(),
    ]
