# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según [SemVer](https://semver.org/lang/es/).

## [2.1.2] — 2026-10-30 — Portadas y cuadrícula

### Añadido
- **Selector de portada** en el editor: miniatura original (por defecto), fotograma del vídeo con deslizador y vista previa generada en el servidor con ffmpeg (avisa si es casi negro), foto subida (JPG/PNG/WebP, tamaño máximo validado, sin EXIF/XMP ni otros metadatos y con la orientación aplicada) o foto genérica libre de `data/sample/covers/` con su crédito.
- **Ajustes → Portadas**: portada por defecto global (original, fotograma o genérica).
- Migración `m3_cover_source`: columnas `cover_source` y `cover_param` en `recipes`.
- API: `GET /api/portadas/biblioteca`, `GET|PUT /api/ajustes/portada`, `PUT /api/recipes/{id}/portada`, `GET /api/recipes/{id}/portada/fotograma`, `POST /api/recipes/{id}/portada/subir`; para agentes `GET /api/v1/covers/library` y `PUT /api/v1/recipes/{id}/cover`. MCP: `list_cover_library` y `set_recipe_cover`.
- Reimportar (`reimportar: true` en la selección del importador) actualiza vídeo/foto/miniatura **sin pisar nunca** una portada subida, de fotograma o genérica.
- Cuadrícula: línea de datos bajo el título (tiempo · €/ración) con altura fija; las tarjetas siguen igualadas.
- Detalle: fecha en que se añadió la receta, en formato es-ES.

### Cambiado
- La portada automática prioriza la **miniatura original** de la publicación; el importador la guarda siempre (`media/originals/`), también en importaciones solo de vídeo.
- El fotograma automático salta los fotogramas negros (prueba 1, 2, 3, 5, 8, 0,5 y 0 s; si todos son oscuros usa el menos oscuro).
- Reels 9:16: **recorte centrado** (`object-fit: cover`) a la proporción de la tarjeta en todas las vistas. Se descartó el fondo desenfocado: en tarjetas 4:3 deja el plato en una franja estrecha, recarga la cuadrícula densa y duplica el trabajo de imagen; en los reels de recetas el plato suele estar centrado.
- `scripts/screenshots.py`: contexto y Chromium en es-ES (también el `<input type=date>`), portadas solo de la biblioteca CC0 y nuevas capturas `editor-portada-*` y `detalle-fecha-*`. La captura del deslizador con un vídeo real es opcional (`--private-video`), se llama `*-private.png`, está en `.gitignore` y no se usa en la landing ni en la demo.

## [2.1.1] — 2026-10-30 — Correcciones visuales

### Cambiado
- **Filtros** agrupados en un botón con contador de filtros activos: *popover* en escritorio y hoja inferior en móvil, con trampa de foco y cierre con Esc. La búsqueda y el selector de vista siguen siempre visibles.
- Vista **Una sola**: portada 16:9 con altura máxima de ~380 px; la información se ve sin desplazarse.
- **Etiquetas**: sin cortes a mitad de palabra; desvanecido en los bordes del carrusel y chip «+N» en las tarjetas.
- **Cuadrícula**: tarjetas de igual altura, títulos limitados a 2 líneas y portadas con proporción fija 4:3.
- **Planificador**: las raciones por defecto son las de la receta (2 si son estimadas, no numéricas o fuera de 1–12).
- Miniaturas del importador simulado sobrias y con cuentas inventadas.

### Añadido
- Fotos de muestra libres (CC0 / dominio público) en `data/sample/covers/` con `ATTRIBUTION.md`; la demo estática ya no incluye vídeos ni contenido de Instagram.
- `scripts/seed_demo.py`: plan semanal, favoritos, despensa y listas de la compra realistas para las capturas.
- `docs/screenshots/_overview.png` y nueva captura `filtros-*`.

### Corregido
- Ninguna captura muestra cartas de ajuste ni barras de color.
- Etiqueta duplicada «Precio/ración por ración».

## [2.1.0] — 2026-10-30 — Fase 2

