/* Recetario C — single-page app (vanilla JS, no build step). */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const main = $("#main");
const eur = n => n == null ? "—" : n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
const norm = s => (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

/* ---------- small UI helpers ---------- */
function toast(msg, err = false) {
  const el = $("#toast"); el.textContent = msg; el.className = "toast on" + (err ? " err" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => el.className = "toast", err ? 5000 : 2600);
}
async function guard(fn) { try { return await fn(); } catch (e) { toast(e.message || String(e), true); } }
function dialog(html, onMount) {
  const d = $("#dlg"); d.innerHTML = html; d.showModal(); onMount && onMount(d);
  return d;
}
function setTitle(s) { document.title = s ? `${s} · Recetario C` : "Recetario C"; }
function download(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); }

const FR = [[.25, "¼"], [.5, "½"], [.75, "¾"], [1 / 3, "⅓"], [2 / 3, "⅔"]];
function fmtQty(n) {
  if (n == null) return "";
  if (n >= 10) return String(Math.round(n));
  const w = Math.floor(n), f = n - w;
  for (const [v, s] of FR) if (Math.abs(f - v) < .04) return (w ? w : "") + s;
  return (Math.round(n * 10) / 10).toLocaleString("es-ES");
}
/* Smart scaling: whole-unit items (eggs, cloves, cans) are rounded sensibly. */
const WHOLE = /huevo|diente|lata|sobre|yema|clara|pechuga|muslo|loncha|rebanada|tortilla|lomo/;
function scaleIng(i, k) {
  if (i.cantidad_num == null) return { q: i.cantidad_normal || "al gusto", approx: false };
  let q = i.cantidad_num * k, approx = false;
  const whole = i.unidad === "ud" || i.unidad === "diente" || WHOLE.test(norm(i.nombre));
  if (whole && k !== 1) { const r = q < 1 ? Math.max(.5, Math.round(q * 2) / 2) : Math.round(q); approx = Math.abs(r - q) > .01; q = /huevo/.test(norm(i.nombre)) ? Math.max(1, Math.round(q)) : r; }
  const unit = i.unidad === "ud" ? "" : " " + i.unidad;
  return { q: fmtQty(q) + unit, approx };
}
function priceBadge(i) {
  const src = i.precio_fuente || "estimado";
  if (src === "estimado") return `<span class="badge est" title="Precio aproximado, no real">${t("est")}</span>`;
  const bits = [i.precio_super || src, (i.precio_fecha || "").slice(0, 10)].filter(Boolean).join(", ");
  return `<span class="badge real">real (${esc(bits)})</span>`;
}
const EMOJI = [["postre", "🍰"], ["pasta", "🍝"], ["arroz", "🍚"], ["pescado y marisco", "🐟"], ["pollo", "🍗"], ["ternera", "🥩"], ["cerdo", "🥓"], ["ensalada", "🥗"], ["sopa y crema", "🍲"], ["huevos", "🍳"], ["vegetariana", "🥦"]];
const emojiFor = r => (EMOJI.find(([tg]) => (r.etiquetas || []).includes(tg)) || [0, "🍽️"])[1];

