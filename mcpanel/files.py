"""Éditeur des fichiers de configuration (plugins, mods, Paper/Spigot), avec garde-fous.

Seuls des fichiers texte de config, de taille raisonnable, dans des dossiers connus sont
lisibles et modifiables. Chaque enregistrement garde l'ancienne version en « .bak ».
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

EXTENSIONS = {".yml", ".yaml", ".json", ".json5", ".toml", ".properties", ".txt", ".conf", ".cfg", ".ini", ".snbt"}
FOLDERS = ("config", "plugins", "defaultconfigs")
TOP_LEVEL = {".yml", ".yaml", ".toml"}  # bukkit.yml, spigot.yml, commands.yml…
MAX_SIZE = 1024 * 1024
MAX_FILES = 500


def _allowed(srv, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(srv.dir.resolve())
    except (ValueError, OSError):
        return False
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        return False
    if len(rel.parts) == 1:
        return path.suffix.lower() in TOP_LEVEL
    return rel.parts[0] in FOLDERS


def list_files(srv) -> list[dict]:
    found = []
    candidates = [p for p in srv.dir.iterdir() if p.is_file()] if srv.dir.exists() else []
    for folder in FOLDERS:
        base = srv.dir / folder
        if base.is_dir():
            candidates += [p for p in base.rglob("*") if p.is_file()]
    for path in sorted(candidates):
        if _allowed(srv, path) and path.stat().st_size <= MAX_SIZE:
            found.append({"path": path.relative_to(srv.dir).as_posix(), "size": path.stat().st_size})
            if len(found) >= MAX_FILES:
                break
    return found


def _resolve(srv, rel: str) -> Path:
    pure = PurePosixPath((rel or "").replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError("Chemin refusé.")
    path = srv.dir / Path(*pure.parts)
    if not _allowed(srv, path):
        raise ValueError("Fichier non modifiable depuis le panel : %s" % rel)
    if path.stat().st_size > MAX_SIZE:
        raise ValueError("Fichier trop gros pour l'éditeur (1 Mo max).")
    return path


def read_file(srv, rel: str) -> str:
    return _resolve(srv, rel).read_text(encoding="utf-8", errors="replace")


def write_file(srv, rel: str, text: str) -> None:
    path = _resolve(srv, rel)
    if len(text.encode("utf-8")) > MAX_SIZE:
        raise ValueError("Contenu trop gros (1 Mo max).")
    backup = path.with_name(path.name + ".bak")
    backup.write_bytes(path.read_bytes())
    path.write_text(text, encoding="utf-8", newline="")
