"""Détection et installation automatique des dépendances: Java + server.jar.

Aucune installation système n'est requise: le JRE est téléchargé en version
portable (archive Adoptium/Temurin) et extrait dans .runtime/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config as cfg
from .bus import BUS

_JAVA_VERSION_RE = re.compile(r'version "?(\d+)(?:\.(\d+))?')
_manifest_lock = threading.Lock()
_manifest_cache: dict = {"data": None, "at": 0.0}
_java_lock = threading.RLock()
_java_cache: dict[int, str] = {}
_scan_cache: dict = {"result": [], "at": 0.0}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": cfg.USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_json(url: str, timeout: int = 30) -> dict:
    return json.loads(http_get(url, timeout).decode("utf-8"))


def download(url: str, dest: Path, on_progress=None, expect_sha1: str | None = None) -> Path:
    """Télécharge avec reprise sur fichier temporaire + vérification SHA1."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": cfg.USER_AGENT})
    last_emit = 0.0
    sha1 = hashlib.sha1()
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                sha1.update(chunk)
                done += len(chunk)
                now = time.time()
                if on_progress and (now - last_emit > 0.15 or done == total):
                    last_emit = now
                    on_progress(done, total)
    if expect_sha1 and sha1.hexdigest() != expect_sha1:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            "Checksum invalide pour %s (attendu %s, obtenu %s)"
            % (dest.name, expect_sha1, sha1.hexdigest())
        )
    tmp.replace(dest)
    return dest


