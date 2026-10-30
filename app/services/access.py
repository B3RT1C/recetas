"""Network access settings: detected URLs + QR, and admin editing of host/port.

Production contract (Windows mini PC, ops scripts are the source of truth):
the scheduled task RecetasWeb runs start-recetas.ps1, which reads RECETAS_CONFIG_FILE (config.env),
starts run.py, checks /api/health within 45 s and rolls back to config.env.last-good on failure.
The app only writes the config file atomically, manages its own firewall rules and asks the task to run.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from ..config import config_file_path, parse_dotenv

log = logging.getLogger("recetas.access")
TASK_NAME = "RecetasWeb"
TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")


def local_ips() -> list[str]:
    """IPv4 addresses assigned to local interfaces (best effort, no extra dependencies)."""
    ips: set[str] = set()
    try:
        import psutil  # optional
        for addrs in psutil.net_if_addrs().values():
            ips.update(a.address for a in addrs if a.family == socket.AF_INET)
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    for probe in ("192.0.2.1", "100.100.100.100"):  # route lookup only, nothing is sent over UDP connect
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 80))
                ips.add(s.getsockname()[0])
        except OSError:
            pass
    ips.add("127.0.0.1")
    return sorted(ips, key=lambda ip: ipaddress.ip_address(ip))


def access_urls(host: str, port: int) -> list[dict]:
    out = []
    if host in ("127.0.0.1", "localhost"):
        return [{"url": f"http://localhost:{port}/", "tipo": "local"}]
    ips = local_ips() if host == "0.0.0.0" else [host]
    for ip in ips:
        a = ipaddress.ip_address(ip)
        if a.is_loopback:
            continue
        kind = "tailscale" if a in TAILSCALE_NET else "lan" if a.is_private else "otra"
        out.append({"url": f"http://{ip}:{port}/", "tipo": kind})
    out.append({"url": f"http://localhost:{port}/", "tipo": "local"})
    return out


def qr_svg(text: str) -> str:
    from ..vendor.qrcodegen import QrCode
    q = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    n, b = q.get_size(), 4
    parts = [f"M{x + b},{y + b}h1v1h-1z" for y in range(n) for x in range(n) if q.get_module(x, y)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n + 2 * b} {n + 2 * b}" '
            f'shape-rendering="crispEdges" role="img" aria-label="Código QR"><rect width="100%" height="100%" fill="#fff"/>'
            f'<path d="{" ".join(parts)}" fill="#000"/></svg>')


# ------------------------------------------------------------------ validation
class ConfigError(ValueError):
    pass


def can_bind(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def validate(host: str, port, current_host: str, current_port: int, bind=None, ips=None) -> tuple[str, int]:
    bind, ips = bind or can_bind, ips or local_ips
    host = (host or "").strip()
    if isinstance(port, bool) or (isinstance(port, float) and not port.is_integer()):
        raise ConfigError("El puerto debe ser un número entero")
    try:
        port = int(port)
        if str(port) != str(port).strip():
            raise ValueError
    except (TypeError, ValueError):
        raise ConfigError("El puerto debe ser un número entero") from None
    if isinstance(port, bool) or not 1024 <= port <= 65535:
        raise ConfigError("El puerto debe estar entre 1024 y 65535")
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        raise ConfigError("La dirección debe ser una IPv4 (0.0.0.0, 127.0.0.1 o una IP de este equipo)") from None
    if host not in ("0.0.0.0", "127.0.0.1") and host not in ips():
        raise ConfigError(f"{host} no es una IP de ninguna interfaz de este equipo")
    if port != current_port and not bind(host, port):
        raise ConfigError(f"El puerto {port} ya está en uso")
    return host, port


def write_config(path: Path, updates: dict[str, str]) -> None:
    """Rewrite KEY=VALUE lines atomically, keeping every other line (comments, other keys) untouched."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    pending = dict(updates)
    out = []
    for line in lines:
        key = line.strip().removeprefix("export ").partition("=")[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in pending:
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in pending.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_config(path: Optional[Path]) -> dict[str, str]:
    if path and Path(path).is_file():
        return parse_dotenv(Path(path).read_text(encoding="utf-8-sig"))
    return {}


# ------------------------------------------------------------------ system operations (mocked in tests)
class SystemOps:
    """Firewall + restart. Real only on Windows with RECETAS_CONFIG_FILE set; otherwise a no-op that says so."""

    def __init__(self, config_file: Optional[Path]):
        self.config_file = config_file
        self.enabled = sys.platform == "win32" and config_file is not None

    def unavailable_reason(self) -> Optional[str]:
        if sys.platform != "win32":
            return "Reinicio automático no disponible fuera de Windows: reinicia el servidor a mano."
        if self.config_file is None:
            return "RECETAS_CONFIG_FILE no está definido: reinicia el servidor a mano."
        return None

    def _run(self, args: list[str]) -> bool:
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        if r.returncode:
            log.warning("%s -> %s", args[0], r.returncode)
        return r.returncode == 0

    def add_firewall(self, port: int) -> bool:
        ok = self._run(["netsh", "advfirewall", "firewall", "add", "rule", f"name=Recetario {port} (LAN)",
                        "dir=in", "action=allow", "protocol=TCP", f"localport={port}", "profile=private"])
        return self._run(["netsh", "advfirewall", "firewall", "add", "rule", f"name=Recetario {port} (Tailscale)",
                          "dir=in", "action=allow", "protocol=TCP", f"localport={port}",
                          "remoteip=100.64.0.0/10"]) and ok

    def remove_firewall(self, port: int) -> bool:
        ok = True
        for suffix in ("LAN", "Tailscale"):  # only our own exactly-named rules
            ok = self._run(["netsh", "advfirewall", "firewall", "delete", "rule",
                            f"name=Recetario {port} ({suffix})"]) and ok
        return ok

    def restart(self) -> bool:
        return self._run(["schtasks", "/Run", "/TN", TASK_NAME])


def pending_cleanup_file(secret_dir: Path) -> Path:
    return secret_dir / "firewall-old-port.txt"


def cleanup_old_rules(ops: SystemOps, secret_dir: Path, current_port: int) -> Optional[int]:
    """Run on the first successful /api/health of a new server (= the start script sees it healthy).

    File holds "old,new". Serving on new -> drop old rules. Serving on old (rolled back) -> drop new rules."""
    f = pending_cleanup_file(secret_dir)
    if not f.is_file():
        return None
    try:
        old, new = (int(x) for x in f.read_text(encoding="utf-8").strip().split(","))
    except ValueError:
        f.unlink(missing_ok=True)
        return None
    drop = old if current_port == new else new if current_port == old else None
    if drop is not None and ops.enabled:
        ops.remove_firewall(drop)
    f.unlink(missing_ok=True)
    return drop
