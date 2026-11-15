"""Lecture/écriture de server.properties + schéma typé pour l'interface.

Le schéma sert à l'UI : elle sait afficher une case à cocher, un menu ou un
champ numérique borné au lieu d'un champ texte libre. Les clés absentes du
schéma (mods, plugins, versions futures) restent éditables en texte et ne sont
jamais perdues à l'écriture.
"""
from __future__ import annotations

import re
from pathlib import Path

BOOL, INT, STR, ENUM = "bool", "int", "str", "enum"

# Le panel efface le dossier du monde à chaque reset : le nom doit rester un simple
# dossier du serveur, jamais un chemin (« .. », « / », lecteur Windows...).
LEVEL_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}$")

# Clés pilotées par le panel : l'utilisateur les voit mais ne les édite pas ici.
LOCKED = ("server-port", "query.port", "prevent-proxy-connections", "level-seed")

GROUPS = (
    ("gameplay", "Jeu"),
    ("world", "Monde"),
    ("players", "Joueurs"),
    ("network", "Réseau"),
    ("perf", "Performance"),
    ("advanced", "Avancé"),
)

# (clé, groupe, type, label, options/bornes, aide)
SCHEMA: tuple[dict, ...] = (
    # ---------------------------------------------------------------- gameplay
    {"key": "difficulty", "group": "gameplay", "type": ENUM, "label": "Difficulté",
     "options": ["peaceful", "easy", "normal", "hard"], "default": "hard"},
    {"key": "gamemode", "group": "gameplay", "type": ENUM, "label": "Mode de jeu",
     "options": ["survival", "creative", "adventure", "spectator"], "default": "survival"},
    {"key": "hardcore", "group": "gameplay", "type": BOOL, "label": "Hardcore", "default": "true",
     "hint": "Mort définitive, passage en spectateur."},
    {"key": "pvp", "group": "gameplay", "type": BOOL, "label": "PvP", "default": "true"},
    {"key": "force-gamemode", "group": "gameplay", "type": BOOL, "label": "Forcer le mode de jeu",
     "default": "false", "hint": "Remet chaque joueur dans le mode par défaut à la connexion."},
    {"key": "allow-flight", "group": "gameplay", "type": BOOL, "label": "Autoriser le vol",
     "default": "false", "hint": "À activer si vous utilisez un mod de vol, sinon anti-triche."},
    {"key": "enable-command-block", "group": "gameplay", "type": BOOL, "label": "Blocs de commande",
     "default": "false"},
    {"key": "spawn-protection", "group": "gameplay", "type": INT, "label": "Rayon de spawn protégé",
     "min": 0, "max": 256, "default": "0", "hint": "0 = pas de protection (recommandé en speedrun)."},

    # ------------------------------------------------------------------- world
    {"key": "level-name", "group": "world", "type": STR, "label": "Nom du monde", "default": "world",
     "hint": "Changer ce nom crée un nouveau monde ; l'ancien reste sur le disque. "
             "Lettres, chiffres, _ - . uniquement."},
    {"key": "level-type", "group": "world", "type": ENUM, "label": "Type de monde",
     "options": ["minecraft:normal", "minecraft:flat", "minecraft:large_biomes",
                 "minecraft:amplified", "minecraft:single_biome_surface"],
     "default": "minecraft:normal"},
    {"key": "generate-structures", "group": "world", "type": BOOL, "label": "Générer les structures",
     "default": "true", "hint": "Villages, forteresses, portails ruinés…"},
    {"key": "allow-nether", "group": "world", "type": BOOL, "label": "Nether activé", "default": "true"},
    {"key": "spawn-monsters", "group": "world", "type": BOOL, "label": "Monstres", "default": "true"},
    {"key": "spawn-animals", "group": "world", "type": BOOL, "label": "Animaux", "default": "true"},
    {"key": "spawn-npcs", "group": "world", "type": BOOL, "label": "Villageois", "default": "true"},
    {"key": "max-world-size", "group": "world", "type": INT, "label": "Taille max du monde",
     "min": 1, "max": 29999984, "default": "29999984", "hint": "Rayon en blocs depuis 0,0."},
    {"key": "generator-settings", "group": "world", "type": STR, "label": "Réglages du générateur",
     "default": "{}", "hint": "JSON, uniquement pour les mondes plats ou biome unique."},

    # ----------------------------------------------------------------- players
    {"key": "max-players", "group": "players", "type": INT, "label": "Joueurs max",
     "min": 1, "max": 200, "default": "8"},
    {"key": "motd", "group": "players", "type": STR, "label": "Message du serveur (MOTD)",
     "default": "A Minecraft Server", "hint": "Affiché sous le nom dans la liste des serveurs."},
    {"key": "white-list", "group": "players", "type": BOOL, "label": "Whitelist activée",
     "default": "false", "hint": "Seuls les joueurs de la liste peuvent se connecter."},
    {"key": "enforce-whitelist", "group": "players", "type": BOOL, "label": "Appliquer immédiatement",
     "default": "false", "hint": "Expulse les joueurs retirés de la whitelist sans attendre."},
    # Affiché inversé (« invert ») : l'interrupteur dit « accepter », la valeur stockée est online-mode.
    {"key": "online-mode", "group": "players", "type": BOOL, "label": "Accepter les comptes crack",
     "default": "true", "invert": True,
     "hint": "Activé = online-mode=false : plus aucune vérification Mojang, n'importe qui peut prendre "
             "n'importe quel pseudo, y compris celui d'un OP. Uniquement entre joueurs de confiance."},
    {"key": "player-idle-timeout", "group": "players", "type": INT, "label": "Expulsion si inactif (min)",
     "min": 0, "max": 240, "default": "0", "hint": "0 = jamais."},
    {"key": "op-permission-level", "group": "players", "type": INT, "label": "Niveau des OP",
     "min": 1, "max": 4, "default": "4"},
    {"key": "hide-online-players", "group": "players", "type": BOOL, "label": "Masquer la liste des joueurs",
     "default": "false"},

    # ----------------------------------------------------------------- network
    {"key": "server-port", "group": "network", "type": INT, "label": "Port", "min": 1024, "max": 65535,
     "default": "25565", "hint": "Réglé depuis l'onglet Réglages du serveur."},
    {"key": "server-ip", "group": "network", "type": STR, "label": "Interface d'écoute", "default": "",
     "hint": "Vide = toutes les interfaces."},
    {"key": "enable-status", "group": "network", "type": BOOL, "label": "Répondre au ping",
     "default": "true", "hint": "Affiche le serveur comme en ligne dans la liste."},
    {"key": "enable-query", "group": "network", "type": BOOL, "label": "Protocole Query", "default": "false"},
    {"key": "enable-rcon", "group": "network", "type": BOOL, "label": "RCON", "default": "false",
     "hint": "Console à distance. Inutile avec le panel, et expose un port."},
    {"key": "prevent-proxy-connections", "group": "network", "type": BOOL, "label": "Bloquer les proxys",
     "default": "false", "hint": "Forcé sur non : le mode Turbo passe par un proxy local."},
    {"key": "enforce-secure-profile", "group": "network", "type": BOOL, "label": "Signature du chat",
     "default": "false", "hint": "Sur oui, refuse les comptes sans clé de signature Mojang."},
    {"key": "rate-limit", "group": "network", "type": INT, "label": "Limite de paquets",
     "min": 0, "max": 1000, "default": "0", "hint": "0 = pas de limite."},

    # -------------------------------------------------------------------- perf
    {"key": "view-distance", "group": "perf", "type": INT, "label": "Distance d'affichage",
     "min": 2, "max": 32, "default": "10", "hint": "Chunks envoyés au client. Baisser soulage le CPU."},
    {"key": "simulation-distance", "group": "perf", "type": INT, "label": "Distance de simulation",
     "min": 3, "max": 32, "default": "8", "hint": "Chunks où mobs et redstone tournent."},
    {"key": "entity-broadcast-range-percentage", "group": "perf", "type": INT,
     "label": "Portée d'affichage des entités (%)", "min": 10, "max": 500, "default": "100"},
    {"key": "sync-chunk-writes", "group": "perf", "type": BOOL, "label": "Écritures synchrones",
     "default": "false", "hint": "Sur non, sauvegarde plus rapide. Recommandé."},
    {"key": "use-native-transport", "group": "perf", "type": BOOL, "label": "Transport natif Linux",
     "default": "true"},
    {"key": "network-compression-threshold", "group": "perf", "type": INT, "label": "Seuil de compression",
     "min": -1, "max": 1024, "default": "256", "hint": "-1 désactive. En local, 512 allège le CPU."},
    {"key": "max-tick-time", "group": "perf", "type": INT, "label": "Watchdog (ms)",
     "min": -1, "max": 600000, "default": "60000", "hint": "-1 désactive l'arrêt auto en cas de freeze."},

    # ---------------------------------------------------------------- advanced
    {"key": "function-permission-level", "group": "advanced", "type": INT, "label": "Niveau des fonctions",
     "min": 1, "max": 4, "default": "2"},
    {"key": "broadcast-console-to-ops", "group": "advanced", "type": BOOL,
     "label": "Diffuser la console aux OP", "default": "true"},
    {"key": "log-ips", "group": "advanced", "type": BOOL, "label": "Journaliser les IP", "default": "true"},
    {"key": "resource-pack", "group": "advanced", "type": STR, "label": "Pack de ressources (URL)", "default": ""},
    {"key": "resource-pack-sha1", "group": "advanced", "type": STR, "label": "SHA-1 du pack", "default": ""},
    {"key": "require-resource-pack", "group": "advanced", "type": BOOL, "label": "Pack obligatoire",
     "default": "false"},
    {"key": "max-chained-neighbor-updates", "group": "advanced", "type": INT,
     "label": "Mises à jour redstone chaînées", "min": -1, "max": 10000000, "default": "1000000"},
)

