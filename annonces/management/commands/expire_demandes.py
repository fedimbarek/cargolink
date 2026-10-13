from django.core.management.base import BaseCommand
from django.utils import timezone

from annonces.models import DemandeTransport


class Command(BaseCommand):
    help = "Passe en EXPIREE les demandes ouvertes dont la date de chargement est dépassée."

    def handle(self, *args, **options):
        demandes = DemandeTransport.objects.filter(
            status=DemandeTransport.Status.OPEN, pickup_date__lt=timezone.now())
        n = 0
        for d in demandes:
            d.expirer()
            n += 1
        self.stdout.write(self.style.SUCCESS(f"{n} demande(s) expirée(s)."))