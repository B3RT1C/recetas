#!/usr/bin/env python3
"""Generate landing/index.html (ES) and landing/en/index.html (EN) from one template.

Output is plain static HTML committed to the repo, so Cloudflare Pages needs no build step.
Config: landing/site.config.json (site_url, demo_url, repo_public, repo_url).
Run: python scripts/build_landing.py
"""
import html, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L = ROOT / "landing"
CFG = json.loads((L / "site.config.json").read_text())
SITE = CFG["site_url"].rstrip("/")
VERSION = re.search(r'"([^"]+)"', (ROOT / "app/__init__.py").read_text()).group(1)

def load_icons():
    src = (ROOT / "static/assets/icons.js").read_text()
    out = {m.group(1): m.group(2).replace('\\"', '"') for m in re.finditer(r'^  "([a-z0-9-]+)": "(.*)",?$', src, re.M)}
    # Lucide "smartphone" (ISC), not in the app set.
    out["smartphone"] = '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/> <path d="M12 18h.01"/>'
    # Lucide brand/extra icons (ISC), not in the app set.
    out["github"] = '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/> <path d="M9 18c-4.51 2-5-2-7-2"/>'
    out["linkedin"] = '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/> <rect width="4" height="12" x="2" y="9"/> <circle cx="4" cy="4" r="2"/>'
    out["monitor"] = '<rect width="20" height="14" x="2" y="3" rx="2"/> <line x1="8" x2="16" y1="21" y2="21"/> <line x1="12" x2="12" y1="17" y2="21"/>'
    out["container"] = '<path d="M22 7.7c0-.6-.4-1.2-.8-1.5l-6.3-3.9a1.72 1.72 0 0 0-1.7 0l-10.3 6c-.5.2-.9.8-.9 1.4v6.6c0 .5.4 1.2.8 1.5l6.3 3.9a1.72 1.72 0 0 0 1.7 0l10.3-6c.5-.3.9-1 .9-1.5Z"/> <path d="M10 21.9V14L2.1 9.1"/> <path d="m10 14 11.9-6.9"/> <path d="M14 19.8v-8.1"/> <path d="M18 17.5V9.4"/>'
    out["pause"] = '<rect x="14" y="4" width="4" height="16" rx="1"/> <rect x="6" y="4" width="4" height="16" rx="1"/>'
    out["play"] = '<polygon points="6 3 20 12 6 21 6 3"/>'
    return out
ICONS = load_icons()

