/* Landing interactivity: hero mockup (sample data only, no network), feature cards, lightbox, price calculator, scroll reveal. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var T = JSON.parse(document.body.getAttribute("data-i18n") || "{}"), LANG = document.body.getAttribute("data-lang") || "es";
  var D = window.RC_DATA || { r: [], plan: [] }, byId = {}, bySlug = {};
  D.r.forEach(function (r) { byId[r.id] = r; bySlug[r.s] = r; });
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function eur(x) { var v = x.toFixed(2); return LANG === "es" ? v.replace(".", ",") + " €" : "€" + v; }
  function num(x) { var v = Math.round(x * 10) / 10; v = v >= 10 ? Math.round(v) : v; return LANG === "es" ? String(v).replace(".", ",") : String(v); }
  function qty(i, f) { return i[1] == null ? i[3] : num(i[1] * f) + (i[2] && i[2] !== "ud" ? " " + i[2] : ""); }

  /* ---- desktop mockup ---- */
  var tabs = $$(".mtabs [role=tab]");
  function selTab(b, focus) {
    tabs.forEach(function (t) { var on = t === b; t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1; $("#" + t.getAttribute("aria-controls")).hidden = !on; });
    if (focus) b.focus();
    if (b.id === "mt-buy") renderBuy();
  }
  tabs.forEach(function (b, i) {
    b.addEventListener("click", function () { selTab(b); });
    b.addEventListener("keydown", function (e) {
      var k = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (k) { e.preventDefault(); selTab(tabs[(i + k + tabs.length) % tabs.length], true); }
    });
  });
  var q = $("#mq"), tag = "all";
  function filter() {
    var s = (q && q.value || "").trim().toLowerCase(), n = 0;
    $$("#mgrid li").forEach(function (li) {
      var ok = (!s || li.getAttribute("data-name").indexOf(s) >= 0) && (tag === "all" || (" " + li.getAttribute("data-tags") + " ").indexOf(" " + tag + " ") >= 0);
      li.hidden = !ok; if (ok) n++;
    });
    var none = $("#mnone"); if (none) none.hidden = n > 0;
  }
  if (q) q.addEventListener("input", filter);
  $$(".chips .chip").forEach(function (c) {
    c.addEventListener("click", function () {
      tag = c.getAttribute("data-tag");
      $$(".chips .chip").forEach(function (o) { o.setAttribute("aria-pressed", o === c); });
      filter();
    });
  });
  var det = $("#mdet"), list = $(".mlist"), lastCard = null;
  function openDet(r, serv) {
    var f = serv / r.r;
    det.innerHTML = '<div class="mdh"><button type="button" class="mback">← ' + esc(T.mk_back) + '</button><img src="/img/r/' + r.s + '.webp" alt="" width="160" height="100"><div><h3>' + esc(r.t) + '</h3><p class="mm">' + r.m + ' min · ' + eur(r.p * f) + '</p></div></div>' +
      '<div class="step" role="group" aria-label="' + esc(T.mk_serv) + '"><span>' + esc(T.mk_serv) + '</span><button type="button" class="sb" data-d="-1" aria-label="' + esc(T.mk_less) + '"' + (serv <= 1 ? " disabled" : "") + '>−</button><output aria-live="polite">' + serv + '</output><button type="button" class="sb" data-d="1" aria-label="' + esc(T.mk_more) + '"' + (serv >= 12 ? " disabled" : "") + '>+</button></div>' +
      '<p class="ph">' + esc(T.mk_ing) + '</p><ul class="ping">' + r.i.map(function (i) { return "<li>" + esc(i[0]) + " <span>" + esc(qty(i, f)) + "</span></li>"; }).join("") + "</ul>";
    $(".mback", det).addEventListener("click", function () { det.hidden = true; list.hidden = false; if (lastCard) lastCard.focus(); });
    $$(".sb", det).forEach(function (b) {
      b.addEventListener("click", function () { var d = +b.getAttribute("data-d"); openDet(r, serv + d); var nb = $('.sb[data-d="' + d + '"]', det); (nb.disabled ? $(".sb:not([disabled])", det) : nb).focus(); });
    });
  }
  $$(".mcard").forEach(function (c) {
    c.addEventListener("click", function () { var r = byId[c.getAttribute("data-id")]; lastCard = c; openDet(r, r.r); list.hidden = true; det.hidden = false; $(".mback", det).focus(); });
  });
  function renderBuy() {
    var acc = {}, order = [];
    D.plan.forEach(function (s) { var r = bySlug[s]; if (!r) return; r.i.forEach(function (i) {
      var k = i[0] + "|" + i[2]; if (!acc[k]) { acc[k] = { n: i[0], u: i[2], q: 0, txt: i[3] }; order.push(k); }
      if (i[1] != null) acc[k].q += i[1]; });
    });
    var ul = $("#mbuy"); if (!ul || ul.childElementCount) return;
    ul.innerHTML = order.slice(0, 40).map(function (k, n) { var a = acc[k];
      return '<li><label><input type="checkbox"> ' + esc(a.n) + ' <span>' + esc(a.q ? num(a.q) + (a.u && a.u !== "ud" ? " " + a.u : "") : a.txt) + "</span></label></li>"; }).join("");
  }

  /* ---- phone mockup ---- */
  var P = bySlug.paella, bag = [], badge = $("#pbadge"), cart = $("#pcart"), step = 0;
  function view(id) { ["pdet", "plist", "pcookv"].forEach(function (v) { var el = $("#" + v); if (el) el.hidden = v !== id; }); if (cart) cart.setAttribute("aria-expanded", id === "plist"); }
  function upd() { badge.textContent = bag.length; cart.setAttribute("aria-label", T.mk_list + ": " + bag.length); badge.classList.remove("pop"); void badge.offsetWidth; badge.classList.add("pop"); }
  if (P && cart) {
    $("#padd").addEventListener("click", function () {
      P.i.forEach(function (i) { if (bag.indexOf(i[0]) < 0) bag.push(i[0]); });
      $("#padd span").textContent = T.mk_added + " ✓"; upd();
    });
    cart.addEventListener("click", function () {
      if ($("#plist").hidden) {
        $("#plistul").innerHTML = bag.length ? P.i.filter(function (i) { return bag.indexOf(i[0]) >= 0; }).map(function (i) { return "<li>" + esc(i[0]) + " <span>" + esc(i[3]) + "</span></li>"; }).join("") : "<li>" + esc(T.mk_empty) + "</li>";
        view("plist");
      } else view("pdet");
    });
    function showStep() {
      var n = P.st.length, done = step >= n;
      $("#pstepn").textContent = done ? T.mk_cook : T.mk_step + " " + (step + 1) + " " + T.mk_of + " " + n;
      $("#pstep").textContent = done ? T.mk_done : P.st[step];
      $("#pprev").disabled = false; $("#pnext").disabled = done;
    }
    $("#pcook").addEventListener("click", function () { step = 0; view("pcookv"); showStep(); $("#pnext").focus(); });
    $("#pprev").addEventListener("click", function () { if (step === 0) { view("pdet"); $("#pcook").focus(); return; } step--; showStep(); });
    $("#pnext").addEventListener("click", function () { step++; showStep(); if ($("#pnext").disabled) $("#pprev").focus(); });
  }

  /* ---- feature cards ---- */
  $$(".card .more").forEach(function (b) {
    b.addEventListener("click", function () {
      var open = b.getAttribute("aria-expanded") !== "true", p = $("#" + b.getAttribute("aria-controls"));
      b.setAttribute("aria-expanded", open); p.hidden = !open; b.textContent = b.getAttribute(open ? "data-less" : "data-more");
      b.closest(".card").classList.toggle("open", open);
    });
  });

  /* ---- lightbox ---- */
  var lb = $("#lb"), zs = $$(".zoom"), cur = 0, opener = null;
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
