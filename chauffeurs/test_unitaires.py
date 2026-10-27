from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from .forms import ChauffeurForm, PermisForm
from .models import Permis


class TestsUnitaires(SimpleTestCase):
    def test_permis_expire(self):
        permis = Permis(
            date_expiration=timezone.localdate() - timedelta(days=1)
        )

        self.assertTrue(permis.est_expire)

    def test_permis_valide(self):
        permis = Permis(
            date_expiration=timezone.localdate() + timedelta(days=1)
        )

        self.assertFalse(permis.est_expire)

    def test_permis_expire_aujourdhui_reste_valide(self):
        permis = Permis(
            date_expiration=timezone.localdate()
        )

        self.assertFalse(permis.est_expire)

    def test_nom_obligatoire(self):
        form = ChauffeurForm(data={
            "prenom": "Ahmed",
            "telephone": "22123456",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("nom", form.errors)

    def test_date_invalide(self):
        champ = PermisForm().fields["date_expiration"]

        with self.assertRaises(ValidationError):
            champ.clean("pas une date")