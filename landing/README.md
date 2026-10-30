# Landing de Recetario C

Página de presentación estática (ES en `/`, EN en `/en/`). HTML y CSS escritos a mano, JS vanilla (tema, simuladores, carrusel),
fuentes del sistema, sin frameworks ni CDN. Iconos Lucide (ISC), los mismos que la app.

## Cloudflare Pages

| Ajuste | Valor |
|---|---|
| Framework preset | None |
| Build command | *(vacío)* |
| Build output directory | `landing` |
| Root directory | *(raíz del repo)* — o `landing` con output `.` |
| Variables | ninguna |

`_headers` define caché (HTML siempre revalida; `img/` 30 días; `assets/` 1 día) y cabeceras de seguridad (CSP estricta
`'self'`, HSTS, nosniff, frame-ancestors none). No hay hash: si cambia un asset, se renombra con un número de versión (`landing.3.css`, `landing.2.js`) y se
regenera el HTML. `/demo/*` tiene su propia CSP (solo `'self'`, `frame-ancestors 'self'`, `noindex`).

## Simuladores (demo en vivo)

Los marcos de navegador y móvil del hero incrustan `/demo/`: una copia **sin modificar** de `static/` (la app real)
sobre una API simulada en memoria (`demo/assets/mock-api.js`) con respuestas grabadas de la app FastAPI real usando
los datos de ejemplo (`demo/data/api.json`). Sin sesión, claves, IA ni vídeos de terceros; los cambios no se guardan.
Un recorrido guiado navega solo (recetas → búsqueda → receta → raciones → planificador → compra → ajustes); se
detiene 25 s al interactuar, con el botón de pausa, fuera de pantalla y con `prefers-reduced-motion`.


## Configuración

`site.config.json`:

- `site_url`: dominio público definitivo (canonical, hreflang, og:image, sitemap). **Placeholder**: `https://recetario-c.pages.dev`.
- `demo_url`: URL de la demo estática (**placeholder**).
- `repo_public` / `repo_url`: el enlace al repositorio solo aparece con `repo_public: true`.

Tras cambiarlo, regenerar el HTML (el resultado se versiona; Pages no compila nada):

```bash
python scripts/build_landing_demo.py     # demo/ (copia de static/ + API grabada; ffmpeg para las portadas)
python scripts/build_landing.py          # index.html, en/index.html, creditos/, en/credits/
sh scripts/landing_images.sh             # WebP y og.jpg desde docs/screenshots
python scripts/check_landing.py          # sin URLs externas fuera de la lista permitida
python scripts/landing_screenshots.py    # capturas en landing/docs/screenshots
```

Las imágenes son capturas reales con los datos de ejemplo y las fotos CC0 de `data/sample/covers/` (créditos en `/creditos/`).
`docs/` contiene capturas de la propia landing (no se indexan).
