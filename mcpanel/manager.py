"""Gestionnaire multi-serveurs: cycle de vie, resets rapides, mode turbo."""
from __future__ import annotations

import json
import re
import shutil
import socket
import threading
import time
import uuid
from pathlib import Path

from . import config as cfg
from . import deps, players, props
from .bus import BUS
from .instance import ERROR, RESETTING, RUNNING, STARTING, STOPPED, ServerProcess
from .jobs import RUNNER
from .proxy import TurboProxy

SLOT_A, SLOT_B = "a", "b"
MAIN = "main"
# Ordre d'essai quand la JVM installée est trop ancienne pour le jar.
JAVA_LADDER = (17, 21, 25)

# Réglages que Minecraft accepte de changer sans redémarrer, via la console.
LIVE_COMMANDS = {
    "difficulty": lambda v: "difficulty %s" % v,
    "gamemode": lambda v: "defaultgamemode %s" % v,
    "white-list": lambda v: "whitelist %s" % ("on" if v == "true" else "off"),
    "player-idle-timeout": lambda v: "setidletimeout %s" % v,
}

# Ce que l'interface affiche en permanence, sans ouvrir l'éditeur complet.
SNAPSHOT_KEYS = ("difficulty", "gamemode", "hardcore", "pvp", "max-players", "motd",
                 "white-list", "online-mode", "level-name", "level-type")
_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "serveur"


def free_port(start: int, avoid: set[int] | None = None) -> int:
    avoid = avoid or set()
    for port in range(start, start + 200):
        if port in avoid:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
            except OSError:
                continue
            return port
    raise RuntimeError("Aucun port libre trouvé à partir de %d" % start)


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.settimeout(0.35)
            return sock.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.4)
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def async_delete(path: Path) -> None:
    """Déplace puis supprime en tâche de fond: le renommage est instantané."""
    if not path.exists():
        return
    cfg.TRASH_DIR.mkdir(parents=True, exist_ok=True)
    grave = cfg.TRASH_DIR / ("%s-%s" % (path.name, uuid.uuid4().hex[:8]))
    try:
        path.rename(grave)
    except OSError:
        grave = path  # volumes différents ou fichier verrouillé: suppression directe
    threading.Thread(target=shutil.rmtree, args=(grave,), kwargs={"ignore_errors": True}, daemon=True).start()


def purge_trash() -> None:
    if not cfg.TRASH_DIR.exists():
        return
    for child in cfg.TRASH_DIR.iterdir():
        threading.Thread(target=shutil.rmtree, args=(child,), kwargs={"ignore_errors": True}, daemon=True).start()


DEFAULT_META = {
    "name": "Speedrun",
    "version": "",
    "ram_mb": 0,
    "port": cfg.DEFAULT_PORT,
    "turbo": False,
    "seed_mode": "random",
    "seed": "",
    "created": 0.0,
    "resets": 0,
    "best_boot": None,
}


