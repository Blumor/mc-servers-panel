"""Logiciels serveur : Vanilla, Paper (plugins), Fabric et NeoForge (mods).

Chaque logiciel se télécharge depuis sa source officielle :
- Paper : API « Fill » de PaperMC (l'ancienne API v2 répond 410 Gone), fichier vérifié par SHA-256 ;
- Fabric : « server launcher » de meta.fabricmc.net, un seul jar exécutable ;
- NeoForge : installateur officiel (maven.neoforged.net) lancé une fois avec --installServer,
  puis démarrage via le fichier d'arguments qu'il génère (comme son run.sh / run.bat).
"""
from __future__ import annotations

import hashlib
import subprocess
import threading
import time
from pathlib import Path

from . import config as cfg
from . import deps

SOFTWARE = {
    "vanilla": {"label": "Vanilla", "content": None, "folder": None, "loaders": []},
    "paper": {"label": "Paper", "content": "plugin", "folder": "plugins", "loaders": ["paper", "spigot", "bukkit", "purpur"]},
    "fabric": {"label": "Fabric", "content": "mod", "folder": "mods", "loaders": ["fabric"]},
    "neoforge": {"label": "NeoForge", "content": "mod", "folder": "mods", "loaders": ["neoforge"]},
}
FILL = "https://fill.papermc.io/v3/projects/paper"
FABRIC_META = "https://meta.fabricmc.net/v2"
NEOFORGE_MAVEN = "https://maven.neoforged.net"

_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()
_install_lock = threading.Lock()


def _cached(key: str, fetch, ttl: float = 900.0):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = fetch()
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def _version_key(text: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in text.replace("-", ".").split("."))


# ------------------------------------------------------------------ versions
def paper_versions() -> set[str]:
    def fetch():
        groups = deps.http_json(FILL).get("versions", {})
        return {v for versions in groups.values() for v in versions}
    return _cached("paper", fetch)


def fabric_versions() -> set[str]:
    return _cached("fabric", lambda: {v["version"] for v in deps.http_json(FABRIC_META + "/versions/game")})


def neoforge_for(mc_version: str) -> str | None:
    """Dernière version stable de NeoForge pour ce Minecraft (21.1.x pour 1.21.1, 26.3.0.x pour 26.3)."""
    versions = _cached("neoforge", lambda: deps.http_json(
        NEOFORGE_MAVEN + "/api/maven/versions/releases/net/neoforged/neoforge").get("versions", []))
    parts = mc_version.split(".")
    if parts[0] == "1" and len(parts) >= 2:   # 1.21.1 -> « 21.1. »
        prefix = "%s.%s." % (parts[1], parts[2] if len(parts) > 2 else "0")
    elif parts[0].isdigit():                  # 26.3 -> « 26.3.0. »
        prefix = "%s.%s.%s." % (parts[0], parts[1] if len(parts) > 1 else "0", parts[2] if len(parts) > 2 else "0")
    else:
        return None
    stable = [v for v in versions if v.startswith(prefix) and v[len(prefix):].replace(".", "").isdigit()]
    return max(stable, key=_version_key) if stable else None


def availability(mc_version: str) -> dict[str, bool]:
    """Logiciels disponibles pour cette version (Paper dès 1.8, Fabric dès 1.14, NeoForge dès 1.20.2)."""
    result = {"vanilla": True}
    checks = {"paper": lambda: mc_version in paper_versions(),
              "fabric": lambda: mc_version in fabric_versions(),
              "neoforge": lambda: neoforge_for(mc_version) is not None}
    for name, check in checks.items():
        try:
            result[name] = bool(check())
        except Exception:  # noqa: BLE001 - source injoignable : on ne propose pas
            result[name] = False
    return result


