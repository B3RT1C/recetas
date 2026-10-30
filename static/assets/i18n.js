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
    new_recipe: "Nueva receta", export: "Exportar", select: "Seleccionar", selected: n => `${n} seleccionada${n === 1 ? "" : "s"}`,
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
    new_recipe: "New recipe", export: "Export", select: "Select", selected: n => `${n} selected`,
    est: "estimate", servings: "servings", ingredients: "Ingredients", steps: "Steps", notes: "Notes",
    pending_banner: "Waiting for transcription: only the video for now.", transcribe: "Transcribe manually",
    edit: "Edit", delete: "Delete", print: "Print / PDF", cook_mode: "Cook mode", translate: "Translate with AI",
    back: "Back", save: "Save", cancel: "Cancel", close: "Close", theme: "Toggle theme", language: "Language",
    soon: "Coming soon", about: "About this project", appearance: "Appearance", view_group: "List view", view_una: "Single: one large recipe per row", view_compacta: "Compact list: text only", view_miniatura: "List with thumbnail", view_cuadricula: "Cover grid", view_una_s: "Single", view_compacta_s: "Compact", view_miniatura_s: "Thumbnails", view_cuadricula_s: "Grid",
  },
};
window.LANG = localStorage.getItem("lang") || "es";
window.t = (k, ...a) => { const v = (I18N[LANG] || I18N.es)[k] ?? I18N.es[k] ?? k; return typeof v === "function" ? v(...a) : v; };
document.documentElement.lang = LANG;
