# Hoja de ruta

Estado: la **Fase 2** (v2.1.0) está cerrada. Lo de abajo es especificación, **no está implementado**.

## Backlog sin fase

### Galería
Vista alternativa del recetario en cuadrícula de portadas (foto o fotograma del vídeo), estilo perfil de Instagram,
con reproducción del vídeo local al abrir, filtros actuales reutilizados y navegación con teclado.
**Estimación:** 1–1,5 días (componente de cuadrícula + carga diferida de portadas + tests de accesibilidad y capturas).
No requiere cambios de esquema.

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
