import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_reservation_details(apps, _schema_editor):
    Reservation = apps.get_model("reservations", "Reservation")
    for reservation in Reservation.objects.select_related(
        "proposition__demande__pme__user", "proposition__transporteur"
    ).iterator():
        pme = reservation.proposition.demande.pme
        reservation.user_id = pme.user_id
        reservation.transporteur_id = reservation.proposition.transporteur_id
        reservation.nom_contact = pme.user.username
        reservation.email_contact = pme.user.email
        reservation.nom_societe = pme.company_name
        reservation.matricule = pme.registration_number
        reservation.adresse = pme.address
        reservation.telephone = pme.phone
        reservation.save(update_fields=[
            "user", "transporteur", "nom_contact", "email_contact",
            "nom_societe", "matricule", "adresse", "telephone",
        ])


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0002_alter_notification_user"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="user",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="transporteur",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations", to="users.transporteur",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="nom_contact",
            field=models.CharField(max_length=150, null=True, verbose_name="Nom du contact"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="email_contact",
            field=models.EmailField(max_length=254, null=True, verbose_name="Email de contact"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="nom_societe",
            field=models.CharField(max_length=150, null=True, verbose_name="Société"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="matricule",
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name="Matricule / registre"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="adresse",
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name="Adresse"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="telephone",
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name="Téléphone"),
        ),
        migrations.RunPython(populate_reservation_details, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="reservation",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="transporteur",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reservations", to="users.transporteur",
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="nom_contact",
            field=models.CharField(max_length=150, verbose_name="Nom du contact"),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="email_contact",
            field=models.EmailField(max_length=254, verbose_name="Email de contact"),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="nom_societe",
            field=models.CharField(max_length=150, verbose_name="Société"),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="matricule",
            field=models.CharField(blank=True, max_length=50, verbose_name="Matricule / registre"),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="adresse",
            field=models.CharField(blank=True, max_length=255, verbose_name="Adresse"),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="telephone",
            field=models.CharField(blank=True, max_length=20, verbose_name="Téléphone"),
        ),
    ]