class ManagedServer:
    def __init__(self, sid: str, meta: dict) -> None:
        self.id = sid
        self.dir = cfg.SERVERS_DIR / sid
        self.meta = {**DEFAULT_META, **meta}
        self.lock = threading.RLock()
        self.slots: dict[str, ServerProcess] = {}
        self.live_label = MAIN
        self.standby_label: str | None = None
        self.proxy: TurboProxy | None = None
        self.run_started: float | None = None
        self.last_reset_ms: int | None = None
        self.deps_ready = False
        self.create_notes: list[str] = []
        self._java: str | None = None
        self._jar: Path | None = None

    # ------------------------------------------------------------ persistence
    @property
    def meta_path(self) -> Path:
        return self.dir / "panel.json"

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ManagedServer":
        meta = {}
        conf = path / "panel.json"
        if conf.exists():
            try:
                meta = json.loads(conf.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        meta.setdefault("name", path.name)
        return cls(path.name, meta)

    # ----------------------------------------------------------------- slots
    def slot(self, label: str) -> ServerProcess:
        with self.lock:
            if label not in self.slots:
                workdir = self.dir if label == MAIN else self.dir / ".slots" / label
                proc = ServerProcess(self.id, workdir, label)
                proc.bind(on_state=self._on_slot_state, on_line=self._on_slot_line)
                self.slots[label] = proc
            return self.slots[label]

    @property
    def live(self) -> ServerProcess:
        return self.slot(self.live_label)

    @property
    def standby(self) -> ServerProcess | None:
        return self.slot(self.standby_label) if self.standby_label else None

    def _on_slot_state(self, proc: ServerProcess) -> None:
        if proc.label == self.live_label and proc.state == RUNNING and self.run_started is None:
            self.run_started = proc.ready_at or time.time()
        if proc.state == RUNNING and proc.boot_seconds:
            best = self.meta.get("best_boot")
            if best is None or proc.boot_seconds < best:
                self.meta["best_boot"] = proc.boot_seconds
                self.save()
        BUS.emit("server", self.snapshot())

    def _proxy_event(self, message: str) -> None:
        BUS.emit("log", {"server": self.id, "slot": "proxy", "line": "[turbo] %s" % message, "lvl": "panel", "t": time.time()})

    def _on_slot_line(self, proc: ServerProcess, item: dict) -> None:
        if proc.label != self.live_label and proc.state != RUNNING:
            # Les logs du remplaçant en préchauffage restent discrets.
            if item["lvl"] not in ("error", "warn", "panel"):
                return
        BUS.emit(
            "log",
            {
                "server": self.id,
                "slot": proc.label,
                "n": item["n"],
                "line": item["line"],
                "lvl": item["lvl"],
                "t": item["t"],
            },
        )

    # ------------------------------------------------------------------ deps
    def resolve_version(self) -> str:
        if self.meta.get("version"):
            return self.meta["version"]
        version = deps.latest_release()
        self.meta["version"] = version
        self.save()
        return version

    def ensure_deps(self, report=None) -> tuple[str, Path]:
        """Java + jar disponibles. Télécharge en parallèle si nécessaire."""

        def say(msg, prog=None):
            if report:
                report(msg, prog)

        version = self.resolve_version()
        results: dict[str, object] = {}
        errors: list[str] = []

        def do_java():
            try:
                results["java"] = deps.ensure_java(
                    version,
                    on_progress=lambda p: say(
                        p.get("message", ""),
                        (p["done"] / p["total"] * 0.45) if p.get("total") else None,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                errors.append("Java: %s" % exc)

        def do_jar():
            try:
                results["jar"] = deps.ensure_server_jar(
                    version,
                    on_progress=lambda p: say(
                        p.get("message", ""),
                        (0.45 + p["done"] / p["total"] * 0.5) if p.get("total") else None,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                errors.append("Minecraft %s: %s" % (version, exc))

        say("Vérification de Java et du jar serveur...", 0.02)
        threads = [
            threading.Thread(target=do_java, daemon=True),
            threading.Thread(target=do_jar, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise RuntimeError(" | ".join(errors))

        self._java = str(results["java"])
        self._jar = Path(str(results["jar"]))
        self.deps_ready = True
        say("Dépendances prêtes", 0.96)
        return self._java, self._jar

    # -------------------------------------------------------- auto-réparation
    def _try_fix(self, proc: ServerProcess, ram: int, report=None) -> tuple[bool, int]:
        """Corrige les pannes connues au démarrage. Retourne (corrigé, nouvelle_ram)."""
        code = proc.fatal_code or ""

        def say(msg):
            if report:
                report(msg, None)
            BUS.emit("log", {"server": self.id, "line": "[panel] auto-réparation: %s" % msg, "lvl": "panel", "t": time.time()})

        if code == "UnsupportedClassVersionError":
            current = deps.java_version_of(self._java) if self._java else None
            for feature in JAVA_LADDER:
                if current and feature <= current:
                    continue
                say("installation de Java %d (le serveur en exige une plus récente)" % feature)
                try:
                    self._java = deps.install_java(feature)
                    return True, ram
                except Exception:
                    continue
            return False, ram

        if code in ("Unable to access jarfile", "Invalid or corrupt jarfile"):
            say("re-téléchargement du jar serveur")
            if self._jar:
                Path(self._jar).unlink(missing_ok=True)
            self._jar = deps.ensure_server_jar(self.resolve_version())
            return True, ram

        if code == "Could not reserve enough space" or code == "java.lang.OutOfMemoryError":
            reduced = max(1024, ram // 2)
            if reduced < ram:
                say("RAM réduite à %d Mo (allocation refusée par le système)" % reduced)
                self.meta["ram_mb"] = reduced
                self.save()
                return True, reduced
            return False, ram

        if code == "You need to agree to the EULA":
            say("acceptation de l'EULA")
            (proc.workdir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            return True, ram

        return False, ram

    def _launch_slot(self, proc: ServerProcess, port: int, ram: int, fresh_seed: bool,
                     report=None, timeout: float = 300.0) -> int:
        """Démarre un slot et réessaie une fois si la panne est réparable."""
        for attempt in (0, 1):
            self.prepare_dir(proc.workdir, port, fresh_seed=fresh_seed)
            proc.start(self._java, self._jar, ram, port)
            if proc.wait_ready(timeout):
                return ram
            fixed, ram = self._try_fix(proc, ram, report)
            if not fixed or attempt == 1:
                raise RuntimeError(proc.last_error or "Le serveur n'a pas fini de démarrer (délai dépassé).")
            if report:
                report("Nouvelle tentative de démarrage...", None)
        return ram

    # ------------------------------------------------------- filesystem prep
    def _seed_value(self) -> str:
        if self.meta.get("seed_mode") == "fixed":
            return str(self.meta.get("seed") or "")
        return ""  # vide = Minecraft tire une graine aléatoire

    def prepare_dir(self, path: Path, port: int, fresh_seed: bool = False) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "eula.txt").write_text(
            "#Accepte via MC Speedrun Panel\neula=true\n", encoding="utf-8"
        )
        overrides = {"server-port": port, "query.port": port}
        if fresh_seed:
            overrides["level-seed"] = self._seed_value()
        props.bootstrap(path / "server.properties", port, overrides)

        if path != self.dir:  # slot turbo: on recopie la config canonique
            for fname in ("whitelist.json", "ops.json", "banned-players.json", "banned-ips.json"):
                src = self.dir / fname
                if src.exists():
                    try:
                        shutil.copy2(src, path / fname)
                    except OSError:
                        pass
            canonical = props.read(self.dir / "server.properties")
            canonical.pop("server-port", None)
            canonical.pop("query.port", None)
            canonical["level-seed"] = self._seed_value()
            canonical["prevent-proxy-connections"] = "false"
            props.write(path / "server.properties", canonical)

    def world_dirs(self, path: Path) -> list[Path]:
        level = props.read(path / "server.properties").get("level-name", "world")
        names = {level, level + "_nether", level + "_the_end", "world", "world_nether", "world_the_end"}
        return [path / n for n in names if (path / n).exists()]

    def wipe_world(self, path: Path) -> None:
        for d in self.world_dirs(path):
            async_delete(d)
        for extra in ("crash-reports", "logs"):
            target = path / extra
            if target.exists():
                async_delete(target)

    # ---------------------------------------------------------------- actions
    def start(self, report=None) -> dict:
        with self.lock:
            if self.live.alive:
                return {"already": True}
        java, jar = self.ensure_deps(report)
        turbo = bool(self.meta.get("turbo"))
        public_port = int(self.meta["port"])
        ram = int(self.meta.get("ram_mb") or cfg.suggested_ram_mb())

        if report:
            report("Lancement du serveur...", 0.97)

        if turbo:
            return self._start_turbo(java, jar, ram, public_port, report)

        if port_busy(public_port):
            raise RuntimeError(
                "Le port %d est déjà utilisé. Arrêtez l'autre serveur ou changez de port." % public_port
            )
        self.live_label = MAIN
        self.standby_label = None
        proc = self.slot(MAIN)
        self.run_started = None
        self._launch_slot(proc, public_port, ram, fresh_seed=False, report=report)
        if report:
            report("Serveur prêt en %.1fs" % (proc.boot_seconds or 0), 1.0)
        BUS.emit("server", self.snapshot())
        return {"boot": proc.boot_seconds}

    def _start_turbo(self, java: str, jar: Path, ram: int, public_port: int, report=None) -> dict:
        back_a = free_port(public_port + 10, {public_port})
        back_b = free_port(back_a + 1, {public_port, back_a})

        self.live_label = SLOT_A
        self.standby_label = SLOT_B
        live = self.slot(SLOT_A)

        if self.proxy is None:
            self.proxy = TurboProxy(public_port, on_event=self._proxy_event)
        if not self.proxy.running:
            self.proxy.start()

        self.run_started = None
        if report:
            report("Génération du monde...", 0.98)
        ram = self._launch_slot(live, back_a, ram, fresh_seed=True, report=report)
        self.proxy.set_backend(back_a, drop=False)
        if report:
            report("Serveur prêt en %.1fs — préchauffage du remplaçant" % (live.boot_seconds or 0), 1.0)
        BUS.emit("server", self.snapshot())
        self._warm_standby(java, jar, ram, back_b)
        return {"boot": live.boot_seconds, "turbo": True}

    def _warm_standby(self, java: str, jar: Path, ram: int, port: int | None = None) -> None:
        """Démarre en fond un serveur de secours avec un monde neuf."""
        if not self.meta.get("turbo"):
            return
        label = self.standby_label or (SLOT_B if self.live_label == SLOT_A else SLOT_A)
        self.standby_label = label
        proc = self.slot(label)
        if proc.alive:
            return
        target_port = port or free_port(int(self.meta["port"]) + 11, {int(self.meta["port"]), self.live.port or 0})

        def worker():
            try:
                self.wipe_world(proc.workdir)
                self._launch_slot(proc, target_port, ram, fresh_seed=True)
                BUS.emit("server", self.snapshot())
            except Exception as exc:  # noqa: BLE001
                BUS.emit(
                    "log",
                    {"server": self.id, "slot": label, "line": "[panel] préchauffage échoué: %s" % exc, "lvl": "warn", "t": time.time()},
                )

        threading.Thread(target=worker, name="warm-%s" % self.id, daemon=True).start()

    def stop(self, report=None, graceful: bool = True) -> dict:
        if report:
            report("Arrêt en cours...", 0.2)
        procs = [p for p in self.slots.values() if p.alive]
        threads = []
        for proc in procs:
            t = threading.Thread(target=proc.stop, args=(graceful,), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(40)
        if self.proxy and self.proxy.running:
            self.proxy.stop()
        self.run_started = None
        if report:
            report("Serveur arrêté", 1.0)
        BUS.emit("server", self.snapshot())
        return {"stopped": len(procs)}

    def restart(self, report=None) -> dict:
        self.stop(report)
        time.sleep(0.4)
        return self.start(report)

    def reset(self, report=None) -> dict:
        """Monde neuf le plus vite possible. Cœur du workflow speedrun."""
        t0 = time.time()
        turbo = bool(self.meta.get("turbo"))
        java, jar = (self._java, self._jar) if self.deps_ready else self.ensure_deps(report)
        ram = int(self.meta.get("ram_mb") or cfg.suggested_ram_mb())

        if turbo and self.proxy and self.proxy.running:
            standby = self.standby
            if standby and standby.state == RUNNING and standby.alive:
                result = self._swap(standby, java, jar, ram, report)
                self.last_reset_ms = int((time.time() - t0) * 1000)
                self.meta["resets"] = int(self.meta.get("resets", 0)) + 1
                self.save()
                BUS.emit("server", self.snapshot())
                return {**result, "ms": self.last_reset_ms}
            if standby and standby.state == STARTING:
                if report:
                    report("Le remplaçant finit de démarrer...", 0.4)
                if standby.wait_ready(120):
                    result = self._swap(standby, java, jar, ram, report)
                    self.last_reset_ms = int((time.time() - t0) * 1000)
                    self.meta["resets"] = int(self.meta.get("resets", 0)) + 1
                    self.save()
                    BUS.emit("server", self.snapshot())
                    return {**result, "ms": self.last_reset_ms}

        # Reset à froid: on tue, on jette le monde, on relance.
        live = self.live
        live.set_state(RESETTING)
        BUS.emit("server", self.snapshot())
        if report:
            report("Arrêt immédiat...", 0.15)
        live.kill()
        if report:
            report("Suppression du monde...", 0.35)
        self.wipe_world(live.workdir)
        port = live.port or (int(self.meta["port"]) if not turbo else free_port(int(self.meta["port"]) + 10))
        if report:
            report("Nouveau monde en génération...", 0.5)
        self._launch_slot(live, port, ram, fresh_seed=True, report=report)
        self.run_started = live.ready_at
        if turbo and self.proxy and self.proxy.running:
            self.proxy.set_backend(port, drop=True)
            self._warm_standby(java, jar, ram)
        self.last_reset_ms = int((time.time() - t0) * 1000)
        self.meta["resets"] = int(self.meta.get("resets", 0)) + 1
        self.save()
        if report:
            report("Monde neuf prêt en %.1fs" % (self.last_reset_ms / 1000), 1.0)
        BUS.emit("server", self.snapshot())
        return {"cold": True, "ms": self.last_reset_ms, "boot": live.boot_seconds}

    def _swap(self, standby: ServerProcess, java: str, jar: Path, ram: int, report=None) -> dict:
        """Bascule instantanée sur le serveur de secours déjà chargé."""
        old = self.live
        # L'ancien monde part au recyclage : il ne doit pas passer pour un remplaçant prêt.
        old.set_state(RESETTING)
        if report:
            report("Bascule sur le monde préchargé...", 0.6)
        self.proxy.set_backend(standby.port, drop=True)
        self.live_label = standby.label
        self.standby_label = old.label
        self.run_started = time.time()
        standby.ready_at = time.time()

        def recycle():
            old.kill()
            self.wipe_world(old.workdir)
            self._warm_standby(java, jar, ram)

        threading.Thread(target=recycle, name="recycle-%s" % self.id, daemon=True).start()
        if report:
            report("Monde neuf actif — reconnectez-vous", 1.0)
        return {"instant": True, "boot": standby.boot_seconds}

    def command(self, cmd: str) -> bool:
        return self.live.send(cmd)

    def broadcast(self, cmd: str) -> int:
        """Envoie une commande à tous les slots vivants (live + remplaçant turbo)."""
        return sum(1 for proc in list(self.slots.values()) if proc.alive and proc.send(cmd))

    # ------------------------------------------------------- server.properties
    def settings_path(self) -> Path:
        return self.dir / "server.properties"

    def get_settings(self) -> dict:
        return props.effective(self.settings_path())

    def apply_settings(self, values: dict) -> dict:
        """Écrit les réglages et applique en direct ceux que Minecraft accepte à chaud."""
        clean, rejected = props.sanitize(values)
        if not clean:
            return {"applied": {}, "rejected": rejected, "restart_needed": [], "live": []}

        before = props.read(self.settings_path())
        changed = {k: v for k, v in clean.items() if before.get(k) != v}
        props.write(self.settings_path(), clean)

        live_applied, restart_needed = [], []
        running = self.live.alive
        for key, value in changed.items():
            command = LIVE_COMMANDS.get(key)
            if running and command:
                self.broadcast(command(value))
                live_applied.append(key)
            else:
                restart_needed.append(key)

        # Les slots turbo repartent d'une copie de la config canonique au prochain reset.
        for label, proc in list(self.slots.items()):
            if label != MAIN and proc.workdir.exists():
                slot_values = dict(clean)
                slot_values.pop("server-port", None)
                slot_values.pop("query.port", None)
                props.write(proc.workdir / "server.properties", slot_values)

        BUS.emit("server", self.snapshot())
        return {
            "applied": changed,
            "rejected": rejected,
            "restart_needed": restart_needed if running else [],
            "live": live_applied,
        }

    # ------------------------------------------------------- whitelist et OP
    def _list_path(self, which: str) -> Path:
        return self.dir / ("ops.json" if which == "ops" else "whitelist.json")

    def get_players(self) -> dict:
        settings = props.read(self.settings_path())
        return {
            "whitelist": players.read_list(self._list_path("whitelist")),
            "ops": players.read_list(self._list_path("ops")),
            "online_mode": settings.get("online-mode", "true") != "false",
            "whitelist_enabled": settings.get("white-list", "false") == "true",
            "enforce_whitelist": settings.get("enforce-whitelist", "false") == "true",
        }

    def edit_player(self, which: str, action: str, name: str) -> dict:
        """Ajoute ou retire un joueur de la whitelist ou des OP.

        Serveur allumé : on passe par la console, c'est Minecraft qui écrit ses
        fichiers, donc aucun risque de désynchronisation. Serveur éteint : on
        écrit le JSON nous-mêmes après avoir résolu l'UUID.
        """
        name = (name or "").strip()
        if not players.valid_name(name):
            raise ValueError("Pseudo invalide : 3 à 16 caractères, lettres, chiffres et _ uniquement.")
        which = "ops" if which == "ops" else "whitelist"
        path = self._list_path(which)
        online_mode = props.read(self.settings_path()).get("online-mode", "true") != "false"
        note = None

        if action == "remove":
            removed = players.remove_entry(path, name)
            if self.live.alive:
                self.broadcast(("deop %s" if which == "ops" else "whitelist remove %s") % name)
            if not removed and not self.live.alive:
                raise ValueError("%s n'est pas dans la liste." % name)
        else:
            result = players.add_entry(path, name, online_mode, op_level=4 if which == "ops" else None)
            if result["origin"] == "offline-fallback":
                note = ("Compte introuvable chez Mojang (hors ligne ?). UUID hors-ligne utilisé : "
                        "il ne fonctionnera que si le serveur est en online-mode=false.")
            if self.live.alive:
                self.broadcast(("op %s" if which == "ops" else "whitelist add %s") % name)

        if self.live.alive and which == "whitelist":
            self.broadcast("whitelist reload")

        # Le remplaçant turbo doit partir avec la même liste.
        for label, proc in list(self.slots.items()):
            if label != MAIN and proc.workdir.exists():
                try:
                    shutil.copy2(path, proc.workdir / path.name)
                except OSError:
                    pass

        payload = self.get_players()
        payload["note"] = note
        BUS.emit("server", self.snapshot())
        return payload

    def set_turbo(self, on: bool) -> None:
        was = bool(self.meta.get("turbo"))
        self.meta["turbo"] = bool(on)
        self.save()
        if was != bool(on) and self.live.alive:
            RUNNER.submit("restart", lambda rep: self.restart(rep), target=self.id)

    def clean(self, report=None) -> dict:
        """Remise à zéro complète: mondes, logs, caches, slots turbo. Config conservée."""
        self.stop(report)
        removed = 0
        keep = {"panel.json", "server.properties", "whitelist.json", "ops.json", "eula.txt", "banned-players.json", "banned-ips.json"}
        for child in list(self.dir.iterdir()):
            if child.name in keep:
                continue
            async_delete(child)
            removed += 1
        if report:
            report("%d éléments supprimés" % removed, 1.0)
        BUS.emit("server", self.snapshot())
        return {"removed": removed}

    def destroy(self) -> None:
        self.stop(graceful=False)
        if self.proxy:
            self.proxy.stop()
        async_delete(self.dir)

    # --------------------------------------------------------------- snapshot
    def snapshot(self) -> dict:
        live = self.live
        standby = self.standby
        state = live.state
        if not live.alive and state in (RUNNING, STARTING):
            state = STOPPED
        settings = props.read((self.dir if self.live_label == MAIN else live.workdir) / "server.properties")
        return {
            "id": self.id,
            "name": self.meta.get("name", self.id),
            "version": self.meta.get("version") or "?",
            "port": int(self.meta.get("port", cfg.DEFAULT_PORT)),
            "ram_mb": int(self.meta.get("ram_mb") or cfg.suggested_ram_mb()),
            "turbo": bool(self.meta.get("turbo")),
            "seed_mode": self.meta.get("seed_mode", "random"),
            "seed": self.meta.get("seed", ""),
            "resets": int(self.meta.get("resets", 0)),
            "best_boot": self.meta.get("best_boot"),
            "state": state,
            "live": live.snapshot(),
            "standby": standby.snapshot() if standby else None,
            "standby_ready": bool(standby and standby.state == RUNNING and standby.alive),
            "proxy": self.proxy.snapshot() if self.proxy else None,
            "run_seconds": round(time.time() - self.run_started, 1) if self.run_started else None,
            "last_reset_ms": self.last_reset_ms,
            "address": "%s:%d" % (local_ip(), int(self.meta.get("port", cfg.DEFAULT_PORT))),
            # Résumé seulement : l'éditeur complet passe par /api/servers/<id>/settings,
            # inutile de pousser 45 clés à chaque tick SSE.
            "settings": {k: settings.get(k, "") for k in SNAPSHOT_KEYS if k in settings},
            "deps_ready": self.deps_ready,
        }


class Manager:
    def __init__(self) -> None:
        self.servers: dict[str, ManagedServer] = {}
        self.lock = threading.RLock()
        self._load_all()
        threading.Thread(target=self._ticker, name="ticker", daemon=True).start()

    def _load_all(self) -> None:
        cfg.ensure_dirs()
        with self.lock:
            for path in sorted(cfg.SERVERS_DIR.iterdir() if cfg.SERVERS_DIR.exists() else []):
                if path.is_dir() and not path.name.startswith("."):
                    srv = ManagedServer.load(path)
                    self.servers[srv.id] = srv

    def _ticker(self) -> None:
        """Pouls régulier: rafraîchit les compteurs UI et purge les clients morts."""
        while True:
            time.sleep(1.0)
            try:
                if BUS.count:
                    BUS.emit("tick", {"servers": [s.snapshot() for s in list(self.servers.values())], "t": time.time()})
            except Exception:
                pass

    # -------------------------------------------------------------- registry
    def get(self, sid: str) -> ManagedServer:
        with self.lock:
            if sid not in self.servers:
                raise KeyError("Serveur inconnu: %s" % sid)
            return self.servers[sid]

    def list(self) -> list[dict]:
        with self.lock:
            return [s.snapshot() for s in self.servers.values()]

    def create(self, name: str, version: str = "", ram_mb: int = 0, port: int = 0, turbo: bool = False,
               seed: str = "", seed_mode: str = "random", settings: dict | None = None,
               whitelist: list | None = None, ops: list | None = None) -> ManagedServer:
        with self.lock:
            base = slugify(name)
            sid, n = base, 2
            while sid in self.servers or (cfg.SERVERS_DIR / sid).exists():
                sid = "%s-%d" % (base, n)
                n += 1
            used = {s.meta.get("port") for s in self.servers.values()}
            chosen = int(port) if port else cfg.DEFAULT_PORT
            while chosen in used:
                chosen += 1
            meta = {
                "name": name.strip() or sid,
                "version": version,
                "ram_mb": int(ram_mb) or cfg.suggested_ram_mb(),
                "port": chosen,
                "turbo": bool(turbo),
                "seed": seed,
                "seed_mode": seed_mode,
                "created": time.time(),
            }
            srv = ManagedServer(sid, meta)
            srv.save()
            srv.prepare_dir(srv.dir, chosen, fresh_seed=True)
            if settings:
                clean, _ = props.sanitize(settings)
                if clean:
                    props.write(srv.dir / "server.properties", clean)
            self.servers[sid] = srv

        notes = []
        online_mode = props.read(srv.settings_path()).get("online-mode", "true") != "false"
        for which, names in (("whitelist", whitelist or []), ("ops", ops or [])):
            path = srv._list_path(which)
            for player_name in names:
                try:
                    result = players.add_entry(path, str(player_name), online_mode,
                                               op_level=4 if which == "ops" else None)
                    if result["origin"] == "offline-fallback":
                        notes.append("%s : compte introuvable chez Mojang, UUID hors-ligne utilisé." % player_name)
                except ValueError as exc:
                    notes.append("%s : %s" % (player_name, exc))
        srv.create_notes = notes
        BUS.emit("servers", self.list())
        return srv

    def delete(self, sid: str) -> None:
        with self.lock:
            srv = self.servers.pop(sid, None)
        if srv:
            srv.destroy()
        BUS.emit("servers", self.list())

    def update(self, sid: str, patch: dict) -> ManagedServer:
        srv = self.get(sid)
        allowed = ("name", "version", "ram_mb", "port", "turbo", "seed", "seed_mode")
        for key in allowed:
            if key in patch:
                srv.meta[key] = patch[key]
        if "ram_mb" in patch:
            srv.meta["ram_mb"] = int(patch["ram_mb"] or 0) or cfg.suggested_ram_mb()
        if "port" in patch:
            srv.meta["port"] = int(patch["port"] or cfg.DEFAULT_PORT)
        srv.save()
        if patch.get("settings"):
            srv.apply_settings(patch["settings"])
        BUS.emit("server", srv.snapshot())
        return srv

    def shutdown_all(self) -> None:
        threads = []
        for srv in list(self.servers.values()):
            t = threading.Thread(target=srv.stop, kwargs={"graceful": True}, daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(30)


MANAGER: Manager | None = None


def manager() -> Manager:
    global MANAGER
    if MANAGER is None:
        MANAGER = Manager()
    return MANAGER
