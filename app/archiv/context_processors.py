from .sichtbarkeit import NACHSCHREIBMODUS_SESSION_KEY


def nachschreibmodus(request):
    """Stellt `nachschreibmodus_aktiv` global für das rote Banner in base.html
    bereit (siehe CLAUDE.md, Abschnitt Nachschreibklausuren)."""
    session = getattr(request, "session", None)
    aktiv = bool(session.get(NACHSCHREIBMODUS_SESSION_KEY, False)) if session is not None else False
    return {"nachschreibmodus_aktiv": aktiv}
