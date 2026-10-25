"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def home(request):
    return JsonResponse({
        "projet": "CargoLink",
        "admin": "/admin/",
        "register": "/api/auth/register/",
        "login": "/api/auth/login/",
        "me": "/api/auth/me/",
    })


urlpatterns = [
   # path('', home),
    path('', include('users.web_urls')),          # pages HTML (login, register, dashboard)

    path('admin/', admin.site.urls),
    path('annonces/', include('annonces.web_urls')),
    path('propositions/', include('propositions.web_urls')),
    path('meteo/', include('meteo.web_urls')),
    path('factures/', include('factures.web_urls')),
    path('ia/', include('ia.web_urls')),
    path('reservations/', include('reservations.web_urls')),
    path('evaluations/', include('evaluations.web_urls')),
    path('api/auth/', include('users.urls')),
    path('api/annonces/', include('annonces.urls')),
    path('api/propositions/', include('propositions.urls')),
    path('api/reservations/', include('reservations.urls')),
    path('api/evaluations/', include('evaluations.urls')),
    path('api/factures/', include('factures.urls')),
    path("reclamations/", include("reclamations.urls")),
    path("chauffeurs/", include("chauffeurs.urls")),
]

# pages d'erreur personnalisées (actives quand DEBUG=False)
handler403 = 'config.error_views.erreur_403'
handler404 = 'config.error_views.erreur_404'
handler500 = 'config.error_views.erreur_500'
