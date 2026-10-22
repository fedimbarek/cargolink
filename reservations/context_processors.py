def notifications(request):
    """Nombre de notifications non lues, affiché dans la barre de navigation."""
    if request.user.is_authenticated:
        return {"nb_notifications": request.user.notifications_suivi.filter(lue=False).count()}
    return {}
