from functools import wraps

from django.shortcuts import redirect


def sus_erforderlich(view_func):
    """Lässt nur Requests mit gültiger SuS-Zugangscode-Session passieren."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.sus_zugangscode is None:
            return redirect("accounts:login_waehlen")
        return view_func(request, *args, **kwargs)

    return wrapper
