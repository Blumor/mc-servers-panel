"""Pilotage d'un processus serveur Minecraft: I/O console, états, diagnostics.

Le serveur tourne en `nogui` avec stdin/stdout branchés sur le panel: on peut
donc envoyer n'importe quelle commande console et lire les logs en direct,
sans dépendre d'une fenêtre Java ni de taskkill.
"""
from __future__ import annotations

import collections
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from . import config as cfg
from .bus import BUS

STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
STOPPING = "stopping"
RESETTING = "resetting"
INSTALLING = "installing"
ERROR = "error"

# Pseudo tel qu'écrit dans les logs. Volontairement large : un compte crack n'est pas tenu
# à [A-Za-z0-9_]{3,16}. Exclure espaces, < > [ ] suffit à écarter le chat (« <Steve> ... »)
# et le préfixe « [Not Secure] » des messages non signés.
_NAME = r"[^\s<>\[\]]{1,16}"

# « ]:? » : avant la 1.7, les logs s'écrivent « [INFO] Steve joined the game », sans deux-points.
RE_DONE = re.compile(r"Done \(([\d.,]+)s\)!")  # virgule si la JVM formate selon la locale
RE_JOIN = re.compile(r"]:? (%s)(?: \(formerly known as %s\))? joined the game" % (_NAME, _NAME))
RE_LEAVE = re.compile(r"]:? (%s) left the game" % _NAME)
RE_PROGRESS = re.compile(r"Preparing spawn area: (\d+)%")
RE_SEED = re.compile(r"Seed: \[?(-?\d+)\]?")
RE_DEATH = re.compile(
    r"]:? (%s) (was |died|drowned|blew up|fell|burned|starved|suffocated|"
    r"withered|hit the ground|went up in flames|tried to swim in lava|discovered the floor)" % _NAME
)

# Messages d'erreur Java -> explication actionnable côté UI.
FATAL_HINTS = (
    ("FAILED TO BIND TO PORT", "Le port est déjà utilisé par un autre programme. Changez de port ou arrêtez l'autre serveur."),
    ("You need to agree to the EULA", "EULA non acceptée. Le panel la réécrit au prochain démarrage."),
    ("java.lang.OutOfMemoryError", "Mémoire insuffisante. Augmentez la RAM allouée au serveur."),
    ("UnsupportedClassVersionError", "Version de Java trop ancienne pour ce Minecraft. Le panel va installer la bonne."),
    ("Unable to access jarfile", "Le fichier server.jar est introuvable ou corrompu. Il sera re-téléchargé."),
    ("Invalid or corrupt jarfile", "Le server.jar est corrompu. Il sera re-téléchargé."),
    ("Could not reserve enough space", "RAM demandée trop élevée pour ce système. Réduisez l'allocation."),
    ("Failed to start the minecraft server", "Le serveur n'a pas démarré, consultez la console ci-dessous."),
)


def _flags(ram_mb: int) -> list[str]:
    """Flags JVM orientés démarrage rapide + GC court (dérivés des flags Aikar).

    Pas de -XX:+AlwaysPreTouch : utile sur un serveur qui tourne des semaines, il fait
    toucher tout le tas au lancement. Ici chaque reset relance une JVM : ça rallongeait
    le boot et, en Turbo, occupait d'emblée toute la RAM des deux serveurs.
    """
    args = [
        "-Xms%dM" % ram_mb,
        "-Xmx%dM" % ram_mb,
        "-XX:+UseG1GC",
        "-XX:+ParallelRefProcEnabled",
        "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:G1HeapWastePercent=5",
        "-XX:G1MixedGCCountTarget=4",
        "-XX:G1MixedGCLiveThresholdPercent=90",
        "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32",
        "-XX:+PerfDisableSharedMem",
        "-XX:MaxTenuringThreshold=1",
        "-Dusing.aikars.flags=https://mcflags.emc.gs",
        "-Daikars.new.flags=true",
        "-Dfile.encoding=UTF-8",
        "-Djava.awt.headless=true",
    ]
    if ram_mb >= 12288:
        args += ["-XX:G1NewSizePercent=40", "-XX:G1MaxNewSizePercent=50", "-XX:G1HeapRegionSize=16M", "-XX:InitiatingHeapOccupancyPercent=15"]
    else:
        args += ["-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M", "-XX:InitiatingHeapOccupancyPercent=15"]
    return args


