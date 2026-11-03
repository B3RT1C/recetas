# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones según [SemVer](https://semver.org/lang/es/).

## [2.1.6] — 2026-11-03 — Pulido de la interfaz y Ajustes por apartados

### Corregido
- Los diálogos, hojas de filtros y el modo cocina se cierran al cambiar de pantalla (también con «Atrás»).
- El paso a paso de importación ya no comparte clases con otros componentes («wizard» → `wizard-steps`) y la ficha de detalle usa `dfacts` en vez del `facts` de la lista.
- Una sola definición de `.form-grid`: «Nueva receta» vuelve a una columna en móvil.
- Sin desplazamiento horizontal a 360 y 390 px en Importar (la etiqueta «Próximamente» larga pasa a una línea aparte) ni en ninguna subpantalla de Ajustes.
- Sin anillo de foco sobre el contenedor principal al navegar.
- Se eliminan declaraciones CSS de maquetación duplicadas y contradictorias.

### Cambiado
- **Ajustes por apartados:** en móvil, un índice de filas grandes y cada apartado en su propia ruta (`#/ajustes/ia`, `#/ajustes/cuenta`…); en escritorio, dos columnas con menú lateral. Desaparecen las pestañas horizontales. Apartados: Apariencia, Portadas, Conectar tu IA, Acceso para agentes, Importación e Instagram, Precios y compra, Copias y exportación, Cuenta y seguridad, Estado y acerca de. Todos los ajustes existentes siguen funcionando.
- El tema se elige con «Claro»/«Oscuro» en Apariencia (sincronizado con el botón de la cabecera).
- Detalle de receta en dos columnas en escritorio con ingredientes fijos; en móvil, datos en tres columnas y acciones en rejilla.
- Diálogos como hoja inferior en móvil; planificador con tira de días fija, huecos vacíos compactos y fechas cortas en «Mover».
- Compra en varias columnas por pasillo en escritorio; las tiendas de origen se resumen como «primera +N».
- Las fechas y los importes siguen el idioma elegido (español o inglés).
- Más contraste en las estrellas de valoración (vacías y llenas, en claro y oscuro).
- El botón flotante «Nueva» se reduce al desplazarse.

### Añadido
- Coste estimado total en la cabecera de la lista de la compra (si la lista muestra precios).
- Apartados «Precios y compra» (aclara que los precios son estimados y que la lista no se envía a ninguna tienda) y «Copias y exportación».
- Textos nuevos traducidos al español y al inglés.

### Pruebas
- La prueba de humo de maquetación recorre también Importar y todas las subrutas de Ajustes a 360, 390 y 1440 px, en claro y oscuro.
- Nuevas pruebas: sin definiciones CSS de maquetación contradictorias para el mismo selector, índice de Ajustes en móvil y dos columnas en escritorio, ajustes de apariencia funcionando, diálogos cerrados al navegar, fechas según el idioma.
- Demo de la landing y capturas móviles regeneradas con la interfaz nueva.

## [2.1.5] — 2026-10-30 — Corrección urgente: caché y planificador en móvil

### Corregido
- **Planificador roto en móvil (causa real):** en v2.1.4 la regla `.hero{flex-wrap:nowrap}` pensada para la cabecera de Recetas se aplicaba a todas las cabeceras, y `.hero-actions{flex:0 0 auto}` impedía encogerse. En 360–390 px los botones de semana y «Añadir a la lista» se montaban sobre el título «Planificador» y lo partían en una columna de palabras. Ahora el comportamiento sin salto de línea es solo para Recetas (`.hero-rec`) y en las demás cabeceras las acciones bajan a su propia fila en móvil.
- **Planificador con datos reales:** un título o nota sin espacios muy largo ensanchaba la rejilla de la semana (`1fr` = `minmax(auto,1fr)`) y provocaba desplazamiento horizontal. Las columnas usan `minmax(0,1fr)` y el texto se parte donde haga falta.
- **Iconos y estilos antiguos tras actualizar:** `/assets` se servía sin `Cache-Control` y con URLs sin versión, así que el navegador del móvil podía reutilizar por heurística el JS/CSS de v2.1.3 con el HTML de v2.1.4. Ahora `index.html` enlaza cada recurso como `?v=<versión>-<hash del contenido>` (calculado al arrancar), esas URLs se sirven con `public, max-age=31536000, immutable` y cualquier otra petición a `/assets` lleva `no-cache` (revalidación con ETag/Last-Modified). No hay service worker.