BY_KEY = {item["key"]: item for item in SCHEMA}

# Réglages taillés pour du speedrun coop : monde dur, pas d'attente, reset propre.
SPEEDRUN_DEFAULTS = {
    "allow-flight": "false",
    "difficulty": "hard",
    "enable-command-block": "false",
    "enforce-secure-profile": "false",
    "gamemode": "survival",
    "hardcore": "true",
    "level-name": "world",
    "level-seed": "",
    "level-type": "minecraft:normal",
    "max-players": "8",
    "motd": "\\u00a7bSpeedrun \\u00a78| \\u00a7fPanel",
    "online-mode": "true",
    "pvp": "true",
    "prevent-proxy-connections": "false",
    "server-port": "25565",
    "simulation-distance": "8",
    "spawn-protection": "0",
    "sync-chunk-writes": "false",
    "view-distance": "10",
    "white-list": "false",
}

# Modifications qui ne prennent effet qu'au redémarrage du serveur.
NEEDS_RESTART = frozenset({
    "server-port", "server-ip", "level-name", "level-type", "level-seed", "generator-settings",
    "online-mode", "enable-rcon", "enable-query", "enable-status", "max-world-size",
    "network-compression-threshold", "use-native-transport", "hardcore",
})


def editable_keys() -> list[str]:
    return [item["key"] for item in SCHEMA if item["key"] not in LOCKED]


