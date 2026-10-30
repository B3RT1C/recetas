/* Landing demo: answers the app's /api/* calls in the browser from data/api.json (recorded from the real app with
   sample data). Writes only change memory; reloading the page resets everything. No network beyond this folder. */
(function () {
  "use strict";
  var realFetch = window.fetch.bind(window), dbP = null;
  function db() { return dbP || (dbP = realFetch("data/api.json").then(function (r) { return r.json(); })); }
  var clone = function (o) { return o == null ? o : JSON.parse(JSON.stringify(o)); };
  var norm = function (s) { return (s || "").toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); };
  function res(body, status) {
    status = status || 200;
    return new Response(status === 204 ? null : JSON.stringify(body), { status: status, headers: { "Content-Type": "application/json" } });
  }
  var EN = (function () { try { return localStorage.getItem("lang") === "en"; } catch (e) { return false; } })();
  var RO = { detail: EN ? "Demo: changes are not saved. Install it on your own computer to use it for real."
                        : "Demo: los cambios no se guardan. Instálalo en tu equipo para usarlo de verdad." };

  // shift every YYYY-MM-DD in the recorded week so the planner always shows the current (or requested) week
  function iso(d) { return d.toISOString().slice(0, 10); }
  function monday(d) { d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); d.setUTCDate(d.getUTCDate() - (d.getUTCDay() + 6) % 7); return d; }
  function shiftDates(o, days) {
    if (!days) return o;
    return JSON.parse(JSON.stringify(o).replace(/"(\d{4}-\d{2}-\d{2})/g, function (m, s) {
      var d = new Date(s + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + days); return '"' + iso(d);
    }));
  }

  function search(all, p) {
    var terms = norm(p.get("q")).split(/\s+/).filter(Boolean), num = function (k) { return +p.get(k) || 0; };
    var out = all.filter(function (r) {
      return (!p.get("estado") || r.estado === p.get("estado")) && (!p.get("favoritos") || r.favorito)
        && (!p.get("etiqueta") || (r.etiquetas || []).indexOf(p.get("etiqueta")) >= 0)
        && (!num("max_min") || (r.tiempo_total_min == null ? 1e9 : r.tiempo_total_min) <= num("max_min"))
        && (!num("max_precio") || (r.precio_racion_eur == null ? 1e9 : r.precio_racion_eur) <= num("max_precio"))
        && terms.every(function (t) { return norm([r.titulo, r.autor].concat((r.ingredientes || []).map(function (i) { return i.nombre; }), r.etiquetas || []).join(" ")).indexOf(t) >= 0; });
    });
    var k = { rapidas: function (r) { return r.tiempo_total_min == null ? 1e9 : r.tiempo_total_min; }, baratas: function (r) { return r.precio_racion_eur == null ? 1e9 : r.precio_racion_eur; }, az: function (r) { return norm(r.titulo); } }[p.get("orden")];
    if (k) out.sort(function (a, b) { return (k(a) > k(b)) - (k(a) < k(b)); });
    return out;
  }

  function handle(D, method, url, body) {
    var u = new URL(url, location.href), path = u.pathname.replace(/^.*?(\/api\/)/, "/api/"), G = D.get, m;
    if (method === "GET") {
      if (path === "/api/recipes") return res(search(G["/api/recipes"], u.searchParams));
      if (path === "/api/plan") {
        var want = u.searchParams.get("inicio") ? new Date(u.searchParams.get("inicio") + "T00:00:00Z") : monday(new Date());
        var days = Math.round((want - new Date(G["/api/plan"].inicio + "T00:00:00Z")) / 864e5);
        return res(shiftDates(G["/api/plan"], days));
      }
      if ((m = path.match(/^\/api\/recipes\/(\d+)\/escalar$/))) {
        var n = Math.max(1, Math.min(12, Math.round(+u.searchParams.get("raciones") || 1)));
        return res(G[path + "?raciones=" + n] || RO, G[path + "?raciones=" + n] ? 200 : 404);
      }
      var hit = G[path + u.search] || G[path];
      return hit !== undefined ? res(clone(hit)) : res({ detail: EN ? "Not available in the demo" : "No disponible en la demo" }, 404);
    }
    var L = G["/api/compra/listas/" + D.lista];
    if ((m = path.match(/^\/api\/compra\/items\/(\d+)$/)) && L) {
      var it = L.items.filter(function (i) { return i.id == m[1]; })[0];
      if (!it) return res(RO, 404);
      if (method === "DELETE") { L.items.splice(L.items.indexOf(it), 1); return res(null, 204); }
      Object.keys(body || {}).forEach(function (k) { it[k] = body[k]; });
      return res(clone(it));
    }
    if ((m = path.match(/^\/api\/plan\/(\d+)$/))) {
      var P = G["/api/plan"], e = P.items.filter(function (i) { return i.id == m[1]; })[0];
      if (!e) return res(RO, 404);
      if (method === "DELETE") { P.items.splice(P.items.indexOf(e), 1); return res(null, 204); }
      Object.keys(body || {}).forEach(function (k) { e[k] = body[k]; });
      return res(clone(e));
    }
    if ((m = path.match(/^\/api\/recipes\/(\d+)$/)) && method === "PATCH") {
      var r = G[path]; Object.keys(body || {}).forEach(function (k) { r[k] = body[k]; });
      G["/api/recipes"].forEach(function (x) { if (x.id == m[1]) Object.keys(body || {}).forEach(function (k) { x[k] = body[k]; }); });
      return res(clone(r));
    }
    if (path === "/api/preferencias/lista" && method === "PUT") { Object.assign(G[path], body || {}); return res(clone(G[path])); }
    if (path === "/api/plan/a-lista" || (/^\/api\/compra\/listas\/\d+\/receta$/).test(path)) {
      var l = clone(G["/api/compra/listas"].filter(function (x) { return x.id == D.lista; })[0] || {}); l.recetas_añadidas = 1; return res(l);
    }
    return res(RO, 403);
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : input.url, method = ((init && init.method) || "GET").toUpperCase();
    if (!/(^|\/)api\//.test(new URL(url, location.href).pathname)) return realFetch(input, init);
    var body = null;
    try { body = init && typeof init.body === "string" ? JSON.parse(init.body) : null; } catch (e) {}
    return db().then(function (D) { return handle(D, method, url, body); });
  };
})();
