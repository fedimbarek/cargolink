/* Estimation de prix par IA depuis le formulaire de création d'une demande.
   - POST /ia/estimer/ ; si le serveur répond 202 (Celery/Redis actif), on interroge /ia/tache/<id>/ jusqu'au résultat.
   - Retour utilisateur : indicateur de chargement (aria-busy + texte), message d'erreur explicite (role="alert"). */
(function () {
  const btn = document.getElementById("ia-estimer");
  if (!btn) return;
  const statut = document.getElementById("ia-statut");
  const erreur = document.getElementById("ia-erreur");
  const resultat = document.getElementById("ia-resultat");
  const spinner = document.getElementById("ia-spinner");
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const val = (id) => (document.getElementById(id) || {}).value || "";

  function afficherErreur(msg) {
    erreur.textContent = msg;
    erreur.hidden = false;
  }
  function charge(actif, texte) {
    btn.disabled = actif;
    btn.setAttribute("aria-busy", actif ? "true" : "false");
    spinner.hidden = !actif;
    statut.textContent = actif ? texte : "";
  }
  function afficher(e) {
    document.getElementById("ia-prix").textContent = e.prix.toLocaleString("fr-FR") + " TND";
    document.getElementById("ia-fourchette").textContent =
      "fourchette probable : " + e.bas.toLocaleString("fr-FR") + " à " + e.haut.toLocaleString("fr-FR") + " TND";
    document.getElementById("ia-detail").textContent =
      "Distance " + e.distance_km + " km (~" + e.duree_h + " h), soit " + e.prix_km + " TND/km. Catégorie : " +
      e.categorie + ". Calculé en " + e.temps_ms + " ms par le modèle « " + e.modele + " ».";
    resultat.hidden = false;
  }
  async function attendre(taskId, essais) {
    for (let i = 0; i < essais; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      const rep = await fetch(btn.dataset.pollUrl.replace("TASK", encodeURIComponent(taskId)), { credentials: "same-origin" });
      const data = await rep.json();
      if (data.etat === "TERMINE") return data;
      if (data.etat === "ECHEC") throw new Error(data.erreur || "Le calcul a échoué.");
    }
    throw new Error("Le calcul prend trop de temps, réessayez.");
  }

  btn.addEventListener("click", async function () {
    erreur.hidden = true;
    resultat.hidden = true;
    const origin = val("id_origin").trim(), destination = val("id_destination").trim(), weight = val("id_weight");
    if (!origin || !destination || !weight) {
      afficherErreur("Renseignez l'origine, la destination et le poids pour obtenir une estimation.");
      return;
    }
    const pickup = new Date(val("id_pickup_date"));
    const urgent = !isNaN(pickup) && pickup - new Date() < 48 * 3600 * 1000;
    charge(true, "Calcul de l'estimation en cours…");
    try {
      const rep = await fetch(btn.dataset.url, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ origin, destination, weight, volume: val("id_volume"), cargo_type: val("id_cargo_type"), urgent }),
      });
      let data = await rep.json();
      if (rep.status === 202) data = await attendre(data.task_id, 40);
      else if (!rep.ok) throw new Error(data.erreur || "Estimation impossible.");
      afficher(data.estimation);
    } catch (e) {
      afficherErreur(e.message || "Service d'estimation indisponible, réessayez plus tard.");
    } finally {
      charge(false);
    }
  });
})();