/* ---------- navigation ---------- */
const SECTIONS = [["recetas", "📖", "nav_recetas"], ["planificador", "🗓️", "nav_plan"], ["compra", "🛒", "nav_compra"], ["importar", "📥", "nav_importar"], ["ajustes", "⚙️", "nav_ajustes"]];
function renderNav(cur) {
  const html = SECTIONS.filter(([id]) => !(API.STATIC && id === "importar"))
    .map(([id, ic, k]) => `<a href="#/${id}" ${cur === id ? 'aria-current="page"' : ""}><span aria-hidden="true">${ic}</span><span>${t(k)}</span></a>`).join("");
  $("#nav").innerHTML = html; $("#tabbar").innerHTML = html;
  $("#tabbar").style.gridTemplateColumns = `repeat(${API.STATIC ? 4 : 5},1fr)`;
}
function themeIcon() { const d = document.documentElement.dataset.theme === "dark"; $("#themeBtn").textContent = d ? "☀️" : "🌙"; $("#themeBtn").setAttribute("aria-label", t("theme")); }
$("#themeBtn").onclick = () => { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark"; localStorage.setItem("tema", r.dataset.theme); themeIcon(); };

const routes = {
  recetas: viewList, receta: viewDetail, editar: viewEditor, nueva: viewEditor, borrador: viewEditor,
  planificador: viewPlanner, compra: viewShopping, importar: viewImport, ajustes: viewSettings,
};
async function router() {
  const [, name = "recetas", arg] = location.hash.split("/");
  const sec = { receta: "recetas", editar: "recetas", nueva: "recetas", borrador: "importar" }[name] || name;
  renderNav(sec); themeIcon();
  const fn = routes[name] || viewList;
  main.innerHTML = `<p class="muted">Cargando…</p>`;
  try { await fn(arg, name); } catch (e) { main.innerHTML = `<div class="empty"><div class="big">😕</div><h2>Algo ha fallado</h2><p>${esc(e.message)}</p><a class="btn" href="#/recetas">${t("back")}</a></div>`; }
  if (!router.first) main.focus({ preventScroll: true });
  router.first = false;
}
router.first = true;
addEventListener("hashchange", () => { window.scrollTo(0, 0); router(); });

/* =========================================================== LIST */
const F = Object.assign({ q: "", estado: "", favoritos: false, etiqueta: "", max_min: "", max_precio: "", orden: "original" }, JSON.parse(sessionStorage.getItem("filtros") || "{}"));
let selecting = false; const selected = new Set(); let lastResults = [];

async function viewList() {
  setTitle("");
  const [tags, meta] = await Promise.all([API.tags(), API.meta()]);
  main.innerHTML = `
  <div class="hero"><div><h1>${t("nav_recetas")}</h1>
    <p class="muted" style="margin:0">${meta.recetas} completas · ${meta.solo_video} pendientes de transcribir</p></div>
    <div class="row no-print">
      ${API.STATIC ? "" : `<a class="btn" href="#/nueva">＋ ${t("new_recipe")}</a>`}
      <button class="btn" id="selBtn" type="button" aria-pressed="${selecting}">☑︎ ${t("select")}</button>
      ${API.STATIC ? "" : `<button class="btn primary" id="expBtn" type="button">⬇ ${t("export")}</button>`}
    </div></div>
  <div class="toolbar">
    <div class="search"><label class="sr" for="q">Buscar</label><input id="q" class="input" type="search" placeholder="${t("search_ph")}" value="${esc(F.q)}" autocomplete="off"></div>
    <div class="filters">
      <div class="seg" role="group" aria-label="Estado">
        ${[["", "all"], ["completa", "complete"], ["pendiente de transcribir", "pending"]].map(([v, k]) => `<button type="button" data-estado="${v}" aria-pressed="${F.estado === v}">${t(k)}</button>`).join("")}
      </div>
      <button class="chip" type="button" id="favF" aria-pressed="${F.favoritos}">★ ${t("favorites")}</button>
      <label class="sr" for="tmax">${t("time")}</label>
      <select id="tmax" class="input" style="width:auto"><option value="">⏱ ${t("time")}: ${t("any")}</option>${[15, 30, 45, 60].map(m => `<option value="${m}" ${F.max_min == m ? "selected" : ""}>≤ ${m} min</option>`).join("")}</select>
      <label class="sr" for="pmax">${t("price")}</label>
      <select id="pmax" class="input" style="width:auto"><option value="">€ ${t("price")}: ${t("any")}</option>${[1, 1.5, 2, 3].map(p => `<option value="${p}" ${F.max_precio == p ? "selected" : ""}>≤ ${eur(p)}</option>`).join("")}</select>
      <label class="sr" for="ord">${t("sort")}</label>
      <select id="ord" class="input" style="width:auto">${[["original", "sort_original"], ["rapidas", "sort_fast"], ["baratas", "sort_cheap"], ["az", "sort_az"], ["recientes", "sort_recent"], ["valoracion", "sort_rating"]].map(([v, k]) => `<option value="${v}" ${F.orden === v ? "selected" : ""}>↕ ${t(k)}</option>`).join("")}</select>
    </div>
    <div class="scroller" role="group" aria-label="${t("tags")}">${tags.map(x => `<button type="button" class="chip" data-tag="${esc(x.etiqueta)}" aria-pressed="${F.etiqueta === x.etiqueta}">${esc(x.etiqueta)} <span class="n">${x.total}</span></button>`).join("")}</div>
  </div>
  <p class="muted small" id="count" aria-live="polite"></p>
  <div id="results" class="grid"></div>
  <div id="selbar"></div>`;
  const reload = () => { sessionStorage.setItem("filtros", JSON.stringify(F)); loadResults(); };
  let deb; $("#q").oninput = e => { F.q = e.target.value; clearTimeout(deb); deb = setTimeout(reload, 180); };
  $$("[data-estado]").forEach(b => b.onclick = () => { F.estado = b.dataset.estado; $$("[data-estado]").forEach(x => x.setAttribute("aria-pressed", x === b)); reload(); });
  $("#favF").onclick = e => { F.favoritos = !F.favoritos; e.currentTarget.setAttribute("aria-pressed", F.favoritos); reload(); };
  $$("[data-tag]").forEach(b => b.onclick = () => { F.etiqueta = F.etiqueta === b.dataset.tag ? "" : b.dataset.tag; $$("[data-tag]").forEach(x => x.setAttribute("aria-pressed", x.dataset.tag === F.etiqueta)); reload(); });
  $("#tmax").onchange = e => { F.max_min = e.target.value; reload(); };
  $("#pmax").onchange = e => { F.max_precio = e.target.value; reload(); };
  $("#ord").onchange = e => { F.orden = e.target.value; reload(); };
  $("#selBtn").onclick = () => { selecting = !selecting; if (!selecting) selected.clear(); $("#selBtn").setAttribute("aria-pressed", selecting); renderResults(); };
  $("#expBtn") && ($("#expBtn").onclick = () => exportDialog());
  await loadResults();
}
async function loadResults() {
  lastResults = await API.recipes(F);
  renderResults();
}
function card(r) {
  const img = r.media?.foto ? `<img src="${esc(r.media.foto)}" alt="" loading="lazy">` : "";
  const pend = r.estado !== "completa";
  return `<article class="card ${pend ? "pending" : ""}">
    ${selecting ? `<input type="checkbox" class="sel" data-sel="${r.id}" aria-label="Seleccionar ${esc(r.titulo)}" ${selected.has(r.id) ? "checked" : ""}>` : ""}
    ${r.favorito ? `<span class="fav" aria-label="Favorita">★</span>` : ""}
    <a href="#/receta/${r.id}" style="color:inherit;text-decoration:none;display:flex;flex-direction:column;flex:1">
      <div class="thumb" aria-hidden="true">${img || emojiFor(r)}</div>
      <div class="body">
        <h3>${esc(r.titulo)}</h3>
        <div class="meta">${pend ? `<span class="badge pend">Pendiente de transcribir</span>` : `
          ${r.tiempo_total_min ? `<span>⏱ ${r.tiempo_total_min} min</span>` : ""}
          ${r.precio_racion_eur != null ? `<span>💶 ${eur(r.precio_racion_eur)}/ración <span class="badge est">${t("est")}</span></span>` : ""}`}
        </div>
        <div class="meta"><span>${esc(r.autor || "")}</span>${r.valoracion ? `<span>${"★".repeat(r.valoracion)}</span>` : ""}${r.media?.video ? "<span>🎬</span>" : ""}</div>
      </div></a></article>`;
}
function renderResults() {
  const box = $("#results"); if (!box) return;
  $("#count").textContent = t("results", lastResults.length);
  if (!lastResults.length) {
    box.innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="big">🥄</div><h2>${t("empty_title")}</h2><p>${t("empty_body")}</p>
      <button class="btn" type="button" id="clearF">${t("clear")}</button></div>`;
    $("#clearF").onclick = () => { Object.assign(F, { q: "", estado: "", favoritos: false, etiqueta: "", max_min: "", max_precio: "" }); sessionStorage.removeItem("filtros"); viewList(); };
  } else box.innerHTML = lastResults.map(card).join("");
  $$("[data-sel]").forEach(c => c.onchange = () => { const id = +c.dataset.sel; c.checked ? selected.add(id) : selected.delete(id); renderSelbar(); });
  renderSelbar();
}
function renderSelbar() {
  const bar = $("#selbar"); if (!bar) return;
  if (!selecting) { bar.innerHTML = ""; return; }
  bar.innerHTML = `<div class="selbar"><b>${t("selected", selected.size)}</b><div class="row">
    <button class="btn sm" type="button" id="selAll">Todas las visibles</button><button class="btn sm" type="button" id="selNone">Ninguna</button>
    ${API.STATIC ? "" : `<button class="btn sm" type="button" id="selExp" ${selected.size ? "" : "disabled"}>⬇ ${t("export")}</button>`}</div></div>`;
  $("#selAll").onclick = () => { lastResults.forEach(r => selected.add(r.id)); renderResults(); };
  $("#selNone").onclick = () => { selected.clear(); renderResults(); };
  $("#selExp") && ($("#selExp").onclick = () => exportDialog("sel"));
}

/* ---------- export dialog ---------- */
function exportDialog(pre) {
  const filtered = lastResults.map(r => r.id);
  const d = dialog(`<form method="dialog" id="expForm">
    <h2>Exportar recetas</h2>
    <fieldset><legend>Qué recetas</legend>
      <label><input type="radio" name="sel" value="all" ${pre ? "" : "checked"}> Todas</label>
      <label><input type="radio" name="sel" value="filtered"> Las filtradas ahora (${filtered.length})</label>
      <label><input type="radio" name="sel" value="sel" ${pre ? "checked" : ""} ${selected.size ? "" : "disabled"}> Las seleccionadas (${selected.size})</label>
    </fieldset>
    <fieldset><legend>Formato</legend>
      <label><input type="radio" name="fmt" value="json" checked> JSON (completo, v2)</label>
      <label><input type="radio" name="fmt" value="html"> HTML (para leer o imprimir)</label>
      <label><input type="radio" name="fmt" value="markdown"> Markdown</label>
      <label><input type="radio" name="fmt" value="json_legacy"> JSON compatible con la web v1</label>
    </fieldset>
    <fieldset><legend>Archivos</legend>
      <label><input type="checkbox" name="media"> Incluir vídeos y fotos (descarga un ZIP)</label>
    </fieldset>
    <p class="muted small">Los precios se exportan marcados como estimados. Nunca se exportan claves ni sesiones.</p>
    <div class="row" style="justify-content:flex-end"><button class="btn" value="cancel" type="submit">${t("cancel")}</button><button class="btn primary" id="doExp" type="button">⬇ Descargar</button></div>
  </form>`);
  $("#doExp", d).onclick = () => guard(async () => {
    const f = new FormData($("#expForm", d));
    const sel = f.get("sel");
    const ids = sel === "all" ? null : sel === "filtered" ? filtered : [...selected];
    const r = await API.exportFile({ ids, formato: f.get("fmt"), con_media: !!f.get("media") });
    const name = (r.headers.get("content-disposition") || "").match(/filename="?([^"]+)"?/)?.[1] || "recetas";
    download(await r.blob(), name); d.close(); toast("Exportación descargada");
  });
}

/* =========================================================== DETAIL */
function videoFrame(r) {
  if (r.media?.video) return `<div class="vf"><video src="${esc(r.media.video)}" controls playsinline preload="metadata"></video></div>`;
  const code = r.shortcode;
  if (!code || API.STATIC) return r.media?.foto ? `<img class="photo" src="${esc(r.media.foto)}" alt="">` : "";
  // Fallback kept from v1: cropped Instagram embed scaled to fit
  return `<div class="emb"><div class="embi"><iframe title="Vídeo de Instagram" src="https://www.instagram.com/reel/${esc(code)}/embed/" loading="lazy" allowfullscreen scrolling="no"></iframe></div></div>`;
}
function fitEmb() { $$(".emb").forEach(e => { const k = Math.min(1, e.clientWidth / 358); e.firstElementChild.style.transform = `scale(${k})`; e.style.height = (431 * k) + "px"; }); }
addEventListener("resize", fitEmb);

async function viewDetail(id) {
  const r = await API.recipe(id);
  setTitle(r.titulo);
  const pend = r.estado !== "completa";
  const base = r.raciones || 1; let k = 1;
  main.innerHTML = `
  <nav class="crumbs"><a href="#/recetas">← ${t("nav_recetas")}</a></nav>
  <div class="detail">
    <div>
      <div class="panel">
        <div class="row" style="justify-content:space-between;align-items:flex-start">
          <h1 class="grow">${esc(r.titulo)}</h1>
          ${API.STATIC ? "" : `<button class="icon-btn no-print" id="favBtn" type="button" aria-pressed="${!!r.favorito}" aria-label="Favorita">${r.favorito ? "★" : "☆"}</button>`}
        </div>
        <p class="muted" style="margin:0">${r.autor ? `de <b>${esc(r.autor)}</b>` : ""} ${r.video_url ? `· <a href="${esc(r.video_url)}" target="_blank" rel="noopener">ver en Instagram ↗</a>` : ""}</p>
        ${API.STATIC ? "" : `<div class="row no-print" style="margin-top:.5rem"><span class="small muted">Tu valoración</span><span class="stars" role="group" aria-label="Valoración">${[1, 2, 3, 4, 5].map(n => `<button type="button" data-star="${n}" class="${(r.valoracion || 0) >= n ? "on" : ""}" aria-label="${n} estrellas">★</button>`).join("")}</span></div>`}
        ${pend ? `<div class="banner"><span>🎬 ${t("pending_banner")}</span>${API.STATIC ? "" : `<a class="btn sm" href="#/editar/${r.id}">✍️ ${t("transcribe")}</a>`}</div>` : `
        <div class="facts">
          <div class="fact"><b>${r.tiempo_total_min ?? "—"} min</b><span>tiempo total</span></div>
          <div class="fact"><b>${eur(r.precio_racion_eur)}</b><span>por ración · ${t("est")}</span></div>
          <div class="fact"><b>${eur(r.precio_total_eur)}</b><span>total · ${t("est")}</span></div>
          ${r.nutricion?.kcal ? `<div class="fact"><b>${r.nutricion.kcal} kcal</b><span>por ración · ${t("est")}</span></div>` : ""}
        </div>`}
        <div class="row">${(r.etiquetas || []).map(x => `<a class="chip" href="#/recetas" data-gotag="${esc(x)}">${esc(x)}</a>`).join("")}</div>
        ${(r.alergenos || []).length ? `<p class="small" style="margin:.6rem 0 0"><b>Alérgenos (orientativo):</b> ${(r.alergenos).map(a => `<span class="badge alg">${esc(a)}</span>`).join(" ")}</p>` : ""}
        <div class="actions no-print">
          ${pend || !r.pasos?.length ? "" : `<button class="btn primary" id="cookBtn" type="button">👩‍🍳 ${t("cook_mode")}</button>`}
          <button class="btn" type="button" onclick="print()">🖨 ${t("print")}</button>
          ${API.STATIC ? "" : `<a class="btn" href="#/editar/${r.id}">✏️ ${t("edit")}</a>
          <button class="btn" id="trBtn" type="button">🌐 ${t("translate")}</button>
          <button class="btn ghost danger" id="delBtn" type="button">🗑 ${t("delete")}</button>`}
        </div>
      </div>
      ${pend ? "" : `
      <section class="panel" aria-labelledby="hIng">
        <div class="row" style="justify-content:space-between"><h2 id="hIng">${t("ingredients")}</h2>
          <div class="scaler"><button class="icon-btn" type="button" id="minus" aria-label="Menos raciones">−</button>
            <output id="srv" aria-live="polite">${base}</output><span>${t("servings")}${r.raciones_estimadas ? ` <span class="badge est" title="El vídeo no lo dice">${t("est")}</span>` : ""}</span>
            <button class="icon-btn" type="button" id="plus" aria-label="Más raciones">＋</button></div></div>
        <ul class="ings" id="ings"></ul>
        <p class="small muted" style="margin-bottom:0">💶 Precios <b>estimados</b>: solo orientativos. <span id="ptot"></span></p>
      </section>
      <section class="panel" aria-labelledby="hSt"><h2 id="hSt">${t("steps")}</h2>
        <ol class="steps">${(r.pasos || []).map((s, i) => `<li><div><p style="margin:0">${esc(s.texto)}</p>${s.minutos ? `<button class="btn sm no-print" style="margin-top:.4rem" type="button" data-timer="${i}">⏱ ${s.minutos} min</button>` : ""}</div></li>`).join("")}</ol>
        ${(r.pasos_sugeridos) ? `<p class="small muted">Pasos sugeridos (no aparecen en el vídeo).</p>` : ""}
      </section>`}
      ${r.notas || r.nota ? `<section class="panel"><h2>${t("notes")}</h2><p style="white-space:pre-line;margin:0">${esc(r.notas || r.nota)}</p></section>` : ""}
    </div>
    <aside>
      ${videoFrame(r) ? `<div class="panel no-print">${videoFrame(r)}</div>` : ""}
      ${API.STATIC ? "" : `<section class="panel no-print"><h2>Lo he cocinado</h2>
        <ul class="joblist">${(r.cocinado || []).map((c, i) => `<li>🍽 <b>${esc(c.fecha)}</b> <span class="grow">${esc(c.notas || "")}</span><button class="btn sm ghost" type="button" data-delc="${i}" aria-label="Borrar">✕</button></li>`).join("") || `<li class="muted small">Aún no hay registros.</li>`}</ul>
        <form id="cookLog" class="row"><label class="sr" for="cd">Fecha</label><input id="cd" class="input" type="date" required value="${new Date().toISOString().slice(0, 10)}" style="width:auto">
          <label class="sr" for="cn">Notas</label><input id="cn" class="input grow" placeholder="Notas (opcional)" maxlength="500"><button class="btn" type="submit">Añadir</button></form></section>`}
    </aside>
  </div>`;
  setTimeout(fitEmb, 50);
  $$("[data-gotag]").forEach(a => a.onclick = () => { F.etiqueta = a.dataset.gotag; sessionStorage.setItem("filtros", JSON.stringify(F)); });
  const ings = $("#ings");
  function paint() {
    if (!ings) return;
    $("#srv").textContent = fmtQty(base * k);
    ings.innerHTML = (r.ingredientes || []).map((i, n) => { const s = scaleIng(i, k);
      return `<li><input type="checkbox" id="i${n}"><label for="i${n}"><span class="q">${esc(s.q)}</span> ${esc(i.nombre)}${s.approx ? ` <span class="small muted">(redondeado)</span>` : ""}${i.estimada ? ` <span class="badge est" title="Cantidad estimada">≈</span>` : ""}</label>
      <span class="p">${i.precio_eur != null ? eur(i.precio_eur * k) + " " + priceBadge(i) : ""}</span></li>`; }).join("");
    $("#ptot").textContent = r.precio_total_eur != null ? `Total ≈ ${eur(r.precio_total_eur * k)}` : "";
  }
  paint();
  $("#plus") && ($("#plus").onclick = () => { k = (base * k + 1) / base; paint(); });
  $("#minus") && ($("#minus").onclick = () => { if (base * k > 1) { k = (base * k - 1) / base; paint(); } });
  $$("[data-timer]").forEach(b => b.onclick = () => startTimer(`${r.titulo.slice(0, 24)} · paso ${+b.dataset.timer + 1}`, r.pasos[b.dataset.timer].minutos));
  $("#cookBtn") && ($("#cookBtn").onclick = () => cookMode(r));
  $("#favBtn") && ($("#favBtn").onclick = () => guard(async () => { r.favorito = !r.favorito; await API.patch(r.id, { favorito: r.favorito }); $("#favBtn").textContent = r.favorito ? "★" : "☆"; $("#favBtn").setAttribute("aria-pressed", r.favorito); toast(r.favorito ? "Añadida a favoritas" : "Quitada de favoritas"); }));
  $$("[data-star]").forEach(b => b.onclick = () => guard(async () => { const v = +b.dataset.star === r.valoracion ? 0 : +b.dataset.star; r.valoracion = v; await API.patch(r.id, { valoracion: v }); $$("[data-star]").forEach(x => x.classList.toggle("on", +x.dataset.star <= v)); }));
  $("#delBtn") && ($("#delBtn").onclick = () => { if (confirm(`¿Eliminar «${r.titulo}»? No se borran los vídeos.`)) guard(async () => { await API.remove(r.id); toast("Receta eliminada"); location.hash = "#/recetas"; }); });
  $("#trBtn") && ($("#trBtn").onclick = () => guard(async () => { toast("Traduciendo…"); const tr = await API.ai.translate(r.id, "en");
    dialog(`<div class="dlg"><h2>${esc(tr.titulo)}</h2><p class="muted small">Traducción generada por IA (no se guarda).</p><ul>${(tr.ingredientes || []).map(i => `<li>${esc(i.nombre)}</li>`).join("")}</ul><ol>${(tr.pasos || []).map(s => `<li>${esc(s.texto)}</li>`).join("")}</ol><form method="dialog" class="row" style="justify-content:flex-end"><button class="btn">${t("close")}</button></form></div>`); }));
  $("#cookLog") && ($("#cookLog").onsubmit = e => { e.preventDefault(); guard(async () => { await API.addCooked(r.id, { fecha: $("#cd").value, notas: $("#cn").value }); toast("¡Apuntado!"); viewDetail(id); }); });
  $$("[data-delc]").forEach(b => b.onclick = () => guard(async () => { await API.delCooked(r.id, +b.dataset.delc); viewDetail(id); }));
}

/* ---------- timers ---------- */
let audioCtx;
function beep() { try { audioCtx ??= new AudioContext(); const o = audioCtx.createOscillator(), g = audioCtx.createGain(); o.connect(g); g.connect(audioCtx.destination); o.frequency.value = 880; g.gain.value = .2; o.start(); o.stop(audioCtx.currentTime + .6); } catch { } navigator.vibrate?.([300, 150, 300]); }
function startTimer(label, min) {
  const end = Date.now() + min * 60000, el = document.createElement("div");
  el.className = "timer"; $("#timers").append(el);
  const tick = () => { const s = Math.max(0, Math.round((end - Date.now()) / 1000));
    el.innerHTML = `<span>⏱ ${esc(label)}</span><b>${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}</b><button type="button" aria-label="Quitar temporizador">✕</button>`;
    el.querySelector("button").onclick = () => { clearInterval(iv); el.remove(); };
    if (!s) { clearInterval(iv); el.classList.add("done"); beep(); toast(`⏰ ${label}: ¡tiempo!`); } };
  const iv = setInterval(tick, 1000); tick();
}

/* ---------- cook mode (fullscreen, wake lock) ---------- */
async function cookMode(r) {
  const box = $("#cook"); let i = 0, lock = null;
  try { lock = await navigator.wakeLock?.request("screen"); } catch { }
  try { await box.requestFullscreen?.(); } catch { }
  box.hidden = false;
  const close = () => { box.hidden = true; lock?.release?.(); document.fullscreenElement && document.exitFullscreen(); removeEventListener("keydown", key); };
  const key = e => { if (e.key === "ArrowRight") go(1); if (e.key === "ArrowLeft") go(-1); if (e.key === "Escape") close(); };
  addEventListener("keydown", key);
  function go(d) { i = Math.min(r.pasos.length - 1, Math.max(0, i + d)); paint(); }
  function paint() {
    const s = r.pasos[i];
    box.innerHTML = `<header><div><div class="stepnum">PASO ${i + 1} DE ${r.pasos.length}</div><b>${esc(r.titulo)}</b></div>
      <button class="btn" type="button" id="ckX">✕ Salir</button></header>
      <div class="progress" style="margin:1rem 0"><i style="width:${(i + 1) / r.pasos.length * 100}%"></i></div>
      <div class="big"><p>${esc(s.texto)}</p></div>
      <footer><button class="btn" type="button" id="ckP" ${i ? "" : "disabled"}>← Anterior</button>
      ${s.minutos ? `<button class="btn" type="button" id="ckT">⏱ ${s.minutos} min</button>` : ""}
      <button class="btn primary" type="button" id="ckN">${i === r.pasos.length - 1 ? "¡Listo! ✓" : "Siguiente →"}</button></footer>`;
    $("#ckX").onclick = close; $("#ckP").onclick = () => go(-1);
    $("#ckN").onclick = () => i === r.pasos.length - 1 ? close() : go(1);
    $("#ckT") && ($("#ckT").onclick = () => startTimer(`Paso ${i + 1}`, s.minutos));
  }
  paint();
}

/* =========================================================== EDITOR (recipes and drafts) */
const UNITS = ["g", "ml", "ud", "cda", "cdta", "taza", "diente", "pizca", "lonchas", "puñado", "manojo", "ramita", "trozo", "rebanada", "rodaja", "lata", "sobre"];
async function viewEditor(id, mode) {
  const isDraft = mode === "borrador";
  let r;
  if (isDraft) r = (await API.drafts()).find(d => d.id == id);
  else if (id) r = await API.recipe(id);
  r ??= { titulo: "", autor: "", raciones: 2, ingredientes: [], pasos: [], etiquetas: [], tipo: "receta" };
  setTitle(isDraft ? "Revisar borrador" : id ? "Editar receta" : t("new_recipe"));
  const ingRow = (i = {}) => `<div class="editor-row" data-ing>
    <input class="input" aria-label="Cantidad" inputmode="decimal" name="q" value="${i.cantidad_num ?? ""}" placeholder="Cant.">
    <select class="input" aria-label="Unidad" name="u">${[...new Set([...UNITS, i.unidad || "ud"])].map(u => `<option ${u === (i.unidad || "ud") ? "selected" : ""}>${esc(u)}</option>`).join("")}</select>
    <input class="input nm" aria-label="Ingrediente" name="n" value="${esc(i.nombre || "")}" placeholder="Ingrediente" required>
    <input class="input" aria-label="Precio estimado €" inputmode="decimal" name="p" value="${i.precio_eur ?? ""}" placeholder="€ est.">
    <button class="btn sm ghost" type="button" data-rm aria-label="Quitar">✕</button></div>`;
  const stepRow = (s = {}) => `<div class="editor-row step" data-step>
    <textarea class="input" aria-label="Paso" name="t" rows="2" style="min-height:60px" required>${esc(s.texto || "")}</textarea>
    <input class="input" aria-label="Minutos" inputmode="numeric" name="m" value="${s.minutos ?? ""}" placeholder="min">
    <button class="btn sm ghost" type="button" data-rm aria-label="Quitar">✕</button></div>`;
  main.innerHTML = `
  <nav class="crumbs"><a href="${isDraft ? "#/importar" : id ? `#/receta/${id}` : "#/recetas"}">← ${t("back")}</a></nav>
  <form id="ed" class="panel" novalidate>
    <div class="row" style="justify-content:space-between"><h1>${isDraft ? "Revisar borrador importado" : id ? "Editar receta" : t("new_recipe")}</h1>
      ${isDraft ? `<span class="badge ${r.metodo === "ia" ? "real" : "est"}">${r.metodo === "ia" ? "extraído con IA" : "extraído automáticamente"}</span>` : ""}</div>
    ${isDraft && r.caption_original ? `<details><summary>Ver texto original del post</summary><p class="small" style="white-space:pre-line">${esc(r.caption_original)}</p></details>` : ""}
    <div class="form-grid">
      <div><label class="f" for="ti">Título</label><input id="ti" class="input" name="titulo" required maxlength="200" value="${esc(r.titulo)}"></div>
      <div><label class="f" for="au">Autor</label><input id="au" class="input" name="autor" value="${esc(r.autor || "")}" placeholder="@usuario"></div>
      <div><label class="f" for="vu">Enlace al vídeo</label><input id="vu" class="input" name="video_url" type="url" value="${esc(r.video_url || "")}" placeholder="https://www.instagram.com/reel/…"></div>
      <div><label class="f" for="ra">Raciones</label><input id="ra" class="input" name="raciones" type="number" min="1" max="100" value="${r.raciones || 2}"></div>
    </div>
    <label class="f" for="et">Etiquetas (separadas por comas; vacío = automáticas)</label>
    <input id="et" class="input" name="etiquetas" value="${esc((r.etiquetas || []).join(", "))}">
    ${!id && !isDraft ? `<details style="margin-top:1rem"><summary><b>Pegar el texto de un post</b> y rellenar automáticamente</summary>
      <textarea class="input" id="cap" placeholder="Pega aquí la descripción del vídeo…"></textarea><button class="btn sm" type="button" id="parse" style="margin-top:.4rem">✨ Rellenar</button></details>` : ""}
    <h2 style="margin-top:1.5rem">${t("ingredients")}</h2><div id="ingList">${(r.ingredientes || []).map(ingRow).join("")}</div>
    <div class="row"><button class="btn sm" type="button" id="addIng">＋ Ingrediente</button>${API.STATIC ? "" : `<button class="btn sm" type="button" id="estBtn">💶 Estimar precios con IA</button>`}</div>
    <h2 style="margin-top:1.5rem">${t("steps")}</h2><div id="stepList">${(r.pasos || []).map(stepRow).join("")}</div>
    <button class="btn sm" type="button" id="addStep">＋ Paso</button>
    <label class="f" for="no">${t("notes")}</label><textarea id="no" class="input" name="notas">${esc(r.notas || r.nota || "")}</textarea>
    ${id && !isDraft ? `<h2 style="margin-top:1.5rem">Foto y vídeo</h2>
      <div class="form-grid"><div class="drop"><label class="f" for="upF">Foto (JPG, PNG, WebP · máx. 10 MB)</label><input id="upF" type="file" accept="image/jpeg,image/png,image/webp">${r.media?.foto ? `<p class="small">Actual: <a href="${esc(r.media.foto)}" target="_blank">ver</a> · <button class="btn sm ghost" type="button" data-delm="foto">quitar</button></p>` : ""}</div>
      <div class="drop"><label class="f" for="upV">Vídeo (MP4, WebM, MOV · máx. 300 MB)</label><input id="upV" type="file" accept="video/mp4,video/webm,video/quicktime">${r.media?.video ? `<p class="small">Actual: <a href="${esc(r.media.video)}" target="_blank">ver</a> · <button class="btn sm ghost" type="button" data-delm="video">quitar</button></p>` : ""}</div></div>` : !isDraft ? `<p class="muted small">Podrás subir foto y vídeo después de guardar.</p>` : ""}
    <div class="row" style="justify-content:flex-end;margin-top:1.5rem">
      ${isDraft ? `<button class="btn ghost danger" type="button" id="discard">Descartar</button><button class="btn" type="button" id="saveDraft">Guardar borrador</button><button class="btn primary" type="submit">✓ Añadir al recetario</button>`
      : `<a class="btn" href="${id ? `#/receta/${id}` : "#/recetas"}">${t("cancel")}</a><button class="btn primary" type="submit">${t("save")}</button>`}
    </div>
  </form>`;
  const ed = $("#ed");
  const wireRm = () => $$("[data-rm]", ed).forEach(b => b.onclick = () => b.parentElement.remove());
  wireRm();
  $("#addIng").onclick = () => { $("#ingList").insertAdjacentHTML("beforeend", ingRow()); wireRm(); $("#ingList").lastElementChild.querySelector("[name=n]").focus(); };
  $("#addStep").onclick = () => { $("#stepList").insertAdjacentHTML("beforeend", stepRow()); wireRm(); $("#stepList").lastElementChild.querySelector("textarea").focus(); };
  const num = v => v === "" ? null : Number(String(v).replace(",", "."));
  function collect() {
    const f = new FormData(ed), orig = r.ingredientes || [];
    const ingredientes = $$("[data-ing]", ed).map((row, n) => {
      const g = k => row.querySelector(`[name=${k}]`).value.trim();
      const prev = orig.find(o => o.nombre === g("n")) || {};
      const out = { ...prev, nombre: g("n"), cantidad_num: num(g("q")), unidad: g("u"), precio_eur: num(g("p")), estimada: prev.estimada ?? num(g("q")) == null };
      if (prev.cantidad_num !== out.cantidad_num || prev.unidad !== out.unidad) { delete out.cantidad_1; delete out.cantidad_normal; }
      return out;
    }).filter(i => i.nombre);
    const pasos = $$("[data-step]", ed).map(row => ({ texto: row.querySelector("textarea").value.trim(), minutos: num(row.querySelector("[name=m]").value) })).filter(s => s.texto);
    const body = { ...r, titulo: f.get("titulo").trim(), autor: f.get("autor").trim(), video_url: f.get("video_url").trim() || null,
      raciones: +f.get("raciones") || 1, etiquetas: f.get("etiquetas").split(",").map(s => s.trim()).filter(Boolean), notas: f.get("notas"), ingredientes, pasos };
    body.tipo = ingredientes.length || pasos.length ? "receta" : (r.tipo || "receta");
    for (const k of ["id", "media", "shortcode", "estado", "job_id", "creado", "actualizado", "origen", "metodo", "caption_original", "foto", "video"]) delete body[k];
    if (!body.titulo) throw new Error("El título es obligatorio");
    return body;
  }
  $("#parse") && ($("#parse").onclick = () => guard(async () => { const res = await API.parseCaption($("#cap").value, $("#au").value, $("#vu").value);
    Object.assign(r, res.receta); $("#ti").value = r.titulo; $("#ra").value = r.raciones || 2; $("#et").value = (r.etiquetas || []).join(", ");
    $("#ingList").innerHTML = r.ingredientes.map(ingRow).join(""); $("#stepList").innerHTML = r.pasos.map(stepRow).join(""); wireRm();
    toast(res.metodo === "ia" ? "Rellenado con IA: revísalo" : "Rellenado automáticamente: revísalo"); }));
  $("#estBtn") && ($("#estBtn").onclick = () => guard(async () => { toast("Estimando precios…"); const e = await API.ai.estimate(collect());
    r.ingredientes = e.ingredientes; $("#ingList").innerHTML = e.ingredientes.map(ingRow).join(""); wireRm(); toast("Precios estimados (orientativos)"); }));
  ed.onsubmit = e => { e.preventDefault(); guard(async () => {
    const body = collect();
    if (isDraft) { const saved = await API.saveDraft(r.id, body); toast("Añadida al recetario"); location.hash = `#/receta/${saved.id}`; }
    else if (id) { await API.update(id, body); toast("Guardado"); location.hash = `#/receta/${id}`; }
    else { const c = await API.create(body); toast("Receta creada"); location.hash = `#/receta/${c.id}`; }
  }); };
  $("#saveDraft") && ($("#saveDraft").onclick = () => guard(async () => { await API.updateDraft(r.id, collect()); toast("Borrador guardado"); }));
  $("#discard") && ($("#discard").onclick = () => confirm("¿Descartar este borrador?") && guard(async () => { await API.deleteDraft(r.id); location.hash = "#/importar"; }));
  for (const [inp, kind] of [["#upF", "foto"], ["#upV", "video"]]) $(inp) && ($(inp).onchange = e => guard(async () => {
    const f = e.target.files[0]; if (!f) return; toast("Subiendo…"); await API.upload(id, kind, f); toast("Archivo subido"); viewEditor(id, mode); }));
  $$("[data-delm]").forEach(b => b.onclick = () => guard(async () => { await API.delMedia(id, b.dataset.delm); viewEditor(id, mode); }));
}