# Conservé pour compatibilité : l'API accepte toute clé validée par le schéma.
EDITABLE = tuple(editable_keys())


def schema_payload() -> dict:
    return {
        "groups": [{"id": gid, "label": label} for gid, label in GROUPS],
        "fields": [dict(item, locked=item["key"] in LOCKED,
                        restart=item["key"] in NEEDS_RESTART) for item in SCHEMA],
        "locked": list(LOCKED),
    }


def coerce(key: str, value) -> str | None:
    """Normalise une valeur selon le schéma. None si elle est refusée."""
    text = "" if value is None else str(value).strip()
    spec = BY_KEY.get(key)
    if spec is None:
        # Clé inconnue (mod, plugin, future version) : on accepte du texte simple.
        return text.replace("\n", " ").replace("\r", "")

    if spec["type"] == BOOL:
        low = text.lower()
        if low in ("true", "1", "yes", "on"):
            return "true"
        if low in ("false", "0", "no", "off", ""):
            return "false"
        return None

    if spec["type"] == INT:
        try:
            number = int(float(text))
        except (TypeError, ValueError):
            return None
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None:
            number = max(lo, number)
        if hi is not None:
            number = min(hi, number)
        return str(number)

    if spec["type"] == ENUM:
        if text in spec["options"]:
            return text
        return None

    if key == "level-name":
        return text if LEVEL_NAME_RE.match(text) else None

    return text.replace("\n", " ").replace("\r", "")


def sanitize(values: dict, allow_locked: bool = False) -> tuple[dict, list[str]]:
    """Filtre un dict venant de l'UI. Retourne (valeurs propres, clés rejetées)."""
    clean, rejected = {}, []
    for key, raw in (values or {}).items():
        key = str(key).strip()
        if not key or "=" in key or "\n" in key:
            rejected.append(key)
            continue
        if key in LOCKED and not allow_locked:
            rejected.append(key)
            continue
        value = coerce(key, raw)
        if value is None:
            rejected.append(key)
            continue
        clean[key] = value
    return clean, rejected


def read(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return data
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def write(path: Path, values: dict[str, str]) -> None:
    """Fusionne values dans le fichier existant sans perdre les autres clés."""
    current = read(path)
    current.update({k: str(v) for k, v in values.items()})
    lines = ["#Minecraft server properties", "#Genere par MC Speedrun Panel"]
    lines += ["%s=%s" % (k, current[k]) for k in sorted(current)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def bootstrap(path: Path, port: int, overrides: dict | None = None) -> dict[str, str]:
    """Crée server.properties s'il manque ; ne remplace jamais les choix de l'utilisateur."""
    values = dict(SPEEDRUN_DEFAULTS)
    values["server-port"] = str(port)
    values["query.port"] = str(port)
    if overrides:
        values.update({k: str(v) for k, v in overrides.items() if v is not None})
    existing = read(path)
    for key, val in existing.items():
        values[key] = val
    # Le port et le proxy restent pilotés par le panel.
    values["server-port"] = str(port)
    values["query.port"] = str(port)
    values["prevent-proxy-connections"] = "false"
    if overrides:
        values.update({k: str(v) for k, v in overrides.items() if v is not None})
    write(path, values)
    return values


def effective(path: Path) -> dict[str, str]:
    """Valeurs actuelles, complétées par les défauts du schéma pour les clés absentes."""
    current = read(path)
    for item in SCHEMA:
        current.setdefault(item["key"], item.get("default", ""))
    return current
