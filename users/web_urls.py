from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from .web_views import CargoLoginView, dashboard, register_page

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard"), name="home"),
    path("login/", CargoLoginView.as_view(), name="login_page"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", register_page, name="register_page"),
    path("dashboard/", dashboard, name="dashboard"),
]