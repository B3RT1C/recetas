#!/usr/bin/env python3
"""Fail if landing/ references any external URL outside the allowlist, or a local file that doesn't exist."""
import json, re, sys
from pathlib import Path
from urllib.parse import urlparse

L = Path(__file__).resolve().parent.parent / "landing"
cfg = json.loads((L / "site.config.json").read_text())
ALLOWED = {urlparse(cfg["site_url"]).netloc, urlparse(cfg["demo_url"]).netloc,
           "commons.wikimedia.org", "creativecommons.org", "www.sitemaps.org", "www.w3.org"}
ALLOWED |= {urlparse(u).netloc for u in cfg.get("profiles", {}).values()}
ALLOWED |= {urlparse(u).netloc for u in cfg.get("downloads", {}).values() if u}
ALLOWED.discard("")
if cfg.get("repo_public"):
    ALLOWED.add(urlparse(cfg["repo_url"]).netloc)

def check():
    errors = []
    for f in L.rglob("*"):
        if f.suffix not in {".html", ".css", ".js", ".xml", ".txt", ".svg"} or "docs" in f.relative_to(L).parts or f.name.startswith("LICENSE"):
            continue
        text = f.read_text()
        for u in re.findall(r"https?://[^\s\"'<>)]+", text):
            if urlparse(u).netloc not in ALLOWED:
                errors.append(f"{f.relative_to(L)}: external URL not allowed: {u}")
        if f.suffix == ".html":
            if "@import" in text or "fonts.googleapis" in text:
                errors.append(f"{f.relative_to(L)}: remote font/import")
            for ref in re.findall(r'(?:src|href|srcset)="(/[^"#]*)', text):
                for part in ref.split(","):
                    p = part.strip().split(" ")[0]
                    t = L / p.lstrip("/")
                    if p.endswith("/"): t = t / "index.html"
                    if p and not t.exists():
                        errors.append(f"{f.relative_to(L)}: missing local file {p}")
            for img in re.findall(r"<img [^>]*>", text):
                if 'width="' not in img or 'height="' not in img or 'alt="' not in img:
                    errors.append(f"{f.relative_to(L)}: img without width/height/alt: {img[:80]}")
            if "instagram.com" in text or re.search(r"(?<![\w.])@[a-z0-9_.]{3,}", text):
                errors.append(f"{f.relative_to(L)}: Instagram URL or @handle")
    return errors

if __name__ == "__main__":
    errs = check()
    print("\n".join(errs) or f"landing OK (allowed hosts: {', '.join(sorted(ALLOWED))})")
    sys.exit(1 if errs else 0)