class LogRing:
    """Buffer circulaire numéroté: permet à un client de reprendre où il en était."""

    def __init__(self, size: int = 4000) -> None:
        self._buf: collections.deque = collections.deque(maxlen=size)
        self._lock = threading.Lock()
        self._seq = 0

    def add(self, line: str, level: str = "info") -> dict:
        with self._lock:
            self._seq += 1
            item = {"n": self._seq, "t": time.time(), "line": line, "lvl": level}
            self._buf.append(item)
            return item

    def since(self, seq: int, limit: int = 1500) -> list[dict]:
        with self._lock:
            return [x for x in self._buf if x["n"] > seq][-limit:]

    def tail(self, count: int = 300) -> list[dict]:
        with self._lock:
            return list(self._buf)[-count:]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    @property
    def seq(self) -> int:
        with self._lock:
            return self._seq


class ServerProcess:
    """Un processus java. Réutilisable: start/stop/start sans recréer l'objet."""

    def __init__(self, server_id: str, workdir: Path, label: str = "main") -> None:
        self.server_id = server_id
        self.workdir = workdir
        self.label = label
        self.proc: subprocess.Popen | None = None
        self.state = STOPPED
        self.log = LogRing()
        self.players: set[str] = set()
        self.ready_at: float | None = None
        self.started_at: float | None = None
        self.boot_seconds: float | None = None
        self.seed: str | None = None
        self.spawn_progress = 0
        self.last_error: str | None = None
        self.fatal_code: str | None = None
        self.port: int | None = None
        self._ready = threading.Event()
        self._exited = threading.Event()
        self._lock = threading.RLock()
        self._pump: threading.Thread | None = None
        self._on_state = None
        self._on_line = None

    # ---------------------------------------------------------------- states
    def bind(self, on_state=None, on_line=None) -> None:
        self._on_state = on_state
        self._on_line = on_line

    def set_state(self, state: str, error: str | None = None, only_for=None) -> None:
        """only_for : ne change l'état que si ce processus est toujours le processus courant."""
        with self._lock:
            if only_for is not None and self.proc is not only_for:
                return
            if self.state == state and error == self.last_error:
                return
            self.state = state
            if error is not None:
                self.last_error = error
            if state == STOPPED:
                self.players.clear()
                self.spawn_progress = 0
        if self._on_state:
            self._on_state(self)

    def emit_line(self, line: str, level: str = "info") -> None:
        item = self.log.add(line, level)
        if self._on_line:
            self._on_line(self, item)

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def uptime(self) -> float:
        return time.time() - self.started_at if self.started_at and self.alive else 0.0

    # ---------------------------------------------------------------- launch
    def start(self, java_bin: str, jar: Path, ram_mb: int, port: int, extra_args=None) -> None:
        with self._lock:
            if self.alive:
                raise RuntimeError("Le serveur %s tourne déjà." % self.server_id)
            self.workdir.mkdir(parents=True, exist_ok=True)
            # Événements neufs à chaque lancement : le thread de lecture du processus tué
            # juste avant (reset) ne peut plus réveiller ni dérégler celui-ci.
            self._ready = threading.Event()
            self._exited = threading.Event()
            self.players.clear()
            self.ready_at = None
            self.boot_seconds = None
            self.spawn_progress = 0
            self.last_error = None
            self.fatal_code = None
            self.seed = None
            self.port = port
            self.started_at = time.time()

            cmd = [java_bin] + _flags(ram_mb) + list(extra_args or []) + ["-jar", str(jar), "nogui"]
            self.emit_line("[panel] %s" % " ".join([Path(cmd[0]).name] + cmd[1:][-4:]), "panel")

            popen_kwargs = {
                "cwd": str(self.workdir),
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "bufsize": 0,
            }
            if cfg.IS_WINDOWS:
                popen_kwargs["creationflags"] = 0x08000000 | 0x00000200  # NO_WINDOW | NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True

            try:
                proc = subprocess.Popen(cmd, **popen_kwargs)
            except OSError as exc:
                self.set_state(ERROR, "Lancement impossible: %s" % exc)
                raise
            self.proc = proc

            self.set_state(STARTING)
            self._pump = threading.Thread(
                target=self._pump_output,
                args=(proc, self._ready, self._exited),
                name="mc-log-%s-%s" % (self.server_id, self.label),
                daemon=True,
            )
            self._pump.start()

    def _pump_output(self, proc: subprocess.Popen, ready: threading.Event, exited: threading.Event) -> None:
        assert proc.stdout
        try:
            for raw in iter(proc.stdout.readline, b""):
                if self.proc is not proc:
                    continue  # processus déjà remplacé : on vide le tube sans toucher à l'état
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line:
                    self._consume(line, proc, ready)
        except (OSError, ValueError):
            pass
        finally:
            code = proc.wait()
            # État final posé avant de réveiller wait_ready() / kill() : ils lisent l'état.
            if self.state not in (STOPPING, RESETTING) and code != 0:
                hint = self.last_error or "Le serveur s'est arrêté (code %s)." % code
                if self.proc is proc:
                    self.emit_line("[panel] Arrêt inattendu (code %s)" % code, "error")
                self.set_state(ERROR, hint, only_for=proc)
            else:
                self.set_state(STOPPED, only_for=proc)
            ready.set()
            exited.set()

    def _consume(self, line: str, proc: subprocess.Popen | None = None,
                 ready: threading.Event | None = None) -> None:
        level = "info"
        low = line.lower()
        if "/error" in low or "exception" in low or "severe" in low:
            level = "error"
        elif "/warn" in low:
            level = "warn"

        for needle, hint in FATAL_HINTS:
            if needle.lower() in low:
                self.last_error = hint
                self.fatal_code = needle
                level = "error"
                break

        m = RE_PROGRESS.search(line)
        if m:
            self.spawn_progress = int(m.group(1))

        m = RE_DONE.search(line)
        if m:
            self.boot_seconds = float(m.group(1).replace(",", "."))
            self.ready_at = time.time()
            self.spawn_progress = 100
            self.set_state(RUNNING, only_for=proc)
            (ready or self._ready).set()

        m = RE_SEED.search(line)
        if m:
            self.seed = m.group(1)

        m = RE_JOIN.search(line)
        if m:
            self.players.add(m.group(1))
            level = "join"
            if self._on_state:
                self._on_state(self)
        m = RE_LEAVE.search(line)
        if m:
            self.players.discard(m.group(1))
            level = "leave"
            if self._on_state:
                self._on_state(self)
        if RE_DEATH.search(line) and " joined " not in line and " left " not in line:
            level = "death"

        self.emit_line(line, level)

    def wait_ready(self, timeout: float) -> bool:
        ready = self._ready
        return ready.wait(timeout) and self.state == RUNNING

    # ------------------------------------------------------------------ stop
    def send(self, command: str) -> bool:
        with self._lock:
            if not self.alive or not self.proc or not self.proc.stdin:
                return False
            try:
                self.proc.stdin.write((command.rstrip("\n") + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except (OSError, ValueError):
                return False
        self.emit_line("> %s" % command, "cmd")
        return True

    def stop(self, graceful: bool = True, timeout: float = 25.0) -> None:
        """graceful=False: kill immédiat (utilisé pour les resets, le monde part à la poubelle)."""
        with self._lock:
            if not self.alive:
                self.set_state(STOPPED)
                return
            self.set_state(STOPPING)
            exited = self._exited
        if graceful:
            if self.send("stop"):
                if exited.wait(timeout):
                    return
            self.emit_line("[panel] Arrêt propre trop lent, passage en force.", "warn")
        self.kill()

    def kill(self) -> None:
        with self._lock:
            proc, exited = self.proc, self._exited
        if not proc or proc.poll() is not None:
            self.set_state(STOPPED)
            return
        try:
            if cfg.IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                    timeout=10,
                )
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except (OSError, ProcessLookupError):
                    proc.kill()
        except (OSError, subprocess.SubprocessError):
            try:
                proc.kill()
            except OSError:
                pass
        exited.wait(8)
        self.set_state(STOPPED, only_for=proc)

    def snapshot(self) -> dict:
        return {
            "label": self.label,
            "state": self.state,
            "alive": self.alive,
            "pid": self.proc.pid if self.alive and self.proc else None,
            "port": self.port,
            "players": sorted(self.players),
            "player_count": len(self.players),
            "uptime": round(self.uptime, 1),
            "ready_since": round(time.time() - self.ready_at, 1) if self.ready_at else None,
            "boot_seconds": self.boot_seconds,
            "spawn_progress": self.spawn_progress,
            "seed": self.seed,
            "error": self.last_error,
            "log_seq": self.log.seq,
        }
