from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Teilaufgabe
from .suche import such_vektor_aktualisieren


@receiver(post_save, sender=Teilaufgabe)
def _teilaufgabe_gespeichert(sender, instance, **kwargs):
    such_vektor_aktualisieren(instance)


@receiver(m2m_changed, sender=Teilaufgabe.themen.through)
def _teilaufgabe_themen_geaendert(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        such_vektor_aktualisieren(instance)
