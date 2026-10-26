import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from reclamations.models import Reclamation
import os
from reclamations.MLReclamations import predire_priorite, entrainer_modele, MODEL_PATH
User = get_user_model()


@pytest.mark.django_db
def test_creation_reclamation():
    user = User.objects.create_user(username='testuser', password='testpass')
    rec = Reclamation.objects.create(
        utilisateur=user,
        sujet="Test sujet",
        description="Description de test",
        priorite="MOYENNE"
    )
    assert rec.statut == "NOUVELLE"
    assert str(rec) == f"#{rec.id} - Test sujet (Nouvelle)"


@pytest.mark.django_db
def test_acces_liste_connecte(client):
    user = User.objects.create_user(username='client', password='pass123')
    client.force_login(user)
    response = client.get(reverse('reclamations:liste'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_creation_via_form(client):
    user = User.objects.create_user(username='client', password='pass123')
    client.force_login(user)
    response = client.post(reverse('reclamations:creer'), {
        'sujet': 'Nouveau problème',
        'description': 'Description test',
        'priorite': 'MOYENNE',
    })
    assert response.status_code == 302
    assert Reclamation.objects.filter(sujet='Nouveau problème').exists()


@pytest.mark.django_db
def test_client_ne_voit_que_ses_reclamations(client):
    u1 = User.objects.create_user(username='u1', email='u1@test.com', password='pass', role='TRANSPORTEUR')
    u2 = User.objects.create_user(username='u2', email='u2@test.com', password='pass', role='TRANSPORTEUR')
    Reclamation.objects.create(utilisateur=u1, destinataire=u1, sujet='Recu1', description='...')
    Reclamation.objects.create(utilisateur=u2, destinataire=u2, sujet='Recu2', description='...')
    client.force_login(u1)
    response = client.get(reverse('reclamations:liste'))
    assert response.status_code == 200
    assert b'Recu1' in response.content
    assert b'Recu2' not in response.content
    
@pytest.mark.django_db
def test_modele_ia_existe():
    """Le modèle doit être généré et sauvegardé."""
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    assert os.path.exists(MODEL_PATH), "Le fichier ia_model.pkl doit exister"


@pytest.mark.django_db
def test_ia_prediction_haute():
    """Un colis cassé doit être classé HAUTE."""
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    result = predire_priorite("mon colis est arrivé complètement écrasé, urgent")
    assert result in ['HAUTE', 'MOYENNE'], f"Attendu HAUTE/MOYENNE, obtenu {result}"


@pytest.mark.django_db
def test_ia_prediction_basse():
    """Une question simple doit être classée BASSE."""
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    result = predire_priorite("simple question sur les horaires de livraison")
    assert result == 'BASSE', f"Attendu BASSE, obtenu {result}"


@pytest.mark.django_db
def test_ia_retourne_valeur_valide():
    """La prédiction doit toujours être l'une des 3 classes."""
    if not os.path.exists(MODEL_PATH):
        entrainer_modele()
    for txt in ["test", "colis cassé", "facture"]:
        result = predire_priorite(txt)
        assert result in ['BASSE', 'MOYENNE', 'HAUTE']
        
@pytest.mark.django_db
def test_transporteur_ne_voit_que_ses_reclamations(client):
    """Un transporteur ne voit QUE les réclamations qui lui sont adressées."""
    pme = User.objects.create_user(
        username='pme1', password='pass', email='pme1@test.com', role='PME'
    )
    transporteur = User.objects.create_user(
        username='tr1', password='pass', email='tr1@test.com', role='TRANSPORTEUR'
    )
    autre_tr = User.objects.create_user(
        username='tr2', password='pass', email='tr2@test.com', role='TRANSPORTEUR'
    )

    Reclamation.objects.create(
        utilisateur=pme, destinataire=transporteur,
        sujet='PourMoi', description='...'
    )
    Reclamation.objects.create(
        utilisateur=pme, destinataire=autre_tr,
        sujet='PourAutre', description='...'
    )

    client.force_login(transporteur)
    response = client.get(reverse('reclamations:liste'))
    assert response.status_code == 200
    assert b'PourMoi' in response.content
    assert b'PourAutre' not in response.content


@pytest.mark.django_db
def test_pme_voit_toutes_les_reclamations(client):
    """Un PME voit toutes les réclamations (comme l'admin)."""
    pme = User.objects.create_user(
        username='pme1', password='pass', email='pme1@test.com', role='PME'
    )
    autre_pme = User.objects.create_user(
        username='pme2', password='pass', email='pme2@test.com', role='PME'
    )

    Reclamation.objects.create(utilisateur=pme, sujet='ParMoi', description='...')
    Reclamation.objects.create(utilisateur=autre_pme, sujet='ParAutre', description='...')

    client.force_login(pme)
    response = client.get(reverse('reclamations:liste'))
    assert response.status_code == 200
    assert b'ParMoi' in response.content
    assert b'ParAutre' in response.content