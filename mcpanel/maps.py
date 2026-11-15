"""Maps aventure, parkour, puzzle et mini-jeux : catalogue, import (ZIP ou lien), recommencer.

Une map est un monde Minecraft tout fait : un dossier avec un level.dat, livré en ZIP par son
auteur. Le panel la télécharge (ou la reçoit du navigateur), lit dans level.dat la version de
Minecraft pour laquelle elle a été faite, l'installe comme monde du serveur, applique les
réglages qui vont avec le type de map, puis garde une copie intacte : « Recommencer la map »
remet le monde dans l'état du téléchargement.

Rien n'est redistribué : chaque map du catalogue est téléchargée depuis le site de son auteur,
au moment où l'utilisateur la choisit.
"""
from __future__ import annotations

import gzip
import io
import shutil
import stat
import struct
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from . import backups, deps, props, software
from . import config as cfg

ORIGINAL_LABEL = "map-originale"
MAX_ARCHIVE = 2 * 1024 ** 3      # 2 Go téléchargés ou envoyés
MAX_UNPACKED = 8 * 1024 ** 3     # 8 Go décompressés : protège contre les archives piégées
MAX_ENTRIES = 300_000

# Réglages appliqués à l'installation, selon le type de map. L'utilisateur peut tout changer
# ensuite (catégorie Général). Les blocs de commande et le vol sont indispensables à la
# plupart des maps : téléportations, lévitation, élytres... (sinon « kicked for flying »).
PRESETS = {
    "aventure": {"gamemode": "adventure", "difficulty": "normal", "pvp": "false"},
    "parkour": {"gamemode": "adventure", "difficulty": "peaceful", "pvp": "false"},
    "puzzle": {"gamemode": "adventure", "difficulty": "peaceful", "pvp": "false"},
    "minijeu": {"gamemode": "adventure", "difficulty": "normal", "pvp": "true"},
}
COMMON_PRESET = {"enable-command-block": "true", "allow-flight": "true", "spawn-protection": "0",
                 "hardcore": "false", "level-name": "world"}
CATEGORY_LABEL = {"aventure": "Aventure", "parkour": "Parkour", "puzzle": "Puzzle", "minijeu": "Mini-jeu"}

# Catalogue : maps dont l'auteur propose un téléchargement direct et stable sur son site.
# Les maps de Hielke sont mises à jour pour chaque version de Minecraft : la version réelle
# est lue dans le level.dat après téléchargement, jamais supposée.
_HIELKE = "https://hielkemaps.com"
_HIELKE_MAPS = [
    ("parkour-spiral", "Parkour Spiral", "Une tour en spirale, des sauts de plus en plus durs jusqu'au sommet."),
    ("parkour-spiral-2", "Parkour Spiral 2", "La suite : nouvelle spirale, nouveaux pièges."),
    ("parkour-spiral-3", "Parkour Spiral 3", "Troisième spirale, la plus longue de la série."),
    ("parkour-paradise", "Parkour Paradise", "100 niveaux de parkour, du facile à l'impossible."),
    ("parkour-paradise-2", "Parkour Paradise 2", "100 nouveaux niveaux, encore plus variés."),
    ("parkour-paradise-3", "Parkour Paradise 3", "Le dernier volet de Paradise, 100 niveaux."),
    ("parkour-volcano", "Parkour Volcano", "Grimper un volcan en évitant la lave."),
    ("parkour-pyramid", "Parkour Pyramid", "Une pyramide à gravir, étage par étage."),
    ("parkour-town", "Parkour Town", "Courir sur les toits d'une ville entière."),
    ("parkour-egg", "Parkour Egg", "Un parcours en forme d'œuf géant, court et fun."),
    ("dimension-parkour", "Dimension Parkour", "Un parcours à travers les dimensions du jeu."),
]
CATALOG = [{
    "id": slug, "title": title, "author": "Hielke", "category": "parkour", "players": "1 à plusieurs",
    "description": text, "page": "%s/maps/%s" % (_HIELKE, slug),
    "download": "%s/downloads/%s.zip" % (_HIELKE, urllib.parse.quote(title)),
} for slug, title, text in _HIELKE_MAPS]

