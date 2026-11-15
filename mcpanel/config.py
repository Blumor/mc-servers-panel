"""Chemins, constantes et configuration globale du panel."""
from __future__ import annotations

import json
import os
import platform
import socket
import sys
import threading
from pathlib import Path

APP_NAME = "MC Servers Panel"
OLD_APP_NAMES = ("MC Speedrun Panel",)  # même panel, ancien nom (instance déjà lancée, données)
APP_VERSION = "2.3.3"

# Exécutable (PyInstaller, un seul fichier) : le code est décompressé dans un dossier
# temporaire effacé à la fermeture. L'interface est lue là-dedans, mais les données
# (mondes, Java, config) vont dans « mcpanel-data » à côté de l'exe, pour survivre.
FROZEN = bool(getattr(sys, "frozen", False))
CODE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _data_root() -> Path:
    if not FROZEN:
        return CODE_ROOT  # depuis les sources : données à côté du code, comme toujours
    beside_exe = Path(sys.executable).resolve().parent / "mcpanel-data"
    try:
        beside_exe.mkdir(parents=True, exist_ok=True)
        probe = beside_exe / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return beside_exe
    except OSError:  # exe rangé dans un dossier protégé (Program Files...) : profil utilisateur
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
        old = base / "MC Speedrun Panel"
        return old if old.is_dir() and not (base / APP_NAME).exists() else base / APP_NAME


ROOT = _data_root()
WEB_DIR = CODE_ROOT / "web"
SERVERS_DIR = ROOT / "servers"
CACHE_DIR = ROOT / ".cache"
JAR_CACHE = CACHE_DIR / "jars"
RUNTIME_DIR = ROOT / ".runtime"
TRASH_DIR = ROOT / ".trash"
LOG_DIR = ROOT / ".logs"
PANEL_CONF = ROOT / "panel.json"
BACKUPS_DIR = ROOT / "backups"

VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ADOPTIUM_API = "https://api.adoptium.net/v3/binary/latest"
USER_AGENT = f"{APP_NAME}/{APP_VERSION} (+local server manager)"

DEFAULT_PORT = 25565
DEFAULT_PANEL_PORT = 8765

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# Java requis selon la version Minecraft (seuils officiels Mojang).
JAVA_MATRIX = (
    ((26, 0, 0), 25),  # numérotation annuelle (26.1, 26.2...) : Java 25
    ((1, 20, 5), 21),
    ((1, 18, 0), 17),
    ((1, 17, 0), 16),
    ((0, 0, 0), 8),
)

_conf_lock = threading.Lock()


def os_slug() -> str:
    if IS_WINDOWS:
        return "windows"
    if IS_MAC:
        return "mac"
    return "linux"


def arch_slug() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x64"
    if m in ("arm64", "aarch64"):
        return "aarch64"
    if m in ("i386", "i686", "x86"):
        return "x86-32"
    return "x64"


def tune_listen_socket(sock: socket.socket) -> None:
    """À appeler avant bind() sur tout socket d'écoute.

    Linux/macOS : SO_REUSEADDR évite d'attendre la fin des connexions en TIME_WAIT.
    Windows : SO_REUSEADDR autorise au contraire à se brancher sur un port déjà ouvert
    par un autre programme ; on demande un port exclusif pour détecter les conflits.
    """
    if IS_WINDOWS:
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            sock.setsockopt(socket.SOL_SOCKET, exclusive, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def ensure_dirs() -> None:
    for d in (WEB_DIR, SERVERS_DIR, CACHE_DIR, JAR_CACHE, RUNTIME_DIR, TRASH_DIR, LOG_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def total_ram_mb() -> int:
    """RAM physique totale, best effort, sans dépendance externe."""
    try:
        if IS_WINDOWS:
            import ctypes

            class MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MemStatus()
            stat.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return int(stat.ullTotalPhys // (1024 * 1024))
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024))
    except Exception:
        return 8192


def suggested_ram_mb() -> int:
    """RAM à allouer par défaut: moitié de la RAM physique, bornée 2-8 Go."""
    total = total_ram_mb()
    return max(2048, min(8192, (total // 2) // 512 * 512))


_DEFAULT_CONF = {
    "panel_port": DEFAULT_PANEL_PORT,
    "auto_open_browser": True,
    "turbo_default": False,
    "theme": "aurora",
}


def load_conf() -> dict:
    with _conf_lock:
        data = dict(_DEFAULT_CONF)
        if PANEL_CONF.exists():
            try:
                data.update(json.loads(PANEL_CONF.read_text(encoding="utf-8")))
            except Exception:
                pass
        return data


def save_conf(patch: dict) -> dict:
    with _conf_lock:
        data = dict(_DEFAULT_CONF)
        if PANEL_CONF.exists():
            try:
                data.update(json.loads(PANEL_CONF.read_text(encoding="utf-8")))
            except Exception:
                pass
        data.update(patch)
        PANEL_CONF.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


def parse_mc_version(version: str) -> tuple:
    """'1.21.4' -> (1, 21, 4). Snapshots et versions exotiques -> très haut."""
    parts = []
    for chunk in version.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def required_java(mc_version: str) -> int:
    if not mc_version or mc_version[0].isalpha():
        return 25
    v = parse_mc_version(mc_version)
    for threshold, java in JAVA_MATRIX:
        if v >= threshold:
            return java
    return 25
