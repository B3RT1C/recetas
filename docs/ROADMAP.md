# Hoja de ruta

Estado: la **Fase 2** está cerrada (v2.1.0, correcciones en v2.1.1) y la **landing** está hecha. Lo de abajo es especificación, **no está implementado**, salvo donde se indique.

## Backlog sin fase

### Galería
Vista alternativa del recetario en cuadrícula de portadas (foto o fotograma del vídeo), estilo perfil de Instagram,
con reproducción del vídeo local al abrir, filtros actuales reutilizados y navegación con teclado.
**Estimación:** 1–1,5 días (componente de cuadrícula + carga diferida de portadas + tests de accesibilidad y capturas).
No requiere cambios de esquema.

## v2.1.6 — Runner y Ajustes (antes previsto para v2.1.5)
El trabajo planificado del runner y de Ajustes pasa a v2.1.6: v2.1.5 se dedicó a una corrección urgente.

## v2.1.5 — Corrección urgente (hecho)
Caché de recursos versionada y planificador roto en móvil; ver CHANGELOG.

## v2.1.3 — Selector de vistas

Hecho: «una sola» más compacta; iconos y orden corregidos (una · compacta · miniatura · cuadrícula); vista recordada por dispositivo; ajuste de miniatura/icono en listas (API y MCP); comprobación a 360 px.

Pendiente:
- (a) Una foto CC0 distinta por receta de ejemplo. **Hecho**: las 12 recetas ya tenían foto propia; el duplicado (pasta) venía del emparejamiento por título del script de capturas, ahora usa la foto de cada receta. Test `test_sample_covers` impide duplicados y exige crédito en `ATTRIBUTION.md`. Si se añaden recetas, descargar más fotos de Wikimedia Commons y acreditarlas.
- (b) *Opcional.* Tira de ~6 fotogramas automáticos para elegir portada; elección automática que descarte negros o borrosos (varianza del laplaciano) y penalice texto superpuesto.
- (c) *Opcional.* Tarea única y limitada en ritmo con `yt-dlp --write-thumbnail --skip-download` sobre las URL guardadas: primero **sin cookies**; con cookies solo con aprobación expresa del usuario. Nunca sobrescribe portadas manuales.

## v2.1.2 — Portadas y cuadrícula (hecho)

1. **Cuadrícula**: el hueco bajo el título se rellena con una línea de metadatos pequeña (tiempo · €/ración); si no hay datos,
   la tarjeta ajusta su altura al título.
2. **Portadas con datos reales**
   - Por defecto, la miniatura original del post/reel si la fuente la ofrece; si no, un fotograma de ffmpeg hacia el segundo 1,
     saltando fotogramas negros.
   - `object-fit: cover`; los reels 9:16 se recortan centrados o se muestran sobre un fondo desenfocado.
3. **Selector de portada** en el editor de la receta:
   - miniatura original (por defecto);
   - fotograma del vídeo elegido con un deslizador;
   - foto propia subida;
   - foto genérica de la biblioteca libre CC0.

   Valor por defecto global en **Ajustes** (original, fotograma o genérica). Se guarda `cover_source` por receta y una
   portada elegida a mano **nunca** se sobrescribe al reimportar.

## v2.2 — Pasos en paralelo

- Cada paso tiene `depends_on[]` (ids de pasos anteriores): los pasos forman un **grafo acíclico (DAG)**. Sin dependencias
  explícitas, la receta es una **cadena lineal** (cada paso depende del anterior), como ahora.
- **Dos vistas**: lista ordenada (por defecto, orden topológico estable) y **árbol/grafo** para el trabajo en paralelo,
  p. ej. «cuece la pasta» ∥ «haz la salsa» → «mezcla».
- La **IA infiere** las dependencias al importar o transcribir; se **editan a mano** en el editor (casillas «después de…»),
  con validación de ciclos.