/* =========================================================== IMPORT WIZARD (source-agnostic) */
const W = { step: 1, source: "instagram", coll: null, posts: [], pick: new Map(), job: null };
const WSTEPS = ["Fuente y conexión", "Colección", "Publicaciones", "Importando", "Revisar"];
async function viewImport() {
  setTitle(t("nav_importar"));
  const [sources, st, drafts] = await Promise.all([fetch("/api/sources").then(r => r.json()), API.ig.status(), API.drafts()]);
  if (W.step > 1 && !st.conectado && W.step < 4) W.step = 1;
  main.innerHTML = `<div class="hero"><div><h1>${t("nav_importar")}</h1><p class="muted" style="margin:0">Trae recetas de tus guardados. Antes de guardarlas podrás revisarlas y editarlas.</p></div>
    ${drafts.length ? `<button class="btn" type="button" id="goRev">📝 ${drafts.length} borrador${drafts.length > 1 ? "es" : ""} por revisar</button>` : ""}</div>
    <ol class="stepper">${WSTEPS.map((s, i) => `<li ${W.step === i + 1 ? 'aria-current="step"' : ""} class="${W.step > i + 1 ? "done" : ""}"><b>${W.step > i + 1 ? "✓" : i + 1}</b>${s}</li>`).join("")}</ol>
    <section class="panel" id="wz"></section>`;
  $("#goRev") && ($("#goRev").onclick = () => { W.step = 5; viewImport(); });
  const wz = $("#wz");
  if (W.step === 1) return wizConnect(wz, sources, st);
  if (W.step === 2) return wizCollections(wz);
  if (W.step === 3) return wizPosts(wz);
  if (W.step === 4) return wizJob(wz);
  return wizReview(wz, drafts);
}
function wizConnect(wz, sources, st) {
  wz.innerHTML = `<h2>1. Elige la fuente</h2>
  <div class="row" role="radiogroup">${sources.map(s => `<label class="chip" style="cursor:${s.disponible ? "pointer" : "not-allowed"};opacity:${s.disponible ? 1 : .55}"><input type="radio" name="src" value="${s.id}" ${s.id === W.source ? "checked" : ""} ${s.disponible ? "" : "disabled"}> ${esc(s.label)}${s.disponible ? "" : ` <span class="n">${t("soon")}</span>`}</label>`).join("")}</div>
  <h2 style="margin-top:1.5rem">2. Conecta tu cuenta</h2>
  ${st.conectado ? `<div class="banner">✅ Conectado como <b>@${esc(st.usuario)}</b> <span class="muted small">(${esc(st.proveedor)})</span><button class="btn sm" type="button" id="igOut">Desconectar</button><button class="btn primary" type="button" id="next">Continuar →</button></div>` : `
  <p class="muted small">🔒 La contraseña solo se usa para iniciar sesión y <b>nunca se guarda</b>: se conserva únicamente el archivo de sesión en este equipo. Instagram puede pedir verificación o limitar peticiones si importas mucho de golpe.</p>
  <div class="seg" role="tablist"><button type="button" aria-pressed="true" data-lt="pw">Usuario y contraseña</button><button type="button" aria-pressed="false" data-lt="ck">Cookie de sesión</button></div>
  <form id="lgPw" style="max-width:420px"><label class="f" for="u">Usuario</label><input id="u" class="input" autocomplete="username" required>
    <label class="f" for="p">Contraseña</label><input id="p" class="input" type="password" autocomplete="current-password" required>
    <button class="btn primary" style="margin-top:1rem" type="submit">Conectar Instagram</button></form>
  <form id="lg2fa" hidden style="max-width:420px"><label class="f" for="c">Código de verificación (2FA)</label><input id="c" class="input" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required>
    <button class="btn primary" style="margin-top:1rem" type="submit">Verificar</button></form>
  <form id="lgCk" hidden style="max-width:520px"><p class="small muted">Si ya tienes sesión en el navegador: copia el valor de la cookie <code>sessionid</code> de instagram.com (herramientas de desarrollador → Almacenamiento → Cookies).</p>
    <label class="f" for="sid">sessionid</label><input id="sid" class="input" type="password" autocomplete="off">
    <label class="f" for="ck">…o la cabecera Cookie completa</label><textarea id="ck" class="input" style="min-height:70px"></textarea>
    <button class="btn primary" style="margin-top:1rem" type="submit">Usar esta sesión</button></form>`}`;
  $$("[name=src]").forEach(i => i.onchange = () => W.source = i.value);
  $("#next") && ($("#next").onclick = () => { W.step = 2; viewImport(); });
  $("#igOut") && ($("#igOut").onclick = () => guard(async () => { await API.ig.logout(); viewImport(); }));
  $$("[data-lt]").forEach(b => b.onclick = () => { $$("[data-lt]").forEach(x => x.setAttribute("aria-pressed", x === b)); $("#lgPw").hidden = b.dataset.lt !== "pw"; $("#lg2fa").hidden = true; $("#lgCk").hidden = b.dataset.lt !== "ck"; });
  const ok = () => { toast("Instagram conectado"); W.step = 2; viewImport(); };
  $("#lgPw") && ($("#lgPw").onsubmit = e => { e.preventDefault(); guard(async () => { const pw = $("#p"); const r = await API.ig.login($("#u").value.trim(), pw.value); pw.value = "";
    if (r.estado === "2fa") { $("#lgPw").hidden = true; $("#lg2fa").hidden = false; $("#c").focus(); toast("Introduce el código de verificación"); } else ok(); }); });
  $("#lg2fa") && ($("#lg2fa").onsubmit = e => { e.preventDefault(); guard(async () => { await API.ig.twofa($("#c").value.trim()); ok(); }); });
  $("#lgCk") && ($("#lgCk").onsubmit = e => { e.preventDefault(); guard(async () => { await API.ig.cookies($("#sid").value.trim(), $("#ck").value.trim()); $("#sid").value = $("#ck").value = ""; ok(); }); });
}
async function wizCollections(wz) {
  wz.innerHTML = `<p class="muted">Cargando colecciones…</p>`;
  const cols = await API.ig.collections();
  wz.innerHTML = `<h2>Elige una colección de guardados</h2><div class="coll">${cols.map(c => `<button class="panel" type="button" data-c="${esc(c.id)}" style="margin:0"><b style="font-size:1.05rem">📁 ${esc(c.nombre)}</b><br><span class="muted small">${c.total != null ? c.total + " publicaciones" : "todas tus publicaciones guardadas"}</span></button>`).join("")}</div>
  <div class="row" style="margin-top:1rem"><button class="btn" type="button" id="bk">← Atrás</button></div>`;
  $$("[data-c]").forEach(b => b.onclick = () => { W.coll = cols.find(c => c.id === b.dataset.c); W.step = 3; W.pick.clear(); viewImport(); });
  $("#bk").onclick = () => { W.step = 1; viewImport(); };
}
const thumbSrc = u => !u ? "" : u.startsWith("data:") ? u : `/api/instagram/thumb?u=${encodeURIComponent(u)}`;
async function wizPosts(wz) {
  wz.innerHTML = `<p class="muted">Cargando publicaciones…</p>`;
  W.posts = await API.ig.posts(W.coll.id);
  const nuevos = W.posts.filter(p => p.estado === "nuevo");
  function paint() {
    wz.innerHTML = `<div class="row" style="justify-content:space-between"><h2 style="margin:0">📁 ${esc(W.coll.nombre)} <span class="muted small">· ${W.posts.length} publicaciones, ${nuevos.length} nuevas</span></h2>
      <div class="row"><button class="btn sm" type="button" id="all">Seleccionar nuevas</button><button class="btn sm" type="button" id="none">Ninguna</button>
      <label class="small">Para todas: <select class="input" id="bulk" style="width:auto;min-height:34px"><option value="">—</option><option value="ambos">vídeo + foto</option><option value="video">solo vídeo</option><option value="foto">solo foto</option></select></label></div></div>
    <div class="posts" style="margin-top:1rem">${W.posts.map(p => { const on = W.pick.has(p.shortcode), dis = p.estado !== "nuevo";
      return `<div class="post ${on ? "on" : ""}"><div class="thumb">${p.miniatura ? `<img src="${esc(thumbSrc(p.miniatura))}" alt="" loading="lazy">` : "📷"}</div>
      <div class="pb"><label class="pick"><input type="checkbox" data-p="${esc(p.shortcode)}" ${on ? "checked" : ""} ${dis ? "disabled" : ""}> <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.caption.split("\n")[0] || p.shortcode)}</span></label>
      <span class="muted">${esc(p.autor)} ${p.es_video ? "· 🎬" : "· 📷"}</span>
      ${dis ? `<span class="badge ${p.estado === "importado" ? "real" : "est"}">${p.estado === "importado" ? "ya en el recetario" : "borrador pendiente"}</span>` :
      `<select class="input" data-k="${esc(p.shortcode)}" aria-label="Qué descargar" ${on ? "" : "disabled"}>${[["ambos", "vídeo + foto"], ["video", "solo vídeo"], ["foto", "solo foto"]].map(([v, l]) => `<option value="${v}" ${(W.pick.get(p.shortcode) || (p.es_video ? "ambos" : "foto")) === v ? "selected" : ""}>${l}</option>`).join("")}</select>`}</div></div>`; }).join("")}</div>
    <div class="selbar"><b>${W.pick.size} seleccionada${W.pick.size === 1 ? "" : "s"}</b><div class="row"><button class="btn sm" type="button" id="bk">← Colecciones</button><button class="btn sm" type="button" id="go" ${W.pick.size ? "" : "disabled"}>Importar →</button></div></div>`;
    $("#all").onclick = () => { nuevos.forEach(p => W.pick.set(p.shortcode, W.pick.get(p.shortcode) || (p.es_video ? "ambos" : "foto"))); paint(); };
    $("#none").onclick = () => { W.pick.clear(); paint(); };
    $("#bulk").onchange = e => { if (e.target.value) { for (const k of W.pick.keys()) W.pick.set(k, e.target.value); paint(); } };
    $$("[data-p]", wz).forEach(c => c.onchange = () => { const p = W.posts.find(x => x.shortcode === c.dataset.p); c.checked ? W.pick.set(p.shortcode, p.es_video ? "ambos" : "foto") : W.pick.delete(p.shortcode); paint(); });
    $$("[data-k]", wz).forEach(s => s.onchange = () => W.pick.set(s.dataset.k, s.value));
    $("#bk").onclick = () => { W.step = 2; viewImport(); };
    $("#go").onclick = () => guard(async () => { W.job = await API.ig.importItems([...W.pick].map(([shortcode, contenido]) => ({ shortcode, contenido }))); W.pick.clear(); W.step = 4; viewImport(); });
  }
  paint();
}
async function wizJob(wz) {
  const ICON = { pendiente: "⏳", descargando: "⬇️", ok: "✅", duplicado: "↺", error: "⚠️" };
  async function poll() {
    if (!document.body.contains(wz)) return;
    const j = W.job = await API.ig.job(W.job.id);
    wz.innerHTML = `<h2>Importando ${j.hechos} de ${j.total}</h2>
      <div class="progress" role="progressbar" aria-valuenow="${j.progreso}" aria-valuemin="0" aria-valuemax="100"><i style="width:${j.progreso}%"></i></div>
      <ul class="joblist">${j.items.map(i => `<li>${ICON[i.estado] || "•"} <b>${esc(i.shortcode)}</b> <span class="muted">${esc(i.mensaje || i.estado)}</span></li>`).join("")}</ul>
      <div class="row">${["terminado", "cancelado"].includes(j.estado) ? `<button class="btn primary" type="button" id="rev">Revisar borradores →</button>` : `<button class="btn" type="button" id="cn">Cancelar</button><span class="muted small">Puedes salir de esta pantalla: la importación sigue en segundo plano.</span>`}</div>`;
    $("#rev") && ($("#rev").onclick = () => { W.step = 5; viewImport(); });
    $("#cn") && ($("#cn").onclick = () => guard(() => API.ig.cancel(j.id)));
    if (!["terminado", "cancelado"].includes(j.estado)) setTimeout(poll, 800);
  }
  if (!W.job) { W.step = 5; return viewImport(); }
  await poll();
}
function wizReview(wz, drafts) {
  wz.innerHTML = `<h2>Revisa antes de guardar</h2>
  ${drafts.length ? `<p class="muted">Abre cada borrador, corrige lo que haga falta y añádelo al recetario.</p><div class="grid">${drafts.map(d => `<article class="card"><a href="#/borrador/${d.id}" style="color:inherit;text-decoration:none">
    <div class="thumb">${d.foto ? `<img src="/${esc(d.foto)}" alt="" loading="lazy">` : emojiFor(d)}</div>
    <div class="body"><h3>${esc(d.titulo)}</h3><div class="meta"><span>${(d.ingredientes || []).length} ingredientes · ${(d.pasos || []).length} pasos</span>
    <span class="badge ${d.metodo === "ia" ? "real" : "est"}">${d.metodo === "ia" ? "IA" : "automático"}</span></div></div></a></article>`).join("")}</div>`
    : `<div class="empty"><div class="big">📭</div><h2>No hay borradores</h2><p>Importa publicaciones para revisarlas aquí.</p></div>`}
  <div class="row" style="margin-top:1rem"><button class="btn" type="button" id="again">＋ Importar más</button></div>`;
  $("#again").onclick = () => { W.step = 1; W.job = null; viewImport(); };
}

