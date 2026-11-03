/* UI strings. ES (Spain) default, EN available. Recipe content itself is not translated here
   (use "Traducir con IA" for that). Add a language by adding a dictionary. */
window.I18N = {
  es: {
    nav_recetas: "Recetas", nav_plan: "Planificador", nav_compra: "Compra", nav_importar: "Importar", nav_ajustes: "Ajustes",
    search_ph: "Busca por plato, ingrediente o autor…", all: "Todas", complete: "Completas", pending: "Pendientes",
    favorites: "Favoritas", sort: "Ordenar", sort_original: "Orden original", sort_fast: "Más rápidas", sort_cheap: "Más baratas",
    sort_az: "A–Z", sort_recent: "Recientes", sort_rating: "Mejor valoradas", time: "Tiempo", price: "Precio/ración",
    any: "Cualquiera", tags: "Etiquetas", clear: "Limpiar filtros", results: n => `${n} receta${n === 1 ? "" : "s"}`,
    empty_title: "No hay recetas con esos filtros", empty_body: "Prueba con otra palabra o quita algún filtro.",
    new_recipe: "Nueva receta", new_short: "Nueva", columns: "Columnas", more_actions: "Más acciones", density: "Densidad", density_comfy: "Cómoda", density_compact: "Compacta", density_note: "Cómoda deja más aire; compacta muestra más recetas a la vez.", export: "Exportar", select: "Seleccionar", selected: n => `${n} seleccionada${n === 1 ? "" : "s"}`,
    est: "estimado", servings: "raciones", ingredients: "Ingredientes", steps: "Pasos", notes: "Notas",
    pending_banner: "Pendiente de transcribir: de momento solo está el vídeo.", transcribe: "Transcribir a mano",
    edit: "Editar", delete: "Eliminar", print: "Imprimir / PDF", cook_mode: "Modo cocina", translate: "Traducir con IA",
    back: "Volver", save: "Guardar", cancel: "Cancelar", close: "Cerrar", theme: "Cambiar tema", language: "Idioma",
    soon: "Próximamente", about: "Acerca de este proyecto", appearance: "Apariencia", view_group: "Vista de la lista", view_una: "Una sola: una receta grande por fila", view_compacta: "Lista compacta: solo texto", view_miniatura: "Lista con miniatura", view_cuadricula: "Cuadrícula de portadas", view_una_s: "Una sola", view_compacta_s: "Compacta", view_miniatura_s: "Con miniatura", view_cuadricula_s: "Cuadrícula",
  },
  en: {
    nav_recetas: "Recipes", nav_plan: "Planner", nav_compra: "Shopping", nav_importar: "Import", nav_ajustes: "Settings",
    search_ph: "Search dish, ingredient or author…", all: "All", complete: "Complete", pending: "Pending",
    favorites: "Favourites", sort: "Sort", sort_original: "Original order", sort_fast: "Fastest", sort_cheap: "Cheapest",
    sort_az: "A–Z", sort_recent: "Newest", sort_rating: "Top rated", time: "Time", price: "Price/serving",
    any: "Any", tags: "Tags", clear: "Clear filters", results: n => `${n} recipe${n === 1 ? "" : "s"}`,
    empty_title: "No recipes match", empty_body: "Try another word or remove a filter.",
    new_recipe: "New recipe", new_short: "New", columns: "Columns", more_actions: "More actions", density: "Density", density_comfy: "Comfortable", density_compact: "Compact", density_note: "Comfortable has more breathing room; compact fits more recipes on screen.", export: "Export", select: "Select", selected: n => `${n} selected`,
    est: "estimate", servings: "servings", ingredients: "Ingredients", steps: "Steps", notes: "Notes",
    pending_banner: "Waiting for transcription: only the video for now.", transcribe: "Transcribe manually",
    edit: "Edit", delete: "Delete", print: "Print / PDF", cook_mode: "Cook mode", translate: "Translate with AI",
    back: "Back", save: "Save", cancel: "Cancel", close: "Close", theme: "Toggle theme", language: "Language",
    soon: "Coming soon", about: "About this project", appearance: "Appearance", view_group: "List view", view_una: "Single: one large recipe per row", view_compacta: "Compact list: text only", view_miniatura: "List with thumbnail", view_cuadricula: "Cover grid", view_una_s: "Single", view_compacta_s: "Compact", view_miniatura_s: "Thumbnails", view_cuadricula_s: "Grid",
  },
};
/* v2.1.6 strings */
Object.assign(I18N.es, {
  favorite: "Favorita", by_author: a => `de ${a}`, added_on: d => `añadida el ${d}`, your_rating: "Tu valoración", rating: "Valoración", n_stars: n => `${n} estrellas`,
  total_time: "tiempo total", per_serving: "por ración", total: "total", allergens: "Alérgenos (orientativo)", add_to_list: "Añadir a la lista", plan_it: "Planificar",
  suggested_steps: "Pasos sugeridos (no aparecen en el vídeo).", fewer_servings: "Menos raciones", more_servings: "Más raciones", not_in_video: "El vídeo no lo dice",
  prices_estimated: "Precios estimados: solo orientativos.", cooked_it: "Lo he cocinado", no_logs: "Aún no hay registros.", date: "Fecha", notes_optional: "Notas (opcional)",
  cook_notes_ph: "¿Qué cambiarías la próxima vez?", add: "Añadir",
});
Object.assign(I18N.en, {
  favorite: "Favourite", by_author: a => `by ${a}`, added_on: d => `added ${d}`, your_rating: "Your rating", rating: "Rating", n_stars: n => `${n} stars`,
  total_time: "total time", per_serving: "per serving", total: "total", allergens: "Allergens (approximate)", add_to_list: "Add to list", plan_it: "Plan",
  suggested_steps: "Suggested steps (not shown in the video).", fewer_servings: "Fewer servings", more_servings: "More servings", not_in_video: "Not stated in the video",
  prices_estimated: "Estimated prices: for guidance only.", cooked_it: "I cooked it", no_logs: "No entries yet.", date: "Date", notes_optional: "Notes (optional)",
  cook_notes_ph: "What would you change next time?", add: "Add",
});
window.LANG = localStorage.getItem("lang") || "es";
window.t = (k, ...a) => { const v = (I18N[LANG] || I18N.es)[k] ?? I18N.es[k] ?? k; return typeof v === "function" ? v(...a) : v; };
document.documentElement.lang = LANG;
