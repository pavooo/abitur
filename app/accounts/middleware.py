class LehrkraftSessionMiddleware:
    """Beendet die Session sofort, wenn eine Lehrkraft nachträglich gesperrt wird oder
    ihre Freischaltung zurückgenommen wurde (analog zur SuS-Zugangscode-Bindung)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.contrib.auth import logout as auth_logout

        from accounts.models import Lehrkraft

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.status != Lehrkraft.Status.AKTIV:
            auth_logout(request)
        return self.get_response(request)


class SusSessionMiddleware:
    """Bindet die SuS-Session an einen gültigen Zugangscode.

    Wird der Code gesperrt oder läuft er ab, endet die Session spätestens beim
    nächsten Request (siehe CLAUDE.md, Abschnitt Nachschreibklausuren).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from accounts.models import Zugangscode

        request.sus_zugangscode = None
        zugangscode_id = request.session.get("sus_zugangscode_id")
        if zugangscode_id is not None:
            zugangscode = (
                Zugangscode.objects.filter(pk=zugangscode_id).select_related("fach").first()
            )
            if zugangscode is not None and zugangscode.ist_gueltig():
                request.sus_zugangscode = zugangscode
            else:
                request.session.flush()
        return self.get_response(request)
