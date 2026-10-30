"""Export recipes as JSON / legacy JSON / Markdown / printable HTML, optionally zipped with media."""
from __future__ import annotations
from .source_link import LABELS, with_source
from ..db import shortcode_of

import html
import io
import json
import zipfile
from datetime import date

from .recipes import RecipeService

PRIVATE_KEYS = ("caption_original",)


def _eur(v) -> str:
    return "—" if v is None else f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _qty(i: dict) -> str:
    return ("~" if i.get("estimada") else "") + (i.get("cantidad_normal") or "")


def _src_label(r: dict) -> str:
    return LABELS.get(r.get("source_type") or "web", "Web")


def _clean(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in PRIVATE_KEYS}


def to_markdown(recipes: list[dict], media_prefix: str = "") -> str:
    out = [f"# Recetario C\n\n_Exportado el {date.today():%d/%m/%Y} · {len(recipes)} recetas. "
           "Los precios son **estimados** (supermercado en España, solo la cantidad usada)._\n"]
    for r in recipes:
        out.append(f"\n## {r['titulo']}\n")
        meta = [r.get("autor") or ""]
        if r.get("tiempo_total_min"):
            meta.append(f"⏱ {r['tiempo_total_min']} min")
        if r.get("raciones"):
            meta.append(f"👥 {r['raciones']} raciones" + (" (est.)" if r.get("raciones_estimadas") else ""))
        if r.get("precio_racion_eur") is not None:
            meta.append(f"💶 {_eur(r['precio_racion_eur'])}/ración (estimado)")
        out.append(" · ".join(m for m in meta if m) + "\n")
        if r.get("source_url"):
            out.append(f"\n[Ver original ({_src_label(r)})]({r['source_url']})\n")
        media = r.get("media") or {}
        if media_prefix and media.get("foto"):
            out.append(f"\n![{r['titulo']}]({media_prefix}{media['foto'].lstrip('/')})\n")
        if media_prefix and media.get("video"):
            out.append(f"\n[Vídeo local]({media_prefix}{media['video'].lstrip('/')})\n")
        if r.get("ingredientes"):
            out.append("\n### Ingredientes\n")
            out += [f"- {_qty(i)} {i['nombre']}".replace("-  ", "- ") + "\n" for i in r["ingredientes"]]
        if r.get("pasos"):
            out.append("\n### Pasos\n")
            out += [f"{n}. {p['texto']}" + (f" _({p['minutos']} min)_" if p.get("minutos") else "") + "\n"
                    for n, p in enumerate(r["pasos"], 1)]
        if r.get("notas") or r.get("nota"):
            out.append(f"\n> {r.get('notas') or r.get('nota')}\n")
    return "".join(out)


def to_html(recipes: list[dict], media_prefix: str = "") -> str:
    e = html.escape
    cards = []
    for r in recipes:
        media = r.get("media") or {}
        foto = f'<img src="{e(media_prefix + media["foto"].lstrip("/"))}" alt="">' if media_prefix and media.get("foto") else ""
        meta = " · ".join(x for x in [
            e(r.get("autor") or ""),
            f"⏱ {r['tiempo_total_min']} min" if r.get("tiempo_total_min") else "",
            f"👥 {r['raciones']} raciones" if r.get("raciones") else "",
            f"💶 {_eur(r.get('precio_racion_eur'))}/ración <small>(estimado)</small>" if r.get("precio_racion_eur") is not None else "",
        ] if x)
        ings = "".join(f"<tr><td>{e(_qty(i))}</td><td>{e(i['nombre'])}</td><td class=r>{_eur(i.get('precio_eur'))}</td></tr>"
                       for i in r.get("ingredientes", []))
        steps = "".join(
            "<li>" + e(p["texto"]) + (" <small>· %s min</small>" % p["minutos"] if p.get("minutos") else "") + "</li>"
            for p in r.get("pasos", []))
        link = ('<p><a href="%s" target="_blank" rel="noopener noreferrer">Ver original (%s)</a></p>'
                % (e(r["source_url"]), e(_src_label(r)))) if r.get("source_url") else ""
        ing_html = ("<h3>Ingredientes</h3><table><thead><tr><th>Cantidad</th><th>Ingrediente</th>"
                    "<th class=r>Precio est.</th></tr></thead><tbody>" + ings + "</tbody></table>") if ings else ""
        step_html = "<h3>Pasos</h3><ol>" + steps + "</ol>" if steps else ""
        note = r.get("notas") or r.get("nota") or ""
        note_html = "<p class=note>" + e(note) + "</p>" if note else ""
        cards.append(f"<article>{foto}<h2>{e(r['titulo'])}</h2><p class=meta>{meta}</p>{link}{ing_html}{step_html}{note_html}</article>")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recetario C — exportación</title><style>
body{{font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#1f1a17;max-width:820px;margin:2rem auto;padding:0 1rem}}
header{{border-bottom:3px solid #e8590c;margin-bottom:1rem}}h1{{margin:.2rem 0}}h2{{margin:.2rem 0;color:#c2410c}}
article{{break-inside:avoid;page-break-inside:avoid;border:1px solid #eadfd6;border-radius:14px;padding:1rem 1.2rem;margin:1rem 0}}
article img{{max-width:220px;border-radius:10px;float:right;margin:0 0 .5rem 1rem}}
.meta{{color:#6b5e55;margin:0}}table{{border-collapse:collapse;width:100%}}td,th{{padding:.25rem .4rem;border-bottom:1px solid #f0e6de;text-align:left}}
.r{{text-align:right}}.note{{background:#fff7ed;padding:.5rem .8rem;border-radius:8px}}small{{color:#6b5e55}}
@media print{{body{{margin:0}}article{{border:none;border-bottom:1px solid #ccc;border-radius:0}}a{{color:inherit}}}}
</style></head><body><header><h1>🍳 Recetario C</h1><p>Exportado el {date.today():%d/%m/%Y} · {len(recipes)} recetas ·
<small>Precios estimados (supermercado en España, solo la cantidad usada).</small></p></header>
{''.join(cards)}</body></html>"""


def build_export(svc: RecipeService, recipes: list[dict], formato: str, con_media: bool) -> tuple[bytes, str, str]:
    """Returns (content, media_type, filename)."""
    stamp = f"{date.today():%Y%m%d}"
    prefix = "" if not con_media else "./"
    if formato == "json":
        body = json.dumps({"formato": "recetas-web-v2", "exportado": stamp, "recetas": [_clean(r) for r in recipes]},
                          ensure_ascii=False, indent=1).encode()
        name, mime = "recetas.json", "application/json"
    elif formato == "json_legacy":
        doc = svc.legacy_document({r["id"] for r in recipes})
        for item in doc.get("recetas", []) + doc.get("solo_video", []):
            with_source(item, shortcode_of(item.get("video_url")))
        body = json.dumps(doc, ensure_ascii=False, indent=1).encode()
        name, mime = "recetas.json", "application/json"
    elif formato == "markdown":
        body, name, mime = to_markdown(recipes, prefix).encode(), "recetas.md", "text/markdown; charset=utf-8"
    else:
        body, name, mime = to_html(recipes, prefix).encode(), "recetas.html", "text/html; charset=utf-8"
    if not con_media:
        return body, mime, f"recetas-{stamp}.{name.rsplit('.', 1)[1]}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, body)
        seen = set()
        for r in recipes:
            for path, arc in svc.local_files(r):
                if arc not in seen:
                    seen.add(arc)
                    z.write(path, arc, compress_type=zipfile.ZIP_STORED)  # media is already compressed
    return buf.getvalue(), "application/zip", f"recetas-{stamp}.zip"
