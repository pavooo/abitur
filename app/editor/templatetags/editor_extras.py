from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """Wörterbuch-Zugriff mit einer Variable als Schlüssel (`{{ mapping.key }}` erlaubt
    in Django-Templates nur literale Schlüssel, keine Variablen)."""
    return mapping.get(key)