# Pas de téléchargement direct possible (publicités, pages intermédiaires) : on y envoie
# l'utilisateur, il télécharge le ZIP et l'importe.
MORE_SITES = [
    {"title": "Minecraft Maps", "url": "https://www.minecraftmaps.com/", "text": "Archive de maps aventure, puzzle, parkour, PvP."},
    {"title": "Planet Minecraft", "url": "https://www.planetminecraft.com/projects/tag/map/", "text": "La plus grande communauté de créations Minecraft."},
    {"title": "CurseForge — Worlds", "url": "https://www.curseforge.com/minecraft/worlds", "text": "Maps classées par catégorie et par version."},
]


def catalog() -> dict:
    return {"maps": CATALOG, "sites": MORE_SITES, "categories": CATEGORY_LABEL}


def find(map_id: str) -> dict:
    for item in CATALOG:
        if item["id"] == map_id:
            return item
    raise ValueError("Map inconnue : %s" % map_id)


# --------------------------------------------------------------- level.dat (NBT)
class _NBT:
    """Lecteur NBT minimal (format des fichiers de monde Minecraft), sans dépendance."""

    def __init__(self, data: bytes) -> None:
        self.buf, self.pos = data, 0

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.buf):
            raise ValueError("NBT tronqué")
        chunk = self.buf[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def string(self) -> str:
        (n,) = struct.unpack(">H", self.take(2))
        return self.take(n).decode("utf-8", "replace")

    def payload(self, tag: int, depth: int = 0):
        if depth > 64:
            raise ValueError("NBT trop imbriqué")
        if tag == 1:
            return struct.unpack(">b", self.take(1))[0]
        if tag == 2:
            return struct.unpack(">h", self.take(2))[0]
        if tag == 3:
            return struct.unpack(">i", self.take(4))[0]
        if tag == 4:
            return struct.unpack(">q", self.take(8))[0]
        if tag == 5:
            return struct.unpack(">f", self.take(4))[0]
        if tag == 6:
            return struct.unpack(">d", self.take(8))[0]
        if tag in (7, 11, 12):
            (n,) = struct.unpack(">i", self.take(4))
            self.take(max(0, n) * {7: 1, 11: 4, 12: 8}[tag])
            return None  # tableaux : inutiles ici
        if tag == 8:
            return self.string()
        if tag == 9:
            inner, n = self.take(1)[0], struct.unpack(">i", self.take(4))[0]
            return [self.payload(inner, depth + 1) for _ in range(max(0, n))]
        if tag == 10:
            out = {}
            while True:
                inner = self.take(1)[0]
                if inner == 0:
                    return out
                name = self.string()
                out[name] = self.payload(inner, depth + 1)
        raise ValueError("Tag NBT inconnu : %d" % tag)

    def root(self) -> dict:
        tag = self.take(1)[0]
        if tag != 10:
            raise ValueError("level.dat invalide")
        self.string()
        return self.payload(10)


def read_level(raw: bytes) -> dict:
    """Nom et version de Minecraft d'un level.dat (compressé gzip, ou brut)."""
    try:
        data = gzip.decompress(raw)
    except OSError:
        data = raw
    root = _NBT(data).root()
    level = root.get("Data") if isinstance(root.get("Data"), dict) else root
    version = level.get("Version") if isinstance(level.get("Version"), dict) else {}
    name = level.get("LevelName")
    return {
        "name": _strip_colors(name) if isinstance(name, str) else "",
        "version": version.get("Name") if isinstance(version.get("Name"), str) else None,
        "data_version": level.get("DataVersion") if isinstance(level.get("DataVersion"), int) else None,
    }


def _strip_colors(text: str) -> str:
    out, skip = [], False
    for ch in text:
        if skip:
            skip = False
        elif ch == "§":
            skip = True
        else:
            out.append(ch)
    return "".join(out).strip()


# ------------------------------------------------------------------- archives
def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def inspect(archive: Path) -> dict:
    """Trouve le monde dans l'archive (le level.dat le moins profond) et lit sa version."""
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        raise RuntimeError("Ce fichier n'est pas une archive ZIP valide.") from None
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise RuntimeError("Archive trop grosse (%d fichiers)." % len(infos))
        names = [i.filename.replace("\\", "/") for i in infos]
        if any(PurePosixPath(n).name == "levelname.txt" for n in names) and any("/db/" in "/" + n for n in names):
            raise RuntimeError("C'est une map Bedrock (téléphone, console, Windows) : incompatible avec Minecraft Java.")
        levels = [n for n in names if PurePosixPath(n).name == "level.dat"
                  and not n.startswith("__MACOSX/") and "/." not in "/" + n]
        if not levels:
            raise RuntimeError("Aucun monde Minecraft dans cette archive (pas de fichier level.dat).")
        level = min(levels, key=lambda n: (n.count("/"), len(n)))
        prefix = level[: -len("level.dat")]
        total = sum(i.file_size for i in infos if i.filename.replace("\\", "/").startswith(prefix))
        if total > MAX_UNPACKED:
            raise RuntimeError("Map trop grosse une fois décompressée (%.1f Go, 8 Go max)." % (total / 1024 ** 3))
        try:
            meta = read_level(zf.read(level))
        except (ValueError, OSError, EOFError, struct.error):
            meta = {"name": "", "version": None, "data_version": None}
        pack = next((n for n in names if n == prefix + "resources.zip"), None)
    return {"prefix": prefix, "size": total, "resource_pack": pack, **meta}


def _extract(archive: Path, prefix: str, dest: Path) -> None:
    """Extrait le dossier du monde (et lui seul) dans dest, sans jamais écrire à côté."""
    root = dest.resolve()
    written = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith(prefix) or _is_symlink(info):
                continue
            rel = PurePosixPath(name[len(prefix):])
            if not rel.parts or rel.name == "session.lock":
                continue
            if rel.is_absolute() or ".." in rel.parts or ":" in rel.parts[0]:
                raise RuntimeError("Archive invalide : chemin suspect %s" % name)
            target = (dest / Path(*rel.parts)).resolve()
            if not target.is_relative_to(root):
                raise RuntimeError("Archive invalide : chemin suspect %s" % name)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            written += info.file_size
            if written > MAX_UNPACKED:
                raise RuntimeError("Map trop grosse une fois décompressée (8 Go max).")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)


