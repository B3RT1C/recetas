# Landing de Recetario C

Página de presentación estática (ES en `/`, EN en `/en/`). HTML y CSS escritos a mano, ~1 KB de JS (tema),
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
`'self'`, HSTS, nosniff, frame-ancestors none). Si se renombra un asset, cambiar su nombre (no hay hash).

## Configuración

`site.config.json`:

- `site_url`: dominio público definitivo (canonical, hreflang, og:image, sitemap). **Placeholder**: `https://recetario-c.pages.dev`.
- `demo_url`: URL de la demo estática (**placeholder**).
- `repo_public` / `repo_url`: el enlace al repositorio solo aparece con `repo_public: true`.

Tras cambiarlo, regenerar el HTML (el resultado se versiona; Pages no compila nada):

```bash
python scripts/build_landing.py          # index.html, en/index.html, creditos/, en/credits/
sh scripts/landing_images.sh             # WebP y og.jpg desde docs/screenshots
python scripts/check_landing.py          # sin URLs externas fuera de la lista permitida
python scripts/landing_screenshots.py    # capturas en landing/docs/screenshots
```

Las imágenes son capturas reales con los datos de ejemplo y las fotos CC0 de `data/sample/covers/` (créditos en `/creditos/`).
`docs/` contiene capturas de la propia landing (no se indexan).
