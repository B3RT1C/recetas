"""Original-post link for a recipe, whatever the source (Instagram, TikTok, YouTube, web...)."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

KNOWN = {  # host suffix -> source_type
    "instagram.com": "instagram", "instagr.am": "instagram",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube", "youtu.be": "youtube",
    "pinterest.com": "pinterest", "pin.it": "pinterest",
    "facebook.com": "facebook", "fb.watch": "facebook",
    "x.com": "x", "twitter.com": "x",
}
LABELS = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "pinterest": "Pinterest",
          "facebook": "Facebook", "x": "X", "web": "Web"}


def source_type(url: str) -> Optional[str]:
    if not url or not url.startswith(("http://", "https://")):
        return None
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    for suffix, kind in KNOWN.items():
        if host == suffix or host.endswith("." + suffix):
            return kind
    return "web"


def source_of(data: dict, shortcode: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """(source_url, source_type). Explicit source_url wins, then video_url, then an Instagram shortcode."""
    for key in ("source_url", "video_url"):
        url = (data.get(key) or "").strip()
        kind = source_type(url)
        if kind:
            return url, kind
    if shortcode and not shortcode.startswith("r"):
        return f"https://www.instagram.com/reel/{shortcode}/", "instagram"
    return None, None


def with_source(data: dict, shortcode: Optional[str] = None) -> dict:
    url, kind = source_of(data, shortcode)
    data["source_url"], data["source_type"] = url, kind
    return data