def ic(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{ICONS[name]}</svg>')

T = {
 "es": dict(
  lang="es-ES", path="/", other="en", other_path="/en/", other_label="English", other_short="EN",
  title="Recetario C — tus recetas de Instagram, listas para cocinar",
  desc="Recetario personal que convierte recetas guardadas de Instagram en recetas escalables con vídeo, lista de la compra, planificador semanal, precios estimados e IA. Autoalojado y de código propio.",
  skip="Saltar al contenido", nav_feat="Funciones", nav_gal="Capturas", nav_stack="Tecnología", theme="Cambiar tema claro/oscuro",
  claim="Tus recetas guardadas, por fin listas para cocinar.",
  sub="Recetario C importa las recetas que guardas en Instagram y las convierte en fichas con ingredientes escalables, vídeo, lista de la compra, planificador semanal y precios estimados. Autoalojado en casa, en tu propio miniPC.",
  cta_demo="Ver la demo", cta_feat="Qué hace", demo_note="Demo estática con recetas de ejemplo; no guarda nada.",
  hero_alt="Recetario C en escritorio: cuadrícula de recetas de ejemplo con fotos de comida",
  hero_m_alt="Recetario C en el móvil: detalle de la paella de marisco con ingredientes y precios",
  feat_h="Funciones", feat_p="Lo que ya funciona en la versión 2.1, y lo que viene después.",
  soon="Próximamente", now="Disponible", partial="Básica · existencias próximamente",
  feats=[
   ("instagram","Importar desde Instagram","Asistente paso a paso: eliges colección, revisas las publicaciones y decides si traer vídeo, foto o ambos. Detecta duplicados.",False),
   ("film","Vídeos y modo cocina","El vídeo original se guarda en tu servidor. Modo cocina con pasos grandes y temporizadores.",False),
   ("shopping-cart","Lista de la compra personalizada","Suma los ingredientes de las recetas y del plan, agrupa unidades y descuenta lo que ya tienes en la despensa.",False),
   ("inbox","Despensa","Básicos y artículos recurrentes que no se añaden a la lista. Existencias con cantidades y descuento al cocinar: en la fase 3.","partial"),
   ("calendar-days","Planificador semanal","Organiza comidas y cenas; las raciones parten de las de cada receta y se envían a la lista.",False),
   ("euro","Precios estimados","Coste por ración y total de cada receta, marcado siempre como estimado.",False),
   ("activity","Estadísticas y «ahora más baratas»","Historial de precios, recetas más cocinadas y avisos cuando una receta sale más barata que su media.",True),
   ("bot","IA y MCP","«Conecta tu IA» con OpenAI, OpenRouter u Ollama local (claves cifradas). API REST y servidor MCP con tokens de solo lectura o escritura.",False),
  ],
  gal_h="Capturas", gal_p="Capturas reales de la aplicación con recetas de ejemplo y fotos libres CC0.",
  gal=[("cuadricula","Cuadrícula de recetas (v2.1.2)"),("detalle","Detalle de receta con raciones y precios"),("planificador","Planificador semanal"),("compra","Lista de la compra"),
       ("filtros","Filtros por tiempo y precio"),("lista-una","Vista «Una sola»"),("lista-info","Vista «Con info»")],
  mob=[("lista","Lista en el móvil"),("detalle","Detalle en el móvil"),("compra","Compra en el móvil")],
  demo_h="Pruébalo", demo_p="La demo estática funciona en el navegador con recetas de ejemplo. Para usarla con tus recetas, se instala en tu propio equipo.",
  stack_h="Tecnología", stack_p="Sin frameworks de frontend ni servicios de terceros obligatorios.",
  stack=[("FastAPI + Uvicorn","API y servidor web en Python"),("SQLite","Base de datos en un único fichero, con migraciones"),
         ("JavaScript sin frameworks","Interfaz de una sola página, sin paso de compilación"),("MCP","Servidor Model Context Protocol (HTTP y stdio)"),
         ("Instaloader","Lectura de colecciones guardadas"),("ffmpeg","Portadas y miniaturas de vídeo"),
         ("cryptography + Argon2","Claves de IA cifradas con Fernet y contraseñas con Argon2"),("pytest + Playwright","Tests automáticos y capturas de pantalla")],
  repo="Código fuente", repo_soon="El repositorio será público próximamente.",
  app_h="App: próximamente", app_p="Una app para el móvil con tus recetas sin conexión, la lista de la compra en el súper y el plan de la semana. Aún en diseño.",
  foot_credits="Créditos de las fotos", foot_credits_p="Fotos de comida libres (CC0 y dominio público) de Wikimedia Commons.",
  foot_icons="Iconos: Lucide (licencia ISC).",
  mk_label="Demo interactiva de Recetario C con recetas de ejemplo", mk_tabs=("Recetas","Planificador","Compra"), mk_search="Buscar receta", mk_tags=("Todas","Rápidas","Baratas","Legumbres","Postres"),
  mk_back="Volver", mk_serv="Raciones", mk_less="Menos raciones", mk_more="Más raciones", mk_ing="Ingredientes", mk_none="Ninguna receta coincide.",
  mk_add="Añadir a la lista", mk_added="Añadido", mk_list="Lista de la compra", mk_cook="Modo cocina", mk_prev="Anterior", mk_next="Siguiente", mk_step="Paso", mk_of="de", mk_done="¡Listo! Buen provecho.",
  mk_days=("Lun","Mar","Mié","Jue","Vie"), mk_meals=("Comida","Cena"), mk_hint="Es la app de verdad con recetas de ejemplo: mira el recorrido o tócala tú (buscar, raciones, planificador, compra). No se guarda nada.",
  mk_dlabel="Demo en vivo de Recetario C en el escritorio", mk_mlabel="Demo en vivo de Recetario C en el móvil", mk_dtitle="Recetario C (demo con recetas de ejemplo), vista de escritorio", mk_mtitle="Recetario C (demo con recetas de ejemplo), vista de móvil",
  mk_pause="Pausar recorrido", mk_play="Reproducir recorrido", mk_search_demo="paella",
  car_label="Carrusel de capturas", car_slide="diapositiva", car_of="de", car_go="Ir a la captura", car_pause="Pausar carrusel", car_play="Reproducir carrusel", mob_h="En el móvil", mk_per="/ración", mk_empty="La lista está vacía.",
  more="Ver más", less="Ver menos",
  feat_more=["Elige qué traer de cada publicación y la app lo descarga en segundo plano.","Cada paso con su temporizador; la pantalla no se apaga.","Marca lo que ya llevas en el carro; se ordena por pasillos.","Lo que siempre tienes en casa no vuelve a la lista.","Arrastra recetas a cada día; las raciones se ajustan solas.","El precio se recalcula al cambiar las raciones.","Gráficas sencillas de lo que cocinas y lo que cuesta.","Tu IA puede leer y crear recetas con permisos limitados."],
  gal_open="Ampliar captura", gal_close="Cerrar", gal_prev="Anterior", gal_next="Siguiente",
  calc_h="Precio por ración", calc_p="Elige una receta de ejemplo y las raciones: el total se recalcula como en la app (precios estimados).", calc_r="Receta", calc_s="Raciones", calc_tot="Total estimado", calc_per="Por ración",
  about_h="Sobre el proyecto", about_p="Enlaces al código y a mi perfil.", dl_h="Descargas", dl=[("windows","monitor","Instalador de Windows"),("docker","container","Docker"),("app","smartphone","App")],
 ),
 "en": dict(
  lang="en", path="/en/", other="es", other_path="/", other_label="Español", other_short="ES",
  title="Recetario C — your Instagram recipes, ready to cook",
  desc="A personal recipe book that turns saved Instagram recipes into scalable recipes with video, shopping list, weekly planner, estimated prices and AI. Self-hosted.",
  skip="Skip to content", nav_feat="Features", nav_gal="Screenshots", nav_stack="Tech", theme="Toggle light/dark theme",
  claim="Your saved recipes, finally ready to cook.",
  sub="Recetario C imports the recipes you save on Instagram and turns them into recipe cards with scalable ingredients, video, a shopping list, a weekly planner and estimated prices. Self-hosted at home on your own mini PC.",
  cta_demo="Open the demo", cta_feat="What it does", demo_note="Static demo with sample recipes; nothing is saved. Interface in Spanish.",
  hero_alt="Recetario C on desktop: grid of sample recipes with food photos",
  hero_m_alt="Recetario C on mobile: seafood paella detail with ingredients and prices",
  feat_h="Features", feat_p="What already works in version 2.1, and what comes next.",
  soon="Coming soon", now="Available", partial="Basic · stock coming soon",
  feats=[
   ("instagram","Import from Instagram","Step-by-step wizard: pick a collection, review the posts and choose video, photo or both. Detects duplicates.",False),
   ("film","Videos and cooking mode","The original video is stored on your server. Cooking mode with large steps and timers.",False),
   ("shopping-cart","Personalised shopping list","Adds up ingredients from recipes and the plan, merges units and skips what is already in your pantry.",False),
   ("inbox","Pantry","Staples and recurring items kept off the list. Stock quantities and deduction when you cook: in phase 3.","partial"),
   ("calendar-days","Weekly planner","Plan lunches and dinners; servings start from each recipe and flow into the list.",False),
   ("euro","Estimated prices","Cost per serving and total for every recipe, always labelled as an estimate.",False),
   ("activity","Statistics and “cheaper now”","Price history, most-cooked recipes and alerts when a recipe is cheaper than its average.",True),
   ("bot","AI and MCP","“Connect your AI” with OpenAI, OpenRouter or local Ollama (encrypted keys). REST API and MCP server with read or write tokens.",False),
  ],
  gal_h="Screenshots", gal_p="Real screenshots of the app with sample recipes and free CC0 photos. The interface is in Spanish.",
  gal=[("cuadricula","Recipe grid (v2.1.2)"),("detalle","Recipe detail with servings and prices"),("planificador","Weekly planner"),("compra","Shopping list"),
       ("filtros","Filters by time and price"),("lista-una","“Single” view"),("lista-info","“With info” view")],
  mob=[("lista","List on mobile"),("detalle","Detail on mobile"),("compra","Shopping on mobile")],
  demo_h="Try it", demo_p="The static demo runs in your browser with sample recipes. To use it with your own recipes, install it on your own machine.",
  stack_h="Tech stack", stack_p="No frontend frameworks and no mandatory third-party services.",
  stack=[("FastAPI + Uvicorn","Python API and web server"),("SQLite","Single-file database with migrations"),
         ("Vanilla JavaScript","Single-page interface, no build step"),("MCP","Model Context Protocol server (HTTP and stdio)"),
         ("Instaloader","Reads saved collections"),("ffmpeg","Video covers and thumbnails"),
         ("cryptography + Argon2","Fernet-encrypted AI keys, Argon2 password hashes"),("pytest + Playwright","Automated tests and screenshots")],
  repo="Source code", repo_soon="The repository will be public soon.",
  app_h="App: coming soon", app_p="A mobile app with your recipes offline, the shopping list at the supermarket and the week's plan. Still being designed.",
  foot_credits="Photo credits", foot_credits_p="Free food photos (CC0 and public domain) from Wikimedia Commons.",
  foot_icons="Icons: Lucide (ISC licence).",
  mk_label="Interactive Recetario C demo with sample recipes", mk_tabs=("Recipes","Planner","Shopping"), mk_search="Search recipes", mk_tags=("All","Quick","Cheap","Pulses","Desserts"),
  mk_back="Back", mk_serv="Servings", mk_less="Fewer servings", mk_more="More servings", mk_ing="Ingredients", mk_none="No recipe matches.",
  mk_add="Add to list", mk_added="Added", mk_list="Shopping list", mk_cook="Cooking mode", mk_prev="Previous", mk_next="Next", mk_step="Step", mk_of="of", mk_done="Done! Enjoy your meal.",
  mk_days=("Mon","Tue","Wed","Thu","Fri"), mk_meals=("Lunch","Dinner"), mk_hint="This is the real app with sample recipes: watch the tour or try it yourself (search, servings, planner, shopping). Nothing is saved.",
  mk_dlabel="Live demo of Recetario C on desktop", mk_mlabel="Live demo of Recetario C on mobile", mk_dtitle="Recetario C (demo with sample recipes), desktop view", mk_mtitle="Recetario C (demo with sample recipes), mobile view",
  mk_pause="Pause tour", mk_play="Play tour", mk_search_demo="paella",
  car_label="Screenshot carousel", car_slide="slide", car_of="of", car_go="Go to screenshot", car_pause="Pause carousel", car_play="Play carousel", mob_h="On mobile", mk_per="/serving", mk_empty="The list is empty.",
  more="More", less="Less",
  feat_more=["Choose what to bring from each post and the app downloads it in the background.","Every step has its own timer; the screen stays on.","Tick what is already in the trolley; sorted by aisle.","What you always have at home stays off the list.","Drop recipes on each day; servings adjust themselves.","The price is recalculated when you change servings.","Simple charts of what you cook and what it costs.","Your AI can read and create recipes with scoped permissions."],
  gal_open="Enlarge screenshot", gal_close="Close", gal_prev="Previous", gal_next="Next",
  calc_h="Price per serving", calc_p="Pick a sample recipe and the servings: the total is recalculated just like in the app (estimated prices).", calc_r="Recipe", calc_s="Servings", calc_tot="Estimated total", calc_per="Per serving",
  about_h="About the project", about_p="Links to the code and my profile.", dl_h="Downloads", dl=[("windows","monitor","Windows installer"),("docker","container","Docker"),("app","smartphone","App")],
 ),
}

SAMPLE = json.loads((ROOT / "data/sample/recetas-demo.json").read_text())["recetas"]
TAGS = {"Legumbres": {"lentejas-estofadas", "ensalada-de-garbanzos"}, "Postres": {"flan-de-huevo", "arroz-con-leche"}}
def slug(r): return Path(r["foto"]).stem
def rtags(r):
    out = [k for k, v in TAGS.items() if slug(r) in v]
    if r["tiempo_total_min"] <= 30: out.append("Rápidas")
    if r["precio_racion_eur"] < 1: out.append("Baratas")
    return out
TAGKEYS = ("all", "Rápidas", "Baratas", "Legumbres", "Postres")
PHONE = next(r for r in SAMPLE if slug(r) == "paella")
PLAN = ["lentejas-estofadas", "tortilla-de-patatas", "crema-de-calabaza", "pescado-al-horno", "macarrones-con-tomate", "salmorejo", "pollo-asado", "ensalada-de-garbanzos", "paella", "croquetas"]

def demo_data():
    rs = [{"id": r["id"], "t": r["titulo"], "s": slug(r), "r": r["raciones"], "m": r["tiempo_total_min"], "p": r["precio_total_eur"], "tags": rtags(r),
           "i": [[x["nombre"], x["cantidad_num"], x["unidad"], x["cantidad_normal"]] for x in r["ingredientes"]],
           "st": [p["texto"] for p in r["pasos"]]} for r in SAMPLE]
    return "/* Generated by scripts/build_landing.py from data/sample/recetas-demo.json (sample data, CC0 covers). */\nwindow.RC_DATA=" + json.dumps({"r": rs, "plan": PLAN}, ensure_ascii=False, separators=(",", ":")) + ";\n"

def eur(x, k): return (f"{x:.2f} €".replace(".", ",") if k == "es" else f"€{x:.2f}")

def mockup(t, k):
    """Hero simulators: the existing browser and phone frames, with the real app (landing/demo, built by
    scripts/build_landing_demo.py) running inside on sample data. landing.js scales them and plays a guided tour."""
    e = html.escape
    q = "?lang=en" if k == "en" else ""
    return f"""<div class="shots" data-mock>
    <div class="frame desk mock" role="region" aria-label="{e(t['mk_dlabel'])}">
      <div class="mbar" aria-hidden="true"><i></i><i></i><i></i><span>recetario.local</span></div>
      <div class="mscreen" data-w="1024"><iframe src="/demo/{q}#/recetas" title="{e(t['mk_dtitle'])}" data-tour="desk"></iframe></div>
    </div>
    <div class="frame phone mock mphone" role="region" aria-label="{e(t['mk_mlabel'])}">
      <div class="mscreen" data-w="390"><iframe src="/demo/{q}#/recetas" title="{e(t['mk_mtitle'])}" data-tour="phone"></iframe></div>
    </div>
    <p class="muted small mhint">{e(t['mk_hint'])} <button type="button" class="tourbtn" id="tourbtn" data-pause="{e(t['mk_pause'])}" data-play="{e(t['mk_play'])}">{ic('pause', 'ic i-pause')}{ic('play', 'ic i-play')}<span>{e(t['mk_pause'])}</span></button></p>
  </div>"""

def pic(base, alt, w, h, eager=False, sizes=None, small=None):
    """<picture> with a dark source; theme.js rewrites media when the user forces a theme."""
    r = "" if not small else f" {base}-light-{small}.webp"
    lz = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    def ss(t):
        return f"/img/{base}-{t}.webp {w}w" + (f", /img/{base}-{t}-{small[0]}.webp {small[0]}w" if small else "")
    sz = f' sizes="{sizes}"' if sizes else ""
    return (f'<picture><source data-dark media="(prefers-color-scheme: dark)" srcset="{ss("dark")}"{sz}>'
            f'<img src="/img/{base}-light.webp" srcset="{ss("light")}"{sz} width="{w}" height="{h}" alt="{html.escape(alt)}" {lz}></picture>')

def page(k):
    t = T[k]; o = T[t["other"]]
    e = html.escape
    feats = "\n".join(
        f'<li class="card rv{" soon" if f[3] is True else ""}">{ic(f[0], "ic fi")}<h3>{e(f[1])}</h3><p>{e(f[2])}</p>'
        + f'<button type="button" class="more" aria-expanded="false" aria-controls="fm-{k}-{n}" data-more="{e(t["more"])}" data-less="{e(t["less"])}">{e(t["more"])}</button>'
        + f'<p class="fmore" id="fm-{k}-{n}" hidden><span class="pulse" aria-hidden="true"></span>{e(t["feat_more"][n])}</p>'
        + (f'<span class="badge b-soon">{e(t["soon"])}</span>' if f[3] is True else
           f'<span class="badge b-part">{e(t["partial"])}</span>' if f[3] == "partial" else
           f'<span class="badge b-ok">{e(t["now"])}</span>') + "</li>" for n, f in enumerate(t["feats"]))
    slides = [f'<figure><button type="button" class="zoom" aria-label="{e(t["gal_open"])}: {e(c)}" data-full="/img/g-{n}-light.webp" data-full-dark="/img/g-{n}-dark.webp" data-cap="{e(c)}">{pic("g-"+n, c, 960, 600, sizes="(max-width: 1000px) 92vw, 900px", small=(480,))}</button><figcaption>{e(c)}</figcaption></figure>' for n, c in t["gal"]]
    slides.append('<figure class="car-mob"><div>' + "".join(f'<figure>{pic("m-"+n, c, 300, 650)}<figcaption>{e(c)}</figcaption></figure>' for n, c in t["mob"]) + f'</div><figcaption class="sr">{e(t["mob_h"])}</figcaption></figure>')
    nsl = len(slides)
    gal = "\n".join(f'<li class="car-s" id="cs-{i}" role="group" aria-roledescription="{e(t["car_slide"])}" aria-label="{i+1} {e(t["car_of"])} {nsl}">{sl}</li>' for i, sl in enumerate(slides))
    caps = [c for _, c in t["gal"]] + [t["mob_h"]]
    dots = "".join(f'<button type="button" class="car-dot" aria-controls="cs-{i}" aria-label="{e(t["car_go"])} {i+1}: {e(c)}"{" aria-current=\"true\"" if i == 0 else ""}></button>' for i, c in enumerate(caps))
    carousel = f'''<div class="car" role="region" aria-roledescription="carousel" aria-label="{e(t['car_label'])}">
  <ul class="car-track" id="cartrack" tabindex="0" aria-label="{e(t['gal_h'])}">
{gal}
  </ul>
  <div class="car-ctl">
    <button type="button" class="car-btn" id="carprev" aria-label="{e(t['gal_prev'])}">{ic('arrow-left')}</button>
    <div class="car-dots">{dots}</div>
    <button type="button" class="car-btn" id="carnext" aria-label="{e(t['gal_next'])}">{ic('arrow-right')}</button>
    <button type="button" class="car-btn car-play" id="carplay" aria-label="{e(t['car_pause'])}" data-pause="{e(t['car_pause'])}" data-play="{e(t['car_play'])}">{ic('pause', 'ic i-pause')}{ic('play', 'ic i-play')}</button>
  </div>
</div>'''
    lightbox = f'''<dialog class="lb" id="lb" aria-label="{e(t['gal_h'])}"><figure><img id="lbimg" src="/img/g-cuadricula-light.webp" alt="" width="960" height="600"><figcaption id="lbcap"></figcaption></figure>
<div class="lbnav"><button type="button" class="btn" id="lbprev">{ic('arrow-left')} {e(t['gal_prev'])}</button><button type="button" class="btn" id="lbclose">{e(t['gal_close'])}</button><button type="button" class="btn" id="lbnext">{e(t['gal_next'])} {ic('arrow-right')}</button></div></dialog>'''
    opts = "".join(f'<option value="{r["id"]}"{" selected" if slug(r) == "paella" else ""}>{e(r["titulo"])}</option>' for r in SAMPLE)
    calc = f'''<section id="precio" class="wrap sec rv"><div class="card calc"><div><h2>{e(t['calc_h'])}</h2><p class="muted">{e(t['calc_p'])}</p></div>
<div class="calcf"><label>{e(t['calc_r'])}<select id="cr">{opts}</select></label><label>{e(t['calc_s'])}<input id="cs" type="number" min="1" max="20" value="{PHONE['raciones']}" inputmode="numeric"></label>
<output id="co" for="cr cs" aria-live="polite"><span>{e(t['calc_tot'])} <b id="ct">{eur(PHONE['precio_total_eur'], k)}</b></span><span>{e(t['calc_per'])} <b id="cp">{eur(PHONE['precio_racion_eur'], k)}</b></span></output></div></div></section>'''
    stack = "\n".join(f"<li><strong>{e(a)}</strong><span>{e(b)}</span></li>" for a, b in t["stack"])
    repo = (f'<a class="btn" href="{e(CFG["repo_url"])}" rel="noopener">{e(t["repo"])} {ic("external-link")}</a>'
            if CFG["repo_public"] else f'<p class="muted">{ic("lock")} {e(t["repo_soon"])}</p>')
    links = [("linkedin", "LinkedIn", CFG["profiles"]["linkedin"]), ("github", "GitHub", CFG["profiles"]["github"])]
    if CFG["repo_public"]: links.append(("github", t["repo"], CFG["repo_url"]))
    about = " ".join(f'<a class="btn" href="{e(u)}" rel="noopener">{ic(i)} {e(n)}</a>' for i, n, u in links)
    dls = " ".join(
        (f'<a class="btn" href="{e(CFG["downloads"][key])}" rel="noopener">{ic(i)} {e(n)} {ic("download")}</a>' if CFG.get("downloads", {}).get(key)
         else f'<span class="btn dis" aria-disabled="true">{ic(i)} {e(n)} <span class="badge b-soon">{e(t["soon"])}</span></span>')
        for key, i, n in t["dl"])
    demo1 = f'<a class="btn primary" href="{e(CFG["demo_url"])}" rel="noopener">{e(t["cta_demo"])} {ic("arrow-right")}</a>' if CFG["demo_url"] else ""
    url = SITE + t["path"]; credits = "/creditos/" if k == "es" else "/en/credits/"
    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t['title'])}</title>
