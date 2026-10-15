"""
Logique métier du module factures.
  - creer_facture()          : seulement pour une proposition acceptée (demande assignée/en cours/livrée),
                               une seule facture par proposition
  - emettre() / annuler()    : changement d'état de la facture
  - enregistrer_paiement() / modifier_paiement() / supprimer_paiement()
        le statut de la facture (EMISE / PARTIELLE / PAYEE) est recalculé automatiquement
  - supprimer_facture()      : seulement un brouillon ou une facture annulée
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from annonces.models import DemandeTransport
from propositions.models import Proposition

from .models import ZERO, Facture, Paiement

S = Facture.Status
TVA_DEFAUT = Decimal("19")
DELAI_DEFAUT_JOURS = 30


class ErreurFacture(Exception):
    """Règle métier non respectée (message affichable à l'utilisateur)."""


def factures_visibles(user):
    """Transporteur: ses factures. PME: factures reçues (jamais les brouillons). Admin: tout."""
    qs = (Facture.objects
          .select_related("proposition__demande__pme", "proposition__transporteur")
          .prefetch_related("paiements"))
    if user.role == "TRANSPORTEUR":
        return qs.filter(proposition__transporteur__user=user)
    if user.role == "PME":
        return qs.filter(proposition__demande__pme__user=user).exclude(status=S.BROUILLON)
    if user.role == "ADMIN" or user.is_superuser:
        return qs
    return qs.none()


def _verrouiller(facture):
    return Facture.objects.select_for_update().get(pk=facture.pk)


def echeance_par_defaut():
    return timezone.localdate() + timedelta(days=DELAI_DEFAUT_JOURS)


# Une facture n'est autorisée que pour une mission déjà livrée.
STATUTS_FACTURABLES = (DemandeTransport.Status.DELIVERED,)


def est_facturable(proposition):
    """Mission facturable = proposition ACCEPTÉE et demande assignée / en cours / livrée."""
    return (proposition.status == Proposition.Status.ACCEPTED
            and proposition.demande.status in STATUTS_FACTURABLES)


def propositions_a_facturer(transporteur_user):
    """Missions acceptées de ce transporteur qui n'ont pas encore de facture."""
    return (Proposition.objects
            .filter(transporteur__user=transporteur_user, status=Proposition.Status.ACCEPTED,
                    demande__status__in=STATUTS_FACTURABLES, facture__isnull=True)
            .select_related("demande")
            .order_by("-id"))


@transaction.atomic
def creer_facture(proposition, date_echeance, taux_tva=TVA_DEFAUT, notes="", montant_ht=None):
    if not est_facturable(proposition):
        raise ErreurFacture("Cette mission n'est pas facturable (la proposition doit être acceptée).")
    if Facture.objects.filter(proposition=proposition).exists():
        raise ErreurFacture("Cette mission a déjà une facture.")
    return Facture.objects.create(
        proposition=proposition, date_echeance=date_echeance, taux_tva=taux_tva, notes=notes,
        montant_ht=proposition.price if montant_ht is None else montant_ht)


@transaction.atomic
def emettre(facture):
    f = _verrouiller(facture)
    if not f.peut_emettre:
        raise ErreurFacture("Seul un brouillon peut être émis.")
    f.status, f.emise_le = S.EMISE, timezone.now()
    f.save(update_fields=["status", "emise_le"])
    return f


@transaction.atomic
def annuler(facture):
    f = _verrouiller(facture)
    if not f.peut_annuler:
        raise ErreurFacture("Cette facture ne peut plus être annulée (paiement enregistré ou déjà annulée).")
    f.status = S.ANNULEE
    f.save(update_fields=["status"])
    return f


@transaction.atomic
def supprimer_facture(facture):
    f = _verrouiller(facture)
    if not f.est_supprimable:
        raise ErreurFacture("Seul un brouillon ou une facture annulée peut être supprimée.")
    f.delete()


# ---------------- paiements ----------------
def verifier_montant(facture, montant, exclure=None):
    """Le montant doit être positif et ne pas dépasser le reste à payer."""
    if montant is None or montant <= 0:
        raise ErreurFacture("Le montant doit être positif.")
    deja = sum((p.montant for p in facture.paiements.all() if not exclure or p.pk != exclure.pk), ZERO)
    reste = facture.total_ttc - deja
    if montant > reste:
        raise ErreurFacture(f"Le montant dépasse le reste à payer ({reste} TND).")


def recalculer_statut(facture):
    if facture.status in (S.BROUILLON, S.ANNULEE):
        return facture
    paye = facture.total_paye
    facture.status = S.PAYEE if paye >= facture.total_ttc else S.PARTIELLE if paye > 0 else S.EMISE
    facture.save(update_fields=["status"])
    return facture


@transaction.atomic
def enregistrer_paiement(facture, montant, date_paiement=None, mode=Paiement.Mode.VIREMENT,
                         reference="", user=None):
    f = _verrouiller(facture)
    if not f.accepte_paiements:
        raise ErreurFacture("Un paiement ne peut être enregistré que sur une facture émise et non soldée.")
    verifier_montant(f, montant)
    p = Paiement.objects.create(facture=f, montant=montant, date_paiement=date_paiement or timezone.localdate(),
                                mode=mode, reference=reference, enregistre_par=user)
    recalculer_statut(f)
    return p


@transaction.atomic
def modifier_paiement(paiement, **champs):
    f = _verrouiller(paiement.facture)
    if not f.paiements_modifiables:
        raise ErreurFacture("Les paiements de cette facture ne sont plus modifiables.")
    verifier_montant(f, champs.get("montant", paiement.montant), exclure=paiement)
    for cle, valeur in champs.items():
        setattr(paiement, cle, valeur)
    paiement.save()
    recalculer_statut(f)
    return paiement


@transaction.atomic
def supprimer_paiement(paiement):
    f = _verrouiller(paiement.facture)
    if not f.paiements_modifiables:
        raise ErreurFacture("Les paiements de cette facture ne sont plus modifiables.")
    paiement.delete()
    recalculer_statut(f)