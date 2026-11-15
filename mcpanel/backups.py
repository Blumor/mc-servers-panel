"""Sauvegardes des mondes : archive ZIP à chaud, restauration, rotation des sauvegardes auto.

Une sauvegarde contient les dossiers du monde et la config du serveur (server.properties,
whitelist, OP, bannis). Elles vivent dans backups/<serveur>/, hors du dossier du serveur :
« Nettoyer » ou supprimer le monde ne les emporte pas.
"""
from __future__ import annotations

import re
import shutil
import time
import zipfile
from pathlib import Path

from . import config as cfg

NAME_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9-]{1,32}\.zip$")
# Le suffixe « -2 », « -3 »... sépare deux sauvegardes faites dans la même seconde ; il ne
# fait pas partie de l'étiquette (sinon « auto-2 » passerait pour une sauvegarde manuelle).
LABEL_RE = re.compile(r"^\d{8}-\d{6}-(?P<label>[a-z0-9-]+?)(?:-\d+)?\.zip$")
CONFIG_FILES = ("server.properties", "whitelist.json", "ops.json", "banned-players.json", "banned-ips.json")
AUTO_LABEL = "auto"
KEEP_AUTO = 10


def folder(sid: str) -> Path:
    return cfg.BACKUPS_DIR / sid


def _path(sid: str, name: str) -> Path:
    if not NAME_RE.match(name or ""):
        raise ValueError("Nom de sauvegarde invalide.")
    path = folder(sid) / name
    if not path.is_file():
        raise ValueError("Sauvegarde introuvable : %s" % name)
    return path


def list_backups(sid: str) -> list[dict]:
    base = folder(sid)
    if not base.exists():
        return []
    items = []
    for path in base.glob("*.zip"):
        match = LABEL_RE.match(path.name)
        if not match or not NAME_RE.match(path.name):
            continue
        stat = path.stat()
        label = match.group("label")
        items.append({"name": path.name, "size": stat.st_size, "created": stat.st_mtime,
                      "label": label, "auto": label == AUTO_LABEL})
    return sorted(items, key=lambda b: (b["created"], b["name"]), reverse=True)  # plus récente d'abord


def _wait_saved(proc, since: int, timeout: float = 60.0) -> bool:
    """Attend « Saved the game » (« Saved the world » sur les vieilles versions) dans la console."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in proc.log.since(since):
            if "Saved the game" in item["line"] or "Saved the world" in item["line"]:
                return True
        if not proc.alive:
            return False
        time.sleep(0.2)
    return False


def create(srv, label: str = "manuel", report=None) -> dict:
    """Sauvegarde le monde du serveur, même allumé (écritures suspendues le temps de l'archive)."""
    say = report or (lambda *_a: None)
    label = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")[:32] or "manuel"
    proc = srv.live
    workdir = proc.workdir
    worlds = srv.world_dirs(workdir)
    if not worlds:
        raise RuntimeError("Aucun monde à sauvegarder : le serveur n'a encore jamais démarré.")

    paused = False
    if proc.alive:
        say("Écriture du monde sur le disque...", 0.1)
        since = proc.log.seq
        proc.send("save-off")
        version = srv.meta.get("version") or ""
        modern = not version[:1].isdigit() or cfg.parse_mc_version(version) >= (1, 14, 0)
        proc.send("save-all flush" if modern else "save-all")
        paused = True
        if not _wait_saved(proc, since):
            say("Le serveur n'a pas confirmé la sauvegarde, archive quand même", None)

    base = folder(srv.id)
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "%s-%s.zip" % (stamp, label)
    n = 2
    while (base / name).exists():
        name = "%s-%s-%d.zip" % (stamp, label[:29], n)
        n += 1
    tmp = base / (name + ".part")
    skipped = []
    try:
        say("Archivage du monde...", 0.3)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for world in worlds:
                for path in sorted(world.rglob("*")):
                    if path.is_dir() or path.name == "session.lock":  # verrou tenu par le serveur
                        continue
                    try:
                        zf.write(path, path.relative_to(workdir).as_posix())
                    except OSError:
                        skipped.append(path.name)
            for fname in CONFIG_FILES:
                if (workdir / fname).is_file():
                    zf.write(workdir / fname, fname)
        tmp.replace(base / name)
    finally:
        tmp.unlink(missing_ok=True)
        if paused:
            proc.send("save-on")
    if label == AUTO_LABEL:
        prune(srv.id)
    size = (base / name).stat().st_size
    say("Sauvegarde %s (%.1f Mo)" % (name, size / 1048576), 1.0)
    return {"name": name, "size": size, "skipped": skipped}


def prune(sid: str, keep: int = KEEP_AUTO) -> None:
    """Ne garde que les dernières sauvegardes automatiques ; les manuelles ne sont jamais touchées."""
    autos = [b for b in list_backups(sid) if b["auto"]]
    for item in autos[keep:]:
        (folder(sid) / item["name"]).unlink(missing_ok=True)


def delete(sid: str, name: str) -> None:
    _path(sid, name).unlink()


def restore(srv, name: str, report=None, safety: bool = True) -> dict:
    """Remplace le monde par celui de la sauvegarde. Le monde actuel est d'abord sauvegardé
    (sauf safety=False : « Recommencer la map », où la progression doit justement disparaître)."""
    from .manager import async_delete  # import tardif : manager importe ce module

    say = report or (lambda *_a: None)
    archive = _path(srv.id, name)
    was_running = srv.live.alive
    if was_running:
        srv.stop(report)
    workdir = srv.live.workdir
    safety_name = None
    if safety and srv.world_dirs(workdir):
        safety_name = create(srv, "avant-restauration", report)["name"]

    say("Extraction de la sauvegarde...", 0.6)
    staging = workdir / ".restauration"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    root = staging.resolve()
    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not (root / member).resolve().is_relative_to(root):  # archive piégée (« ../ »)
                    raise RuntimeError("Sauvegarde invalide : chemin suspect %s" % member)
            zf.extractall(staging)
        for world in srv.world_dirs(workdir):
            async_delete(world)
        for entry in staging.iterdir():
            target = workdir / entry.name
            if target.is_dir():
                async_delete(target)
            elif target.exists():
                target.unlink()
            entry.replace(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if was_running:  # même en cas d'échec : le monde n'a pas été touché, on le relance
            srv.start(report)
    say("Monde restauré depuis %s" % name, 1.0)
    return {"restored": name, "safety_backup": safety_name}


def disk_usage(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total