<meta name="description" content="{e(t['desc'])}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#fbf8f4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14110f" media="(prefers-color-scheme: dark)">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="es" href="{SITE}/">
<link rel="alternate" hreflang="en" href="{SITE}/en/">
<link rel="alternate" hreflang="x-default" href="{SITE}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Recetario C">
<meta property="og:title" content="{e(t['title'])}">
<meta property="og:description" content="{e(t['desc'])}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{'es_ES' if k == 'es' else 'en_GB'}">
<meta property="og:locale:alternate" content="{'en_GB' if k == 'es' else 'es_ES'}">
<meta property="og:image" content="{SITE}/img/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(t['hero_alt'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(t['title'])}">
<meta name="twitter:description" content="{e(t['desc'])}">
<meta name="twitter:image" content="{SITE}/img/og.jpg">
<link rel="stylesheet" href="/assets/landing.2.css">
<script src="/assets/theme.js"></script>
<script src="/assets/demo-data.js" defer></script>
<script src="/assets/landing.2.js" defer></script>
</head>
<body data-i18n="{e(json.dumps({x: t[x] for x in t if x.startswith('mk_')}, ensure_ascii=False))}" data-lang="{k}">
<a class="skip" href="#main">{e(t['skip'])}</a>
<header class="top"><div class="wrap bar">
  <a class="brand" href="{t['path']}">{ic('chef-hat')} Recetario C</a>
  <nav aria-label="{e(t['nav_feat'])}"><a href="#funciones">{e(t['nav_feat'])}</a><a href="#capturas">{e(t['nav_gal'])}</a><a href="#stack">{e(t['nav_stack'])}</a></nav>
  <div class="tools">
    <a class="lang" href="{t['other_path']}" hreflang="{t['other']}" lang="{o['lang']}">{ic('languages')}<span class="sr">{e(t['other_label'])}</span><span aria-hidden="true">{t['other_short']}</span></a>
    <button class="theme" type="button" id="themeBtn" aria-label="{e(t['theme'])}" aria-pressed="false">{ic('moon','ic i-moon')}{ic('sun','ic i-sun')}</button>
  </div>
