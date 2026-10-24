"""Fabriques de données partagées par les tests de toutes les applications."""
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from users.models import PME, Transporteur, User

# hash rapide pour accélérer les tests (jamais utilisé hors tests)
RAPIDE = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def make_user(name, role, **kw):
    return User.objects.create_user(username=name, email=f"{name}@test.tn", password="pass12345", role=role, **kw)


def make_pme(name="pme"):
    u = make_user(name, "PME")
    return u, PME.objects.create(user=u, company_name=f"{name} SA")


def make_transporteur(name="tr", verified=True, rating="4.00"):
    u = make_user(name, "TRANSPORTEUR")
    return u, Transporteur.objects.create(user=u, company_name=f"{name} SARL", verified=verified,
                                          rating=Decimal(rating))


def make_demande(pme, **kw):
    from annonces.models import DemandeTransport
    now = timezone.now()
    data = dict(pme=pme, origin="Tunis", destination="Sfax", weight=1000, cargo_type="Palettes",
                pickup_date=now + timedelta(days=3), delivery_date=now + timedelta(days=4),
                distance_km=Decimal("270.0"), duration_hours=Decimal("3.0"))
    data.update(kw)
    return DemandeTransport.objects.create(**data)


def make_vehicle(transporteur, plate="111 TUN 1", weight=5000, volume=30):
    from propositions.models import Vehicle
    return Vehicle.objects.create(transporteur=transporteur, registration_number=plate,
                                  capacity_weight=weight, capacity_volume=volume)


def make_proposition(demande, transporteur, vehicle, price="400", duration=5, status="PENDING"):
    from propositions.models import Proposition
    return Proposition.objects.create(demande=demande, transporteur=transporteur, vehicle=vehicle,
                                      price=Decimal(price), estimated_duration=duration, status=status)
