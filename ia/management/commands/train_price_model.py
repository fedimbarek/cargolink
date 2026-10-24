from django.core.management.base import BaseCommand

from ia import ml


class Command(BaseCommand):
    help = "Entraîne le modèle d'estimation de prix, affiche les métriques et sauvegarde le modèle (ia/artifacts)."

    def add_arguments(self, parser):
        parser.add_argument("--n", type=int, default=3000, help="Nombre de lignes synthétiques (défaut 3000)")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--sans-reelles", action="store_true",
                            help="Ne pas ajouter les propositions acceptées de la base")

    def handle(self, *args, **options):
        m = ml.entrainer(n_synthetiques=options["n"], seed=options["seed"],
                         avec_reelles=not options["sans_reelles"])
        d = m["donnees"]
        self.stdout.write(f"Données : {d['synthetiques']} synthétiques + {d['reelles']} réelles "
                          f"(train {d['train']} / calibration {d['calibration']} / test {d['test']})")
        self.stdout.write(f"{'Modèle':<22}{'CV RMSE(log)':>13}{'MAE':>9}{'RMSE':>9}{'R²':>8}{'MAPE %':>8}")
        for r in m["modeles"]:
            self.stdout.write(f"{r['nom']:<22}{r['cv_rmse_log']:>13}{r['test_mae']:>9}{r['test_rmse']:>9}"
                              f"{r['test_r2']:>8}{r['test_mape']:>8}")
        t = m["test_retenu"]
        self.stdout.write(self.style.SUCCESS(
            f"Modèle retenu : {m['retenu']} | test : MAE {t['mae']} TND, RMSE {t['rmse']} TND, "
            f"R² {t['r2']}, MAPE {t['mape']} %"))
        i = m["intervalle"]
        self.stdout.write(f"Intervalle à {int(i['niveau'] * 100)} % : couverture réelle sur le test = "
                          f"{i['couverture_test'] * 100:.1f} %")
        self.stdout.write(f"Latence d'inférence : {m['latence']['moyenne_ms']} ms en moyenne "
                          f"(p95 {m['latence']['p95_ms']} ms)")