</div></header>
<main id="main">
<section class="hero wrap">
  <div class="copy">
    <p class="kicker">v{VERSION} · self-hosted</p>
    <h1>{e(t['claim'])}</h1>
    <p class="lead">{e(t['sub'])}</p>
    <p class="ctas">{demo1}<a class="btn" href="#funciones">{e(t['cta_feat'])}</a></p>
    {f'<p class="muted small">{e(t["demo_note"])}</p>' if CFG['demo_url'] else ''}
  </div>
  {mockup(t, k)}
</section>
<section id="funciones" class="wrap sec">
  <h2>{e(t['feat_h'])}</h2><p class="muted">{e(t['feat_p'])}</p>
  <ul class="grid feats">
{feats}
  </ul>
</section>
<section id="capturas" class="wrap sec">
  <h2>{e(t['gal_h'])}</h2><p class="muted">{e(t['gal_p'])}</p>
  {carousel}
</section>
{f'''<section id="demo" class="wrap sec band">
  <div><h2>{e(t['demo_h'])}</h2><p>{e(t['demo_p'])}</p></div>
  <p class="ctas"><a class="btn primary" href="{e(CFG['demo_url'])}" rel="noopener">{e(t['cta_demo'])} {ic('external-link')}</a></p>
</section>
''' if CFG['demo_url'] else ''}{calc}
<section id="stack" class="wrap sec">
  <h2>{e(t['stack_h'])}</h2><p class="muted">{e(t['stack_p'])}</p>
  <ul class="stack">
{stack}
  </ul>
  <div class="repo">{repo}</div>
