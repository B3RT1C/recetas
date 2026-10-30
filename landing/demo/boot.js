/* Landing demo boot: theme follows the landing page (or the system), replaces the app's inline theme script (CSP). */
(function () {
  var t = null;
  try { if (parent !== window) t = parent.document.documentElement.getAttribute("data-theme"); } catch (e) {}
  if (!t) t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t;
  if (!location.hash) history.replaceState(null, "", "#/recetas");
})();
