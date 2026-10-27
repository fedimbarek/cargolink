from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def classer_profils(profils, mission):
    """Comparer des textes. Le score est une similarité, pas une probabilité."""
    if not profils or not mission.strip():
        return []

    modele = TfidfVectorizer(strip_accents="unicode", ngram_range=(1, 2))
    try:
        historique = modele.fit_transform(profils)
    except ValueError:
        return []

    demande = modele.transform([mission])
    scores = cosine_similarity(demande, historique)[0]
    classement = [
        (indice, float(score))
        for indice, score in enumerate(scores) if score > 0
    ]
    return sorted(classement, key=lambda ligne: ligne[1], reverse=True)


def texte_demande(demande):
    return f"{demande.origin} {demande.destination} {demande.cargo_type}"


def recommander(transporteur, proposition):
    from django.utils import timezone
    from .models import Affectation, Chauffeur

    candidats = list(Chauffeur.objects.filter(
        transporteur=transporteur,
        disponible=True,
        permis__date_expiration__gte=timezone.localdate(),
    ).order_by("pk"))

    historiques = Affectation.objects.filter(
        chauffeur__in=candidats,
        proposition__transporteur=transporteur,
        proposition__demande__status="DELIVERED",
    ).exclude(
        proposition__demande_id=proposition.demande_id
    ).select_related("proposition__demande")

    textes = {chauffeur.pk: [] for chauffeur in candidats}
    for affectation in historiques:
        textes[affectation.chauffeur_id].append(
            texte_demande(affectation.proposition.demande)
        )

    profils = [" ".join(textes[c.pk]) for c in candidats]
    classement = classer_profils(profils, texte_demande(proposition.demande))
    return [
        {"chauffeur": candidats[indice], "score": round(score, 3)}
        for indice, score in classement
    ]