- Ideas: resaltar la **ruta crítica** y el **tiempo total estimado** (suma por la ruta más larga, no de todos los pasos);
  **modo cocina** paso a paso con **temporizadores por rama**.
- **Migración**: los pasos existentes pasan a cadena lineal (`depends_on = [paso anterior]`); nada cambia para el usuario.
- **API y MCP**: `depends_on` en lectura/escritura de recetas (`GET/PUT /api/v1/recipes/{id}`), validación de DAG en el servidor
  y herramienta MCP `recipe_step_graph` (orden, ramas, ruta crítica y tiempo total).
- **Estimación aproximada:** 5–7 días (modelo + migración 1; validación, ruta crítica y API/MCP 1; inferencia con IA 1–1,5;
  editor 1–1,5; vista de grafo accesible 1–1,5; modo cocina por ramas 1).

## Landing — aprobada y hecha

Página de presentación estática bilingüe en `landing/` (ES en `/`, EN en `/en/`), lista para Cloudflare Pages sin paso de
compilación. Ver `landing/README.md`.

## Fase 4 — Versión pública *local-first* (aprobada, en este orden)

| Paso | Contenido | Estimación |
|---|---|---|
| **L0** | Capa de datos abstracta: un único frontend y compilaciones para pública, local y app. | 3 días |
| **L1** | SQLite WASM sobre OPFS con el mismo esquema y migraciones; alternativa IndexedDB. | 4 días |
| **L2** | BYOK: clave cifrada en local con frase de paso; Ollama/LM Studio en localhost (documentar `OLLAMA_ORIGINS`); WebLLM más adelante. | 3 días |
| **L3** | Importar pegando texto o subiendo un vídeo; proxy opcional en un Worker con lista de dominios permitidos y límite de peticiones. | 2 días |
| **L4** | Banner persistente «Descarga la versión local» (descartable por sesión); guías de instalación para Windows y Docker (Dockerfile y compose); hueco para la app. | 2 días |
| **L5** | Exportar/importar en un clic con el formato v2; duplicados por `source_url` o, si no, por título + ingredientes normalizados; vista previa y nada de sobrescrituras silenciosas. | 3 días |
| **L6** | Transferencia directa: `fetch` a localhost (CORS + cabecera Private Network Access) y, en la LAN, `window.open` de `http://IP:8088/importar` con `postMessage` y código de emparejamiento de 6 dígitos; alternativa con fichero. | 3 días |
| **L7** | Registro central `features.json` (función → pública/local/app), una insignia reutilizable «Local» con candado y un aviso («Disponible en la versión local / app» con *Descargar* y *Exportar mis datos*). Contador opcional, solo local, de clics en funciones bloqueadas; sin telemetría. | 2 días |

### Extras

| Paso | Contenido | Estimación |
|---|---|---|
| **L8** | Copias de seguridad: recordatorio configurable cada N días para exportar, `navigator.storage.persist()` y escritura automática en un fichero o carpeta elegidos con la File System Access API cuando el navegador la admita. | 2 días |
| **L9** | Recetas de ejemplo 100 % funcionales (planificador, compra, precios, estadísticas) con las fotos CC0; marca `is_sample`; «Quitar recetas de ejemplo» y restaurar en un clic desde Ajustes; fuera de las estadísticas reales salvo que el usuario las use; la exportación pregunta si incluirlas. | 2 días |
| **L10** | Recorrido inicial breve y omitible (3–4 pasos) y enlace `?demo=1` desde la landing que abre la versión pública con el recorrido. | 1 día |

**Total aproximado:** 27 días (L0–L7: 22; extras: 5).

### Riesgos

- **OPFS y Safari**: soporte y cuotas desiguales (sobre todo en iOS y en ventanas privadas); hace falta la alternativa
  IndexedDB y probar en Safari real antes de dar L1 por cerrado.