/* =========================================================== PLANNER / SHOPPING (skeletons) */
function viewPlanner() {
  setTitle(t("nav_plan"));
  main.innerHTML = `<h1>${t("nav_plan")}</h1><div class="empty"><div class="big">🗓️</div><h2>${t("soon")}</h2>
  <p>Arrastra recetas a los días de la semana y genera la lista de la compra con las cantidades sumadas.</p></div>`;
}
function viewShopping() {
  setTitle(t("nav_compra"));
  main.innerHTML = `<h1>${t("nav_compra")}</h1><div class="soon">
   <div class="panel"><h2>📝 Tus listas</h2><p class="muted">Varias listas personales, no ligadas a ningún supermercado. Añade cosas a mano o desde recetas, con cantidades sumadas y unidades convertidas.</p></div>
   <div class="panel"><h2>🗂️ Pasillos a tu manera</h2><p class="muted">Categorías propias que puedes reordenar. Marca «ya lo tengo» o «comprado», añade notas y artículos recurrentes.</p></div>
   <div class="panel"><h2>📤 Compartir</h2><p class="muted">Como texto o por WhatsApp, o imprímela. Precio orientativo opcional.</p></div>
  </div><p class="muted small" style="margin-top:1rem">${t("soon")}.</p>`;
}

/* =========================================================== SETTINGS */
async function viewSettings() {
  setTitle(t("nav_ajustes"));
  const meta = await API.meta();
  main.innerHTML = `<h1>${t("nav_ajustes")}</h1><div class="settings">
  <nav class="side" aria-label="Apartados">${[["ap", t("appearance")], ...(API.STATIC ? [] : [["ia", "Conectar tu IA"], ["tok", "Acceso para agentes"], ["ig", "Instagram"]]), ["about", t("about")]].map(([id, l]) => `<a href="#/ajustes" data-jump="${id}">${l}</a>`).join("")}</nav>
  <div>
   <section class="panel" id="s-ap"><h2>${t("appearance")}</h2><div class="row">
     <button class="btn" type="button" id="tg">🌓 ${t("theme")}</button>
     <label>${t("language")} <select class="input" id="lang" style="width:auto">${[["es", "Español"], ["en", "English"]].map(([v, l]) => `<option value="${v}" ${LANG === v ? "selected" : ""}>${l}</option>`).join("")}</select></label></div></section>
   ${API.STATIC ? "" : `<section class="panel" id="s-ia"></section><section class="panel" id="s-tok"></section><section class="panel" id="s-ig"></section>`}
   <section class="panel" id="s-about"><h2>${t("about")}</h2>
     <p>Recetario personal que convierte vídeos de recetas guardados en Instagram en recetas escalables, con precios <b>estimados</b> y modo cocina. Versión ${esc(meta.version || "2")}.</p>
     <pre class="arch" aria-label="Arquitectura">Navegador (SPA vanilla JS, sin build)
   │  /api (UI)   /api/v1 + /mcp (agentes, con token)
   ▼
FastAPI + uvicorn ──► SQLite (recetas como documentos JSON, migración sin pérdidas)
   │                  └─ tokens con hash, IA cifrada con Fernet
   ├─ Fuentes de recetas: Instagram (instaloader) · simulada para tests
   ├─ Extracción: IA compatible OpenAI ─► si falla, parser heurístico en español
   ├─ Exportar: JSON · HTML · Markdown · ZIP con medios
   └─ Medios: videos/CÓDIGO.mp4 (compatible v1) · media/…</pre>
     <p class="small muted">${esc(meta.nota_precios || "")}</p>
     ${API.STATIC ? `<p class="small">Esta es una demo estática de solo lectura con datos de ejemplo.</p>` : `<p class="small"><a href="/docs" target="_blank">Documentación de la API (OpenAPI) ↗</a></p>`}</section>
  </div></div>`;
  $$("[data-jump]").forEach(a => a.onclick = e => { e.preventDefault(); $(`#s-${a.dataset.jump}`).scrollIntoView({ behavior: "smooth" }); });
  $("#tg").onclick = () => $("#themeBtn").click();
  $("#lang").onchange = e => { localStorage.setItem("lang", e.target.value); location.reload(); };
  if (API.STATIC) return;
  renderAI(); renderTokens(); renderIG();
}
async function renderAI() {
  const box = $("#s-ia"), c = await API.ai.config(), P = c.presets;
  box.innerHTML = `<h2>🤖 Conectar tu IA</h2>
  <p class="muted small">Cualquier servicio compatible con la API de OpenAI. Se usa para extraer recetas de los textos (si falla, se usa el parser automático), traducir y estimar precios (siempre marcados como estimados). La clave se guarda cifrada en el servidor y nunca vuelve al navegador.</p>
  <form id="aiF"><div class="form-grid">
    <div><label class="f" for="pr">Proveedor</label><select id="pr" class="input">${Object.entries(P).map(([k, v]) => `<option value="${k}" ${c.preset === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></div>
    <div><label class="f" for="mo">Modelo</label><input id="mo" class="input" value="${esc(c.model || P[c.preset || "openai"].model)}"></div>
  </div>
  <label class="f" for="bu">URL base</label><input id="bu" class="input" type="url" value="${esc(c.base_url || P[c.preset || "openai"].base_url)}">
  <label class="f" for="ak">Clave API ${c.tiene_api_key ? `<span class="badge">guardada ${esc(c.api_key_hint)}</span>` : ""}</label>
  <input id="ak" class="input" type="password" autocomplete="off" placeholder="${c.tiene_api_key ? "Déjalo vacío para mantener la actual" : "sk-… (no hace falta para Ollama / LM Studio)"}">
  <label class="row" style="margin-top:.6rem"><input type="checkbox" id="en" ${c.enabled !== false ? "checked" : ""}> Usar la IA al importar</label>
  <div class="row" style="margin-top:1rem"><button class="btn primary" type="submit">${t("save")}</button><button class="btn" type="button" id="aiT">🔌 Probar conexión</button>
    ${c.configurado ? `<button class="btn ghost danger" type="button" id="aiD">Quitar</button>` : ""}<span id="aiR" class="small" aria-live="polite"></span></div></form>`;
  $("#pr").onchange = e => { const p = P[e.target.value]; $("#bu").value = p.base_url; $("#mo").value = p.model; };
  $("#aiF").onsubmit = e => { e.preventDefault(); guard(async () => { const key = $("#ak").value; await API.ai.save({ preset: $("#pr").value, base_url: $("#bu").value.trim(), model: $("#mo").value.trim(), api_key: key ? key : null, enabled: $("#en").checked }); $("#ak").value = ""; toast("IA guardada"); renderAI(); }); };
  $("#aiT").onclick = () => guard(async () => { $("#aiR").textContent = "Probando…"; const r = await API.ai.test(); $("#aiR").innerHTML = r.ok ? `<span class="badge real">✓ Conectado</span>` : `<span class="badge est">✕ ${esc(r.error)}</span>`; });
  $("#aiD") && ($("#aiD").onclick = () => guard(async () => { await API.ai.remove(); renderAI(); }));
}
async function renderTokens(fresh) {
  const box = $("#s-tok"), list = await API.tokens.list();
  box.innerHTML = `<h2>🔑 Acceso para agentes (API y MCP)</h2>
  <p class="muted small">Crea un token para que otros programas o asistentes lean o añadan recetas: API REST en <a href="/docs" target="_blank">/docs</a> y servidor MCP en <code>${location.origin}/mcp</code>. El token se muestra <b>una sola vez</b>; aquí solo guardamos su huella.</p>
  ${fresh ? `<div class="banner" style="display:block"><b>Copia tu token ahora, no se volverá a mostrar:</b><code class="code" id="newTok">${esc(fresh)}</code><button class="btn sm" type="button" id="cp">📋 Copiar</button></div>` : ""}
  <form id="tkF" class="row"><label class="sr" for="tn">Nombre</label><input id="tn" class="input grow" placeholder="Nombre (p. ej. «Claude en el portátil»)" required maxlength="60">
   <label class="chip"><input type="checkbox" id="tw"> también escribir</label><button class="btn primary" type="submit">Crear token</button></form>
  ${list.length ? `<div style="overflow-x:auto"><table class="t" style="margin-top:1rem"><thead><tr><th>Nombre</th><th>Permisos</th><th>Creado</th><th>Último uso</th><th></th></tr></thead><tbody>
  ${list.map(k => `<tr><td>${esc(k.name)} <code class="small muted">${esc(k.prefix)}…</code></td><td>${k.scopes.join(", ")}</td><td>${esc((k.created || "").slice(0, 10))}</td><td>${esc((k.last_used || "—").slice(0, 16).replace("T", " "))}</td>
   <td>${k.revoked ? `<span class="badge">revocado</span>` : `<button class="btn sm ghost danger" type="button" data-rv="${k.id}">Revocar</button>`}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
  $("#cp") && ($("#cp").onclick = () => navigator.clipboard.writeText(fresh).then(() => toast("Copiado")));
  $("#tkF").onsubmit = e => { e.preventDefault(); guard(async () => { const k = await API.tokens.create($("#tn").value.trim(), $("#tw").checked ? ["read", "write"] : ["read"]); renderTokens(k.token); }); };
  $$("[data-rv]", box).forEach(b => b.onclick = () => confirm("¿Revocar este token?") && guard(async () => { await API.tokens.revoke(b.dataset.rv); renderTokens(); }));
}
async function renderIG() {
  const box = $("#s-ig"), st = await API.ig.status();
  box.innerHTML = `<h2>📸 Instagram</h2><p>${st.conectado ? `Conectado como <b>@${esc(st.usuario)}</b>.` : "No conectado."} <span class="muted small">Proveedor: ${esc(st.proveedor)}</span></p>
  <div class="row">${st.conectado ? `<button class="btn" type="button" id="igo">Desconectar y borrar sesión</button>` : ""}<a class="btn" href="#/importar">Ir a Importar</a></div>`;
  $("#igo") && ($("#igo").onclick = () => guard(async () => { await API.ig.logout(); renderIG(); }));
}

router();
