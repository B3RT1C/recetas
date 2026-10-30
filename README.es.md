<p align="center"><a href="README.md">English</a> | <b>Español</b></p>

<p align="center"><img src="docs/brand/logo.svg" width="96" alt="Recetario C logo"></p>
<h1 align="center">Recetario C</h1>
<p align="center"><b>Tus recetas guardadas de Instagram convertidas en un recetario autoalojado y local-first.</b></p>
<p align="center">
  <img alt="version" src="https://img.shields.io/badge/version-v2.1.2-c2410c">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="tests" src="https://img.shields.io/badge/tests-169%20passing-2ea44f">
  <img alt="license" src="https://img.shields.io/badge/licencia-pendiente-lightgrey">
  <img alt="self-hosted" src="https://img.shields.io/badge/autoalojado-6d28d9">
  <img alt="local-first" src="https://img.shields.io/badge/local--first-0e7490">
</p>
<p align="center"><img alt="tech" src="https://skillicons.dev/icons?i=python,fastapi,sqlite,js,html,css,cloudflare,windows,git,github"></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/lista-cuadricula-dark-desktop.png">
    <img alt="Cuadrícula de recetas" src="docs/screenshots/lista-cuadricula-light-desktop.png" width="900">
  </picture>
</p>

## ✨ Funciones

- 📥 **Importador de Instagram** – asistente de 5 pasos: colección guardada, publicaciones, revisión de borradores (sin duplicados).
- 🔎 **Recetas** – búsqueda tolerante a erratas, filtros, etiquetas/alérgenos, cinco vistas de lista con portada elegida.
- 🍳 **Modo cocina** – escalado de raciones, temporizadores por paso, pantalla completa con Wake Lock, imprimir/PDF.
- 🗓️ **Planificador** – semana por días y comidas, enviar a la compra en un clic.
- 🛒 **Compra y despensa** – varias listas, pasillos, conversión de unidades, recurrentes, precios *estimados*.
- 🤖 **Tu propia IA** – OpenAI, OpenRouter, Ollama, LM Studio…; clave cifrada.
- 🔌 **Acceso para agentes** – API REST con token y servidor MCP (HTTP + stdio).
- 📦 **Exportar** – JSON, HTML, Markdown, JSON compatible v1, ZIP con medios.
- 🌍 Interfaz ES/EN, tema claro y oscuro, adaptada a móvil.
- 🧭 *En la hoja de ruta:* pasos en paralelo, edición pública local-first, estadísticas de precios (ver abajo).

## 📸 Galería

<table>
<tr><td align="center"><img src="docs/screenshots/lista-cuadricula-dark-desktop.png" width="260" alt="Cuadrícula (oscuro)"><br><sub>Cuadrícula (oscuro)</sub></td><td align="center"><img src="docs/screenshots/detalle-light-desktop.png" width="260" alt="Detalle"><br><sub>Detalle</sub></td><td align="center"><img src="docs/screenshots/planificador-dark-desktop.png" width="260" alt="Planificador (oscuro)"><br><sub>Planificador (oscuro)</sub></td></tr>
<tr><td align="center"><img src="docs/screenshots/compra-light-mobile.png" width="160" alt="Lista de la compra"><br><sub>Lista de la compra</sub></td><td align="center"><img src="docs/screenshots/detalle-dark-mobile.png" width="160" alt="Detalle (móvil, oscuro)"><br><sub>Detalle (móvil, oscuro)</sub></td><td align="center"><img src="docs/screenshots/importar-light-mobile.png" width="160" alt="Importar"><br><sub>Importar</sub></td></tr>
</table>

<sub>Solo datos de demostración con fotos CC0. Más en <a href="docs/screenshots/">docs/screenshots/</a>.</sub>

## 🏗️ Arquitectura

```mermaid
flowchart LR
  IG[("Instagram<br/>saved collections")] --> IMP
  subgraph IMP["Importer"]
    direction TB
    IL["Instaloader"] --> FF["ffmpeg<br/>(covers, frames)"]
    YT["yt-dlp (planned)"] -.-> FF
    FF --> AI["OpenAI-compatible AI / caption parser<br/>(Whisper planned)"]
  end
  IMP --> API["FastAPI"]
  API --> DB[("SQLite")]
  API --> MED[("media/ · videos/")]
  UI["Web UI<br/>(HTML/CSS/JS, ES/EN)"] <--> API
  AG["AI agents"] <-->|"REST /api/v1 · MCP /mcp + stdio"| API
```

## 🚀 Arranque rápido

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                                  # http://localhost:8088 – el primer arranque crea el administrador
python run.py --mock-instagram                 # prueba el importador sin Instagram
```

Variables de entorno, primer administrador, agentes/MCP y seguridad: **[docs/CONFIG.md](docs/CONFIG.md)** · Despliegue en el mini PC con Windows: **[DEPLOY.md](DEPLOY.md)**.

## 🗺️ Hoja de ruta

- [x] v2.1.2 – portadas y cuadrícula
- [x] Landing bilingüe
- [ ] v2.2 – pasos en paralelo (DAG con `depends_on`)
- [ ] Fase 4 – versión pública local-first (SQLite WASM/OPFS, BYOK, exportar/importar, transferencia en LAN)
- [ ] Fase 3 – precios: «ahora más baratas», existencias de despensa, estadísticas
- [ ] Más fuentes (TikTok, YouTube, Pinterest, web), yt-dlp y transcripción con Whisper

Plan completo: [docs/ROADMAP.md](docs/ROADMAP.md) · Cambios: [CHANGELOG.md](CHANGELOG.md)

## 📄 Licencia

Pendiente: AGPL-3.0 o MIT. Hasta elegirla, todos los derechos reservados.

## 👤 Autor

[GitHub @B3RT1C](https://github.com/B3RT1C) · [LinkedIn](https://www.linkedin.com/in/albertopn)
