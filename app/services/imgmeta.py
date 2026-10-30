"""Strip metadata (EXIF, XMP, IPTC, text chunks) from uploaded JPEG/PNG/WebP without Pillow.

Pure byte-level parsing: pixels are untouched. ``jpeg_orientation`` reads the EXIF orientation
first so the caller can bake the rotation in (with ffmpeg) before the tag is dropped.
"""
from __future__ import annotations

import struct
from typing import Optional

JPEG_DROP = {0xE1, 0xED, 0xFE} | set(range(0xE3, 0xED)) | {0xEE, 0xEF}  # APP1 EXIF/XMP, APP13 IPTC, COM, misc APPn
PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"}
WEBP_DROP = {b"EXIF", b"XMP "}


class BadImage(ValueError):
    pass


def _jpeg_segments(b: bytes):
    if not b.startswith(b"\xff\xd8"):
        raise BadImage("no es un JPEG")
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            raise BadImage("JPEG corrupto")
        while i < len(b) and b[i] == 0xFF:
            i += 1
        if i >= len(b):
            raise BadImage("JPEG truncado")
        marker = b[i]
        i += 1
        if marker in (0xD9,) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            yield marker, i - 2, i
            continue
        if i + 2 > len(b):
            raise BadImage("JPEG truncado")
        ln = struct.unpack(">H", b[i:i + 2])[0]
        yield marker, i - 2, i + ln
        if marker == 0xDA:  # start of scan: the rest is entropy-coded data
            yield -1, i + ln, len(b)
            return
        i += ln


def jpeg_orientation(b: bytes) -> int:
    try:
        for marker, start, end in _jpeg_segments(b):
            if marker == 0xE1 and b[start + 4:start + 10] == b"Exif\x00\x00":
                t = b[start + 10:end]
                end_c = "<" if t[:2] == b"II" else ">"
                ifd = struct.unpack(end_c + "I", t[4:8])[0]
                n = struct.unpack(end_c + "H", t[ifd:ifd + 2])[0]
                for k in range(n):
                    e = t[ifd + 2 + 12 * k: ifd + 14 + 12 * k]
                    if struct.unpack(end_c + "H", e[:2])[0] == 0x0112:
                        v = struct.unpack(end_c + "H", e[8:10])[0]
                        return v if 1 <= v <= 8 else 1
            if marker == 0xDA:
                break
    except (BadImage, struct.error, IndexError):
        pass
    return 1


def strip_jpeg(b: bytes) -> bytes:
    out = bytearray(b"\xff\xd8")
    for marker, start, end in _jpeg_segments(b):
        if marker in JPEG_DROP:
            continue
        out += b[start:end]
    return bytes(out)


def strip_png(b: bytes) -> bytes:
    if not b.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BadImage("no es un PNG")
    out, i = bytearray(b[:8]), 8
    while i + 8 <= len(b):
        ln = struct.unpack(">I", b[i:i + 4])[0]
        typ = b[i + 4:i + 8]
        end = i + 12 + ln
        if end > len(b):
            raise BadImage("PNG truncado")
        if typ not in PNG_DROP:
            out += b[i:end]
        i = end
        if typ == b"IEND":
            break
    return bytes(out)


def strip_webp(b: bytes) -> bytes:
    if not (b[:4] == b"RIFF" and b[8:12] == b"WEBP"):
        raise BadImage("no es un WebP")
    chunks, i = [], 12
    while i + 8 <= len(b):
        typ = b[i:i + 4]
        ln = struct.unpack("<I", b[i + 4:i + 8])[0]
        end = i + 8 + ln + (ln & 1)
        if end > len(b) + 1:
            raise BadImage("WebP truncado")
        if typ not in WEBP_DROP:
            data = bytearray(b[i:min(end, len(b))])
            if typ == b"VP8X" and len(data) > 8:
                data[8] &= ~0x0C & 0xFF  # clear EXIF (0x08) and XMP (0x04) flags
            chunks.append(bytes(data))
        i = end
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def strip(b: bytes, ext: str) -> bytes:
    return {"jpg": strip_jpeg, "png": strip_png, "webp": strip_webp}[ext](b)


def orientation_filter(o: int) -> Optional[str]:
    """ffmpeg -vf chain that bakes an EXIF orientation into the pixels."""
    return {2: "hflip", 3: "hflip,vflip", 4: "vflip", 5: "transpose=0", 6: "transpose=1",
            7: "transpose=3", 8: "transpose=2"}.get(o)
