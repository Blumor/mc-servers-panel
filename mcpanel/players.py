"""Whitelist et opérateurs : lecture/écriture des JSON + résolution des UUID.

Minecraft identifie les joueurs par UUID, pas par pseudo. Écrire whitelist.json
à la main demande donc de connaître l'UUID : ce module le récupère chez Mojang
(serveur en online-mode) ou le calcule localement (serveur en offline-mode,
même algorithme que le jeu).
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.error
import uuid as uuidlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import deps

NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
_MOJANG_ENDPOINTS = (
    "https://api.mojang.com/users/profiles/minecraft/%s",
    "https://api.minecraftservices.com/minecraft/profile/lookup/name/%s",
)

_cache_lock = threading.Lock()
_uuid_cache: dict[str, tuple[str, str]] = {}


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match((name or "").strip()))


def dashed(hex32: str) -> str:
    raw = hex32.replace("-", "")
    if len(raw) != 32:
        return hex32
    return "%s-%s-%s-%s-%s" % (raw[0:8], raw[8:12], raw[12:16], raw[16:20], raw[20:32])


def offline_uuid(name: str) -> str:
    """Même calcul que Minecraft en offline-mode : UUID v3 MD5 de 'OfflinePlayer:<nom>'."""
    digest = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuidlib.UUID(bytes=bytes(digest)))


def lookup_mojang(name: str) -> tuple[str, str] | None:
    """(uuid, pseudo exact) depuis les serveurs Mojang, ou None si introuvable."""
    with _cache_lock:
        hit = _uuid_cache.get(name.lower())
        if hit:
            return hit
    for template in _MOJANG_ENDPOINTS:
        try:
            data = deps.http_json(template % urllib_quote(name), timeout=8)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, OSError):
            continue
        ident = data.get("id") if isinstance(data, dict) else None
        if ident:
            result = (dashed(ident), data.get("name") or name)
            with _cache_lock:
                _uuid_cache[name.lower()] = result
            return result
    return None


def urllib_quote(text: str) -> str:
    import urllib.parse

    return urllib.parse.quote(text, safe="")


def resolve(name: str, online_mode: bool) -> tuple[str, str, str]:
    """Retourne (uuid, pseudo, origine). Bascule sur l'UUID hors-ligne si Mojang est injoignable."""
    name = name.strip()
    if online_mode:
        found = lookup_mojang(name)
        if found:
            return found[0], found[1], "mojang"
        return offline_uuid(name), name, "offline-fallback"
    return offline_uuid(name), name, "offline"


# --------------------------------------------------------------------------- #
# Fichiers JSON
# --------------------------------------------------------------------------- #
def read_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
    except (ValueError, OSError):
        return []
    return [x for x in data if isinstance(x, dict) and x.get("name")] if isinstance(data, list) else []


def write_list(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def add_entry(path: Path, name: str, online_mode: bool, op_level: int | None = None) -> dict:
    if not valid_name(name):
        raise ValueError("Pseudo invalide : 3 à 16 caractères, lettres, chiffres et _ uniquement.")
    entries = read_list(path)
    player_uuid, exact, origin = resolve(name, online_mode)
    for entry in entries:
        if entry.get("name", "").lower() == exact.lower() or entry.get("uuid") == player_uuid:
            raise ValueError("%s est déjà dans la liste." % exact)
    entry = {"uuid": player_uuid, "name": exact}
    if op_level is not None:
        entry["level"] = int(op_level)
        entry["bypassesPlayerLimit"] = False
    entries.append(entry)
    write_list(path, entries)
    return {"entry": entry, "origin": origin}


def remove_entry(path: Path, name: str) -> bool:
    entries = read_list(path)
    kept = [e for e in entries if e.get("name", "").lower() != name.strip().lower()]
    if len(kept) == len(entries):
        return False
    write_list(path, kept)
    return True


def rekey(path: Path, online_mode: bool) -> list[str]:
    """Recalcule les UUID d'une liste (whitelist, OP) pour le mode d'authentification donné.

    Un même pseudo n'a pas le même UUID en online-mode (compte Mojang) et en offline-mode
    (calculé depuis le pseudo). Minecraft compare les UUID : sans cette conversion,
    accepter ou refuser les comptes crack ferait perdre la whitelist et les OP.
    Retourne les pseudos sans compte Mojang trouvé (laissés tels quels).
    """
    entries = read_list(path)
    if not entries:
        return []
    names = [entry["name"] for entry in entries]
    if online_mode:
        with ThreadPoolExecutor(max_workers=8) as pool:
            found = list(pool.map(lookup_mojang, names))
    else:
        found = [(offline_uuid(name), name) for name in names]
    unresolved = []
    for entry, hit in zip(entries, found):
        if hit:
            entry["uuid"], entry["name"] = hit
        else:
            unresolved.append(entry["name"])
    write_list(path, entries)
    return unresolved