# ---------------------------------------------------------------- préparation
def prepare(software: str, mc_version: str, workdir: Path, java_bin: str, say,
            pinned: str | None = None) -> tuple[list[str], str]:
    """Télécharge/installe le logiciel. Retourne (arguments de lancement, version du loader).

    pinned : version de loader imposée (modpack) ; sinon la dernière stable."""
    if software == "paper":
        jar, build = _paper_jar(mc_version, say)
        return ["-jar", str(jar)], build
    if software == "fabric":
        jar, loader = _fabric_jar(mc_version, say, pinned)
        return ["-jar", str(jar)], loader
    if software == "neoforge":
        version = pinned or neoforge_for(mc_version)
        return _neoforge(version, mc_version, workdir, java_bin, say), version
    raise ValueError("Logiciel inconnu : %s" % software)


def latest_loader(software: str, mc_version: str) -> str | None:
    if software == "fabric":
        return next(v["version"] for v in deps.http_json(FABRIC_META + "/versions/loader") if v["stable"])
    if software == "neoforge":
        return neoforge_for(mc_version)
    return None


def _paper_jar(mc_version: str, say) -> tuple[Path, str]:
    build = deps.http_json("%s/versions/%s/builds/latest" % (FILL, mc_version))
    download = (build.get("downloads") or {}).get("server:default")
    if not download:
        raise RuntimeError("Pas de Paper pour Minecraft %s." % mc_version)
    jar = cfg.JAR_CACHE / download["name"]
    if not jar.exists():
        say("Téléchargement de Paper %s (build %s)" % (mc_version, build.get("id")), 0.5)
        tmp = deps.download(download["url"], jar.with_suffix(".tmp"))
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if digest != download["checksums"]["sha256"]:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Paper téléchargé corrompu (SHA-256 différent).")
        tmp.replace(jar)
    return jar, str(build.get("id"))


def _fabric_jar(mc_version: str, say, pinned: str | None = None) -> tuple[Path, str]:
    loader = pinned or latest_loader("fabric", mc_version)
    installer = next(v["version"] for v in deps.http_json(FABRIC_META + "/versions/installer") if v["stable"])
    jar = cfg.JAR_CACHE / ("fabric-server-mc.%s-loader.%s-launcher.%s.jar" % (mc_version, loader, installer))
    if not jar.exists():
        say("Téléchargement de Fabric %s pour Minecraft %s" % (loader, mc_version), 0.5)
        deps.download("%s/versions/loader/%s/%s/%s/server/jar" % (FABRIC_META, mc_version, loader, installer), jar)
    return jar, loader


def _neoforge(version: str | None, mc_version: str, workdir: Path, java_bin: str, say) -> list[str]:
    if not version:
        raise RuntimeError("Pas de NeoForge pour Minecraft %s (disponible à partir de 1.20.2)." % mc_version)
    args_file = Path("libraries/net/neoforged/neoforge/%s/%s" % (version, "win_args.txt" if cfg.IS_WINDOWS else "unix_args.txt"))
    marker = workdir / ".neoforge-version"
    with _install_lock:
        if not (workdir / args_file).exists() or (marker.read_text().strip() if marker.exists() else "") != version:
            installer = cfg.CACHE_DIR / ("neoforge-%s-installer.jar" % version)
            if not installer.exists():
                say("Téléchargement de l'installateur NeoForge %s" % version, 0.4)
                deps.download("%s/releases/net/neoforged/neoforge/%s/neoforge-%s-installer.jar"
                              % (NEOFORGE_MAVEN, version, version), installer)
            say("Installation de NeoForge %s (bibliothèques, peut prendre une minute)..." % version, 0.6)
            workdir.mkdir(parents=True, exist_ok=True)
            run = subprocess.run([java_bin, "-jar", str(installer), "--installServer"], cwd=str(workdir),
                                 capture_output=True, text=True, timeout=900,
                                 creationflags=0x08000000 if cfg.IS_WINDOWS else 0)
            if run.returncode != 0 or not (workdir / args_file).exists():
                tail = (run.stdout + run.stderr).strip().splitlines()[-3:]
                raise RuntimeError("Installation de NeoForge impossible : %s" % " / ".join(tail))
            marker.write_text(version, encoding="utf-8")
    return ["@" + args_file.as_posix()]