- **Private Network Access**: Chrome está cambiando cómo se permiten las peticiones de una web pública a localhost/LAN
  (preflight, permisos); L6 debe tener siempre la alternativa con fichero y revisarse con cada versión de Chrome.
- **XSS y la clave BYOK**: cualquier XSS en la versión pública podría leer la clave descifrada en memoria. Mitigar con CSP
  estricta sin `unsafe-inline`, sin HTML de terceros sin sanear, descifrado solo en el momento de usarla y opción de no
  recordarla.

## Fase 3 — Precios

Todo lo de esta fase se expone también en la **API v1** y en el servidor **MCP** (lectura con token `read`,
acciones con `write`).

### 1. «Ahora más baratas»
- Coste por receta calculado a partir del **historial de precios** de sus ingredientes, comparado con la **media
  de los últimos 30 días**.
- Si el coste actual está por debajo de esa media más que un **umbral configurable (por defecto 15 %)**, la receta
  aparece en una sección de la portada con el porcentaje y los ingredientes que han bajado.
- Insignia tipo **«-18 %»** en la tarjeta y en el detalle siempre que el coste esté por debajo de la media de 30 días.
- Ordenar y filtrar por mayor bajada.
- **Ajustes**: interruptor que oculta la sección y las insignias; umbral; notificaciones push opcionales (cuando
  exista la PWA).
- API v1 / MCP: `GET /api/v1/recipes/cheaper?umbral=` y herramienta `cheaper_recipes`.

### 2. Despensa con existencias (amplía el modelo `pantry` actual)
- Cantidades y fechas de caducidad por artículo.
- Cocinar una receta descuenta sus ingredientes de la despensa.
- Las recetas muestran **«Lo tienes todo»** o **«Te faltan X»**; lo que falta se envía a la lista de la compra.
- Filtro **«Puedo cocinar ya»**.

### 3. Sección «Estadísticas» (nueva entrada de navegación)
- Selector: gráfica de precio de un **plato** (total y por ración) o de un **ingrediente**, a lo largo del tiempo,
  con marcas de **cuándo se cocinó** y **cuándo se compró**.
- Gráfica SVG en línea, ligera, sin CDN, con tema claro/oscuro.
- Panel general en la misma sección: gasto mensual **estimado vs. real**, recetas más cocinadas, ingredientes más caros.
- En el detalle de la receta, como mucho un enlace **«Ver en estadísticas»** (las gráficas no van dentro de la receta).
- Registro de cocinado: botón **«La he hecho»** (fecha, raciones, nota y valoración opcionales).
- Registro de compras: **«Marcar como comprado»** desde la lista de la compra con fecha, precio real opcional y tienda
  opcional (la tienda solo si el usuario la escribe). Alimenta también la despensa.

### Cambios de esquema necesarios
| Tabla / columna | Para qué | Estado |
|---|---|---|
| `price_history` (ingrediente, súper, fuente, precio por kg/l/ud, fecha) | medias de 30 días, gráficas | **Creada en v2.1.0** (migración 2, solo añade filas cuando cambia el precio). Falta guardar el coste por receta si se quiere precalcular. |
| `cook_log` (receta, fecha, raciones, nota, valoración) | «La he hecho», descuento de despensa, marcas en gráficas, más cocinadas | pendiente |
| `purchase_log` (artículo/ingrediente, fecha, cantidad, unidad, precio real opcional, tienda opcional, lista de origen) | marcas de compra, gasto real, alta en despensa | pendiente |
| `pantry`: columnas `quantity`, `unit`, `expires_on` | despensa con existencias | pendiente (añadir columnas, migración trivial) |
| `settings`: `cheaper_enabled`, `cheaper_threshold`, `push_enabled` | Ajustes de «Ahora más baratas» | pendiente (tabla `settings` ya existe) |

Hoy los precios son **estimados**; mientras no haya un proveedor real, el historial se llenará poco y las bajadas
serán raras: conviene implementar primero el registro de compras con precio real.