def download(url: str, dest: Path, report=None) -> Path:
    """Télécharge une map (HTTPS uniquement, 2 Go max), avec progression."""
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Lien refusé : il faut une adresse https:// vers un fichier .zip.")
    say = report or (lambda *_a: None)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url.strip(), headers={"User-Agent": cfg.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            if total > MAX_ARCHIVE:
                raise RuntimeError("Fichier trop gros (%.1f Go, 2 Go max)." % (total / 1024 ** 3))
            done, last = 0, 0.0
            with open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > MAX_ARCHIVE:
                        raise RuntimeError("Fichier trop gros (2 Go max).")
                    fh.write(chunk)
                    now = time.time()
                    if now - last > 0.3:
                        last = now
                        mb = done / 1048576
                        say("Téléchargement de la map : %.0f Mo%s" % (mb, " / %.0f Mo" % (total / 1048576) if total else ""),
                            0.05 + 0.45 * (done / total) if total else None)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def uploads_dir() -> Path:
    return cfg.CACHE_DIR / "uploads"


# -------------------------------------------------------------- installation
def _require_map_server(srv) -> None:
    if srv.kind != "adventure":
        raise RuntimeError("Les maps s'installent sur un serveur Aventure & mini-jeux.")
    if srv.live.alive:
        raise RuntimeError("Arrête le serveur avant de changer de map.")


def _target_version(detected: str | None, srv, notes: list) -> str:
    known = {v["id"] for v in deps.version_manifest().get("versions", [])}
    if detected and detected in known:
        return detected
    fallback = srv.meta.get("version") or deps.latest_release()
    if detected:
        notes.append("Map faite pour Minecraft %s, version inconnue de Mojang : le serveur reste en %s." % (detected, fallback))
    else:
        notes.append("Version de la map introuvable (map ancienne, d'avant la 1.9 ?) : le serveur reste en %s. "
                     "Change la version dans Général si la map le demande." % fallback)
    return fallback


def install(srv, archive: Path, source: dict, report=None) -> dict:
    """Installe la map de l'archive comme monde du serveur (serveur arrêté)."""
    from .manager import async_delete  # import tardif : manager importe ce module

    say = report or (lambda *_a: None)
    _require_map_server(srv)
    say("Lecture de la map...", 0.55)
    info = inspect(archive)
    notes: list[str] = []
    version = _target_version(info["version"], srv, notes)
    if srv.software != "vanilla" and not software.availability(version).get(srv.software):
        notes.append("%s n'existe pas pour Minecraft %s : serveur repassé en Vanilla."
                     % (software.SOFTWARE[srv.software]["label"], version))
        srv.meta["software"] = "vanilla"
        srv.meta.pop("loader_pin", None)

    if srv.world_dirs(srv.dir):
        say("Sauvegarde du monde actuel...", 0.6)
        srv.backup(report, "avant-map")

    staging = srv.dir / ".map-import"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        say("Installation de la map (%.0f Mo)..." % (info["size"] / 1048576), 0.7)
        _extract(archive, info["prefix"], staging)
        for world in srv.world_dirs(srv.dir):
            async_delete(world)
        target = srv.dir / "world"
        if target.exists():
            async_delete(target)
        staging.replace(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    pack_note = None
    pack = srv.dir / "map-resources.zip"
    pack.unlink(missing_ok=True)
    if info["resource_pack"] and (srv.dir / "world" / "resources.zip").is_file():
        shutil.copyfile(srv.dir / "world" / "resources.zip", pack)
        pack_note = "La map a son propre pack de ressources : télécharge-le depuis la catégorie Map et donne-le aux joueurs."
        notes.append(pack_note)

    category = source.get("category") if source.get("category") in PRESETS else "aventure"
    values = props.read(srv.settings_path())
    values.update({**COMMON_PRESET, **PRESETS[category]})
    props.write(srv.settings_path(), values)  # serveur arrêté : pris en compte au démarrage

    title = source.get("title") or info["name"] or "Map importée"
    srv.meta.update({
        "version": version,
        "map": {"title": title, "author": source.get("author") or "", "page": source.get("page") or "",
                "category": category, "origin": source.get("origin") or "import", "id": source.get("id") or "",
                "map_version": info["version"], "installed": time.time(), "resource_pack": bool(pack_note)},
    })
    srv.deps_ready = False
    srv.save()

    say("Copie de la map d'origine (pour pouvoir recommencer)...", 0.9)
    for old in backups.list_backups(srv.id):
        if old["label"] == ORIGINAL_LABEL:
            backups.delete(srv.id, old["name"])
    backups.create(srv, ORIGINAL_LABEL, None)
    say("Map « %s » installée (Minecraft %s)" % (title, version), 1.0)
    return {"map": title, "version": version, "notes": notes}


def install_from(srv, source: dict, report=None) -> dict:
    """Map du catalogue ou lien : télécharge, installe, supprime le fichier temporaire."""
    _require_map_server(srv)
    if source.get("id"):
        source = {**find(source["id"]), "origin": "catalogue"}
        url = source["download"]
    else:
        url = str(source.get("url") or "")
        name = PurePosixPath(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).stem
        source = {"title": source.get("title") or name or "Map importée", "page": url, "origin": "lien",
                  "category": source.get("category") or "aventure"}
    archive = uploads_dir() / ("%s-%d.zip" % (srv.id, int(time.time() * 1000)))
    try:
        download(url, archive, report)
        return install(srv, archive, source, report)
    finally:
        archive.unlink(missing_ok=True)


def original_backup(srv) -> str | None:
    found = [b for b in backups.list_backups(srv.id) if b["label"] == ORIGINAL_LABEL]
    return found[0]["name"] if found else None


def restart(srv, report=None) -> dict:
    """Remet la map dans l'état du téléchargement (progression des joueurs effacée)."""
    if srv.kind != "adventure":
        raise RuntimeError("Recommencer n'existe que pour les serveurs Aventure & mini-jeux.")
    name = original_backup(srv)
    if not name:
        raise RuntimeError("Pas de copie d'origine de la map : réinstalle-la depuis la catégorie Map.")
    return backups.restore(srv, name, report, safety=False)


def resource_pack(srv) -> Path | None:
    path = srv.dir / "map-resources.zip"
    return path if path.is_file() else None


def receive_upload(stream: io.BufferedIOBase, length: int, dest: Path) -> Path:
    """Copie le corps d'une requête (fichier envoyé par le navigateur) sur le disque."""
    if length <= 0:
        raise ValueError("Fichier vide.")
    if length > MAX_ARCHIVE:
        raise ValueError("Fichier trop gros (2 Go max).")
    dest.parent.mkdir(parents=True, exist_ok=True)
    left = length
    with open(dest, "wb") as out:
        while left > 0:
            chunk = stream.read(min(1024 * 1024, left))
            if not chunk:
                break
            out.write(chunk)
            left -= len(chunk)
    if left:
        dest.unlink(missing_ok=True)
        raise ValueError("Envoi interrompu.")
    return dest
