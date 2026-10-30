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
/* sober cover placeholder for recipes without an image: neutral tile + one line icon per main tag */
const TAG_ICON = [["postre", "cake-slice"], ["pasta", "wheat"], ["arroz", "cooking-pot"], ["pescado y marisco", "fish"], ["pollo", "drumstick"], ["ternera", "beef"], ["cerdo", "ham"], ["ensalada", "salad"], ["sopa y crema", "soup"], ["huevos", "egg"], ["vegetariana", "carrot"]];
const iconFor = r => (TAG_ICON.find(([tg]) => (r.etiquetas || []).includes(tg)) || [0, "utensils-crossed"])[1];
const placeholder = r => `<span class="ph">${ic(iconFor(r))}</span>`;

/* ---------- navigation ---------- */
const SECTIONS = [["recetas", "book-open", "nav_recetas"], ["planificador", "calendar-days", "nav_plan"], ["compra", "shopping-cart", "nav_compra"], ["importar", "import", "nav_importar"], ["ajustes", "settings", "nav_ajustes"]];
function renderNav(cur) {
  const html = SECTIONS.filter(([id]) => !(API.STATIC && id === "importar"))
    .map(([id, icon, k]) => `<a href="#/${id}" ${cur === id ? 'aria-current="page"' : ""}>${ic(icon)}<span>${t(k)}</span></a>`).join("");
  $("#nav").innerHTML = html; $("#tabbar").innerHTML = html;
  $("#tabbar").style.gridTemplateColumns = `repeat(${API.STATIC ? 4 : 5},1fr)`;
}
function themeIcon() { const d = document.documentElement.dataset.theme === "dark"; $("#themeBtn").innerHTML = ic(d ? "sun" : "moon"); $("#themeBtn").setAttribute("aria-label", t("theme")); }
$("#themeBtn").onclick = () => { const r = document.documentElement; r.dataset.theme = r.dataset.theme === "dark" ? "light" : "dark"; localStorage.setItem("tema", r.dataset.theme); themeIcon(); };

