from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_erforderlich(view_func):
    """Lässt nur eingeloggte Lehrkräfte mit Admin-Recht passieren (Standard: verweigern)."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.ist_admin:
            raise PermissionDenied("Diese Seite ist nur für Admins zugänglich.")
        return view_func(request, *args, **kwargs)

    return wrapper
