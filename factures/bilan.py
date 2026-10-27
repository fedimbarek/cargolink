"""
Bilan de facturation: calculs exacts (Decimal) + analyse par règles + analyse IA optionnelle.
Les chiffres viennent TOUJOURS du code, jamais de l'IA.
"""
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from . import services
from .models import CENTIME, ZERO, Facture

S = Facture.Status
TRANCHES = ["Non échu", "1-30 j", "31-60 j", "61-90 j", "+90 j"]
DELAI_STANDARD_JOURS = 30


def _pct(a, b):
    return (Decimal(a) * 100 / Decimal(b)).quantize(Decimal("0.1")) if b else Decimal("0.0")


def _date_emission(f):
    return timezone.localtime(f.emise_le).date()


def _tranche(jours_retard):
    if jours_retard <= 0:
        return TRANCHES[0]
    if jours_retard <= 30:
        return TRANCHES[1]
    if jours_retard <= 60:
        return TRANCHES[2]
    if jours_retard <= 90:
        return TRANCHES[3]
    return TRANCHES[4]


def calculer_bilan(user, annee, mois=None):
    aujourdhui = timezone.localdate()
    visibles = list(services.factures_visibles(user))
    emises = [f for f in visibles if f.status in (S.EMISE, S.PARTIELLE, S.PAYEE)]
    de_lannee = [f for f in emises if _date_emission(f).year == annee]
    periode = [f for f in de_lannee if not mois or _date_emission(f).month == mois]

    # ---- totaux de la période
    ca_ht = sum((f.montant_ht for f in periode), ZERO)
    tva = sum((f.montant_tva for f in periode), ZERO)
    ttc = sum((f.total_ttc for f in periode), ZERO)
    paye = sum((f.total_paye for f in periode), ZERO)
    reste = ttc - paye

    # ---- créances à date (toutes périodes confondues) + balance âgée
    balance_agee = {t: ZERO for t in TRANCHES}
    creances = ZERO
    en_retard_montant = ZERO
    nb_en_retard = 0
    for f in emises:
        r = f.reste_a_payer
        if r <= 0:
            continue
        creances += r
        jours = (aujourdhui - f.date_echeance).days
        balance_agee[_tranche(jours)] += r
        if jours > 0:
            en_retard_montant += r
            nb_en_retard += 1

    # ---- délai moyen de paiement (factures soldées de la période)
    delais = []
    for f in periode:
        if f.status == S.PAYEE:
            dates = [p.date_paiement for p in f.paiements.all()]
            if dates:
                delais.append((max(dates) - _date_emission(f)).days)
    delai_moyen = (Decimal(sum(delais)) / len(delais)).quantize(Decimal("0.1")) if delais else None

    # ---- par partenaire (client pour un transporteur, fournisseur pour une PME)
    partenaires = defaultdict(lambda: {"ttc": ZERO, "paye": ZERO, "nb": 0})
    for f in periode:
        nom = f.transporteur.company_name if user.role == "PME" else f.pme.company_name
        d = partenaires[nom]
        d["ttc"] += f.total_ttc
        d["paye"] += f.total_paye
        d["nb"] += 1
    liste_partenaires = []
    for nom, d in sorted(partenaires.items(), key=lambda x: x[1]["ttc"], reverse=True):
        liste_partenaires.append({"nom": nom, **d, "reste": d["ttc"] - d["paye"], "part": _pct(d["ttc"], ttc)})

    # ---- évolution mensuelle (toute l'année choisie)
    mensuel = []
    for m in range(1, 13):
        fm = [f for f in de_lannee if _date_emission(f).month == m]
        mensuel.append({"mois": m,
                        "ht": sum((f.montant_ht for f in fm), ZERO),
                        "ttc": sum((f.total_ttc for f in fm), ZERO),
                        "paye": sum((f.total_paye for f in fm), ZERO)})

    return {
        "annee": annee, "mois": mois, "role": user.role,
        "nb_factures": len(periode),
        "nb_payees": sum(1 for f in periode if f.status == S.PAYEE),
        "nb_partielles": sum(1 for f in periode if f.status == S.PARTIELLE),
        "nb_brouillons": sum(1 for f in visibles if f.status == S.BROUILLON),
        "ca_ht": ca_ht, "tva": tva, "ttc": ttc, "paye": paye, "reste": reste,
        "taux_recouvrement": _pct(paye, ttc),
        "creances": creances, "en_retard_montant": en_retard_montant, "nb_en_retard": nb_en_retard,
        "part_retard": _pct(en_retard_montant, creances),
        "balance_agee": balance_agee, "delai_moyen": delai_moyen,
        "partenaires": liste_partenaires,
        "part_top_partenaire": liste_partenaires[0]["part"] if liste_partenaires else Decimal("0.0"),
        "mensuel": mensuel,
    }


def donnees_graphique(b):
    """Version float pour Chart.js."""
    return {
        "labels": ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"],
        "facture": [float(m["ttc"]) for m in b["mensuel"]],
        "encaisse": [float(m["paye"]) for m in b["mensuel"]],
        "age_labels": TRANCHES,
        "age_valeurs": [float(b["balance_agee"][t]) for t in TRANCHES],
    }