### Pruebas
- Cada recurso de `index.html` existe en `git archive HEAD` (no solo en la copia de trabajo) y responde 200; las URLs versionadas cambian con el contenido; cabeceras de caché correctas; todos los iconos usados existen en `icons.js`.
- Prueba de humo en navegador con los datos reales de `data/seed/recetas.json` más casos límite (título enorme, palabra larguísima, 100 raciones, sin raciones/etiquetas/pasos/precio, semana vacía, plan con receta borrada): las 4 vistas de Recetas, detalle, planificador, compra y ajustes a 360, 390 y 1440 px, claro y oscuro, densidad cómoda y compacta. Falla con errores de consola, peticiones propias fallidas, desbordamiento horizontal, cabecera solapada o días del planificador solapados o de tamaño cero.

## [2.1.4] — 2026-10-30 — Más aire en móvil

### Cambiado
- Escala de espaciado de 8 px (variables CSS): márgenes laterales de 20 px en móvil y 32–48 px en escritorio, contenido centrado a ~1200 px, más separación entre secciones y dentro de las tarjetas.
- Texto base de 16 px con interlineado 1,5 y jerarquía de títulos más clara.
- Cabecera de Recetas agrupada: «Nueva receta», «Seleccionar» y «Exportar» en un menú «Más acciones», con botón flotante «Nueva» en móvil; estado, favoritas y etiquetas dentro del panel de Filtros, con contador de filtros activos. La primera receta sube de 491 px a 325 px en 360×800.
- Cuadrícula: el selector de vista sigue en la fila del recuento y el control «Columnas» está en el menú «Más acciones» (sin fila extra); en móvil 2–3 columnas (2 por defecto) y el número siempre coincide con lo que se ve; títulos en hasta 2 líneas.
- Estrella de favorita con el color de acento en todas las vistas.
- Botón de vista activo con fondo de acento (contraste ≥ 3:1 en claro y oscuro).
- Áreas táctiles de al menos 44 px.
- Subtítulo de Recetas en una sola línea, sin repetir el recuento; «pendientes de transcribir» solo si hay alguna.
- El botón flotante ya no tapa la última tarjeta (margen inferior con zona segura) y se oculta al bajar y reaparece al subir (sin animación con «reducir movimiento»).
- Superficies por elevación en ambos temas: en oscuro fondo #121010, tarjetas #24201D, paneles y hojas (Filtros, «Más acciones», diálogos) #36312D y controles un nivel por encima (≥ 7 puntos de luminosidad OKLCH entre niveles), borde de 1 px rgba(255,255,255,.08) y separadores al 6 %; en claro, tarjetas blancas sobre fondo crema con borde sutil y sombra suave. Texto ≥ 4,5:1 y controles ≥ 3:1 en todas las superficies.
- Cuadrícula en móvil: tiempo y precio por ración en hasta 2 líneas, sin cortar el precio.

### Añadido
- Ajustes → Apariencia → Densidad: «Cómoda» (por defecto) o «Compacta»; se recuerda por dispositivo y se guarda en `/api/preferencias/lista` (`interfaz`).
- Tests a 360 px: cabecera sin desbordes, áreas táctiles ≥ 44 px, columnas = control, títulos en 2 líneas, color de la estrella, contraste del botón activo, panel de filtros y densidad.

## [2.1.3] — 2026-10-30 — Selector de vistas

### Cambiado
- Vistas en orden «Una sola», «Lista compacta», «Lista con miniatura», «Cuadrícula», con iconos propios que corresponden a lo que muestran.
- «Una sola» más fina: portada más baja (16:7 en móvil), menos relleno y texto más pequeño.
- La vista se recuerda por dispositivo (localStorage) y prevalece sobre la preferencia del servidor.
- Valores antiguos `info` y `detalle` se migran a `miniatura` (API y navegador).

### Añadido
- Ajustes → Apariencia: en las listas, miniatura del vídeo/portada (por defecto) o icono genérico. En `/api/preferencias/lista` (`miniaturas`) y MCP (`get_list_preferences`, `set_list_preferences`).
- Botones del selector con `aria-pressed`, `aria-label` y tooltip (ES/EN), flechas del teclado y área táctil ≥ 40 px.
- Tests de navegador a 360 px y test de fotos de ejemplo únicas y acreditadas.

### Corregido
- Capturas: cada receta de ejemplo usa su propia foto CC0 (antes se repetía la pasta).

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
