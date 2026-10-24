/* Bouton « Utiliser le prix conseillé » (formulaire de proposition du transporteur). */
(function () {
  const b = document.getElementById("ia-utiliser");
  if (!b) return;
  b.addEventListener("click", function () {
    const champ = document.getElementById("id_price");
    if (champ) { champ.value = b.dataset.prix; champ.focus(); }
  });
})();