const routes = {
  recetas: viewList, receta: viewDetail, editar: viewEditor, nueva: viewEditor, borrador: viewEditor,
  planificador: viewPlanner, compra: viewShopping, importar: viewImport, ajustes: viewSettings,
};
async function router() {
  const [, name = "recetas", arg] = location.hash.split("/");
  if (!AUTH.ok) {
    let me; try { me = await API.auth.me(); } catch (e) { me = { autenticado: false }; }
    if (!me.autenticado) return viewLogin();
    AUTH.ok = true; AUTH.user = me.usuario || "";
  }
  if (name === "login") { location.hash = "#/recetas"; return; }
  const sec = { receta: "recetas", editar: "recetas", nueva: "recetas", borrador: "importar" }[name] || name;
  renderNav(sec); themeIcon();
  const fn = routes[name] || viewList;
  main.innerHTML = `<p class="muted">Cargando…</p>`;
  try { await fn(arg, name); } catch (e) { main.innerHTML = `<div class="empty"><div class="big">${ic("circle-alert")}</div><h2>Algo ha fallado</h2><p>${esc(e.message)}</p><a class="btn" href="#/recetas">${t("back")}</a></div>`; }
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
    <div class="row no-print hero-actions">
      ${API.STATIC ? "" : `<a class="btn" href="#/nueva">${ic("plus")} ${t("new_recipe")}</a>`}
      <button class="btn" id="selBtn" type="button" aria-pressed="${selecting}">${ic("list-checks")} ${t("select")}</button>
      ${API.STATIC ? "" : `<button class="btn primary" id="expBtn" type="button">${ic("download")} ${t("export")}</button>`}
    </div></div>
  <div class="toolbar">
    <div class="search"><label class="sr" for="q">Buscar</label><input id="q" class="input" type="search" placeholder="${t("search_ph")}" value="${esc(F.q)}" autocomplete="off"></div>
    <div class="filters">
      <div class="seg" role="group" aria-label="Estado">
        ${[["", "all"], ["completa", "complete"], ["pendiente de transcribir", "pending"]].map(([v, k]) => `<button type="button" data-estado="${v}" aria-pressed="${F.estado === v}">${t(k)}</button>`).join("")}
      </div>
      <button class="chip" type="button" id="favF" aria-pressed="${F.favoritos}">${ic("star")} ${t("favorites")}</button>
      <div class="fpop-wrap">
        <button class="btn" type="button" id="filtBtn" aria-haspopup="dialog" aria-expanded="false" aria-controls="filtPanel">${ic("sliders-horizontal")} Filtros<span class="fbadge" id="filtN" hidden></span></button>
        <div class="fpop" id="filtPanel" role="dialog" aria-modal="true" aria-labelledby="filtTitle" hidden>
          <div class="fpop-head"><h2 id="filtTitle">Filtros</h2><button class="btn ghost sm" type="button" id="filtX" aria-label="Cerrar filtros">${ic("x")}</button></div>
          <label class="f" for="tmax">${t("time")}</label>
          <select id="tmax" class="input"><option value="">${t("any")}</option>${[15, 30, 45, 60].map(m => `<option value="${m}" ${F.max_min == m ? "selected" : ""}>≤ ${m} min</option>`).join("")}</select>
          <label class="f" for="pmax">${t("price")}</label>
          <select id="pmax" class="input"><option value="">${t("any")}</option>${[1, 1.5, 2, 3].map(p => `<option value="${p}" ${F.max_precio == p ? "selected" : ""}>≤ ${eur(p)}</option>`).join("")}</select>
          <label class="f" for="ord">${t("sort")}</label>
          <select id="ord" class="input">${[["original", "sort_original"], ["rapidas", "sort_fast"], ["baratas", "sort_cheap"], ["az", "sort_az"], ["recientes", "sort_recent"], ["valoracion", "sort_rating"]].map(([v, k]) => `<option value="${v}" ${F.orden === v ? "selected" : ""}>${t(k)}</option>`).join("")}</select>
          <div class="row fpop-foot"><button class="btn ghost" type="button" id="filtReset">Restablecer</button><button class="btn primary" type="button" id="filtOk">Ver resultados</button></div>
        </div>
      </div>
    </div>
    <div class="scroller" role="group" aria-label="${t("tags")}">${tags.map(x => `<button type="button" class="chip" data-tag="${esc(x.etiqueta)}" aria-pressed="${F.etiqueta === x.etiqueta}">${esc(x.etiqueta)} <span class="n">${x.total}</span></button>`).join("")}</div>
  </div>
  <div class="listbar"><p class="muted small" id="count" aria-live="polite"></p>${viewPicker()}</div>
  <div id="results" class="grid"></div>
  <div id="selbar"></div>`;
  const reload = () => { sessionStorage.setItem("filtros", JSON.stringify(F)); loadResults(); };
  let deb; $("#q").oninput = e => { F.q = e.target.value; clearTimeout(deb); deb = setTimeout(reload, 180); };
  $$("[data-estado]").forEach(b => b.onclick = () => { F.estado = b.dataset.estado; $$("[data-estado]").forEach(x => x.setAttribute("aria-pressed", x === b)); reload(); });
  $("#favF").onclick = e => { F.favoritos = !F.favoritos; e.currentTarget.setAttribute("aria-pressed", F.favoritos); reload(); };
  $$("[data-tag]").forEach(b => b.onclick = () => { F.etiqueta = F.etiqueta === b.dataset.tag ? "" : b.dataset.tag; $$("[data-tag]").forEach(x => x.setAttribute("aria-pressed", x.dataset.tag === F.etiqueta)); reload(); });
  $("#tmax").onchange = e => { F.max_min = e.target.value; badge(); reload(); };
  $("#pmax").onchange = e => { F.max_precio = e.target.value; badge(); reload(); };
  $("#ord").onchange = e => { F.orden = e.target.value; badge(); reload(); };
  const badge = () => { const n = [F.max_min, F.max_precio, F.orden !== "original"].filter(Boolean).length, b = $("#filtN");
    b.hidden = !n; b.textContent = n; $("#filtBtn").setAttribute("aria-label", n ? `Filtros, ${n} activo${n > 1 ? "s" : ""}` : "Filtros"); };
  badge(); bindFilterPopover(() => { Object.assign(F, { max_min: "", max_precio: "", orden: "original" }); $("#tmax").value = ""; $("#pmax").value = ""; $("#ord").value = "original"; badge(); reload(); });
  bindFade($(".toolbar .scroller"));
  $("#selBtn").onclick = () => { selecting = !selecting; if (!selecting) selected.clear(); $("#selBtn").setAttribute("aria-pressed", selecting); renderResults(); };
  $("#expBtn") && ($("#expBtn").onclick = () => exportDialog());
  bindViewPicker();
  await loadResults();
  API.prefsLista().then(p => { if (p && (p.vista !== VIEW.vista || p.densidad !== VIEW.densidad)) { setView(p, false); } }).catch(() => {});
}
// 'Filtros' popover (desktop) / bottom sheet (mobile): focus trap, Esc and outside click close, focus returns to the button
function bindFilterPopover(onReset) {
  const btn = $("#filtBtn"), pnl = $("#filtPanel"), wrap = pnl.parentElement;
  const focusables = () => $$("button,select,input,[tabindex]:not([tabindex='-1'])", pnl).filter(x => !x.disabled && x.offsetParent !== null);
  const outside = e => { if (!wrap.contains(e.target)) close(false); };
  const open = () => { pnl.hidden = false; btn.setAttribute("aria-expanded", "true"); document.body.classList.add("fpop-open");
    document.addEventListener("pointerdown", outside, true); (focusables()[1] || pnl).focus(); };
  const close = (refocus = true) => { if (pnl.hidden) return; pnl.hidden = true; btn.setAttribute("aria-expanded", "false"); document.body.classList.remove("fpop-open");
    document.removeEventListener("pointerdown", outside, true); refocus && btn.focus(); };
  btn.onclick = () => pnl.hidden ? open() : close();
  $("#filtX").onclick = $("#filtOk").onclick = () => close();
  $("#filtReset").onclick = onReset;
  pnl.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key !== "Tab") return;
    const f = focusables(), first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  window.addEventListener("hashchange", () => close(false), { once: true });
}
// horizontal chip rows: fade only the edge that has more content, so no chip looks cut mid-word without a cue
function bindFade(el) {
  if (!el) return;
  const upd = () => { const max = el.scrollWidth - el.clientWidth;
    el.classList.toggle("fade-r", el.scrollLeft < max - 2); el.classList.toggle("fade-l", el.scrollLeft > 2); };
  el.addEventListener("scroll", upd, { passive: true }); new ResizeObserver(upd).observe(el); upd();
}
async function loadResults() {
  lastResults = await API.recipes(F);
  renderResults();
}
/* ---- list view modes: una | info | detalle | cuadricula (+ density 2..8 columns) */
const VIEWS = [["una", "Una sola", "square"], ["info", "Con info", "list"], ["detalle", "Muy detallado", "layout-list"], ["cuadricula", "Cuadrícula", "layout-grid"]];
let VIEW = (() => { try { const v = JSON.parse(localStorage.getItem("vistaLista") || "null"); if (v && VIEWS.some(x => x[0] === v.vista)) return { vista: v.vista, densidad: Math.min(8, Math.max(2, +v.densidad || 4)) }; } catch {} return { vista: "cuadricula", densidad: 4 }; })();
let viewSaveT;
function viewPicker() {
  return `<div class="viewpick"><div role="radiogroup" aria-label="Vista de la lista" class="seg vseg">${VIEWS.map(([v, l, i]) =>
    `<button type="button" role="radio" data-view="${v}" aria-checked="${VIEW.vista === v}" tabindex="${VIEW.vista === v ? 0 : -1}" title="${l}">${ic(i)}<span class="vlabel">${l}</span></button>`).join("")}</div>
    <label class="dens" ${VIEW.vista === "cuadricula" ? "" : "hidden"}><span>Columnas</span><input id="densR" type="range" min="2" max="8" step="1" value="${VIEW.densidad}" aria-valuetext="${VIEW.densidad} columnas"><output id="densO">${VIEW.densidad}</output></label></div>`;
}
function setView(p, save = true) {
  VIEW = { vista: p.vista ?? VIEW.vista, densidad: p.densidad ?? VIEW.densidad };
  localStorage.setItem("vistaLista", JSON.stringify(VIEW));
  $$("[data-view]").forEach(b => { const on = b.dataset.view === VIEW.vista; b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; });
  const d = $(".dens"); if (d) d.hidden = VIEW.vista !== "cuadricula";
  const r = $("#densR"); if (r) { r.value = VIEW.densidad; r.setAttribute("aria-valuetext", VIEW.densidad + " columnas"); $("#densO").textContent = VIEW.densidad; }
  renderResults();
  if (save) { clearTimeout(viewSaveT); viewSaveT = setTimeout(() => API.setPrefsLista(VIEW).catch(() => {}), 300); }
}
function bindViewPicker() {
  const btns = $$("[data-view]");
  btns.forEach((b, i) => {
    b.onclick = () => setView({ vista: b.dataset.view });
    b.onkeydown = e => {
      const k = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      let j = k ? (i + k + btns.length) % btns.length : e.key === "Home" ? 0 : e.key === "End" ? btns.length - 1 : -1;
      if (j < 0) return; e.preventDefault(); setView({ vista: btns[j].dataset.view }); btns[j].focus();
    };
  });
  const r = $("#densR"); if (r) r.oninput = () => setView({ densidad: +r.value });
}
const SRC_LABEL = { instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube", pinterest: "Pinterest", facebook: "Facebook", x: "X", web: "la web" };
const SRC_ICON = { instagram: "instagram", tiktok: "tiktok", youtube: "youtube", pinterest: "pinterest", facebook: "facebook", x: "x", web: "globe" };
function sourceLink(r, cls = "") {
  if (!r.source_url) return "";
  const name = SRC_LABEL[r.source_type] || "la web";
  return `<a class="srclink ${cls}" href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Ver original en ${esc(name)} (se abre en otra pestaña)">${ic(SRC_ICON[r.source_type] || "link")}<span>Ver original</span></a>`;
}
const PHASES = [["Preparación", /\b(cort|pic|pel|mezcl|bat|ralla|lav|añad|sazon|prepar|amas|forma|monta|unt)/i], ["Reposo", /\b(repos|enfr|refriger|marin|dej[ae] (que )?(repos|enfri|levant)|congel|nevera)/i], ["Cocción", /\b(horne|horno|fr[ií]e|cuec|coce|cocin|sofr[ií]|saltea|dora|hierv|asa|gratin|tuesta|hornea|sart[eé]n|airfryer|freidora)/i]];
function phaseTimes(r) {
  const acc = {};
  (r.pasos || []).forEach(p => { if (!p.minutos) return; const t = p.texto || ""; const f = (PHASES.find(([, rx]) => rx.test(t)) || ["Otros"])[0]; acc[f] = (acc[f] || 0) + p.minutos; });
  return ["Preparación", "Cocción", "Reposo", "Otros"].filter(k => acc[k]).map(k => `${k} ${acc[k]} min`);
}
function mainIngredients(r, n = 5) {
  return [...(r.ingredientes || [])].filter(i => i.nombre).sort((a, b) => (b.precio_eur || 0) - (a.precio_eur || 0)).slice(0, n).map(i => i.nombre);
}
const fdate = s => { const d = s ? new Date(s) : null; return d && !isNaN(d) ? d.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" }) : ""; };
function card(r) {
  if (VIEW.vista === "una") return cardWide(r, false);
  if (VIEW.vista === "info") return cardInfo(r);
  if (VIEW.vista === "detalle") return cardWide(r, true);
  return cardGrid(r);
}
function selBox(r) { return selecting ? `<input type="checkbox" class="sel" data-sel="${r.id}" aria-label="Seleccionar ${esc(r.titulo)}" ${selected.has(r.id) ? "checked" : ""}>` : ""; }
function thumbHtml(r) { const src = r.portada || r.media?.foto; return `<div class="thumb" aria-hidden="true">${placeholder(r)}${src ? `<img src="${esc(src)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</div>`; }
function cardGrid(r) {
  return `<article class="card vgrid ${r.estado !== "completa" ? "pending" : ""}">${selBox(r)}${r.favorito ? `<span class="fav">${ic("star", "Favorita", "fill")}</span>` : ""}
    <a href="#/receta/${r.id}" class="cardlink">${thumbHtml(r)}<div class="body"><h3>${esc(r.titulo)}</h3></div></a></article>`;
}
function cardInfo(r) {
  const pend = r.estado !== "completa";
  const bits = pend ? [`<span class="badge pend">Pendiente de transcribir</span>`] : [
    r.tiempo_total_min ? `<span>${ic("timer")} ${r.tiempo_total_min} min</span>` : "",
    r.raciones ? `<span>${ic("users")} ${r.raciones} rac.</span>` : "",
    r.precio_racion_eur != null ? `<span>${ic("euro")} ${eur(r.precio_racion_eur)}/rac. <span class="badge est">${t("est")}</span></span>` : ""].filter(Boolean);
  return `<article class="card vinfo ${pend ? "pending" : ""}">${selBox(r)}
    <a href="#/receta/${r.id}" class="cardlink">${thumbHtml(r)}<div class="body"><h3>${esc(r.titulo)}${r.favorito ? ` ${ic("star", "Favorita", "fill")}` : ""}</h3>${bits.length ? `<div class="meta">${bits.join("")}</div>` : ""}</div></a></article>`;
}
function cardWide(r, detailed) {
  const pend = r.estado !== "completa";
  const meta = pend ? [`<span class="badge pend">Pendiente de transcribir</span>`] : [
    r.tiempo_total_min ? `<span>${ic("timer")} ${r.tiempo_total_min} min</span>` : "",
    r.raciones ? `<span>${ic("users")} ${r.raciones} raciones</span>` : "",
    r.precio_racion_eur != null ? `<span>${ic("euro")} ${eur(r.precio_racion_eur)}/ración <span class="badge est">${t("est")}</span></span>` : ""].filter(Boolean);
  let extra = "";
  if (detailed) {
    const ings = mainIngredients(r), ph = phaseTimes(r), tags = r.etiquetas || [], fecha = fdate(r.creado);
    const rows = [
      ings.length ? `<div><dt>Ingredientes principales</dt><dd>${ings.map(esc).join(", ")}</dd></div>` : "",
      ph.length ? `<div><dt>Tiempo por fase</dt><dd>${ph.join(" · ")}</dd></div>` : "",
      r.precio_total_eur != null || r.precio_racion_eur != null ? `<div><dt>Coste estimado</dt><dd>${[r.precio_total_eur != null ? `${eur(r.precio_total_eur)} total` : "", r.precio_racion_eur != null ? `${eur(r.precio_racion_eur)}/ración` : ""].filter(Boolean).join(" · ")}</dd></div>` : "",
      r.autor ? `<div><dt>Fuente</dt><dd>${esc(r.autor)}</dd></div>` : "",
      fecha ? `<div><dt>Añadida</dt><dd>${fecha}</dd></div>` : ""].filter(Boolean);
    extra = (rows.length ? `<dl class="facts">${rows.join("")}</dl>` : "") + (tags.length ? `<div class="tags">${tags.slice(0, 4).map(x => `<span class="chip small">${esc(x)}</span>`).join("")}${tags.length > 4 ? `<span class="chip small more" title="${esc(tags.slice(4).join(", "))}">+${tags.length - 4}<span class="sr"> etiquetas más: ${esc(tags.slice(4).join(", "))}</span></span>` : ""}</div>` : "");
  }
  return `<article class="card ${detailed ? "vdet" : "vuna"} ${pend ? "pending" : ""}">${selBox(r)}${r.favorito ? `<span class="fav">${ic("star", "Favorita", "fill")}</span>` : ""}
    <a href="#/receta/${r.id}" class="cardlink">${thumbHtml(r)}<div class="body"><h3>${esc(r.titulo)}</h3>
      ${meta.length ? `<div class="meta">${meta.join("")}</div>` : ""}${!detailed && r.autor ? `<div class="meta"><span>${esc(r.autor)}</span></div>` : ""}${extra}</div></a>
    ${detailed && r.source_url ? `<div class="cardfoot">${sourceLink(r)}</div>` : ""}</article>`;
}
function renderResults() {
  const box = $("#results"); if (!box) return;
  $("#count").textContent = t("results", lastResults.length);
  if (!lastResults.length) {
    box.innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="big">${ic("utensils")}</div><h2>${t("empty_title")}</h2><p>${t("empty_body")}</p>
      <button class="btn" type="button" id="clearF">${t("clear")}</button></div>`;
    $("#clearF").onclick = () => { Object.assign(F, { q: "", estado: "", favoritos: false, etiqueta: "", max_min: "", max_precio: "" }); sessionStorage.removeItem("filtros"); viewList(); };
  } else box.innerHTML = lastResults.map(card).join("");
  box.className = `grid v-${VIEW.vista}`; box.style.setProperty("--cols", VIEW.densidad);
  $$("[data-sel]").forEach(c => c.onchange = () => { const id = +c.dataset.sel; c.checked ? selected.add(id) : selected.delete(id); renderSelbar(); });
  renderSelbar();
}
function renderSelbar() {
  const bar = $("#selbar"); if (!bar) return;
  if (!selecting) { bar.innerHTML = ""; return; }
  bar.innerHTML = `<div class="selbar"><b>${t("selected", selected.size)}</b><div class="row">
    <button class="btn sm" type="button" id="selAll">Todas las visibles</button><button class="btn sm" type="button" id="selNone">Ninguna</button>
    ${API.STATIC ? "" : `<button class="btn sm" type="button" id="selExp" ${selected.size ? "" : "disabled"}>${ic("download")} ${t("export")}</button>`}</div></div>`;
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
    <div class="row" style="justify-content:flex-end"><button class="btn" value="cancel" type="submit">${t("cancel")}</button><button class="btn primary" id="doExp" type="button">${ic("download")} Descargar</button></div>
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
  const sl = sourceLink(r);
  const link = sl ? `<p class="iglink">${sl}</p>` : "";
  if (r.media?.video) return `<div class="vf"><video src="${esc(r.media.video)}" controls playsinline preload="metadata" ${r.portada ? `poster="${esc(r.portada)}"` : ""}></video></div>${link}`;
  const code = r.shortcode;
  if (!code || API.STATIC) return (r.media?.foto ? `<img class="photo" src="${esc(r.media.foto)}" alt="">` : "") + link;
  // Fallback kept from v1: cropped Instagram embed scaled to fit
  return `<div class="emb"><div class="embi"><iframe title="Vídeo de Instagram" src="https://www.instagram.com/reel/${esc(code)}/embed/" loading="lazy" allowfullscreen scrolling="no"></iframe></div></div>${link}`;
}
function fitVideo() { $$(".vf video").forEach(v => { const set = () => { if (v.videoWidth) { v.parentElement.style.aspectRatio = `${v.videoWidth} / ${v.videoHeight}`; v.parentElement.classList.toggle("wide", v.videoWidth > v.videoHeight); } };
  v.readyState >= 1 ? set() : v.addEventListener("loadedmetadata", set, { once: true }); }); }
function fitEmb() { $$(".emb").forEach(e => { const k = Math.min(1, e.clientWidth / 358); e.firstElementChild.style.transform = `scale(${k})`; e.style.height = (431 * k) + "px"; }); }
addEventListener("resize", fitEmb);

async function viewDetail(id) {
  const r = await API.recipe(id);
  setTitle(r.titulo);
  const pend = r.estado !== "completa";
  const base = r.raciones || 1; let k = 1;
  main.innerHTML = `
  <nav class="crumbs"><a href="#/recetas">${ic("arrow-left")} ${t("nav_recetas")}</a></nav>
  <div class="detail">
    <div>
      <div class="panel">
        <div class="row" style="justify-content:space-between;align-items:flex-start">
          <h1 class="grow">${esc(r.titulo)}</h1>
          ${API.STATIC ? "" : `<button class="icon-btn no-print" id="favBtn" type="button" aria-pressed="${!!r.favorito}" aria-label="Favorita">${ic("star", "", r.favorito ? "fill" : "")}</button>`}
        </div>
        <p class="muted" style="margin:0">${r.autor ? `de <b>${esc(r.autor)}</b>` : ""} </p>
        ${API.STATIC ? "" : `<div class="row no-print" style="margin-top:.5rem"><span class="small muted">Tu valoración</span><span class="stars" role="group" aria-label="Valoración">${[1, 2, 3, 4, 5].map(n => `<button type="button" data-star="${n}" class="${(r.valoracion || 0) >= n ? "on" : ""}" aria-label="${n} estrellas">${ic("star")}</button>`).join("")}</span></div>`}
        ${pend ? `<div class="banner"><span>${ic("film")} ${t("pending_banner")}</span>${API.STATIC ? "" : `<a class="btn sm" href="#/editar/${r.id}">${ic("pen-line")} ${t("transcribe")}</a>`}</div>` : `
        <div class="facts">
          <div class="fact"><b>${r.tiempo_total_min ?? "—"} min</b><span>tiempo total</span></div>
          <div class="fact"><b>${eur(r.precio_racion_eur)}</b><span>por ración · ${t("est")}</span></div>
          <div class="fact"><b>${eur(r.precio_total_eur)}</b><span>total · ${t("est")}</span></div>
          ${r.nutricion?.kcal ? `<div class="fact"><b>${r.nutricion.kcal} kcal</b><span>por ración · ${t("est")}</span></div>` : ""}
        </div>`}
        <div class="row">${(r.etiquetas || []).map(x => `<a class="chip" href="#/recetas" data-gotag="${esc(x)}">${esc(x)}</a>`).join("")}</div>
        ${(r.alergenos || []).length ? `<p class="small" style="margin:.6rem 0 0"><b>Alérgenos (orientativo):</b> ${(r.alergenos).map(a => `<span class="badge alg">${esc(a)}</span>`).join(" ")}</p>` : ""}
        <div class="actions no-print">
          ${pend || !r.pasos?.length ? "" : `<button class="btn primary" id="cookBtn" type="button">${ic("chef-hat")} ${t("cook_mode")}</button>`}
          ${API.STATIC || pend ? "" : `<button class="btn" id="toList" type="button">${ic("shopping-cart")} Añadir a la lista</button><button class="btn" id="toPlan" type="button">${ic("calendar-days")} Planificar</button>`}
          <button class="btn" type="button" onclick="print()">${ic("printer")} ${t("print")}</button>
          ${API.STATIC ? "" : `<a class="btn" href="#/editar/${r.id}">${ic("pencil")} ${t("edit")}</a>
          <button class="btn" id="trBtn" type="button">${ic("languages")} ${t("translate")}</button>
          <button class="btn ghost danger" id="delBtn" type="button">${ic("trash-2")} ${t("delete")}</button>`}
        </div>
      </div>
      ${pend ? "" : `
      <section class="panel" aria-labelledby="hIng">
        <div class="row" style="justify-content:space-between"><h2 id="hIng">${t("ingredients")}</h2>
          <div class="scaler"><button class="icon-btn" type="button" id="minus" aria-label="Menos raciones">${ic("minus")}</button>
            <output id="srv" aria-live="polite">${base}</output><span>${t("servings")}${r.raciones_estimadas ? ` <span class="badge est" title="El vídeo no lo dice">${t("est")}</span>` : ""}</span>
            <button class="icon-btn" type="button" id="plus" aria-label="Más raciones">${ic("plus")}</button></div></div>
        <ul class="ings" id="ings"></ul>
        <p class="small muted" style="margin-bottom:0">${ic("euro")} Precios <b>estimados</b>: solo orientativos. <span id="ptot"></span></p>
      </section>
      <section class="panel" aria-labelledby="hSt"><h2 id="hSt">${t("steps")}</h2>
        <ol class="steps">${(r.pasos || []).map((s, i) => `<li><div><p style="margin:0">${esc(s.texto)}</p>${s.minutos ? `<button class="btn sm no-print" style="margin-top:.4rem" type="button" data-timer="${i}">${ic("timer")} ${s.minutos} min</button>` : ""}</div></li>`).join("")}</ol>
        ${(r.pasos_sugeridos) ? `<p class="small muted">Pasos sugeridos (no aparecen en el vídeo).</p>` : ""}
      </section>`}
      ${r.notas || r.nota ? `<section class="panel"><h2>${t("notes")}</h2><p style="white-space:pre-line;margin:0">${esc(r.notas || r.nota)}</p></section>` : ""}
    </div>
    <aside>
      ${videoFrame(r) ? `<div class="panel no-print">${videoFrame(r)}</div>` : ""}
      ${API.STATIC ? "" : `<section class="panel no-print"><h2>Lo he cocinado</h2>
        <ul class="joblist">${(r.cocinado || []).map((c, i) => `<li>${ic("utensils")} <b>${esc(c.fecha)}</b> <span class="grow">${esc(c.notas || "")}</span><button class="btn sm ghost" type="button" data-delc="${i}" aria-label="Borrar">${ic("x")}</button></li>`).join("") || `<li class="muted small">Aún no hay registros.</li>`}</ul>
        <form id="cookLog" class="row"><label class="sr" for="cd">Fecha</label><input id="cd" class="input" type="date" required value="${new Date().toISOString().slice(0, 10)}" style="width:auto">
          <label class="sr" for="cn">Notas</label><input id="cn" class="input grow" placeholder="Notas (opcional)" maxlength="500"><button class="btn" type="submit">Añadir</button></form></section>`}
    </aside>
  </div>`;
  setTimeout(fitEmb, 50); fitVideo();
  $$("[data-gotag]").forEach(a => a.onclick = () => { F.etiqueta = a.dataset.gotag; sessionStorage.setItem("filtros", JSON.stringify(F)); });
  const ings = $("#ings");
  let scaled = null, seq = 0;
  async function rescale() {
    if (API.STATIC || k === 1) { scaled = null; return paint(); }
    const my = ++seq; paint();
    try { const s = await API.scale(r.id, base * k); if (my === seq) { scaled = s; paint(); } } catch { }
  }
  function paint() {
    if (!ings) return;
    $("#srv").textContent = fmtQty(base * k);
    const S = scaled && Math.abs(scaled.raciones - base * k) < 1e-9 ? scaled.ingredientes : null;
    ings.innerHTML = (r.ingredientes || []).map((i, n) => { const v = S?.[n]; const s = v ? { q: v.texto, approx: v.redondeado } : scaleIng(i, k);
      return `<li><input type="checkbox" id="i${n}"><label for="i${n}"><span class="q">${esc(s.q)}</span> ${esc(i.nombre)}${s.approx ? ` <span class="small muted">(redondeado)</span>` : ""}${i.estimada ? ` <span class="badge est" title="Cantidad estimada">≈</span>` : ""}</label>
      <span class="p">${i.precio_eur != null ? eur(i.precio_eur * k) + " " + priceBadge(i) : ""}</span></li>`; }).join("");
    $("#ptot").textContent = r.precio_total_eur != null ? `Total ≈ ${eur(r.precio_total_eur * k)}` : "";
  }
  paint();
  $("#plus") && ($("#plus").onclick = () => { k = (base * k + 1) / base; rescale(); });
  $("#minus") && ($("#minus").onclick = () => { if (base * k > 1) { k = (base * k - 1) / base; rescale(); } });
  $("#toList") && ($("#toList").onclick = () => listPicker(`Añadir «${r.titulo}» a la lista`, Math.round(base * k * 100) / 100, async (lid, n) => {
    const l = await API.shop.addRecipe(lid, r.id, n); toast(`${l.añadidos} ingredientes añadidos a «${l.nombre}»`); }));
  $("#toPlan") && ($("#toPlan").onclick = () => planDialog(r, k === 1 ? planServings(r) : Math.round(base * k)));
  $$("[data-timer]").forEach(b => b.onclick = () => startTimer(`${r.titulo.slice(0, 24)} · paso ${+b.dataset.timer + 1}`, r.pasos[b.dataset.timer].minutos));
  $("#cookBtn") && ($("#cookBtn").onclick = () => cookMode(r));
  $("#favBtn") && ($("#favBtn").onclick = () => guard(async () => { r.favorito = !r.favorito; await API.patch(r.id, { favorito: r.favorito }); $("#favBtn").innerHTML = ic("star", "", r.favorito ? "fill" : ""); $("#favBtn").setAttribute("aria-pressed", r.favorito); toast(r.favorito ? "Añadida a favoritas" : "Quitada de favoritas"); }));
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
    el.innerHTML = `<span>${ic("timer")} ${esc(label)}</span><b>${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}</b><button type="button" aria-label="Quitar temporizador">${ic("x")}</button>`;
    el.querySelector("button").onclick = () => { clearInterval(iv); el.remove(); };
    if (!s) { clearInterval(iv); el.classList.add("done"); beep(); toast(`${label}: ¡tiempo!`); } };
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
      <button class="btn" type="button" id="ckX">${ic("x")} Salir</button></header>
      <div class="progress" style="margin:1rem 0"><i style="width:${(i + 1) / r.pasos.length * 100}%"></i></div>
      <div class="big"><p>${esc(s.texto)}</p></div>
      <footer><button class="btn" type="button" id="ckP" ${i ? "" : "disabled"}>${ic("arrow-left")} Anterior</button>
      ${s.minutos ? `<button class="btn" type="button" id="ckT">${ic("timer")} ${s.minutos} min</button>` : ""}
      <button class="btn primary" type="button" id="ckN">${i === r.pasos.length - 1 ? `¡Listo! ${ic("check")}` : `Siguiente ${ic("arrow-right")}`}</button></footer>`;
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
    <button class="btn sm ghost" type="button" data-rm aria-label="Quitar">${ic("x")}</button></div>`;
  const stepRow = (s = {}) => `<div class="editor-row step" data-step>
    <textarea class="input" aria-label="Paso" name="t" rows="2" style="min-height:60px" required>${esc(s.texto || "")}</textarea>
    <input class="input" aria-label="Minutos" inputmode="numeric" name="m" value="${s.minutos ?? ""}" placeholder="min">
    <button class="btn sm ghost" type="button" data-rm aria-label="Quitar">${ic("x")}</button></div>`;
  main.innerHTML = `
  <nav class="crumbs"><a href="${isDraft ? "#/importar" : id ? `#/receta/${id}` : "#/recetas"}">${ic("arrow-left")} ${t("back")}</a></nav>
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
      <textarea class="input" id="cap" placeholder="Pega aquí la descripción del vídeo…"></textarea><button class="btn sm" type="button" id="parse" style="margin-top:.4rem">${ic("sparkles")} Rellenar</button></details>` : ""}
    <h2 style="margin-top:1.5rem">${t("ingredients")}</h2><div id="ingList">${(r.ingredientes || []).map(ingRow).join("")}</div>
    <div class="row"><button class="btn sm" type="button" id="addIng">${ic("plus")} Ingrediente</button>${API.STATIC ? "" : `<button class="btn sm" type="button" id="estBtn">${ic("euro")} Estimar precios con IA</button>`}</div>
    <h2 style="margin-top:1.5rem">${t("steps")}</h2><div id="stepList">${(r.pasos || []).map(stepRow).join("")}</div>
    <button class="btn sm" type="button" id="addStep">${ic("plus")} Paso</button>
    <label class="f" for="no">${t("notes")}</label><textarea id="no" class="input" name="notas">${esc(r.notas || r.nota || "")}</textarea>
    ${id && !isDraft ? `<h2 style="margin-top:1.5rem">Foto y vídeo</h2>
      <div class="form-grid"><div class="drop"><label class="f" for="upF">Foto (JPG, PNG, WebP · máx. 10 MB)</label><input id="upF" type="file" accept="image/jpeg,image/png,image/webp">${r.media?.foto ? `<p class="small">Actual: <a href="${esc(r.media.foto)}" target="_blank">ver</a> · <button class="btn sm ghost" type="button" data-delm="foto">quitar</button></p>` : ""}</div>
      <div class="drop"><label class="f" for="upV">Vídeo (MP4, WebM, MOV · máx. 300 MB)</label><input id="upV" type="file" accept="video/mp4,video/webm,video/quicktime">${r.media?.video ? `<p class="small">Actual: <a href="${esc(r.media.video)}" target="_blank">ver</a> · <button class="btn sm ghost" type="button" data-delm="video">quitar</button></p>` : ""}</div></div>` : !isDraft ? `<p class="muted small">Podrás subir foto y vídeo después de guardar.</p>` : ""}
    <div class="row" style="justify-content:flex-end;margin-top:1.5rem">
      ${isDraft ? `<button class="btn ghost danger" type="button" id="discard">Descartar</button><button class="btn" type="button" id="saveDraft">Guardar borrador</button><button class="btn primary" type="submit">${ic("check")} Añadir al recetario</button>`
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
    ${drafts.length ? `<button class="btn" type="button" id="goRev">${ic("notebook-pen")} ${drafts.length} borrador${drafts.length > 1 ? "es" : ""} por revisar</button>` : ""}</div>
    <ol class="stepper">${WSTEPS.map((s, i) => `<li ${W.step === i + 1 ? 'aria-current="step"' : ""} class="${W.step > i + 1 ? "done" : ""}"><b>${W.step > i + 1 ? ic("check", "Hecho") : i + 1}</b>${s}</li>`).join("")}</ol>
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
  ${st.conectado ? `<div class="banner">${ic("circle-check")} Conectado como <b>@${esc(st.usuario)}</b> <span class="muted small">(${esc(st.proveedor)})</span><button class="btn sm" type="button" id="igOut">Desconectar</button><button class="btn primary" type="button" id="next">Continuar ${ic("arrow-right")}</button></div>` : `
  <p class="muted small">${ic("lock")} La contraseña solo se usa para iniciar sesión y <b>nunca se guarda</b>: se conserva únicamente el archivo de sesión en este equipo. Instagram puede pedir verificación o limitar peticiones si importas mucho de golpe.</p>
  <div class="seg" role="tablist"><button type="button" aria-pressed="true" data-lt="pw">Usuario y contraseña</button><button type="button" aria-pressed="false" data-lt="ck">Cookie de sesión</button></div>
  <form id="lgPw" style="max-width:420px"><label class="f" for="u">Usuario</label><input id="u" class="input" autocomplete="username" required>
    <label class="f" for="p">Contraseña</label><input id="p" class="input" type="password" autocomplete="current-password" required>
    <button class="btn primary" style="margin-top:1rem" type="submit">Conectar Instagram</button></form>
  <form id="lg2fa" hidden style="max-width:420px"><label class="f" for="c">Código de verificación (2FA)</label><input id="c" class="input" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required>
    <button class="btn primary" style="margin-top:1rem" type="submit">Verificar</button></form>
  <form id="lgCk" hidden style="max-width:520px"><p class="small muted">Si ya tienes sesión en el navegador: copia el valor de la cookie <code>sessionid</code> de instagram.com (herramientas de desarrollador ${ic("arrow-right")} Almacenamiento ${ic("arrow-right")} Cookies).</p>
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
  wz.innerHTML = `<h2>Elige una colección de guardados</h2><div class="coll">${cols.map(c => `<button class="panel" type="button" data-c="${esc(c.id)}" style="margin:0"><b style="font-size:1.05rem">${ic("folder")} ${esc(c.nombre)}</b><br><span class="muted small">${c.total != null ? c.total + " publicaciones" : "todas tus publicaciones guardadas"}</span></button>`).join("")}</div>
  <div class="row" style="margin-top:1rem"><button class="btn" type="button" id="bk">${ic("arrow-left")} Atrás</button></div>`;
  $$("[data-c]").forEach(b => b.onclick = () => { W.coll = cols.find(c => c.id === b.dataset.c); W.step = 3; W.pick.clear(); viewImport(); });
  $("#bk").onclick = () => { W.step = 1; viewImport(); };
}
const thumbSrc = u => !u ? "" : u.startsWith("data:") ? u : `/api/instagram/thumb?u=${encodeURIComponent(u)}`;
async function wizPosts(wz) {
  wz.innerHTML = `<p class="muted">Cargando publicaciones…</p>`;
  W.posts = await API.ig.posts(W.coll.id);
  const nuevos = W.posts.filter(p => p.estado === "nuevo");
  function paint() {
    wz.innerHTML = `<div class="row" style="justify-content:space-between"><h2 style="margin:0">${ic("folder")} ${esc(W.coll.nombre)} <span class="muted small">· ${W.posts.length} publicaciones, ${nuevos.length} nuevas</span></h2>
      <div class="row"><button class="btn sm" type="button" id="all">Seleccionar nuevas</button><button class="btn sm" type="button" id="none">Ninguna</button>
      <label class="small">Para todas: <select class="input" id="bulk" style="width:auto;min-height:34px"><option value="">—</option><option value="ambos">vídeo + foto</option><option value="video">solo vídeo</option><option value="foto">solo foto</option></select></label></div></div>
    <div class="posts" style="margin-top:1rem">${W.posts.map(p => { const on = W.pick.has(p.shortcode), dis = p.estado !== "nuevo";
      return `<div class="post ${on ? "on" : ""}"><div class="thumb">${p.miniatura ? `<img src="${esc(thumbSrc(p.miniatura))}" alt="" loading="lazy">` : `<span class="ph">${ic("image")}</span>`}</div>
      <div class="pb"><label class="pick"><input type="checkbox" data-p="${esc(p.shortcode)}" ${on ? "checked" : ""} ${dis ? "disabled" : ""}> <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.caption.split("\n")[0] || p.shortcode)}</span></label>
      <span class="muted">${esc(p.autor)} · ${p.es_video ? ic("film", "Vídeo") : ic("image", "Foto")}</span>
      ${dis ? `<span class="badge ${p.estado === "importado" ? "real" : "est"}">${p.estado === "importado" ? "ya en el recetario" : "borrador pendiente"}</span>` :
      `<select class="input" data-k="${esc(p.shortcode)}" aria-label="Qué descargar" ${on ? "" : "disabled"}>${[["ambos", "vídeo + foto"], ["video", "solo vídeo"], ["foto", "solo foto"]].map(([v, l]) => `<option value="${v}" ${(W.pick.get(p.shortcode) || (p.es_video ? "ambos" : "foto")) === v ? "selected" : ""}>${l}</option>`).join("")}</select>`}</div></div>`; }).join("")}</div>
    <div class="selbar"><b>${W.pick.size} seleccionada${W.pick.size === 1 ? "" : "s"}</b><div class="row"><button class="btn sm" type="button" id="bk">${ic("arrow-left")} Colecciones</button><button class="btn sm" type="button" id="go" ${W.pick.size ? "" : "disabled"}>Importar ${ic("arrow-right")}</button></div></div>`;
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
  const ICON = { pendiente: ["hourglass", "Pendiente"], descargando: ["download", "Descargando"], ok: ["circle-check", "Importada"], incompleto: ["file-pen", "Incompleta"], duplicado: ["rotate-ccw", "Duplicada"], error: ["triangle-alert", "Error"] };
  async function poll() {
    if (!document.body.contains(wz)) return;
    const j = W.job = await API.ig.job(W.job.id);
    wz.innerHTML = `<h2>Importando ${j.hechos} de ${j.total}</h2>
      <div class="progress" role="progressbar" aria-valuenow="${j.progreso}" aria-valuemin="0" aria-valuemax="100"><i style="width:${j.progreso}%"></i></div>
      ${j.resumen && ["terminado", "cancelado"].includes(j.estado) ? `<p class="jobsum">${j.resumen.ok} importadas · ${j.resumen.incompleto} incompletas · ${j.resumen.duplicado} duplicadas · ${j.resumen.error} con error</p>` : ""}
      <ul class="joblist">${j.items.map(i => `<li class="st-${i.estado}">${ic(...(ICON[i.estado] || ["circle-dashed", i.estado]))} <b>${esc(i.shortcode)}</b> <span class="muted grow">${esc(i.mensaje || i.estado)}${i.code ? ` <code class="small">${esc(i.code)}</code>` : ""}</span>
        ${i.estado === "incompleto" && i.draft_id ? `<span class="row"><a class="btn sm" href="#/borrador/${i.draft_id}">${ic("pencil")} Completar a mano</a><button class="btn sm ghost" type="button" data-keep="${i.draft_id}">${ic("file-pen")} Guardar como borrador</button></span>` : ""}</li>`).join("")}</ul>
      <div class="row">${["terminado", "cancelado"].includes(j.estado) ? `<button class="btn primary" type="button" id="rev">Revisar borradores ${ic("arrow-right")}</button>` : `<button class="btn" type="button" id="cn">Cancelar</button><span class="muted small">Puedes salir de esta pantalla: la importación sigue en segundo plano.</span>`}</div>`;
    $("#rev") && ($("#rev").onclick = () => { W.step = 5; viewImport(); });
    $("#cn") && ($("#cn").onclick = () => guard(() => API.ig.cancel(j.id)));
    $$("[data-keep]", wz).forEach(b => b.onclick = () => { b.replaceWith(Object.assign(document.createElement("span"), { className: "badge est", textContent: "En borradores" })); toast("Guardado en borradores: complétalo cuando quieras"); });
    if (!["terminado", "cancelado"].includes(j.estado)) setTimeout(poll, 800);
  }
  if (!W.job) { W.step = 5; return viewImport(); }
  await poll();
}
function wizReview(wz, drafts) {
  wz.innerHTML = `<h2>Revisa antes de guardar</h2>
  ${drafts.length ? `<p class="muted">Abre cada borrador, corrige lo que haga falta y añádelo al recetario.</p><div class="grid">${drafts.map(d => `<article class="card"><a href="#/borrador/${d.id}" style="color:inherit;text-decoration:none">
    <div class="thumb">${d.foto ? `<img src="/${esc(d.foto)}" alt="" loading="lazy">` : placeholder(d)}</div>
    <div class="body"><h3>${esc(d.titulo)}</h3><div class="meta"><span>${(d.ingredientes || []).length} ingredientes · ${(d.pasos || []).length} pasos</span>
    <span class="badge ${d.metodo === "ia" ? "real" : "est"}">${d.metodo === "ia" ? "IA" : "automático"}</span></div></div></a></article>`).join("")}</div>`
    : `<div class="empty"><div class="big">${ic("inbox")}</div><h2>No hay borradores</h2><p>Importa publicaciones para revisarlas aquí.</p></div>`}
  <div class="row" style="margin-top:1rem"><button class="btn" type="button" id="again">${ic("plus")} Importar más</button></div>`;
  $("#again").onclick = () => { W.step = 1; W.job = null; viewImport(); };
}

/* =========================================================== LOGIN */
const AUTH = { ok: API.STATIC, user: "" };
async function viewLogin() {
  setTitle("Entrar");
  renderNav(""); $("#nav").innerHTML = ""; $("#tabbar").innerHTML = "";
  let me = {}; try { me = await API.auth.me(); } catch { }
  const setup = !!me.necesita_configuracion;
  main.innerHTML = `<div class="login"><div class="panel">
    <div class="login-logo" aria-hidden="true">${ic("chef-hat")}</div>
    <h1>${setup ? "Crea tu acceso" : "Entrar"}</h1>
    <p class="muted">${setup ? "Primera vez: elige usuario y contraseña de administrador (mínimo 10 caracteres). También puedes crearlo con <code>python -m app.cli create-admin</code>." : "Tu recetario es privado. Entra para continuar."}</p>
    <form id="lf" autocomplete="on">
      <label class="f" for="lu">Usuario</label><input id="lu" class="input" name="username" autocomplete="username" required maxlength="60" value="${setup ? "admin" : ""}">
      <label class="f" for="lp">Contraseña</label><input id="lp" class="input" name="password" type="password" autocomplete="${setup ? "new-password" : "current-password"}" required ${setup ? 'minlength="10"' : ""}>
      ${setup ? `<label class="f" for="lc">Código de configuración <span class="muted small">(solo si no estás en el propio servidor; aparece en el registro y en <code>setup-code.txt</code>)</span></label><input id="lc" class="input" autocomplete="off" maxlength="64">` : ""}
      <p id="lerr" class="lerr" role="alert" aria-live="assertive"></p>
      <button class="btn primary wide" type="submit">${setup ? "Crear y entrar" : "Entrar"}</button>
    </form></div>
    <p class="small muted" style="text-align:center">${ic("lock")} Sesión segura · la contraseña se guarda cifrada (argon2)</p></div>`;
  $("#lu").focus();
  $("#lf").onsubmit = async e => {
    e.preventDefault(); const btn = $("#lf button[type=submit]"); btn.disabled = true; $("#lerr").textContent = "";
    try {
      const m = setup ? await API.auth.setup($("#lu").value.trim(), $("#lp").value, $("#lc")?.value || "")
        : await API.auth.login($("#lu").value.trim(), $("#lp").value);
      AUTH.ok = true; AUTH.user = m.usuario;
      if (!location.hash || location.hash === "#/login") location.hash = "#/recetas"; else router();
    } catch (err) { $("#lerr").textContent = err.message; $("#lp").select(); }
    finally { btn.disabled = false; }
  };
}
addEventListener("auth-required", () => { if (AUTH.ok) { AUTH.ok = false; toast("Tu sesión ha caducado", true); } viewLogin(); });

/* ---------- shared pickers ---------- */
const COMIDAS = [["comida", "Comida"], ["cena", "Cena"]];
const DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"];
const fmtDay = (iso, long) => new Date(iso + "T12:00").toLocaleDateString("es-ES", long ? { weekday: "long", day: "numeric", month: "long" } : { day: "numeric", month: "short" });
const isoToday = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
let recipeCache = null;
async function allRecipes() { return recipeCache ??= (await API.recipes({})).filter(r => r.tipo === "receta"); }
function recipePicker(title, onPick) {
  const d = dialog(`<div class="dlg picker"><h2>${esc(title)}</h2>
    <label class="sr" for="pq">Buscar receta</label><input id="pq" class="input" type="search" placeholder="Buscar receta…" autocomplete="off">
    <ul class="pick" id="pl" role="listbox" aria-label="Recetas"></ul>
    <form method="dialog" class="row" style="justify-content:flex-end"><button class="btn">${t("cancel")}</button></form></div>`);
  allRecipes().then(all => {
    const paint = () => { const q = norm($("#pq", d).value); $("#pl", d).innerHTML = all.filter(r => !q || norm(r.titulo).includes(q)).slice(0, 60)
      .map(r => `<li><button type="button" class="pickbtn" data-pick="${r.id}">${ic(iconFor(r))}<span class="grow">${esc(r.titulo)}</span><span class="small muted">${r.raciones || ""} rac.</span></button></li>`).join("") || `<li class="muted small">Sin resultados</li>`;
      $$("[data-pick]", d).forEach(b => b.onclick = () => { d.close(); onPick(all.find(r => r.id == b.dataset.pick)); }); };
    $("#pq", d).oninput = paint; paint(); $("#pq", d).focus();
  });
}
async function listPicker(title, servings, onPick) {
  const lists = await API.shop.lists();
  const d = dialog(`<form class="dlg" id="lpF"><h2>${esc(title)}</h2>
    <label class="f" for="lps">Lista</label><select id="lps" class="input">${lists.map(l => `<option value="${l.id}">${esc(l.nombre)}</option>`).join("")}<option value="new">+ Nueva lista…</option></select>
    <div id="lpn" hidden><label class="f" for="lpnn">Nombre de la nueva lista</label><input id="lpnn" class="input" value="Lista de la compra" maxlength="80"></div>
    ${servings != null ? `<label class="f" for="lpr">Raciones</label><input id="lpr" class="input" type="number" min="0.5" max="200" step="any" value="${servings}" style="width:8rem">` : ""}
    <div class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn" type="button" value="cancel" id="lpc">${t("cancel")}</button><button class="btn primary" type="submit">${ic("shopping-cart")} Añadir</button></div></form>`);
  const sel = $("#lps", d); const syncNew = () => $("#lpn", d).hidden = sel.value !== "new";
  if (!lists.length) sel.value = "new"; syncNew(); sel.onchange = syncNew;
  $("#lpc", d).onclick = () => d.close();
  $("#lpF", d).onsubmit = e => { e.preventDefault(); guard(async () => {
    let id = sel.value; if (id === "new") id = (await API.shop.create($("#lpnn", d).value.trim())).id;
    d.close(); await onPick(+id, servings != null ? +$("#lpr", d).value : null); }); };
}
// mirrors app/services/planner.py default_servings: declared servings, else 2 (estimated values and batch yields fall back)
function planServings(r) { const n = r.raciones; return !r.raciones_estimadas && typeof n === "number" && n > 0 && n <= 12 ? n : 2; }
function planDialog(r, servings) {
  const d = dialog(`<form class="dlg" id="pdF"><h2>${ic("calendar-days")} Planificar «${esc(r.titulo)}»</h2>
    <div class="form-grid"><div><label class="f" for="pdd">Día</label><input id="pdd" type="date" class="input" required value="${isoToday()}"></div>
    <div><label class="f" for="pdc">Comida</label><select id="pdc" class="input">${COMIDAS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></div></div>
    <label class="f" for="pdr">Raciones</label><input id="pdr" class="input" type="number" min="1" max="200" value="${servings}" style="width:8rem">
    <div class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn" type="button" id="pdx">${t("cancel")}</button><button class="btn primary" type="submit">Añadir al plan</button></div></form>`);
  $("#pdx", d).onclick = () => d.close();
  $("#pdF", d).onsubmit = e => { e.preventDefault(); guard(async () => { await API.plan.add({ fecha: $("#pdd", d).value, comida: $("#pdc", d).value, receta_id: r.id, raciones: +$("#pdr", d).value }); d.close(); toast("Añadida al planificador"); }); };
}

/* =========================================================== PLANNER */
const PLAN = { inicio: null };
async function viewPlanner() {
  setTitle(t("nav_plan"));
  if (API.STATIC) { main.innerHTML = `<h1>${t("nav_plan")}</h1><div class="empty"><div class="big">${ic("calendar-days")}</div><h2>Disponible en tu servidor</h2><p>El planificador semanal guarda datos, así que no está en la demo de solo lectura.</p></div>`; return; }
  const wk = await API.plan.week(PLAN.inicio);
  PLAN.inicio = wk.inicio;
  const today = isoToday();
  const bySlot = {}; wk.items.forEach(p => (bySlot[p.fecha + "|" + p.comida] ??= []).push(p));
  const totalRac = wk.items.reduce((a, p) => a + p.raciones, 0);
  main.innerHTML = `
  <div class="hero"><div><h1>${t("nav_plan")}</h1><p class="muted" style="margin:0">${wk.items.length ? `${wk.items.length} platos · ${fmtQty(totalRac)} raciones esta semana` : "Organiza tus comidas y cenas de la semana"}</p></div>
    <div class="row no-print hero-actions">
      <button class="btn" type="button" id="wPrev" aria-label="Semana anterior">${ic("arrow-left")}</button>
      <button class="btn" type="button" id="wToday">Esta semana</button>
      <button class="btn" type="button" id="wNext" aria-label="Semana siguiente">${ic("arrow-right")}</button>
      <button class="btn primary full-m" type="button" id="wList" ${wk.items.length ? "" : "disabled"}>${ic("shopping-cart")} Añadir a la lista</button>
    </div></div>
  <p class="weeklabel"><b>Semana del ${fmtDay(wk.inicio)} al ${fmtDay(wk.fin)}</b> <span class="muted small">· Arrastra los platos entre huecos o usa «Mover».</span></p>
  <div class="week" id="week">${wk.dias.map((d, i) => `
    <section class="day ${d === today ? "today" : ""}" aria-label="${fmtDay(d, true)}">
      <h2><span>${DIAS[i]}</span> <span class="muted">${fmtDay(d)}</span>${d === today ? ` <span class="badge pend">hoy</span>` : ""}</h2>
      ${COMIDAS.map(([c, lbl]) => `<div class="slot" data-slot="${d}|${c}"><h3>${lbl}</h3>
        <ul>${(bySlot[d + "|" + c] || []).map(planChip).join("")}</ul>
        <button class="btn sm ghost addslot" type="button" data-add="${d}|${c}" aria-label="Añadir receta a ${lbl.toLowerCase()} del ${fmtDay(d, true)}">${ic("plus")} Añadir</button></div>`).join("")}
    </section>`).join("")}</div>`;
  $("#wPrev").onclick = () => { PLAN.inicio = wk.anterior; viewPlanner(); };
  $("#wNext").onclick = () => { PLAN.inicio = wk.siguiente; viewPlanner(); };
  $("#wToday").onclick = () => { PLAN.inicio = null; viewPlanner(); };
  $("#wList").onclick = () => listPicker("Añadir la semana a la lista", null, async id => {
    const l = await API.plan.toList({ lista_id: id, inicio: wk.inicio, fin: wk.fin });
    toast(`${l.recetas_añadidas} recetas añadidas a «${l.nombre}»`); SHOP.id = id; location.hash = "#/compra"; });
  $$("[data-add]").forEach(b => b.onclick = () => { const [fecha, comida] = b.dataset.add.split("|");
    recipePicker(`Añadir a ${comida} · ${fmtDay(fecha, true)}`, r => guard(async () => { await API.plan.add({ fecha, comida, receta_id: r.id }); viewPlanner(); })); });
  $$("[data-srv]").forEach(b => b.onclick = () => guard(async () => { const p = wk.items.find(x => x.id == b.dataset.id);
    const n = Math.max(1, p.raciones + +b.dataset.srv); await API.plan.update(p.id, { raciones: n }); viewPlanner(); }));
  $$("[data-del]").forEach(b => b.onclick = () => guard(async () => { await API.plan.remove(b.dataset.del); viewPlanner(); }));
  $$("[data-move]").forEach(b => b.onclick = () => moveDialog(wk, wk.items.find(x => x.id == b.dataset.move)));
  // drag & drop (mouse); keyboard/touch use the «Mover» button
  let dragId = null;
  $$(".pchip[draggable]").forEach(el => {
    el.ondragstart = e => { dragId = el.dataset.id; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", dragId); el.classList.add("dragging"); };
    el.ondragend = () => { el.classList.remove("dragging"); $$(".slot.over").forEach(s => s.classList.remove("over")); };
  });
  $$(".slot").forEach(s => {
    s.ondragover = e => { if (dragId) { e.preventDefault(); s.classList.add("over"); } };
    s.ondragleave = () => s.classList.remove("over");
    s.ondrop = e => { e.preventDefault(); s.classList.remove("over"); const id = dragId; dragId = null; if (!id) return;
      const [fecha, comida] = s.dataset.slot.split("|");
      const after = [...s.querySelectorAll(".pchip")].filter(c => c.dataset.id !== id && e.clientY > c.getBoundingClientRect().top + c.offsetHeight / 2).length;
      guard(async () => { await API.plan.update(id, { fecha, comida, posicion: after }); viewPlanner(); }); };
  });
}
function planChip(p) {
  return `<li class="pchip" draggable="true" data-id="${p.id}">
    <a href="#/receta/${p.receta_id}" class="pt">${p.portada ? `<img src="${esc(p.portada)}" alt="" loading="lazy">` : `<span class="ph">${ic("utensils-crossed")}</span>`}<span>${esc(p.titulo)}</span></a>
    <div class="pc"><span class="stepper" role="group" aria-label="Raciones de ${esc(p.titulo)}">
      <button type="button" data-srv="-1" data-id="${p.id}" aria-label="Menos raciones">${ic("minus")}</button><output>${fmtQty(p.raciones)}</output><button type="button" data-srv="1" data-id="${p.id}" aria-label="Más raciones">${ic("plus")}</button></span>
      <span class="small muted">rac.</span><span class="grow"></span>
      <button type="button" class="btn sm ghost" data-move="${p.id}" aria-label="Mover ${esc(p.titulo)}">${ic("arrow-left-right")} Mover</button>
      <button type="button" class="btn sm ghost danger" data-del="${p.id}" aria-label="Quitar ${esc(p.titulo)}">${ic("x")}</button></div></li>`;
}
function moveDialog(wk, p) {
  const d = dialog(`<form class="dlg" id="mvF"><h2>Mover «${esc(p.titulo)}»</h2>
    <div class="form-grid"><div><label class="f" for="mvd">Día</label><select id="mvd" class="input">${wk.dias.map((x, i) => `<option value="${x}" ${x === p.fecha ? "selected" : ""}>${fmtDay(x, true)}</option>`).join("")}<option value="other">Otro día…</option></select>
      <input id="mvo" class="input" type="date" hidden value="${p.fecha}" aria-label="Otro día"></div>
    <div><label class="f" for="mvc">Comida</label><select id="mvc" class="input">${COMIDAS.map(([v, l]) => `<option value="${v}" ${v === p.comida ? "selected" : ""}>${l}</option>`).join("")}</select></div></div>
    <div class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn" type="button" id="mvx">${t("cancel")}</button><button class="btn primary" type="submit">Mover</button></div></form>`);
  $("#mvd", d).onchange = e => $("#mvo", d).hidden = e.target.value !== "other";
  $("#mvx", d).onclick = () => d.close();
  $("#mvF", d).onsubmit = e => { e.preventDefault(); guard(async () => { const f = $("#mvd", d).value === "other" ? $("#mvo", d).value : $("#mvd", d).value;
    await API.plan.update(p.id, { fecha: f, comida: $("#mvc", d).value }); d.close(); viewPlanner(); }); };
}

/* =========================================================== SHOPPING */
const SHOP = { id: +localStorage.getItem("lista") || null, showDone: true };
const SHOP_UNITS = ["", "g", "kg", "ml", "l", "ud", "cda", "cdta", "taza", "vaso", "diente", "lata", "paquete", "bote", "manojo"];
async function viewShopping() {
  setTitle(t("nav_compra"));
  if (API.STATIC) { main.innerHTML = `<h1>${t("nav_compra")}</h1><div class="empty"><div class="big">${ic("shopping-cart")}</div><h2>Disponible en tu servidor</h2><p>Las listas de la compra son personales, así que no están en la demo de solo lectura.</p></div>`; return; }
  const lists = await API.shop.lists();
  if (!lists.length) {
    main.innerHTML = `<h1>${t("nav_compra")}</h1><div class="empty"><div class="big">${ic("shopping-cart")}</div><h2>Aún no tienes listas</h2><p>Crea una y añade cosas a mano, desde una receta o desde el planificador. Las cantidades se suman solas.</p><button class="btn primary" id="nl" type="button">${ic("plus")} Crear mi primera lista</button></div>`;
    $("#nl").onclick = () => guard(async () => { SHOP.id = (await API.shop.create("Lista de la compra")).id; viewShopping(); });
    return;
  }
  if (!lists.some(l => l.id === SHOP.id)) SHOP.id = lists[0].id;
  localStorage.setItem("lista", SHOP.id);
  const L = await API.shop.get(SHOP.id);
  const cats = L.categorias, catName = id => cats.find(c => c.id === id)?.nombre || "Sin pasillo";
  const pend = L.items.filter(i => i.estado === "pendiente"), have = L.items.filter(i => i.estado === "ya_lo_tengo"), done = L.items.filter(i => i.estado === "comprado");
  const groups = []; pend.forEach(i => { const g = groups.find(g => g.id === i.categoria_id); g ? g.items.push(i) : groups.push({ id: i.categoria_id, items: [i] }); });
  main.innerHTML = `
  <div class="hero"><div><h1>${t("nav_compra")}</h1><p class="muted" style="margin:0">${pend.length} por comprar${done.length ? ` · ${done.length} comprados` : ""}${have.length ? ` · ${have.length} ya en casa` : ""}</p></div>
    <div class="row no-print hero-actions">
      <button class="btn" type="button" id="shShare">${ic("share-2")} Compartir</button>
      <button class="btn" type="button" onclick="print()">${ic("printer")} Imprimir</button>
      <button class="btn" type="button" id="shMore" aria-haspopup="dialog">⋯ Más</button>
    </div></div>
  <div class="scroller lists no-print" role="tablist" aria-label="Tus listas">${lists.map(l => `<button type="button" role="tab" class="chip" aria-selected="${l.id === L.id}" aria-pressed="${l.id === L.id}" data-list="${l.id}">${esc(l.nombre)} <span class="n">${l.pendientes}</span></button>`).join("")}
    <button type="button" class="chip" id="shNew">${ic("plus")} Nueva lista</button></div>
  <h2 class="print-only">${esc(L.nombre)}</h2>
  <form id="addF" class="panel addform no-print" autocomplete="off">
    <label class="sr" for="an">Artículo</label><input id="an" class="input nm" placeholder="Añadir artículo (p. ej. leche)" required maxlength="120" list="pantryNames">
    <label class="sr" for="aq">Cantidad</label><input id="aq" class="input" type="number" min="0" step="any" placeholder="Cant.">
    <label class="sr" for="au">Unidad</label><select id="au" class="input">${SHOP_UNITS.map(u => `<option value="${u}">${u || "unidad"}</option>`).join("")}</select>
    <button class="btn primary" type="submit">Añadir</button>
    <details class="more"><summary class="small">Más opciones</summary><div class="row" style="margin-top:.5rem">
      <label class="sr" for="ac">Pasillo</label><select id="ac" class="input" style="width:auto"><option value="">Pasillo automático</option>${cats.map(c => `<option value="${c.id}">${esc(c.nombre)}</option>`).join("")}</select>
      <label class="sr" for="ano">Nota</label><input id="ano" class="input grow" placeholder="Nota (marca, tamaño…)" maxlength="300">
      <label class="chip"><input type="checkbox" id="ar"> ${ic("repeat")} Recurrente</label></div></details>
  </form>
  <div class="shop">
    ${groups.length ? groups.map(g => `<section class="aisle" data-cat="${g.id ?? ""}"><h3>${esc(catName(g.id))} <span class="muted small">${g.items.length}</span></h3><ul class="items">${g.items.map(shopItem).join("")}</ul></section>`).join("")
      : `<div class="empty small-empty"><div class="big">${ic("circle-check")}</div><p>${L.items.length ? "¡Todo listo! No queda nada por comprar." : "Lista vacía. Añade artículos arriba, o desde una receta («Añadir a la lista») o el planificador."}</p></div>`}
    ${have.length ? `<section class="aisle muted-sec"><h3>${ic("house")} Ya lo tengo <span class="muted small">${have.length}</span></h3><ul class="items">${have.map(shopItem).join("")}</ul></section>` : ""}
    ${done.length ? `<section class="aisle muted-sec no-print"><h3>${ic("check")} Comprado <span class="muted small">${done.length}</span> <button class="btn sm ghost" type="button" id="shClear">Limpiar comprados</button></h3><ul class="items">${done.map(shopItem).join("")}</ul></section>` : ""}
  </div>
  <div class="panel shopfoot">
    ${L.mostrar_precios ? `<p style="margin:0"><b>Total orientativo: ${L.precio_estimado_eur != null ? eur(L.precio_estimado_eur) : "—"}</b> <span class="badge est" title="Calculado con precios estimados, no reales">${t("est")}</span>${L.precio_parcial ? ` <span class="small muted">(sin precio para algunos artículos)</span>` : ""}</p>` : ""}
    <label class="row small no-print" style="margin-top:.4rem"><input type="checkbox" id="shPr" ${L.mostrar_precios ? "checked" : ""}> Mostrar precio orientativo</label>
    ${L.notas ? `<p class="small" style="white-space:pre-line">${esc(L.notas)}</p>` : ""}
  </div>
  <datalist id="pantryNames"></datalist>`;
  const reload = () => viewShopping();
  $$("[data-list]").forEach(b => b.onclick = () => { SHOP.id = +b.dataset.list; reload(); });
  $("#shNew").onclick = () => { const n = prompt("Nombre de la nueva lista", "Lista de la compra"); if (n) guard(async () => { SHOP.id = (await API.shop.create(n)).id; reload(); }); };
  $("#addF").onsubmit = e => { e.preventDefault(); guard(async () => {
    const q = $("#aq").value; await API.shop.addItem(L.id, { nombre: $("#an").value.trim(), cantidad: q === "" ? null : +q, unidad: $("#au").value,
      categoria_id: $("#ac").value ? +$("#ac").value : null, nota: $("#ano").value.trim(), recurrente: $("#ar").checked });
    await reload(); $("#an").focus(); }); };
  $("#shPr").onchange = e => guard(async () => { await API.shop.update(L.id, { mostrar_precios: e.target.checked }); reload(); });
  $("#shClear") && ($("#shClear").onclick = () => guard(async () => { await API.shop.clear(L.id); toast("Comprados retirados (los recurrentes vuelven a pendiente)"); reload(); }));
  $("#shShare").onclick = () => shareDialog(L);
  $("#shMore").onclick = () => listMenu(L, lists);
  $$("[data-buy]").forEach(c => c.onchange = () => guard(async () => { await API.shop.updateItem(c.dataset.buy, { estado: c.checked ? "comprado" : "pendiente" }); reload(); }));
  $$("[data-have]").forEach(b => b.onclick = () => guard(async () => { const it = L.items.find(i => i.id == b.dataset.have); await API.shop.updateItem(it.id, { estado: it.estado === "ya_lo_tengo" ? "pendiente" : "ya_lo_tengo" }); reload(); }));
  $$("[data-edit]").forEach(b => b.onclick = () => itemDialog(L, L.items.find(i => i.id == b.dataset.edit)));
  // drag to reorder inside an aisle or move to another aisle
  let drag = null;
  $$(".items li[draggable]").forEach(li => { li.ondragstart = e => { drag = li; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", li.dataset.id); li.classList.add("dragging"); };
    li.ondragend = () => li.classList.remove("dragging"); });
  $$(".aisle[data-cat]").forEach(sec => { const ul = $("ul", sec);
    ul.ondragover = e => { if (!drag) return; e.preventDefault(); const after = [...ul.children].find(c => c !== drag && e.clientY < c.getBoundingClientRect().top + c.offsetHeight / 2); ul.insertBefore(drag, after || null); };
    ul.ondrop = e => { e.preventDefault(); if (!drag) return; drag = null; const cat = sec.dataset.cat === "" ? null : +sec.dataset.cat;
      guard(async () => { await API.shop.order(L.id, [...ul.children].map(li => +li.dataset.id), cat); reload(); }); }; });
  API.shop.pantry().then(p => { const dl = $("#pantryNames"); if (dl) dl.innerHTML = p.map(x => `<option value="${esc(x.nombre)}">`).join(""); });
}
function shopItem(i) {
  const src = i.origenes.filter(o => o.titulo).map(o => o.titulo);
  return `<li draggable="${i.estado === "pendiente"}" data-id="${i.id}" class="st-${i.estado}">
    <input type="checkbox" id="b${i.id}" data-buy="${i.id}" ${i.estado === "comprado" ? "checked" : ""} aria-label="Comprado: ${esc(i.nombre)}">
    <label for="b${i.id}" class="grow"><span class="q">${esc(i.texto_cantidad)}</span> ${esc(i.nombre)}${i.recurrente ? ` <span title="Recurrente">${ic("repeat", "recurrente")}</span>` : ""}
      ${i.nota ? `<span class="small muted"> · ${esc(i.nota)}</span>` : ""}
      ${src.length ? `<span class="src small muted">${[...new Set(src)].map(esc).join(", ")}</span>` : ""}</label>
    ${i.precio_eur != null ? `<span class="p small">${eur(i.precio_eur)}</span>` : ""}
    <button type="button" class="icon-btn sm no-print" data-have="${i.id}" aria-pressed="${i.estado === "ya_lo_tengo"}" title="Ya lo tengo" aria-label="Ya lo tengo: ${esc(i.nombre)}">${ic("house")}</button>
    <button type="button" class="icon-btn sm no-print" data-edit="${i.id}" aria-label="Editar ${esc(i.nombre)}">${ic("pencil")}</button></li>`;
}
function itemDialog(L, it) {
  const d = dialog(`<form class="dlg" id="itF"><h2>Editar artículo</h2>
    <label class="f" for="in">Nombre</label><input id="in" class="input" value="${esc(it.nombre)}" required maxlength="120">
    <div class="form-grid"><div><label class="f" for="iq">Cantidad</label><input id="iq" class="input" type="number" min="0" step="any" value="${it.cantidad ?? ""}"></div>
      <div><label class="f" for="iu">Unidad</label><select id="iu" class="input">${[...new Set([it.unidad, ...SHOP_UNITS])].map(u => `<option value="${esc(u)}" ${u === it.unidad ? "selected" : ""}>${esc(u || "unidad")}</option>`).join("")}</select></div></div>
    <p class="small muted" style="margin:.3rem 0 0">Las tazas y cucharadas se guardan en g o ml para poder sumarlas.</p>
    <label class="f" for="ic">Pasillo</label><select id="ic" class="input"><option value="">Sin pasillo</option>${L.categorias.map(c => `<option value="${c.id}" ${c.id === it.categoria_id ? "selected" : ""}>${esc(c.nombre)}</option>`).join("")}</select>
    <label class="f" for="ino">Nota</label><input id="ino" class="input" value="${esc(it.nota)}" maxlength="300">
    <label class="f" for="ie">Estado</label><select id="ie" class="input">${[["pendiente", "Pendiente"], ["ya_lo_tengo", "Ya lo tengo"], ["comprado", "Comprado"]].map(([v, l]) => `<option value="${v}" ${v === it.estado ? "selected" : ""}>${l}</option>`).join("")}</select>
    <label class="row" style="margin-top:.6rem"><input type="checkbox" id="ir" ${it.recurrente ? "checked" : ""}> ${ic("repeat")} Recurrente (vuelve a «pendiente» al limpiar comprados)</label>
    ${it.origenes.some(o => o.titulo) ? `<p class="small muted">De: ${it.origenes.filter(o => o.titulo).map(o => `${esc(o.titulo)} (${fmtQty(o.raciones)} rac.)`).join(" · ")}</p>` : ""}
    <div class="row" style="justify-content:space-between;margin-top:1rem"><button class="btn ghost danger" type="button" id="idel">${ic("trash-2")} Quitar</button>
      <span class="row"><button class="btn" type="button" id="ix">${t("cancel")}</button><button class="btn primary" type="submit">${t("save")}</button></span></div></form>`);
  $("#ix", d).onclick = () => d.close();
  $("#idel", d).onclick = () => guard(async () => { await API.shop.removeItem(it.id); d.close(); viewShopping(); });
  $("#itF", d).onsubmit = e => { e.preventDefault(); guard(async () => { const q = $("#iq", d).value;
    await API.shop.updateItem(it.id, { nombre: $("#in", d).value.trim(), cantidad: q === "" ? null : +q, unidad: $("#iu", d).value, nota: $("#ino", d).value,
      categoria_id: $("#ic", d).value ? +$("#ic", d).value : null, estado: $("#ie", d).value, recurrente: $("#ir", d).checked });
    d.close(); viewShopping(); }); };
}
async function shareDialog(L) {
  const s = await API.shop.share(L.id);
  const d = dialog(`<div class="dlg"><h2>${ic("share-2")} Compartir «${esc(L.nombre)}»</h2>
    <label class="f" for="stx">Texto</label><textarea id="stx" class="input" rows="10" readonly>${esc(s.texto)}</textarea>
    <label class="row small"><input type="checkbox" id="sinc"> Incluir lo que ya tengo</label>
    <div class="row" style="margin-top:1rem"><button class="btn" type="button" id="scp">${ic("copy")} Copiar</button>
      <a class="btn primary" id="swa" href="${esc(s.whatsapp)}" target="_blank" rel="noopener">WhatsApp ${ic("external-link")}</a>
      ${navigator.share ? `<button class="btn" type="button" id="sns">Compartir…</button>` : ""}
      <span class="grow"></span><form method="dialog"><button class="btn">${t("close")}</button></form></div></div>`);
  $("#sinc", d).onchange = async e => { const n = await API.shop.share(L.id, e.target.checked); $("#stx", d).value = n.texto; $("#swa", d).href = n.whatsapp; };
  $("#scp", d).onclick = () => navigator.clipboard.writeText($("#stx", d).value).then(() => toast("Copiado"));
  $("#sns", d) && ($("#sns", d).onclick = () => navigator.share({ title: L.nombre, text: $("#stx", d).value }).catch(() => { }));
}
function listMenu(L, lists) {
  const d = dialog(`<div class="dlg"><h2>Lista «${esc(L.nombre)}»</h2>
    <div class="menu">
      <button class="btn" type="button" id="mRen">${ic("pencil")} Renombrar</button>
      <button class="btn" type="button" id="mNotes">${ic("notebook-pen")} Notas de la lista</button>
      <button class="btn" type="button" id="mCats">${ic("layout-list")} Pasillos y orden</button>
      <button class="btn" type="button" id="mPan">${ic("house")} Despensa (lo que siempre tienes)</button>
      <button class="btn" type="button" id="mRec">${ic("book-open")} Añadir una receta…</button>
      <button class="btn ghost danger" type="button" id="mDel">${ic("trash-2")} Borrar lista</button></div>
    <form method="dialog" class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn">${t("close")}</button></form></div>`);
  $("#mRen", d).onclick = () => { const n = prompt("Nuevo nombre", L.nombre); if (n) guard(async () => { await API.shop.update(L.id, { nombre: n }); d.close(); viewShopping(); }); };
  $("#mNotes", d).onclick = () => { const n = prompt("Notas de la lista", L.notas); if (n != null) guard(async () => { await API.shop.update(L.id, { notas: n }); d.close(); viewShopping(); }); };
  $("#mCats", d).onclick = () => catsDialog();
  $("#mPan", d).onclick = () => pantryDialog();
  $("#mRec", d).onclick = () => recipePicker("Añadir ingredientes de…", r => guard(async () => { const l = await API.shop.addRecipe(L.id, r.id, null); toast(`${l.añadidos} ingredientes añadidos`); viewShopping(); }));
  $("#mDel", d).onclick = () => confirm(`¿Borrar la lista «${L.nombre}»?`) && guard(async () => { await API.shop.remove(L.id); SHOP.id = null; d.close(); viewShopping(); });
}
async function catsDialog() {
  let cats = await API.shop.cats();
  const d = dialog(`<div class="dlg"><h2>${ic("layout-list")} Pasillos</h2><p class="small muted">Ordénalos como recorres tu tienda. Usa ${ic("arrow-up")} ${ic("arrow-down")} o arrastra.</p><ol class="cats" id="cl"></ol>
    <form id="caF" class="row"><label class="sr" for="can">Nuevo pasillo</label><input id="can" class="input grow" placeholder="Nuevo pasillo" maxlength="80" required><button class="btn" type="submit">Añadir</button></form>
    <form method="dialog" class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn primary">Hecho</button></form></div>`);
  d.onclose = () => location.hash.startsWith("#/compra") && viewShopping();
  const save = async () => { cats = await API.shop.orderCats(cats.map(c => c.id)); paint(); };
  function paint() {
    $("#cl", d).innerHTML = cats.map((c, i) => `<li draggable="true" data-c="${c.id}"><span class="grip" aria-hidden="true">⋮⋮</span><span class="grow">${esc(c.nombre)}</span>
      <button class="icon-btn sm" type="button" data-up="${i}" ${i ? "" : "disabled"} aria-label="Subir ${esc(c.nombre)}">${ic("arrow-up")}</button><button class="icon-btn sm" type="button" data-dn="${i}" ${i < cats.length - 1 ? "" : "disabled"} aria-label="Bajar ${esc(c.nombre)}">${ic("arrow-down")}</button>
      <button class="icon-btn sm" type="button" data-rn="${c.id}" aria-label="Renombrar ${esc(c.nombre)}">${ic("pencil")}</button><button class="icon-btn sm" type="button" data-rm="${c.id}" aria-label="Borrar ${esc(c.nombre)}">${ic("x")}</button></li>`).join("");
    $$("[data-up]", d).forEach(b => b.onclick = () => guard(async () => { const i = +b.dataset.up; [cats[i - 1], cats[i]] = [cats[i], cats[i - 1]]; await save(); $(`[data-up="${i - 1}"]`, d)?.focus() || $(`[data-dn="${i - 1}"]`, d)?.focus(); }));
    $$("[data-dn]", d).forEach(b => b.onclick = () => guard(async () => { const i = +b.dataset.dn; [cats[i + 1], cats[i]] = [cats[i], cats[i + 1]]; await save(); $(`[data-dn="${i + 1}"]`, d)?.focus() || $(`[data-up="${i + 1}"]`, d)?.focus(); }));
    $$("[data-rn]", d).forEach(b => b.onclick = () => { const c = cats.find(x => x.id == b.dataset.rn), n = prompt("Nuevo nombre", c.nombre); if (n) guard(async () => { await API.shop.renameCat(c.id, n); cats = await API.shop.cats(); paint(); }); });
    $$("[data-rm]", d).forEach(b => b.onclick = () => confirm("¿Borrar este pasillo? Sus artículos quedarán sin pasillo.") && guard(async () => { await API.shop.removeCat(b.dataset.rm); cats = await API.shop.cats(); paint(); }));
    let dragEl = null;
    $$("#cl li", d).forEach(li => { li.ondragstart = () => { dragEl = li; li.classList.add("dragging"); }; li.ondragend = () => { li.classList.remove("dragging"); };
      li.ondragover = e => { e.preventDefault(); if (dragEl && dragEl !== li) { const r = li.getBoundingClientRect(); li.parentNode.insertBefore(dragEl, e.clientY < r.top + r.height / 2 ? li : li.nextSibling); } };
      li.ondrop = e => { e.preventDefault(); const ids = $$("#cl li", d).map(x => +x.dataset.c); cats = ids.map(id => cats.find(c => c.id === id)); guard(save); }; });
  }
  paint();
  $("#caF", d).onsubmit = e => { e.preventDefault(); guard(async () => { await API.shop.addCat($("#can", d).value.trim()); $("#can", d).value = ""; cats = await API.shop.cats(); paint(); }); };
}
async function pantryDialog() {
  const d = dialog(`<div class="dlg"><h2>${ic("house")} Despensa</h2><p class="small muted">Lo que siempre tienes en casa (sal, aceite…). Al añadir recetas, estos ingredientes aparecen como «ya lo tengo».</p>
    <ul class="pantry" id="pl"></ul><form id="paF" class="row"><label class="sr" for="pan">Ingrediente</label><input id="pan" class="input grow" placeholder="p. ej. aceite de oliva" maxlength="80" required><button class="btn" type="submit">Añadir</button></form>
    <form method="dialog" class="row" style="justify-content:flex-end;margin-top:1rem"><button class="btn primary">Hecho</button></form></div>`);
  const paint = async () => { const p = await API.shop.pantry();
    $("#pl", d).innerHTML = p.map(x => `<li class="chip">${esc(x.nombre)} <button type="button" class="x" data-prm="${x.id}" aria-label="Quitar ${esc(x.nombre)}">${ic("x")}</button></li>`).join("") || `<li class="muted small">Vacía</li>`;
    $$("[data-prm]", d).forEach(b => b.onclick = () => guard(async () => { await API.shop.removePantry(b.dataset.prm); paint(); })); };
  paint();
  $("#paF", d).onsubmit = e => { e.preventDefault(); guard(async () => { await API.shop.addPantry($("#pan", d).value.trim()); $("#pan", d).value = ""; paint(); }); };
}

/* =========================================================== ACCESO (settings) */
// Probe a different origin without CORS: an opaque no-cors fetch resolves only if the server answers.
async function probeHealth(base, ms = 3000) {
  const c = new AbortController(), tm = setTimeout(() => c.abort(), ms);
  try { await fetch(base + "api/health?t=" + Date.now(), { mode: "no-cors", cache: "no-store", signal: c.signal }); return true; }
  catch { return false; } finally { clearTimeout(tm); }
}
function pickNewUrl(urls) {
  const here = location.hostname;
  return (urls.find(u => new URL(u.url).hostname === here) || urls.find(u => u.tipo === "lan") || urls[0]).url;
}
async function renderAcceso() {
  const box = $("#s-acc"); if (!box) return;
  const a = await API.acceso();
  box.innerHTML = `<h2>${ic("wifi")} Acceso</h2>
  <p class="muted small">Direcciones con las que abrir el recetario desde otros dispositivos. El QR se genera en este servidor.</p>
  <ul class="acc-list">${a.urls.map((u, i) => `<li><code>${esc(u.url)}</code> <span class="chip small">${{ lan: "Red local", tailscale: "Tailscale", local: "Este equipo", otra: "Otra" }[u.tipo]}</span>
    <button class="btn sm" type="button" data-copy="${esc(u.url)}">${ic("copy")} Copiar</button>
    ${u.tipo === "local" ? "" : `<button class="btn sm" type="button" data-qr="${i}" aria-expanded="false">QR</button><div class="qr" id="qr${i}" hidden></div>`}</li>`).join("")}</ul>
  <form id="accF" class="row" style="gap:.5rem;align-items:end;flex-wrap:wrap;margin-top:1rem">
    <label>Dirección <input name="host" value="${esc(a.host)}" list="accHosts" required inputmode="decimal" size="15"></label>
    <datalist id="accHosts"><option value="0.0.0.0"><option value="127.0.0.1"></datalist>
    <label>Puerto <input name="port" type="number" min="1024" max="65535" value="${a.port}" required></label>
    <button class="btn" type="submit">Guardar y reiniciar</button>
  </form>
  <p class="warn small">${ic("triangle-alert")} Si cambias la dirección o el puerto, la URL del recetario cambiará y el servidor se reiniciará. Si no arranca en unos 60 s, se restaura la configuración anterior.</p>
  ${a.aviso ? `<p class="muted small">${esc(a.aviso)}</p>` : ""}
  <p class="muted small">Archivo de configuración: <code>${esc(a.archivo_config)}</code></p>
  <p id="accMsg" role="status" aria-live="polite"></p>`;
  $$("[data-copy]", box).forEach(b => b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.copy); toast("Copiado"); } catch { toast("No se pudo copiar"); } });
  $$("[data-qr]", box).forEach(b => b.onclick = () => {
    const d = $("#qr" + b.dataset.qr), url = a.urls[+b.dataset.qr].url, open = d.hidden;
    if (open && !d.innerHTML) d.innerHTML = `<img src="/api/acceso/qr?url=${encodeURIComponent(url)}" alt="Código QR de ${esc(url)}" width="160" height="160">`;
    d.hidden = !open; b.setAttribute("aria-expanded", open);
  });
  $("#accF").onsubmit = async ev => {
    ev.preventDefault();
    const f = ev.target, host = f.host.value.trim(), port = +f.port.value, msg = $("#accMsg");
    if (host === a.host && port === a.port) { msg.textContent = "No hay cambios."; return; }
    if (!confirm("La URL del recetario cambiará y el servidor se reiniciará. ¿Continuar?")) return;
    let r;
    try { r = await API.accesoRed(host, port); } catch (e) { msg.textContent = e.message; return; }
    if (!r.reiniciando) { msg.textContent = "Guardado. " + r.mensajes.join(" "); return; }
    const target = pickNewUrl(r.urls), t0 = Date.now();
    f.querySelector("button").disabled = true;
    msg.textContent = `Reiniciando… esperando a ${target}`;
    await new Promise(res => setTimeout(res, 4000)); // let the old server go down first
    while (Date.now() - t0 < 60000) {
      if (await probeHealth(target)) { msg.textContent = "Listo. Redirigiendo…"; location.href = target + location.hash; return; }
      await new Promise(res => setTimeout(res, 2000));
    }
    msg.textContent = "El servidor no respondió en la nueva dirección en 60 s: se ha restaurado la configuración anterior. Sigues en la URL actual.";
    f.querySelector("button").disabled = false;
  };
}

/* =========================================================== ESTADO (settings) */
const fmtBytes = b => b == null ? "—" : b < 1024 ** 2 ? `${Math.round(b / 1024)} KB` : b < 1024 ** 3 ? `${(b / 1024 ** 2).toFixed(1).replace(".", ",")} MB` : `${(b / 1024 ** 3).toFixed(2).replace(".", ",")} GB`;
async function renderEstado(refresh) {
  const box = $("#s-estado"); if (!box) return;
  const e = await API.estado(refresh), v = e.videos, k = e.disco, th = e.cola.portadas;
  const pct = v.recetas_con_publicacion ? Math.round(100 * v.con_video_local / v.recetas_con_publicacion) : 0;
  box.innerHTML = `<div class="row" style="justify-content:space-between"><h2>${ic("activity")} Estado</h2><button class="btn sm" type="button" id="eR">${ic("refresh-cw")} Actualizar</button></div>
  <div class="stats">
    <div class="stat"><span class="muted small">Versión</span><b>${esc(e.version)}</b><span class="small muted">commit ${esc(e.commit || "desconocido")} · esquema v${e.esquema}</span></div>
    <div class="stat"><span class="muted small">Vídeos locales</span><b>${v.con_video_local} / ${v.recetas_con_publicacion}</b><span class="bar" role="img" aria-label="${pct}%"><i style="width:${pct}%"></i></span></div>
    <div class="stat"><span class="muted small">Espacio de vídeos</span><b>${fmtBytes(k.videos.bytes)}</b><span class="small muted">${k.videos.archivos} archivos</span></div>
    <div class="stat"><span class="muted small">Fotos y portadas</span><b>${fmtBytes(k.media.bytes)}</b><span class="small muted">${k.media.archivos} archivos · BD ${fmtBytes(k.base_de_datos.bytes)}</span></div>
    <div class="stat"><span class="muted small">Disco libre</span><b>${fmtBytes(k.libre_bytes)}</b><span class="small muted">de ${fmtBytes(k.total_bytes)}</span></div>
    <div class="stat"><span class="muted small">Portadas (ffmpeg)</span><b>${th.disponible ? `${th.en_cache} en caché` : "ffmpeg no encontrado"}</b><span class="small muted">${th.disponible ? `${th.en_cola} en cola · ${th.fallidas} fallidas` : "Se usan miniaturas o emojis"}</span></div>
  </div>
  ${th.disponible ? "" : `<p class="small banner" style="display:block">Para portadas reales desde tus vídeos instala ffmpeg (<code>winget install Gyan.FFmpeg</code> en Windows) y reinicia, o indica la ruta con <code>RECETAS_FFMPEG</code>.</p>`}
  ${v.sin_video ? `<details><summary class="small">${v.sin_video} recetas sin vídeo local</summary><ul class="small">${v.faltan.map(x => `<li><a href="#/receta/${x.id}">${esc(x.titulo || x.shortcode)}</a> <code>${esc(x.shortcode)}</code></li>`).join("")}${v.sin_video > v.faltan.length ? `<li class="muted">…y ${v.sin_video - v.faltan.length} más</li>` : ""}</ul></details>` : ""}
  <h3 style="margin-top:1rem">Últimas importaciones</h3>
  ${e.cola.importaciones_activas.length ? `<p class="small"><span class="badge pend">en curso</span> ${e.cola.importaciones_activas.map(j => `${j.hechos}/${j.total}`).join(", ")}</p>` : ""}
  ${e.importaciones.length ? `<ul class="joblist">${e.importaciones.map(j => `<li><b>${esc((j.creado || "").slice(0, 16).replace("T", " "))}</b> <span class="grow">${j.ok}/${j.total} importadas${j.estado === "cancelado" ? " · cancelada" : ""}</span>${j.errores.length ? `<span class="badge est" title="${esc(j.errores.map(x => x.shortcode + ": " + x.mensaje).join("\n"))}">${j.errores.length} errores</span>` : `<span class="badge real">ok</span>`}</li>`).join("")}</ul>` : `<p class="muted small">Aún no hay importaciones registradas.</p>`}
  ${th.errores.length ? `<details><summary class="small">Errores de portadas</summary><ul class="small">${th.errores.map(x => `<li><code>${esc(x.clave)}</code> ${esc(x.error)}</li>`).join("")}</ul></details>` : ""}`;
  $("#eR").onclick = () => guard(() => renderEstado(true));
}

/* =========================================================== SETTINGS */
async function viewSettings() {
  setTitle(t("nav_ajustes"));
  const meta = await API.meta();
  main.innerHTML = `<h1>${t("nav_ajustes")}</h1><div class="settings">
  <nav class="side" aria-label="Apartados">${[["ap", t("appearance")], ...(API.STATIC ? [] : [["ia", "Conectar tu IA"], ["tok", "Acceso para agentes"], ["ig", "Instagram"], ["estado", "Estado"], ["acc", "Acceso"], ["sesion", "Sesión"]]), ["about", t("about")]].map(([id, l]) => `<a href="#/ajustes" data-jump="${id}">${l}</a>`).join("")}</nav>
  <div>
   <section class="panel" id="s-ap"><h2>${t("appearance")}</h2><div class="row">
     <button class="btn" type="button" id="tg">${ic("sun-moon")} ${t("theme")}</button>
     <label>${t("language")} <select class="input" id="lang" style="width:auto">${[["es", "Español"], ["en", "English"]].map(([v, l]) => `<option value="${v}" ${LANG === v ? "selected" : ""}>${l}</option>`).join("")}</select></label></div></section>
   ${API.STATIC ? "" : `<section class="panel" id="s-ia"></section><section class="panel" id="s-tok"></section><section class="panel" id="s-ig"></section><section class="panel" id="s-acc"></section><section class="panel" id="s-estado"><h2>${ic("activity")} Estado</h2><p class="muted">Cargando…</p></section>
   <section class="panel" id="s-sesion"><h2>${ic("lock")} Sesión</h2><p>Has entrado como <b>${esc(AUTH.user)}</b>. Para cambiar la contraseña usa <code>python -m app.cli create-admin --replace</code> en el servidor.</p><button class="btn" type="button" id="logout">Cerrar sesión</button></section>`}
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
     ${API.STATIC ? `<p class="small">Esta es una demo estática de solo lectura con datos de ejemplo.</p>` : `<p class="small"><a href="/docs" target="_blank">Documentación de la API (OpenAPI) ${ic("external-link")}</a></p>`}</section>
  </div></div>`;
  $$("[data-jump]").forEach(a => a.onclick = e => { e.preventDefault(); $(`#s-${a.dataset.jump}`).scrollIntoView({ behavior: "smooth" }); });
  $("#tg").onclick = () => $("#themeBtn").click();
  $("#lang").onchange = e => { localStorage.setItem("lang", e.target.value); location.reload(); };
  if (API.STATIC) return;
  renderAI(); renderTokens(); renderIG(); renderAcceso().catch(e => $("#s-acc").innerHTML = `<h2>${ic("wifi")} Acceso</h2><p class="muted">${esc(e.message)}</p>`); renderEstado().catch(e => $("#s-estado").innerHTML = `<h2>${ic("activity")} Estado</h2><p class="muted">${esc(e.message)}</p>`);
  $("#logout").onclick = () => guard(async () => { await API.auth.logout(); AUTH.ok = false; location.hash = "#/login"; viewLogin(); });
}
async function renderAI() {
  const box = $("#s-ia"), c = await API.ai.config(), P = c.presets;
  box.innerHTML = `<h2>${ic("bot")} Conectar tu IA</h2>
  <p class="muted small">Cualquier servicio compatible con la API de OpenAI. Se usa para extraer recetas de los textos (si falla, se usa el parser automático), traducir y estimar precios (siempre marcados como estimados). La clave se guarda cifrada en el servidor y nunca vuelve al navegador.</p>
  <form id="aiF"><div class="form-grid">
    <div><label class="f" for="pr">Proveedor</label><select id="pr" class="input">${Object.entries(P).map(([k, v]) => `<option value="${k}" ${c.preset === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></div>
    <div><label class="f" for="mo">Modelo</label><input id="mo" class="input" value="${esc(c.model || P[c.preset || "openai"].model)}"></div>
  </div>
  <label class="f" for="bu">URL base</label><input id="bu" class="input" type="url" value="${esc(c.base_url || P[c.preset || "openai"].base_url)}">
  <label class="f" for="ak">Clave API ${c.tiene_api_key ? `<span class="badge">guardada ${esc(c.api_key_hint)}</span>` : ""}</label>
  <input id="ak" class="input" type="password" autocomplete="off" placeholder="${c.tiene_api_key ? "Déjalo vacío para mantener la actual" : "sk-… (no hace falta para Ollama / LM Studio)"}">
  <label class="row" style="margin-top:.6rem"><input type="checkbox" id="en" ${c.enabled !== false ? "checked" : ""}> Usar la IA al importar</label>
  <div class="row" style="margin-top:1rem"><button class="btn primary" type="submit">${t("save")}</button><button class="btn" type="button" id="aiT">${ic("plug")} Probar conexión</button>
    ${c.configurado ? `<button class="btn ghost danger" type="button" id="aiD">Quitar</button>` : ""}<span id="aiR" class="small" aria-live="polite"></span></div></form>`;
  $("#pr").onchange = e => { const p = P[e.target.value]; $("#bu").value = p.base_url; $("#mo").value = p.model; };
  $("#aiF").onsubmit = e => { e.preventDefault(); guard(async () => { const key = $("#ak").value; await API.ai.save({ preset: $("#pr").value, base_url: $("#bu").value.trim(), model: $("#mo").value.trim(), api_key: key ? key : null, enabled: $("#en").checked }); $("#ak").value = ""; toast("IA guardada"); renderAI(); }); };
  $("#aiT").onclick = () => guard(async () => { $("#aiR").textContent = "Probando…"; const r = await API.ai.test(); $("#aiR").innerHTML = r.ok ? `<span class="badge real">${ic("check")} Conectado</span>` : `<span class="badge est">${ic("x")} ${esc(r.error)}</span>`; });
  $("#aiD") && ($("#aiD").onclick = () => guard(async () => { await API.ai.remove(); renderAI(); }));
}
async function renderTokens(fresh) {
  const box = $("#s-tok"), list = await API.tokens.list();
  box.innerHTML = `<h2>${ic("key-round")} Acceso para agentes (API y MCP)</h2>
  <p class="muted small">Crea un token para que otros programas o asistentes lean o añadan recetas: API REST en <a href="/docs" target="_blank">/docs</a> y servidor MCP en <code>${location.origin}/mcp</code>. El token se muestra <b>una sola vez</b>; aquí solo guardamos su huella.</p>
  ${fresh ? `<div class="banner" style="display:block"><b>Copia tu token ahora, no se volverá a mostrar:</b><code class="code" id="newTok">${esc(fresh)}</code><button class="btn sm" type="button" id="cp">${ic("copy")} Copiar</button></div>` : ""}
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
  box.innerHTML = `<h2>${ic("instagram")} Instagram</h2><p>${st.conectado ? `Conectado como <b>@${esc(st.usuario)}</b>.` : "No conectado."} <span class="muted small">Proveedor: ${esc(st.proveedor)}</span></p>
  <div class="row">${st.conectado ? `<button class="btn" type="button" id="igo">Desconectar y borrar sesión</button>` : ""}<a class="btn" href="#/importar">Ir a Importar</a></div>`;
  $("#igo") && ($("#igo").onclick = () => guard(async () => { await API.ig.logout(); renderIG(); }));
}

router();
