/* API layer. In server mode it talks to FastAPI; in static mode (GitHub Pages demo,
   <html data-mode="static">) it reads data/recipes.json and is read-only. */
(function () {
  const STATIC = document.documentElement.dataset.mode === "static";
  const norm = s => (s || "").toString().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  let cache = null;
  async function staticData() { return cache ??= await (await fetch("data/recipes.json")).json(); }

  async function req(method, url, body, opts = {}) {
    if (STATIC && method !== "GET") throw new Error("Demo de solo lectura");
    const init = { method, headers: {} };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { init.body = JSON.stringify(body); init.headers["Content-Type"] = "application/json"; }
    const r = await fetch(url, init);
    if (opts.raw) { if (!r.ok) throw new Error(await errText(r)); return r; }
    if (!r.ok) throw new Error(await errText(r));
    return r.status === 204 ? null : r.json();
  }
  async function errText(r) {
    try { const j = await r.json(); return typeof j.detail === "string" ? j.detail : (j.detail?.[0]?.msg || JSON.stringify(j.detail)); }
    catch { return `Error ${r.status}`; }
  }
  const qs = p => new URLSearchParams(Object.entries(p).filter(([, v]) => v !== "" && v != null && v !== false)).toString();

  function localSearch(all, p) {
    const terms = norm(p.q).split(/\s+/).filter(Boolean);
    let out = all.filter(r => (!p.estado || r.estado === p.estado) && (!p.favoritos || r.favorito)
      && (!p.etiqueta || (r.etiquetas || []).includes(p.etiqueta))
      && (!p.max_min || (r.tiempo_total_min ?? 1e9) <= p.max_min)
      && (!p.max_precio || (r.precio_racion_eur ?? 1e9) <= p.max_precio)
      && terms.every(t => norm([r.titulo, r.autor, ...(r.ingredientes || []).map(i => i.nombre), ...(r.etiquetas || [])].join(" ")).includes(t)));
    const k = { rapidas: r => r.tiempo_total_min ?? 1e9, baratas: r => r.precio_racion_eur ?? 1e9, az: r => norm(r.titulo) }[p.orden];
    if (k) out = [...out].sort((a, b) => (k(a) > k(b)) - (k(a) < k(b)));
    return out;
  }

  window.API = {
    STATIC,
    async recipes(p = {}) { return STATIC ? localSearch((await staticData()).recetas, p) : req("GET", "/api/recipes?" + qs(p)); },
    async recipe(id) { if (STATIC) { const r = (await staticData()).recetas.find(x => x.id == id); if (!r) throw new Error("No encontrada"); return r; } return req("GET", `/api/recipes/${id}`); },
    async tags() {
      if (!STATIC) return req("GET", "/api/tags");
      const c = {}; (await staticData()).recetas.forEach(r => (r.etiquetas || []).forEach(t => c[t] = (c[t] || 0) + 1));
      return Object.entries(c).sort((a, b) => b[1] - a[1]).map(([etiqueta, total]) => ({ etiqueta, total }));
    },
    async meta() { return STATIC ? { ...(await staticData()).meta, static: true } : req("GET", "/api/meta"); },
    create: b => req("POST", "/api/recipes", b),
    update: (id, b) => req("PUT", `/api/recipes/${id}`, b),
    patch: (id, b) => req("PATCH", `/api/recipes/${id}`, b),
    remove: id => req("DELETE", `/api/recipes/${id}`),
    addCooked: (id, b) => req("POST", `/api/recipes/${id}/cocinado`, b),
    delCooked: (id, i) => req("DELETE", `/api/recipes/${id}/cocinado/${i}`),
    upload: (id, kind, file) => { const f = new FormData(); f.append("file", file); return req("POST", `/api/recipes/${id}/media/${kind}`, f); },
    delMedia: (id, kind) => req("DELETE", `/api/recipes/${id}/media/${kind}`),
    exportFile: b => req("POST", "/api/export", b, { raw: true }),
    ig: {
      status: () => req("GET", "/api/instagram/status"),
      login: (username, password) => req("POST", "/api/instagram/login", { username, password }),
      twofa: code => req("POST", "/api/instagram/2fa", { code }),
      cookies: (sessionid, cookies) => req("POST", "/api/instagram/cookies", { sessionid, cookies }),
      logout: () => req("POST", "/api/instagram/logout"),
      collections: () => req("GET", "/api/instagram/collections"),
      posts: cid => req("GET", `/api/instagram/collections/${encodeURIComponent(cid)}/posts`),
      importItems: items => req("POST", "/api/instagram/import", { items }),
      job: id => req("GET", `/api/instagram/jobs/${id}`),
      cancel: id => req("POST", `/api/instagram/jobs/${id}/cancel`),
    },
    drafts: () => req("GET", "/api/drafts"),
    updateDraft: (id, b) => req("PUT", `/api/drafts/${id}`, b),
    saveDraft: (id, b) => req("POST", `/api/drafts/${id}/save`, b),
    deleteDraft: id => req("DELETE", `/api/drafts/${id}`),
    parseCaption: (caption, autor, video_url) => req("POST", "/api/parse-caption", { caption, autor, video_url }),
    ai: {
      config: () => req("GET", "/api/ai/config"),
      save: b => req("PUT", "/api/ai/config", b),
      remove: () => req("DELETE", "/api/ai/config"),
      test: () => req("POST", "/api/ai/test"),
      translate: (recipe_id, lang) => req("POST", "/api/ai/translate", { recipe_id, lang }),
      estimate: recipe => req("POST", "/api/ai/estimate", { recipe }),
    },
    tokens: { list: () => req("GET", "/api/tokens"), create: (name, scopes) => req("POST", "/api/tokens", { name, scopes }), revoke: id => req("DELETE", `/api/tokens/${id}`) },
  };
})();