# --------------------------------------------------------------------------- #
# Java
# --------------------------------------------------------------------------- #
def java_version_of(java_bin: str) -> int | None:
    """Retourne la version majeure (8, 17, 21...) ou None si binaire inutilisable."""
    try:
        out = subprocess.run(
            [java_bin, "-version"],
            capture_output=True,
            timeout=15,
            **_no_window(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (out.stderr or b"").decode("utf-8", "replace") + (out.stdout or b"").decode("utf-8", "replace")
    m = _JAVA_VERSION_RE.search(text)
    if not m:
        return None
    major = int(m.group(1))
    if major == 1 and m.group(2):  # ancien schéma 1.8.0_xxx
        major = int(m.group(2))
    return major


def _no_window() -> dict:
    if cfg.IS_WINDOWS:
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def _candidate_java_bins() -> list[str]:
    exe = "java.exe" if cfg.IS_WINDOWS else "java"
    found: list[str] = []

    # 1) JRE portables déjà téléchargés par le panel (prioritaires: version connue).
    if cfg.RUNTIME_DIR.exists():
        for path in sorted(cfg.RUNTIME_DIR.glob("**/bin/" + exe)):
            found.append(str(path))

    # 2) PATH
    which = shutil.which("java")
    if which:
        found.append(which)

    # 3) JAVA_HOME
    home = os.environ.get("JAVA_HOME")
    if home:
        cand = Path(home) / "bin" / exe
        if cand.exists():
            found.append(str(cand))

    # 4) Emplacements d'installation classiques
    roots: list[Path] = []
    if cfg.IS_WINDOWS:
        for base in (r"C:\Program Files", r"C:\Program Files (x86)", os.environ.get("LOCALAPPDATA", "")):
            if not base:
                continue
            for vendor in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu", "Amazon Corretto", "BellSoft"):
                roots.append(Path(base) / vendor)
        appdata = os.environ.get("APPDATA")
        if appdata:  # JRE embarqué du launcher Minecraft
            roots.append(Path(appdata) / ".minecraft" / "runtime")
    else:
        roots += [Path("/usr/lib/jvm"), Path("/usr/java"), Path("/opt/java"), Path.home() / ".jdks"]
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in sorted(root.glob("*/bin/" + exe)) + sorted(root.glob("*/*/bin/" + exe)):
                found.append(str(path))
        except OSError:
            continue

    seen, uniq = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def scan_java(max_age: float = 30.0) -> list[dict]:
    """Liste tous les Java trouvés avec leur version.

    Chaque candidat coûte un `java -version`, donc le résultat est mis en cache:
    l'UI interroge /api/state à chaque ouverture de page.
    """
    with _java_lock:
        if _scan_cache["at"] and time.time() - _scan_cache["at"] < max_age:
            return list(_scan_cache["result"])
    binaries = _candidate_java_bins()
    # Un `java -version` prend 50-300 ms : en parallèle, la page s'ouvre sans attendre la somme.
    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = list(pool.map(java_version_of, binaries))
    result = [
        {"path": binary, "major": ver, "managed": str(cfg.RUNTIME_DIR) in binary}
        for binary, ver in zip(binaries, versions) if ver
    ]
    with _java_lock:
        _scan_cache["result"] = result
        _scan_cache["at"] = time.time()
    return list(result)


def find_java(minimum: int) -> str | None:
    """Java installé le plus proche du minimum requis, par le haut.

    On prend la plus basse version qui convient plutôt que la plus récente:
    un Minecraft ancien qui demande Java 8 ne tourne pas sur Java 21.
    """
    with _java_lock:
        cached = _java_cache.get(minimum)
        if cached and Path(cached).exists():
            return cached
        best = None
        best_major = None
        for entry in scan_java():
            major = entry["major"]
            if major < minimum:
                continue
            if best_major is None or major < best_major:
                best, best_major = entry["path"], major
        if best:
            _java_cache[minimum] = best
        return best


def invalidate_java_cache() -> None:
    with _java_lock:
        _java_cache.clear()
        _scan_cache["at"] = 0.0


def temurin_url(feature: int) -> str:
    image = "jre"
    return "%s/%d/ga/%s/%s/%s/hotspot/normal/eclipse" % (
        cfg.ADOPTIUM_API,
        feature,
        cfg.os_slug(),
        cfg.arch_slug(),
        image,
    )


def install_java(feature: int, on_progress=None) -> str:
    """Télécharge et extrait un JRE portable. Retourne le chemin du binaire java."""
    target_dir = cfg.RUNTIME_DIR / ("jre-%d" % feature)
    exe = "java.exe" if cfg.IS_WINDOWS else "java"

    existing = sorted(target_dir.glob("**/bin/" + exe))
    if existing and java_version_of(str(existing[0])) == feature:
        return str(existing[0])

    def emit(stage, done=0, total=0, msg=""):
        if on_progress:
            on_progress({"stage": stage, "done": done, "total": total, "message": msg})

    emit("resolve", msg="Recherche du JRE %d..." % feature)
    url = temurin_url(feature)
    suffix = ".zip" if cfg.IS_WINDOWS else ".tar.gz"
    archive = cfg.CACHE_DIR / ("temurin-jre-%d-%s-%s%s" % (feature, cfg.os_slug(), cfg.arch_slug(), suffix))

    if not archive.exists():
        emit("download", msg="Téléchargement du JRE %d (~45 Mo)" % feature)
        try:
            download(url, archive, on_progress=lambda d, t: emit("download", d, t, "Téléchargement du JRE %d" % feature))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                "Impossible de télécharger Java %d depuis Adoptium (HTTP %s). "
                "Vérifiez votre connexion ou installez Java manuellement." % (feature, exc.code)
            ) from exc

    emit("extract", msg="Extraction du JRE...")
    staging = cfg.RUNTIME_DIR / ("._extract-%d" % feature)
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(staging)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                _safe_extract_tar(tf, staging)
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        archive.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("Archive Java corrompue, relancez l'installation (%s)" % exc) from exc

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    staging.replace(target_dir)

    bins = sorted(target_dir.glob("**/bin/" + exe))
    if not bins:
        raise RuntimeError("JRE extrait mais binaire java introuvable dans %s" % target_dir)
    java_bin = bins[0]
    if not cfg.IS_WINDOWS:
        for path in java_bin.parent.iterdir():
            try:
                path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
    invalidate_java_cache()
    emit("done", msg="Java %d prêt" % feature)
    return str(java_bin)


def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in tf.getmembers():
        target = (dest / member.name).resolve()
        # is_relative_to et non startswith : « /x/jre-evil » commence aussi par « /x/jre ».
        if not target.is_relative_to(dest):
            raise RuntimeError("Archive suspecte (path traversal): %s" % member.name)
    try:
        tf.extractall(dest, filter="data")
    except TypeError:  # Python < 3.12
        tf.extractall(dest)


def ensure_java(mc_version: str, on_progress=None) -> str:
    """Garantit un Java compatible avec la version Minecraft. Installe si absent."""
    needed = cfg.required_java(mc_version)
    found = find_java(needed)
    if found:
        return found
    return install_java(needed, on_progress=on_progress)


# --------------------------------------------------------------------------- #
# Serveur Minecraft (jar officiel Mojang)
# --------------------------------------------------------------------------- #
def version_manifest(force: bool = False) -> dict:
    with _manifest_lock:
        fresh = time.time() - _manifest_cache["at"] < 900
        if _manifest_cache["data"] and fresh and not force:
            return _manifest_cache["data"]
        cache_file = cfg.CACHE_DIR / "version_manifest_v2.json"
        try:
            data = http_json(cfg.VERSION_MANIFEST)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            if cache_file.exists():  # mode hors-ligne
                data = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                raise RuntimeError(
                    "Impossible de contacter les serveurs Mojang et aucun cache local. "
                    "Vérifiez votre connexion internet."
                )
        _manifest_cache["data"] = data
        _manifest_cache["at"] = time.time()
        return data


def list_versions(kind: str = "release", limit: int = 60) -> list[dict]:
    data = version_manifest()
    out = []
    for entry in data.get("versions", []):
        if kind != "all" and entry.get("type") != kind:
            continue
        out.append({"id": entry["id"], "type": entry["type"], "released": entry.get("releaseTime", "")[:10]})
        if len(out) >= limit:
            break
    return out


def latest_release() -> str:
    return version_manifest().get("latest", {}).get("release", "1.21.4")


def resolve_server_jar_url(mc_version: str) -> tuple[str, str | None]:
    data = version_manifest()
    entry = next((v for v in data.get("versions", []) if v["id"] == mc_version), None)
    if not entry:
        raise RuntimeError("Version Minecraft inconnue: %s" % mc_version)
    meta = http_json(entry["url"])
    server = meta.get("downloads", {}).get("server")
    if not server:
        raise RuntimeError(
            "La version %s ne fournit pas de serveur téléchargeable (trop ancienne)." % mc_version
        )
    return server["url"], server.get("sha1")


def ensure_server_jar(mc_version: str, on_progress=None) -> Path:
    """Retourne le chemin du jar serveur, téléchargé et vérifié si besoin."""
    jar = cfg.JAR_CACHE / ("minecraft_server-%s.jar" % mc_version)
    if jar.exists() and jar.stat().st_size > 1024:
        return jar

    def emit(stage, done=0, total=0, msg=""):
        if on_progress:
            on_progress({"stage": stage, "done": done, "total": total, "message": msg})

    emit("resolve", msg="Résolution de la version %s..." % mc_version)
    url, sha1 = resolve_server_jar_url(mc_version)
    emit("download", msg="Téléchargement de Minecraft %s" % mc_version)
    download(
        url,
        jar,
        on_progress=lambda d, t: emit("download", d, t, "Minecraft %s" % mc_version),
        expect_sha1=sha1,
    )
    emit("done", msg="Minecraft %s prêt" % mc_version)
    return jar


def local_jars() -> list[str]:
    return sorted(p.name for p in cfg.JAR_CACHE.glob("*.jar"))
