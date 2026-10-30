/* Landing demo boot (replaces the app's inline theme script, which the CSP blocks).
   - language from ?lang= (the English landing embeds ?lang=en), theme from the landing page or the system
   - view preferences start fresh on every load, like the rest of the demo (nothing is kept) */
(function () {
  var q = new URLSearchParams(location.search), t = null;
  try {
    ["vistaLista", "interfaz", "miniaturas", "densidadMovil", "tema"].forEach(function (k) { localStorage.removeItem(k); });
    localStorage.setItem("lang", q.get("lang") === "en" ? "en" : "es");
  } catch (e) {}
  try { if (parent !== window) t = parent.document.documentElement.getAttribute("data-theme"); } catch (e) {}
  if (!t) t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t;
  if (!location.hash) history.replaceState(null, "", location.pathname + location.search + "#/recetas");
})();
