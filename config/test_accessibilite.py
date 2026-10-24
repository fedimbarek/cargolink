"""
Audit d'accessibilité automatisé (règles WCAG 2.1 vérifiables sans navigateur) sur toutes les pages principales,
pour chaque rôle. Complète l'audit manuel Lighthouse / axe / navigation clavier (voir docs/ACCESSIBILITE.md).
"""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from users.testing import (RAPIDE, make_demande, make_pme, make_proposition, make_transporteur, make_user,
                           make_vehicle)


class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings, self.erreurs = [], []
        self.ids, self.labels_for, self.champs = set(), set(), []
        self.h1 = self.main = self.skip = False
        self.lang = None
        self.pile = []                      # (tag, attrs, texte)
        self.tables, self.captions = 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        elif tag == "main":
            self.main = True
        elif tag == "a" and "skip-link" in (a.get("class") or ""):
            self.skip = True
        elif tag == "img" and "alt" not in a:
            self.erreurs.append("image sans attribut alt")
        elif tag == "label" and a.get("for"):
            self.labels_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            if a.get("type") not in ("hidden", "submit", "button"):
                self.champs.append((tag, a))
        elif tag == "table":
            self.tables += 1
        elif tag == "caption":
            self.captions += 1
        elif tag == "th" and not a.get("scope"):
            self.erreurs.append("th sans scope")
        elif tag == "nav" and not (a.get("aria-label") or a.get("aria-labelledby")):
            self.erreurs.append("nav sans nom accessible")
        if tag in ("a", "button"):
            self.pile.append([tag, a, ""])

    def handle_data(self, data):
        for p in self.pile:
            p[2] += data

    def handle_endtag(self, tag):
        if tag in ("a", "button") and self.pile:
            t, a, texte = self.pile.pop()
            if not (texte.strip() or a.get("aria-label") or a.get("title")):
                self.erreurs.append(f"<{t}> sans texte ni aria-label")

    def verifier(self):
        e = list(self.erreurs)
        if self.lang != "fr":
            e.append("attribut lang manquant ou incorrect")
        if not self.main:
            e.append("pas de landmark <main>")
        if not self.skip:
            e.append("pas de lien d'évitement")
        if self.headings.count(1) != 1:
            e.append(f"{self.headings.count(1)} balise(s) h1 (1 attendue)")
        for prec, cour in zip(self.headings, self.headings[1:]):
            if cour > prec + 1:
                e.append(f"saut de niveau de titre h{prec} -> h{cour}")
        for tag, a in self.champs:
            if not (a.get("aria-label") or (a.get("id") and a["id"] in self.labels_for)):
                e.append(f"champ <{tag} name={a.get('name')}> sans label associé")
        if self.tables != self.captions:
            e.append("tableau sans <caption>")
        return e


def auditer(testcase, response, url):
    a = Audit()
    a.feed(response.content.decode())
    problemes = a.verifier()
    testcase.assertEqual(problemes, [], f"{url}: {problemes}")


@RAPIDE
class AccessibiliteTests(TestCase):
    def setUp(self):
        self.u_pme, self.pme = make_pme()
        self.u_t, self.t = make_transporteur()
        self.u_admin = make_user("adm", "ADMIN")
        v = make_vehicle(self.t)
        self.d = make_demande(self.pme)
        make_proposition(self.d, self.t, v)
        self.d_libre = make_demande(self.pme)          # demande sans proposition (page « proposer »)

    def pages(self, user):
        d = self.d.pk
        communes = [reverse("dashboard"), reverse("annonces:liste"), reverse("annonces:detail", args=[d]),
                    reverse("factures:liste"), reverse("ia:modele"), "/page-inexistante/"]
        if user == self.u_pme:
            return communes + [reverse("annonces:creer"), reverse("propositions:recues"), reverse("propositions:comparer", args=[d]),
                               reverse("meteo:alertes")]
        if user == self.u_t:
            return communes + [reverse("propositions:vehicules"), reverse("propositions:mes_propositions"),
                               reverse("propositions:matching"), reverse("propositions:proposer", args=[self.d_libre.pk]),
                               reverse("meteo:alertes")]
        return [reverse("dashboard")]

    def test_pages_publiques(self):
        for url in (reverse("login_page"), reverse("register_page")):
            auditer(self, self.client.get(url), url)

    def test_pages_pme(self):
        self.client.force_login(self.u_pme)
        for url in self.pages(self.u_pme):
            r = self.client.get(url)
            self.assertIn(r.status_code, (200, 404), url)       # une page inattendue (403/302) ne doit pas être ignorée
            auditer(self, r, url)

    def test_pages_transporteur(self):
        self.client.force_login(self.u_t)
        for url in self.pages(self.u_t):
            r = self.client.get(url)
            self.assertIn(r.status_code, (200, 404), url)       # une page inattendue (403/302) ne doit pas être ignorée
            auditer(self, r, url)

    def test_page_admin(self):
        self.client.force_login(self.u_admin)
        auditer(self, self.client.get(reverse("dashboard")), "dashboard admin")


class AuditSelfTest(TestCase):
    """Vérifie que l'audit détecte bien de vrais défauts (sinon il ne prouverait rien)."""

    def test_detecte_les_defauts(self):
        a = Audit()
        a.feed('<html><body><nav></nav><h1>a</h1><h1>b</h1><h4>c</h4><img src="x"><input id="q" name="q">'
               '<button></button><table><tr><th>x</th></tr></table></body></html>')
        texte = " ".join(a.verifier())
        for attendu in ("lang", "main", "évitement", "2 balise(s) h1", "saut de niveau", "alt", "sans label",
                        "sans texte", "scope", "caption", "nav sans nom"):
            self.assertIn(attendu, texte)
