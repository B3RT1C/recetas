/* Landing interactivity: hero simulators (real app in /demo/ with a guided tour), screenshot carousel, feature cards, lightbox, price calculator, scroll reveal. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var T = JSON.parse(document.body.getAttribute("data-i18n") || "{}"), LANG = document.body.getAttribute("data-lang") || "es";
  var D = window.RC_DATA || { r: [], plan: [] }, byId = {};
  D.r.forEach(function (r) { byId[r.id] = r; });
  function eur(x) { var v = x.toFixed(2); return LANG === "es" ? v.replace(".", ",") + " €" : "€" + v; }

  var RM = matchMedia("(prefers-reduced-motion: reduce)");

  /* ---- hero simulators: the real app (/demo/, sample data, in-memory mock API) inside the frames ---- */
  var screens = $$(".mscreen"), frames = [];
  function effTheme() { var t = document.documentElement.getAttribute("data-theme"); return t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); }
  function fit(sc) {
    var f = $("iframe", sc), w = +sc.getAttribute("data-w"), k = sc.clientWidth / w;
    sc.style.setProperty("--k", k); f.style.height = (sc.clientHeight / k) + "px";
  }
  if ("ResizeObserver" in window) { var ro = new ResizeObserver(function (es) { es.forEach(function (e) { fit(e.target); }); }); screens.forEach(function (sc) { ro.observe(sc); }); }
  else screens.forEach(fit);
  function syncTheme() { frames.forEach(function (F) { try { F.f.contentDocument.documentElement.dataset.theme = effTheme(); } catch (e) {} }); }
  new MutationObserver(syncTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncTheme);

  /* guided tour: real clicks and typing inside the same-origin app; a ring shows each tap */
  var Q = T.mk_search_demo || "paella";
  var TOURS = {
    desk: [[0, "go", "#/recetas"], [1800, "type", "#q", Q], [3600, "tap", 'a[href="#/receta/10"]'], [6200, "tap", "#plus"], [7400, "tap", "#plus"],
      [8800, "scroll", 330], [11000, "tap", '#nav a[href="#/planificador"]'], [14500, "tap", '#nav a[href="#/compra"]'], [16500, "tap", "input[data-buy]"],
      [17600, "tap", "li:nth-of-type(2) input[data-buy]"], [19500, "scroll", 260], [21500, "tap", '#nav a[href="#/ajustes"]'], [24000, "type", "#q", ""], [24500, "end"]],
    phone: [[0, "go", "#/recetas"], [2600, "scroll", 240], [4200, "tap", 'a[href="#/receta/4"]'], [6600, "scroll", 420], [8200, "tap", "#plus"],
      [10000, "tap", '#tabbar a[href="#/planificador"]'], [12400, "scroll", 300], [14200, "tap", '#tabbar a[href="#/compra"]'], [16200, "tap", "input[data-buy]"],
      [18600, "tap", '#tabbar a[href="#/recetas"]'], [21500, "end"]]
  };
  var tb = $("#tourbtn"), userOff = RM.matches, vis = true;
  function setBtn() { if (!tb) return; tb.classList.toggle("off", userOff); $("span", tb).textContent = tb.getAttribute(userOff ? "data-play" : "data-pause"); }
  function running(F) { return !userOff && vis && !document.hidden && Date.now() > F.hold; }
  function ring(F, el) {
    var r = el.getBoundingClientRect(), k = F.f.getBoundingClientRect().width / F.w, t = F.tap;
    t.style.left = (r.left + r.width / 2) * k + "px"; t.style.top = (r.top + r.height / 2) * k + "px";
    t.classList.remove("on"); void t.offsetWidth; t.classList.add("on");
  }
  function act(F, s) {
    var w = F.f.contentWindow, d = F.f.contentDocument; if (!d || !w.API) return;
    if (s[1] === "go") { if (w.location.hash !== s[2]) w.location.hash = s[2]; else w.scrollTo(0, 0); return; }
    if (s[1] === "scroll") { w.scrollBy({ top: s[2], behavior: "smooth" }); return; }
    var el = d.querySelector(s[2]); if (!el) return;
    if (s[1] === "type") {
      var i = 0; el.value = "";
      if (!s[3]) { el.dispatchEvent(new w.Event("input", { bubbles: true })); return; }
      (function next() { if (!running(F)) return; el.value = s[3].slice(0, ++i); el.dispatchEvent(new w.Event("input", { bubbles: true })); if (i < s[3].length) setTimeout(next, 110); })();
      return;
    }
    if (el.getBoundingClientRect().bottom > w.innerHeight || el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "center" });
    ring(F, el); el.click();
  }
  function tick(F) {
    clearTimeout(F.t); if (!running(F)) return;
    var s = F.steps[F.i];
    if (s[1] === "end") { F.i = 0; F.t = setTimeout(function () { tick(F); }, 600); return; }
    act(F, s); F.i++;
    F.t = setTimeout(function () { tick(F); }, F.steps[F.i][0] - s[0]);
  }
  function resumeAll() { frames.forEach(function (F) { clearTimeout(F.t); F.t = setTimeout(function () { tick(F); }, 400); }); }
  screens.forEach(function (sc) {
    var f = $("iframe", sc), tap = document.createElement("span"); tap.className = "mtap"; tap.setAttribute("aria-hidden", "true"); sc.appendChild(tap);
    var F = { f: f, w: +sc.getAttribute("data-w"), tap: tap, steps: TOURS[f.getAttribute("data-tour")], i: 0, hold: 0, t: 0 };
    frames.push(F);
    f.addEventListener("load", function () {
      try {
        var d = f.contentDocument; d.documentElement.dataset.theme = effTheme();
        ["pointerdown", "keydown", "wheel", "touchstart"].forEach(function (ev) { d.addEventListener(ev, function (e) { if (e.isTrusted) { F.hold = Date.now() + 25000; clearTimeout(F.t); F.t = setTimeout(function () { tick(F); }, 25200); } }, { passive: true }); });
      } catch (e) {}
      F.i = 0; clearTimeout(F.t); F.t = setTimeout(function () { tick(F); }, 1200);
    });
  });
  if (tb) tb.addEventListener("click", function () { userOff = !userOff; setBtn(); frames.forEach(function (F) { F.hold = 0; }); resumeAll(); });
  setBtn();
  if ("IntersectionObserver" in window && screens.length) new IntersectionObserver(function (es) { vis = es[0].isIntersecting; resumeAll(); }).observe($(".shots"));
  document.addEventListener("visibilitychange", resumeAll);

  /* ---- screenshot carousel: native scroll-snap (swipe/trackpad), arrows, dots, autoplay ---- */
  $$(".car").forEach(function (car) {
    var tr = $(".car-track", car), sl = $$(".car-s", tr), dots = $$(".car-dot", car), cp = $(".car-play", car), ci = 0, ct = 0, cOff = RM.matches, hov = false, cvis = false;
    var shown = function () { return tr.offsetParent !== null; };
    var left = function (n) { return sl[n].offsetLeft - tr.offsetLeft - (tr.clientWidth - sl[n].offsetWidth) / 2; };
    var idx = function () { var b = 0, d = Infinity; sl.forEach(function (s, n) { var x = Math.abs(left(n) - tr.scrollLeft); if (x < d) { d = x; b = n; } }); return b; };
    function go(i, smooth) { ci = (i + sl.length) % sl.length; tr.scrollTo({ left: left(ci), behavior: smooth === false || RM.matches ? "auto" : "smooth" }); mark(); }
    function mark() { dots.forEach(function (d, n) { if (n === ci) d.setAttribute("aria-current", "true"); else d.removeAttribute("aria-current"); }); sl.forEach(function (s, n) { s.setAttribute("aria-hidden", n !== ci); $$("button", s).forEach(function (b) { b.tabIndex = n === ci ? 0 : -1; }); }); }
    function plan() { clearTimeout(ct); if (!cOff && !hov && cvis && shown() && !document.hidden) ct = setTimeout(function () { go(ci + 1); plan(); }, 5500); }
    function setP() { cp.classList.toggle("off", cOff); cp.setAttribute("aria-label", cp.getAttribute(cOff ? "data-play" : "data-pause")); }
    var st; tr.addEventListener("scroll", function () { clearTimeout(st); st = setTimeout(function () { var n = idx(); if (n !== ci) { ci = n; mark(); plan(); } }, 90); }, { passive: true });
    $(".car-prev", car).addEventListener("click", function () { go(ci - 1); plan(); });
    $(".car-next", car).addEventListener("click", function () { go(ci + 1); plan(); });
    dots.forEach(function (d, n) { d.addEventListener("click", function () { go(n); plan(); }); });
    tr.addEventListener("keydown", function (e) { var k = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0; if (k) { e.preventDefault(); go(ci + k); plan(); } });
    car.addEventListener("mouseenter", function () { hov = true; plan(); }); car.addEventListener("mouseleave", function () { hov = false; plan(); });
    car.addEventListener("focusin", function () { hov = true; plan(); }); car.addEventListener("focusout", function (e) { if (!car.contains(e.relatedTarget)) { hov = false; plan(); } });
    tr.addEventListener("touchstart", function () { hov = true; plan(); }, { passive: true }); tr.addEventListener("touchend", function () { setTimeout(function () { hov = false; plan(); }, 4000); }, { passive: true });
    cp.addEventListener("click", function () { cOff = !cOff; setP(); plan(); });
    document.addEventListener("visibilitychange", plan);
    addEventListener("resize", function () { go(ci, false); plan(); });
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { cvis = es[0].isIntersecting; plan(); }, { threshold: .4 }).observe(tr); else { cvis = true; }
    setP(); mark(); plan();
  });

  /* ---- feature cards ---- */
  $$(".card .more").forEach(function (b) {
    b.addEventListener("click", function () {
      var open = b.getAttribute("aria-expanded") !== "true", p = $("#" + b.getAttribute("aria-controls"));
      b.setAttribute("aria-expanded", open); p.hidden = !open; b.textContent = b.getAttribute(open ? "data-less" : "data-more");
      b.closest(".card").classList.toggle("open", open);
    });
  });

  /* ---- lightbox ---- */
  var lb = $("#lb"), zs = $$(".car-d .zoom"), cur = 0, opener = null;
  function dark() { var t = document.documentElement.getAttribute("data-theme"); return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; }
  function show(i) { cur = (i + zs.length) % zs.length; var z = zs[cur]; $("#lbimg").src = z.getAttribute(dark() ? "data-full-dark" : "data-full"); $("#lbimg").alt = z.getAttribute("data-cap"); $("#lbcap").textContent = z.getAttribute("data-cap"); }
  if (lb && lb.showModal) {
    zs.forEach(function (z, i) { z.addEventListener("click", function () { opener = z; show(i); lb.showModal(); $("#lbclose").focus(); }); });
    $("#lbclose").addEventListener("click", function () { lb.close(); });
    $("#lbprev").addEventListener("click", function () { show(cur - 1); });
    $("#lbnext").addEventListener("click", function () { show(cur + 1); });
    lb.addEventListener("keydown", function (e) { if (e.key === "ArrowLeft") show(cur - 1); if (e.key === "ArrowRight") show(cur + 1); });
    lb.addEventListener("click", function (e) { if (e.target === lb) lb.close(); });
    lb.addEventListener("close", function () { if (opener) opener.focus(); });
  }

  /* ---- price calculator ---- */
  var cr = $("#cr"), cs = $("#cs");
  function calc() { var r = byId[cr.value]; if (!r) return; var n = Math.max(1, Math.min(20, parseInt(cs.value, 10) || r.r)); $("#ct").textContent = eur(r.p / r.r * n); $("#cp").textContent = eur(r.p / r.r); }
  if (cr && cs) { cr.addEventListener("change", function () { cs.value = byId[cr.value].r; calc(); }); cs.addEventListener("input", calc); }

  /* ---- scroll reveal (CSS skips the animation under prefers-reduced-motion) ---- */
  var rv = $$(".rv");
  if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { rootMargin: "0px 0px -8% 0px" });
    rv.forEach(function (el) { el.classList.add("rv-on"); io.observe(el); });
  }
})();