</section>
<section id="app" class="wrap sec">
  <div class="card app">{ic('smartphone','ic fi')}<div><h2>{e(t['app_h'])}</h2><p>{e(t['app_p'])}</p></div><span class="badge b-soon">{e(t['soon'])}</span></div>
</section>
</main>
{lightbox}
<footer class="foot"><div class="wrap">
  <div class="foot-cols"><div><h2 class="h3">{e(t['about_h'])}</h2><p class="links">{about}</p></div>
  <div><h2 class="h3">{e(t['dl_h'])}</h2><p class="links">{dls}</p></div></div>
  <p><a href="{credits}">{ic('camera')} {e(t['foot_credits'])}</a> — {e(t['foot_credits_p'])}</p>
  <p class="muted small">{e(t['foot_icons'])} · <a href="{t['other_path']}" hreflang="{t['other']}" lang="{o['lang']}">{e(t['other_label'])}</a></p>
</div></footer>
</body>
</html>
"""

def credits_page(k):
    t = T[k]; e = html.escape
    rows = []
    for line in (ROOT / "data/sample/covers/ATTRIBUTION.md").read_text().splitlines():
        m = re.match(r"\| (\S+\.jpg) \| \[(.+?)\]\((https://commons\.wikimedia\.org/[^)]+)\) \| (.+?) \| (.+?) \|", line)
        if m:
            f, name, link, author, lic = m.groups()
            rows.append(f'<tr><td>{e(f)}</td><td><a href="{e(link)}" rel="noopener">{e(name)}</a></td><td>{e(author)}</td><td>{e(lic)}</td></tr>')
    h = ("Créditos de las fotos", "Fotos de comida libres usadas en los datos de ejemplo, las capturas y esta página. Todas proceden de Wikimedia Commons; ninguna de Instagram.",
         ("Archivo", "Fuente", "Autor", "Licencia"), "Volver") if k == "es" else \
        ("Photo credits", "Free food photos used in the sample data, the screenshots and this page. All come from Wikimedia Commons; none from Instagram.",
         ("File", "Source", "Author", "Licence"), "Back")
    p = "/creditos/" if k == "es" else "/en/credits/"
    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h[0]} — Recetario C</title>
<meta name="description" content="{e(h[1])}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{SITE}{p}">
<link rel="alternate" hreflang="es" href="{SITE}/creditos/"><link rel="alternate" hreflang="en" href="{SITE}/en/credits/"><link rel="alternate" hreflang="x-default" href="{SITE}/creditos/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="stylesheet" href="/assets/landing.2.css"><script src="/assets/theme.js"></script>
</head>
<body><main id="main" class="wrap sec">
<p><a href="{t['path']}">{ic('arrow-left')} {h[3]}</a></p>
<h1>{h[0]}</h1><p class="muted">{e(h[1])}</p>
<div class="tbl"><table><thead><tr>{''.join(f'<th scope="col">{c}</th>' for c in h[2])}</tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table></div>
<p class="muted small">CC0: <a href="https://creativecommons.org/publicdomain/zero/1.0/" rel="noopener">creativecommons.org/publicdomain/zero/1.0</a></p>
</main></body></html>
"""

if __name__ == "__main__":
    (L / "assets/demo-data.js").write_text(demo_data())
    (L / "index.html").write_text(page("es"))
    (L / "en").mkdir(exist_ok=True); (L / "en/index.html").write_text(page("en"))
    (L / "creditos").mkdir(exist_ok=True); (L / "creditos/index.html").write_text(credits_page("es"))
    (L / "en/credits").mkdir(exist_ok=True); (L / "en/credits/index.html").write_text(credits_page("en"))
    print("landing built:", SITE, "repo_public=", CFG["repo_public"])