# ---------------------------------------------------------------- analyse par règles
def analyse_regles(b):
    """Diagnostic automatique façon expert-comptable. Retourne [{niveau, titre, texte}]."""
    r = []
    est_pme = b["role"] == "PME"

    if b["nb_factures"] == 0:
        return [{"niveau": "info", "titre": "Aucune facture sur la période",
                 "texte": "Il n'y a pas de facture émise pour la période choisie."}]

    t = b["taux_recouvrement"]
    if t >= 80:
        r.append({"niveau": "success", "titre": "Bon taux de recouvrement",
                  "texte": f"{t} % du montant facturé TTC est déjà réglé."})
    elif t >= 50:
        r.append({"niveau": "warning", "titre": "Recouvrement moyen",
                  "texte": f"Seulement {t} % est réglé. Restent {b['reste']} TND à encaisser."})
    else:
        r.append({"niveau": "danger", "titre": "Recouvrement faible",
                  "texte": f"Seulement {t} % est réglé: {b['reste']} TND restent impayés. Relancez les partenaires."})

    if b["nb_en_retard"]:
        niveau = "danger" if b["balance_agee"]["+90 j"] > 0 or b["part_retard"] > 30 else "warning"
        r.append({"niveau": niveau, "titre": "Factures en retard",
                  "texte": f"{b['nb_en_retard']} facture(s) échue(s), soit {b['en_retard_montant']} TND "
                           f"({b['part_retard']} % des créances). "
                           + ("Dont des impayés de plus de 90 jours: risque de créance douteuse." if b["balance_agee"]["+90 j"] > 0 else "")})
    else:
        r.append({"niveau": "success", "titre": "Aucun retard de paiement",
                  "texte": "Toutes les créances ouvertes sont dans les délais."})

    if b["delai_moyen"] is not None:
        niveau = "warning" if b["delai_moyen"] > DELAI_STANDARD_JOURS else "success"
        r.append({"niveau": niveau, "titre": "Délai moyen de paiement",
                  "texte": f"{b['delai_moyen']} jours entre émission et règlement final "
                           f"(délai standard: {DELAI_STANDARD_JOURS} j)."})

    if len(b["partenaires"]) > 1 and b["part_top_partenaire"] > 50:
        nom = "fournisseur" if est_pme else "client"
        r.append({"niveau": "warning", "titre": f"Dépendance à un seul {nom}",
                  "texte": f"Un seul {nom} représente {b['part_top_partenaire']} % du total: risque de concentration."})
    elif len(b["partenaires"]) == 1 and not est_pme:
        r.append({"niveau": "info", "titre": "Un seul client",
                  "texte": "Tout le chiffre d'affaires vient d'un seul client: diversifiez si possible."})

    if not est_pme:
        r.append({"niveau": "info", "titre": "TVA collectée",
                  "texte": f"{b['tva']} TND de TVA facturée sur la période: à reverser à l'État "
                           f"(déclaration), même si les factures ne sont pas encore payées."})
        if b["nb_brouillons"]:
            r.append({"niveau": "info", "titre": "Brouillons non émis",
                      "texte": f"{b['nb_brouillons']} facture(s) en brouillon: elles ne comptent pas dans le chiffre d'affaires."})
    return r


# ---------------------------------------------------------------- analyse IA (optionnelle)
SYSTEM_IA = (
    "Tu es un expert-comptable tunisien. On te donne des chiffres agrégés de facturation (en TND). "
    "Rédige en français, en moins de 250 mots: 1) un diagnostic de la situation, 2) les risques, "
    "3) trois actions concrètes classées par priorité. Utilise uniquement les chiffres fournis, "
    "n'en invente aucun. Si une information manque, dis-le. Pas de formatage markdown lourd."
)


def _resume_anonyme(b):
    """On n'envoie que des agrégats; les noms des partenaires sont remplacés par Partenaire 1, 2..."""
    return {
        "role": b["role"], "annee": b["annee"], "mois": b["mois"],
        "nb_factures": b["nb_factures"], "ca_ht": str(b["ca_ht"]), "tva": str(b["tva"]),
        "total_ttc": str(b["ttc"]), "encaisse": str(b["paye"]), "reste": str(b["reste"]),
        "taux_recouvrement_pct": str(b["taux_recouvrement"]),
        "creances_ouvertes": str(b["creances"]), "en_retard": str(b["en_retard_montant"]),
        "balance_agee": {k: str(v) for k, v in b["balance_agee"].items()},
        "delai_moyen_jours": None if b["delai_moyen"] is None else str(b["delai_moyen"]),
        "partenaires": [{"nom": f"Partenaire {i}", "part_pct": str(p["part"]), "reste": str(p["reste"])}
                        for i, p in enumerate(b["partenaires"][:5], 1)],
    }

def analyse_ia(b):
    """Retourne le texte de l'IA (Gemini), ou None si pas de clé / erreur."""
    cle = getattr(settings, "GEMINI_API_KEY", "")
    if not cle:
        return None
    try:
        import json
        import urllib.request

        modele = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"
        corps = {
            "systemInstruction": {"parts": [{"text": SYSTEM_IA}]},
            "contents": [{"role": "user",
                          "parts": [{"text": json.dumps(_resume_anonyme(b), ensure_ascii=False)}]}],
            "generationConfig": {"maxOutputTokens": 2000},
        }
        req = urllib.request.Request(
            url, data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": cle})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        parts = data["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception as e:
        print("ERREUR IA:", repr(e))      # na7iha ba3d ma tkhdem
        return None