from rest_framework.permissions import BasePermission

from .models import User


class IsPME(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and u.role == User.Role.PME


class IsTransporteur(BasePermission):
    """Transporteur connecté ET validé par l'admin."""
    def has_permission(self, request, view):
        u = request.user
        return (
            u.is_authenticated
            and u.role == User.Role.TRANSPORTEUR
            and hasattr(u, "transporteur")
            and u.transporteur.verified
        )


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u.is_authenticated and u.role == User.Role.ADMIN