### Añadido
- **Selector de vista** en la lista de recetas: *Una sola*, *Con info*, *Muy detallado* y *Cuadrícula* (con control de columnas 2–8). Accesible con teclado (flechas, Inicio/Fin). La elección se guarda por usuario en el servidor (`GET/PUT /api/preferencias/lista`) con respaldo en `localStorage`.
- Enlace discreto **«Ver original»** en cada receta con origen (Instagram, TikTok, YouTube, web…), con icono de la fuente, debajo del reproductor y en la vista *Muy detallado*. Nuevos campos `source_url` y `source_type` en la API, la API v1, MCP y todas las exportaciones (en el JSON v1 se añaden sin cambiar el resto del formato).
- **Inicio de sesión web** con un único administrador (argon2), cookie de sesión, protección CSRF y freno a fuerza bruta.
  Primer arranque con **código de configuración** (registro del servidor / `setup-code.txt`) o `python -m app.cli create-admin`.
- **Lista de la compra** completa: varias listas, pasillos ordenables, agregado de ingredientes con conversión de unidades,
  estados (pendiente / ya lo tengo / comprado), recurrentes, precios orientativos y **despensa**.
- **Planificador semanal**: añade recetas por día y comida, raciones, y envía la semana a la lista de la compra.
- **Escalado de raciones** en la API con redondeo inteligente.
- **Portadas reales** de vídeo con ffmpeg (`RECETAS_FFMPEG`) y marco de vídeo con enlace a Instagram.
- Panel **Estado** en Ajustes: versión, commit, esquema, disco, vídeos que faltan, importaciones y cola de portadas.
- **Validador de importación** con códigos (`NOT_FOUND`, `PRIVATE`, `NO_INGREDIENTS`, `NO_STEPS`, `RATE_LIMITED`…),
  motivo en español e inglés y borradores «incompletos» recuperables («Completar a mano» / «Guardar como borrador»),
  igual en la UI, la API v1 y MCP.
- **Iconos de línea** Lucide incluidos en el proyecto (licencia ISC), sin emojis ni CDN; marcador neutro para recetas sin portada.
- Tarjeta **Acceso** en Ajustes (solo administrador): URLs detectadas (LAN, Tailscale, local), botón copiar, **QR generado en el servidor**
  (qrcodegen, MIT) y edición de dirección/puerto con reglas de cortafuegos propias y reinicio por la tarea programada.
- Soporte de **`.env` / `RECETAS_CONFIG_FILE`** con prioridad: argumentos > variables de entorno > archivo > valores por defecto. `.env.example`.
- Tabla **`price_history`** (migración 2) como base para la Fase 3.
- Migraciones de esquema al arrancar (`PRAGMA user_version`) con copia `recetas.db.bak-vN` antes de migrar.
- Demo estática construida solo con **datos de ejemplo inventados** (`data/sample/`).
- `CHANGELOG.md` y `docs/ROADMAP.md`.

### Cambiado
- La API de la UI (`/api/...`) ahora **exige sesión**; `/api/v1` y `/mcp` siguen con token.
- Crear recetas por la API v1 valida que tengan ingredientes y pasos (salvo las de «solo vídeo»).

### Corregido
- Los iconos SVG anidados se tragaban el texto que les seguía (p. ej. avisos y títulos de Ajustes).
- Desbordamiento horizontal de Ajustes en móvil.
- `build_static.py` en Windows: consola UTF‑8, cierre de SQLite antes de borrar la carpeta temporal y borrado de
  archivos de solo lectura; los tests muestran la salida del subproceso si falla.
- Lista de la compra: «repollo» ya no cae en Carne, «huevos L» / «huevos grandes» se agrupan con «huevos»,
  y las unidades contables van en plural («2 dientes»).
- Lectura y escritura de archivos con `encoding="utf-8"` explícito.

## [2.0.0] — 2026-10-30 — Fase 1

### Añadido
- Reescritura completa: FastAPI + SQLite + SPA sin build (ES/EN, claro/oscuro).
- Recetario con búsqueda tolerante a erratas, filtros, favoritas, valoración, temporizadores, modo cocina e impresión.
- Importador de Instagram (instaloader o simulado) en segundo plano con deduplicado por shortcode; la contraseña no se guarda.
- Exportación JSON / HTML / Markdown / JSON v1 (sin pérdidas) y ZIP con medios.
- «Conecta tu IA» (compatible OpenAI) con clave cifrada (Fernet) fuera de la carpeta de datos.
- Acceso para agentes: tokens con hash, API REST `/api/v1` y servidor MCP (HTTP y stdio).
- Siembra inicial desde los datos de la v1, reutilizando su carpeta de vídeos.

[2.1.0]: #210--2026-10-30--fase-2
[2.0.0]: #200--2026-10-30--fase-1
