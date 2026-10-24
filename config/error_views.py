from django.shortcuts import render


def _page(request, template, status):
    return render(request, template, status=status)


def erreur_403(request, exception=None):
    return _page(request, "errors/403.html", 403)


def erreur_404(request, exception=None):
    return _page(request, "errors/404.html", 404)


def erreur_500(request):
    return _page(request, "errors/500.html", 500)
