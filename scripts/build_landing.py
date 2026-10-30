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
  gal=[("detalle","Detalle de receta con raciones y precios"),("planificador","Planificador semanal"),("compra","Lista de la compra"),
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
  foot_icons="Iconos: Lucide (licencia ISC).", foot_made="",
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
  gal=[("detalle","Recipe detail with servings and prices"),("planificador","Weekly planner"),("compra","Shopping list"),
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
  foot_icons="Icons: Lucide (ISC licence).", foot_made="",
 ),
}

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
        f'<li class="card{" soon" if f[3] is True else ""}">{ic(f[0], "ic fi")}<h3>{e(f[1])}</h3><p>{e(f[2])}</p>'
        + (f'<span class="badge b-soon">{e(t["soon"])}</span>' if f[3] is True else
           f'<span class="badge b-part">{e(t["partial"])}</span>' if f[3] == "partial" else
           f'<span class="badge b-ok">{e(t["now"])}</span>') + "</li>" for f in t["feats"])
    gal = "\n".join(f'<figure>{pic("g-"+n, c, 960, 600, sizes="(max-width: 700px) 92vw, 460px", small=(480,))}<figcaption>{e(c)}</figcaption></figure>' for n, c in t["gal"])
    mob = "\n".join(f'<figure>{pic("m-"+n, c, 300, 650)}<figcaption>{e(c)}</figcaption></figure>' for n, c in t["mob"])
    stack = "\n".join(f"<li><strong>{e(a)}</strong><span>{e(b)}</span></li>" for a, b in t["stack"])
    repo = (f'<a class="btn" href="{e(CFG["repo_url"])}" rel="noopener">{e(t["repo"])} {ic("external-link")}</a>'
            if CFG["repo_public"] else f'<p class="muted">{ic("lock")} {e(t["repo_soon"])}</p>')
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
<link rel="preload" as="image" href="/img/hero-light.webp" imagesrcset="/img/hero-light.webp 1200w, /img/hero-light-720.webp 720w" imagesizes="(max-width: 900px) 92vw, 720px" media="(prefers-color-scheme: light)">
<link rel="stylesheet" href="/assets/landing.css">
<script src="/assets/theme.js"></script>
</head>
<body>
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
    <p class="ctas"><a class="btn primary" href="{e(CFG['demo_url'])}" rel="noopener">{e(t['cta_demo'])} {ic('arrow-right')}</a><a class="btn" href="#funciones">{e(t['cta_feat'])}</a></p>
    <p class="muted small">{e(t['demo_note'])}</p>
  </div>
  <div class="shots">
    <div class="frame desk">{pic('hero', t['hero_alt'], 1200, 750, eager=True, sizes='(max-width: 900px) 92vw, 720px', small=(720,))}</div>
    <div class="frame phone">{pic('hero-m', t['hero_m_alt'], 260, 562, eager=True)}</div>
  </div>
</section>
<section id="funciones" class="wrap sec">
  <h2>{e(t['feat_h'])}</h2><p class="muted">{e(t['feat_p'])}</p>
  <ul class="grid feats">
{feats}
  </ul>
</section>
<section id="capturas" class="wrap sec">
  <h2>{e(t['gal_h'])}</h2><p class="muted">{e(t['gal_p'])}</p>
  <div class="gal">
{gal}
  </div>
  <div class="gal mob">
{mob}
  </div>
</section>
<section id="demo" class="wrap sec band">
  <div><h2>{e(t['demo_h'])}</h2><p>{e(t['demo_p'])}</p></div>
  <p class="ctas"><a class="btn primary" href="{e(CFG['demo_url'])}" rel="noopener">{e(t['cta_demo'])} {ic('external-link')}</a></p>
</section>
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
<footer class="foot"><div class="wrap">
  <p><a href="{credits}">{ic('camera')} {e(t['foot_credits'])}</a> — {e(t['foot_credits_p'])}</p>
  <p class="muted small">{e(t['foot_icons'])}{e(t['foot_made'])} · <a href="{t['other_path']}" hreflang="{t['other']}" lang="{o['lang']}">{e(t['other_label'])}</a></p>
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
<link rel="stylesheet" href="/assets/landing.css"><script src="/assets/theme.js"></script>
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
    (L / "index.html").write_text(page("es"))
    (L / "en").mkdir(exist_ok=True); (L / "en/index.html").write_text(page("en"))
    (L / "creditos").mkdir(exist_ok=True); (L / "creditos/index.html").write_text(credits_page("es"))
    (L / "en/credits").mkdir(exist_ok=True); (L / "en/credits/index.html").write_text(credits_page("en"))
    print("landing built:", SITE, "repo_public=", CFG["repo_public"])
