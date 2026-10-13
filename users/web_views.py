from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


class CargoLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True      # déjà connecté -> dashboard


def register_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)                # connexion automatique
        return redirect("dashboard")
    return render(request, "users/register.html", {"form": form})


@login_required
def dashboard(request):
    return render(request, "users/dashboard.html")