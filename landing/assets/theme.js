/* Theme: prefers-color-scheme by default, explicit choice stored in localStorage ("light" | "dark"). */
(function () {
  var KEY = "recetario-landing-theme", d = document.documentElement;
  d.classList.add("js");
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function sys() { return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  function apply(t) {
    if (t) d.setAttribute("data-theme", t); else d.removeAttribute("data-theme");
    var eff = t || sys();
    var srcs = document.querySelectorAll("source[data-dark]");
    for (var i = 0; i < srcs.length; i++) srcs[i].media = t ? (t === "dark" ? "all" : "not all") : "(prefers-color-scheme: dark)";
    var b = document.getElementById("themeBtn"); if (b) b.setAttribute("aria-pressed", eff === "dark" ? "true" : "false");
  }
  apply(stored());
  document.addEventListener("DOMContentLoaded", function () {
    apply(stored());
    var b = document.getElementById("themeBtn"); if (!b) return;
    b.addEventListener("click", function () {
      var next = (stored() || sys()) === "dark" ? "light" : "dark";
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
  });
})();
