"""Contenu installable en un clic depuis Modrinth : plugins, mods, datapacks, packs de ressources, modpacks.

Modrinth : catalogue ouvert, API sans clé, versions filtrables par Minecraft et par loader,
dépendances déclarées, fichiers vérifiables par SHA-1. Le panel garde la liste de ce qu'il a
installé dans content.json, à la racine du serveur.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath

from . import config as cfg
from . import deps, props, software

API = "https://api.modrinth.com/v2"
TYPES = ("plugin", "mod", "datapack", "resourcepack", "modpack")
LABELS = {"plugin": "plugin", "mod": "mod", "datapack": "datapack", "resourcepack": "pack de ressources", "modpack": "modpack"}


def _get(path: str, **params):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return deps.http_json("%s/%s%s" % (API, path, "?" + query if query else ""), timeout=20)


# ------------------------------------------------------------ registre local
def _index(srv) -> Path:
    return srv.dir / "content.json"


def load(srv) -> list[dict]:
    try:
        data = json.loads(_index(srv).read_text(encoding="utf-8"))
        return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(srv, items: list[dict]) -> None:
    _index(srv).write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def _inside(srv, rel: str) -> Path:
    """Chemin relatif au serveur, sans « .. » ni chemin absolu (fichiers venant d'Internet)."""
    pure = PurePosixPath(rel.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or ":" in pure.parts[0]:
        raise RuntimeError("Chemin refusé : %s" % rel)
    target = (srv.dir / Path(*pure.parts)).resolve()
    if not target.is_relative_to(srv.dir.resolve()):
        raise RuntimeError("Chemin refusé : %s" % rel)
    return target


# ---------------------------------------------------------------- règles
def content_type(srv) -> str | None:
    """Type d'extensions accepté par le logiciel du serveur : plugin (Paper) ou mod (Fabric, NeoForge)."""
    return software.SOFTWARE[srv.software]["content"]


def _check(srv, ctype: str) -> None:
    if srv.kind != "survival":
        raise RuntimeError("Le contenu Modrinth est réservé aux serveurs de survie.")
    if ctype not in TYPES:
        raise ValueError("Type de contenu inconnu : %s" % ctype)
    if ctype in ("plugin", "mod") and content_type(srv) != ctype:
        need = "Paper" if ctype == "plugin" else "Fabric ou NeoForge"
        raise RuntimeError("Les %ss demandent le logiciel %s (catégorie Logiciel)." % (ctype, need))


def _loaders(srv, ctype: str) -> list[str]:
    if ctype in ("plugin", "mod"):
        return software.SOFTWARE[srv.software]["loaders"]
    return {"datapack": ["datapack"], "resourcepack": ["minecraft"]}.get(ctype, [])


def _folder(srv, ctype: str) -> str:
    if ctype == "datapack":
        level = props.read(srv.settings_path()).get("level-name", "world")
        return "%s/datapacks" % level
    return software.SOFTWARE[srv.software]["folder"]


# ------------------------------------------------------------- recherche
def search(srv, ctype: str, query: str = "", offset: int = 0, limit: int = 20) -> dict:
    _check(srv, ctype)
    facets = [["project_type:%s" % ctype]]
    if ctype == "modpack":
        facets.append(["categories:fabric", "categories:neoforge"])  # loaders que le panel sait lancer
    else:
        facets.append(["versions:%s" % srv.resolve_version()])
        if ctype in ("plugin", "mod"):
            facets.append(["categories:%s" % loader for loader in _loaders(srv, ctype)])
    data = _get("search", query=query or None, facets=json.dumps(facets), limit=limit, offset=offset,
                index="relevance" if query else "downloads")
    installed = {i.get("project_id") for i in load(srv)}
    hits = [{
        "project_id": h["project_id"], "slug": h["slug"], "title": h["title"], "description": h["description"],
        "icon_url": h.get("icon_url") or "", "downloads": h.get("downloads", 0), "author": h.get("author", ""),
        "client_side": h.get("client_side"), "server_side": h.get("server_side"),
        "installed": h["project_id"] in installed,
        "client_only": ctype == "mod" and h.get("server_side") == "unsupported",
    } for h in data.get("hits", [])]
    return {"hits": hits, "total": data.get("total_hits", 0)}


def _best_version(project_id: str, loaders: list[str], game_version: str | None) -> dict | None:
    params = {"loaders": json.dumps(loaders)} if loaders else {}
    if game_version:
        params["game_versions"] = json.dumps([game_version])
    versions = _get("project/%s/version" % project_id, **params)
    stable = [v for v in versions if v.get("version_type") == "release"]
    return (stable or versions or [None])[0]


def _primary(version: dict) -> dict:
    files = version.get("files") or []
    if not files:
        raise RuntimeError("Cette version ne contient aucun fichier.")
    return next((f for f in files if f.get("primary")), files[0])


# ------------------------------------------- dépendances écrites dans le fichier
# Modrinth ne liste pas toujours les dépendances (spark ne déclare pas Fabric API, pourtant
# indispensable). Le fichier du mod, lui, les déclare toujours : on les lit après téléchargement.
_IGNORED = {"minecraft", "java", "fabricloader", "fabric-loader", "neoforge", "forge", "javafml"}
FABRIC_API = "fabric-api"

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - Python 3.9/3.10 : on se contente de Modrinth
    tomllib = None


def _file_dependencies(path: Path) -> list[str]:
    """Identifiants des dépendances obligatoires déclarées dans le jar (mod ou plugin)."""
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return []
    with zf:
        names = set(zf.namelist())
        try:
            if "fabric.mod.json" in names:
                data = json.loads(zf.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
                return [k for k in (data.get("depends") or {}) if k not in _IGNORED]
            if "META-INF/neoforge.mods.toml" in names and tomllib:
                data = tomllib.loads(zf.read("META-INF/neoforge.mods.toml").decode("utf-8", "replace"))
                found = []
                for entries in (data.get("dependencies") or {}).values():
                    for dep in entries if isinstance(entries, list) else []:
                        required = dep.get("type", "required" if dep.get("mandatory") else "optional") == "required"
                        if required and dep.get("side", "BOTH") != "CLIENT" and dep.get("modId") not in _IGNORED:
                            found.append(dep["modId"])
                return found
            for meta in ("paper-plugin.yml", "plugin.yml"):
                if meta in names:
                    text = zf.read(meta).decode("utf-8", "replace")
                    inline = re.search(r"^depend:\s*\[(.*?)\]", text, re.M)
                    if inline:
                        return [d.strip().strip("'\"") for d in inline.group(1).split(",") if d.strip()]
                    block = re.search(r"^depend:\s*\n((?:\s+-\s*.+\n?)+)", text, re.M)
                    return re.findall(r"-\s*['\"]?([^'\"\n]+)", block.group(1)) if block else []
        except (ValueError, KeyError, TypeError):
            return []
    return []


def _project_for(mod_id: str) -> str:
    """Identifiant de mod -> projet Modrinth (les modules fabric-* viennent tous de Fabric API)."""
    if mod_id == "fabric" or re.match(r"^fabric-.*(api|-v\d+)", mod_id):
        return FABRIC_API
    return mod_id.lower().replace("_", "-")


# ----------------------------------------------------------- installation
def install(srv, project_id: str, ctype: str, report=None, _depth: int = 0) -> dict:
    """Installe la bonne version d'un projet et ses dépendances obligatoires."""
    say = report or (lambda *_a: None)
    _check(srv, ctype)
    if ctype == "modpack":
        return install_modpack(srv, project_id, report)
    project = _get("project/%s" % urllib.parse.quote(project_id, safe=""))
    title = project.get("title") or project_id
    if ctype == "mod" and project.get("server_side") == "unsupported":
        raise RuntimeError("« %s » ne sert que côté joueur (graphismes, interface...) : inutile sur un serveur." % title)
    mc = srv.resolve_version()
    version = _best_version(project["id"], _loaders(srv, ctype), mc)
    if not version:
        raise RuntimeError("Aucune version de « %s » pour Minecraft %s (%s)." % (title, mc, srv.software))
    file = _primary(version)
    say("Installation de %s %s" % (title, version.get("version_number", "")), 0.3)
    items = [i for i in load(srv) if i.get("project_id") != project["id"]]
    old = next((i for i in load(srv) if i.get("project_id") == project["id"]), None)
    item = {
        "project_id": project["id"], "slug": project.get("slug"), "title": title, "type": ctype,
        "version_id": version["id"], "version_number": version.get("version_number", ""),
        "filename": file["filename"], "icon_url": project.get("icon_url") or "",
        "client_side": project.get("client_side"), "server_side": project.get("server_side"),
        "sha1": file["hashes"].get("sha1"), "sha512": file["hashes"].get("sha512"),
        "url": file["url"], "size": file.get("size", 0), "enabled": True, "installed_at": time.time(),
    }
    if ctype == "resourcepack":
        # Rien à copier : Minecraft envoie le lien aux joueurs, qui téléchargent le pack eux-mêmes.
        items = [i for i in items if i.get("type") != "resourcepack"]
        required = (old or {}).get("required", False)
        props.write(srv.settings_path(), {"resource-pack": file["url"], "resource-pack-sha1": item["sha1"] or "",
                                          "require-resource-pack": "true" if required else "false"})
        item.update(path="", required=required)
    else:
        name = PurePosixPath(file["filename"]).name
        rel = "%s/%s" % (_folder(srv, ctype), name)
        dest = _inside(srv, rel)
        if old and old.get("path") and old["path"] != rel:
            _inside(srv, old["path"]).unlink(missing_ok=True)  # mise à jour : l'ancien fichier part
        deps.download(file["url"], dest, expect_sha1=item["sha1"])
        item["path"] = rel
    items.append(item)
    _save(srv, items)

    notes = []
    installed = {i.get("project_id") for i in items}
    installed_slugs = {i.get("slug") for i in items}
    wanted = list(version.get("dependencies") or [])
    if item.get("path") and ctype in ("mod", "plugin"):
        for mod_id in _file_dependencies(srv.dir / item["path"]):
            slug = _project_for(mod_id)
            if slug not in installed_slugs and slug != item.get("slug"):
                wanted.append({"project_id": slug, "dependency_type": "required", "from_file": True})
    seen = set()
    for dep in wanted:
        dep_id = dep.get("project_id")
        if not dep_id or dep_id in seen:
            continue
        seen.add(dep_id)
        if dep.get("dependency_type") == "required" and dep_id not in installed and _depth < 4:
            try:
                sub = install(srv, dep_id, ctype, report, _depth + 1)
                notes.append("Dépendance installée : %s" % sub["installed"])
                notes += sub.get("notes", [])
                installed = {i.get("project_id") for i in load(srv)}
            except Exception as exc:  # noqa: BLE001 - on installe le reste, l'utilisateur est prévenu
                if not dep.get("from_file"):  # deviner un projet depuis un identifiant peut échouer
                    notes.append("Dépendance %s non installée : %s" % (dep_id, exc))
                else:
                    notes.append("« %s » demande « %s », introuvable automatiquement : installe-le à la main." % (title, dep_id))
        elif dep.get("dependency_type") == "incompatible" and dep_id in installed:
            other = next((i["title"] for i in items if i.get("project_id") == dep_id), dep_id)
            notes.append("Attention : %s est déclaré incompatible avec %s." % (title, other))
    return {"installed": title, "version": item["version_number"], "notes": notes}


def remove(srv, project_id: str) -> list[dict]:
    items = load(srv)
    item = next((i for i in items if i.get("project_id") == project_id or i.get("path") == project_id), None)
    if not item:
        raise ValueError("Contenu introuvable.")
    if item.get("type") == "resourcepack":
        props.write(srv.settings_path(), {"resource-pack": "", "resource-pack-sha1": "", "require-resource-pack": "false"})
    elif item.get("path"):
        _inside(srv, item["path"]).unlink(missing_ok=True)
    items.remove(item)
    _save(srv, items)
    return items


def set_option(srv, project_id: str, enabled: bool | None = None, required: bool | None = None) -> list[dict]:
    """Active/désactive un fichier (renommé .disabled) ou rend le pack de ressources obligatoire."""
    items = load(srv)
    item = next((i for i in items if i.get("project_id") == project_id or i.get("path") == project_id), None)
    if not item:
        raise ValueError("Contenu introuvable.")
    if required is not None and item.get("type") == "resourcepack":
        item["required"] = bool(required)
        props.write(srv.settings_path(), {"require-resource-pack": "true" if required else "false"})
    if enabled is not None and item.get("path") and bool(enabled) != item.get("enabled", True):
        current = _inside(srv, item["path"])
        new_rel = item["path"][:-len(".disabled")] if enabled else item["path"] + ".disabled"
        if current.exists():
            current.replace(_inside(srv, new_rel))
        item["path"], item["enabled"] = new_rel, bool(enabled)
    _save(srv, items)
    return items


def updates(srv) -> list[dict]:
    """Projets dont une version plus récente existe pour ce Minecraft et ce loader."""
    out = []
    mc = srv.resolve_version()
    for item in load(srv):
        if not item.get("project_id") or item.get("from_pack"):
            continue
        try:
            best = _best_version(item["project_id"], _loaders(srv, item["type"]), mc)
        except Exception:  # noqa: BLE001
            continue
        if best and best["id"] != item.get("version_id"):
            out.append({"project_id": item["project_id"], "title": item["title"],
                        "current": item.get("version_number"), "latest": best.get("version_number")})
    return out


# --------------------------------------------------------------- modpacks
def install_modpack(srv, project_id: str, report=None) -> dict:
    """Installe un modpack (.mrpack) : version de Minecraft, loader et fichiers serveur."""
    say = report or (lambda *_a: None)
    if srv.live.alive:
        raise RuntimeError("Arrête le serveur avant d'installer un modpack.")
    project = _get("project/%s" % urllib.parse.quote(project_id, safe=""))
    versions = _get("project/%s/version" % project["id"], loaders=json.dumps(["fabric", "neoforge"]))
    if not versions:
        raise RuntimeError("« %s » n'existe pas pour Fabric ou NeoForge." % project.get("title"))
    version = next((v for v in versions if v.get("version_type") == "release"), versions[0])
    file = _primary(version)
    pack = cfg.CACHE_DIR / "modpacks" / PurePosixPath(file["filename"]).name
    say("Téléchargement du modpack %s %s" % (project.get("title"), version.get("version_number")), 0.1)
    deps.download(file["url"], pack, expect_sha1=file["hashes"].get("sha1"))
    with zipfile.ZipFile(pack) as zf:
        index = json.loads(zf.read("modrinth.index.json").decode("utf-8"))
        dependencies = index.get("dependencies", {})
        mc = dependencies.get("minecraft")
        if "fabric-loader" in dependencies:
            sw, loader = "fabric", dependencies["fabric-loader"]
        elif "neoforge" in dependencies:
            sw, loader = "neoforge", dependencies["neoforge"]
        else:
            raise RuntimeError("Ce modpack demande un loader que le panel ne gère pas (Forge, Quilt).")
        if srv.world_dirs(srv.dir):
            srv.backup(report, "avant-modpack")
        for old in load(srv):  # les anciens mods laissent la place à ceux du pack
            if old.get("type") in ("mod", "file") and old.get("path"):
                _inside(srv, old["path"]).unlink(missing_ok=True)
        items = [i for i in load(srv) if i.get("type") not in ("mod", "file")]
        files = [f for f in index.get("files", []) if (f.get("env") or {}).get("server") != "unsupported"]
        for n, f in enumerate(files, 1):
            dest = _inside(srv, f["path"])
            say("Mod %d/%d : %s" % (n, len(files), PurePosixPath(f["path"]).name), 0.2 + 0.6 * n / max(1, len(files)))
            deps.download(f["downloads"][0], dest, expect_sha1=f["hashes"].get("sha1"))
            items.append({"project_id": None, "title": PurePosixPath(f["path"]).name, "filename": PurePosixPath(f["path"]).name,
                          "type": "mod" if f["path"].startswith("mods/") else "file", "path": f["path"],
                          "sha1": f["hashes"].get("sha1"), "sha512": f["hashes"].get("sha512"), "url": f["downloads"][0],
                          "size": f.get("fileSize", 0), "client_side": (f.get("env") or {}).get("client", "required"),
                          "server_side": (f.get("env") or {}).get("server", "required"), "enabled": True, "from_pack": True})
        root = srv.dir.resolve()
        for member in zf.namelist():
            for prefix in ("overrides/", "server-overrides/"):
                if member.startswith(prefix) and not member.endswith("/"):
                    dest = _inside(srv, member[len(prefix):])
                    if not dest.is_relative_to(root):
                        raise RuntimeError("Modpack invalide : %s" % member)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(member))
    _save(srv, items)
    srv.meta.update(version=mc, software=sw, loader_pin=loader,
                    modpack={"project_id": project["id"], "title": project.get("title"), "version": version.get("version_number")})
    srv.deps_ready = False
    srv.save()
    say("Modpack installé : %d fichiers" % len(files), 1.0)
    return {"installed": project.get("title"), "minecraft": mc, "software": sw, "files": len(files), "notes": []}


def client_pack(srv) -> bytes:
    """Modpack .mrpack à importer par les joueurs (Modrinth App, Prism Launcher) : les mods côté joueur."""
    if content_type(srv) != "mod":
        raise RuntimeError("Pas de mods à partager : le serveur n'est pas en Fabric ou NeoForge.")
    mc = srv.resolve_version()
    loader = srv.meta.get("loader_pin") or srv.meta.get("loader_version") or software.latest_loader(srv.software, mc)
    files = []
    for item in load(srv):
        if item.get("type") != "mod" or not item.get("enabled", True) or item.get("client_side") == "unsupported":
            continue
        if not (item.get("sha1") and item.get("sha512") and item.get("url")):
            continue
        files.append({"path": "mods/%s" % item["filename"], "hashes": {"sha1": item["sha1"], "sha512": item["sha512"]},
                      "env": {"client": "optional" if item.get("client_side") == "optional" else "required",
                              "server": "required"},
                      "downloads": [item["url"]], "fileSize": item.get("size", 0)})
    index = {"formatVersion": 1, "game": "minecraft", "versionId": time.strftime("%Y.%m.%d"),
             "name": "%s (joueurs)" % srv.meta.get("name", srv.id), "files": files,
             "dependencies": {"minecraft": mc, ("fabric-loader" if srv.software == "fabric" else "neoforge"): loader}}
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index, indent=2, ensure_ascii=False))
    return buf.getvalue()
