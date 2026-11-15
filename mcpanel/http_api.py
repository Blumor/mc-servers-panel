"""Serveur HTTP du panel: API JSON + flux SSE + fichiers statiques.

ThreadingHTTPServer: chaque requête (et chaque flux SSE) vit dans son thread,
donc l'UI reste réactive pendant qu'un reset ou un téléchargement tourne.
"""
from __future__ import annotations

import ipaddress
import json
import mimetypes
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config as cfg
from . import backups, deps, props
from .bus import BUS
from .jobs import RUNNER
from .manager import local_ip, manager, port_busy

_public_ip_cache = {"ip": None, "at": 0.0}
_pub_lock = threading.Lock()


def public_ip() -> str | None:
    with _pub_lock:
        if _public_ip_cache["ip"] and time.time() - _public_ip_cache["at"] < 600:
            return _public_ip_cache["ip"]
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            ip = str(ipaddress.ip_address(deps.http_get(url, timeout=4).decode("utf-8").strip()))
        except Exception:  # injoignable, ou réponse qui n'est pas une IP (page d'erreur...)
            continue
        with _pub_lock:
            _public_ip_cache.update({"ip": ip, "at": time.time()})
        return ip
    return None


_HOSTNAME = socket.gethostname().lower()


def host_allowed(host_header: str | None) -> bool:
    """Parade au DNS rebinding : un site dont le domaine pointe soudain vers 127.0.0.1
    parlerait au panel comme une page locale. Seuls localhost, une IP ou le nom de cette
    machine sont acceptés."""
    host = (host_header or "").strip().lower()
    if not host:
        return True  # client sans en-tête Host : pas un navigateur
    name = host[1:].split("]", 1)[0] if host.startswith("[") else host.rsplit(":", 1)[0]
    if name == "localhost" or name.endswith(".localhost") or name in (_HOSTNAME, _HOSTNAME + ".local"):
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def system_info() -> dict:
    javas = deps.scan_java()
    return {
        "app": cfg.APP_NAME,
        "version": cfg.APP_VERSION,
        "os": cfg.os_slug(),
        "arch": cfg.arch_slug(),
        "ram_total_mb": cfg.total_ram_mb(),
        "ram_suggested_mb": cfg.suggested_ram_mb(),
        "java": javas,
        "java_best": max((j["major"] for j in javas), default=None),
        "jars": deps.local_jars(),
        "local_ip": local_ip(),
        "public_ip": _public_ip_cache["ip"],
        "clients": BUS.count,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MCPanel/" + cfg.APP_VERSION

    # ------------------------------------------------------------------ utils
    def log_message(self, fmt: str, *args) -> None:  # silence le bruit console
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", extra=None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json(self, data, code: int = 200) -> None:
        # Pas d'Access-Control-Allow-Origin : l'interface est servie par le panel lui-même,
        # et aucun autre site ne doit pouvoir lire l'état, les IP ou la console.
        self._send(code, json.dumps(data, default=str).encode("utf-8"))

    def fail(self, message: str, code: int = 400) -> None:
        self.json({"ok": False, "error": message}, code)

    def _same_origin(self) -> bool:
        """Parade au CSRF : une page web quelconque ne doit pas pouvoir piloter le panel.
        Les navigateurs envoient Origin sur POST/DELETE ; curl et les scripts, non."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urllib.parse.urlsplit(origin)
        return parsed.scheme in ("http", "https") and \
            parsed.netloc.lower() == (self.headers.get("Host") or "").strip().lower()

    def _guard(self, write: bool) -> bool:
        if not host_allowed(self.headers.get("Host")):
            reason = "Hôte non autorisé"
        elif write and not self._same_origin():
            reason = "Requête venant d'un autre site refusée"
        else:
            return True
        # Corps de requête non lu : la connexion est fermée plutôt que réutilisée, sinon ce
        # corps serait lu comme une nouvelle requête.
        self._send(403, json.dumps({"ok": False, "error": reason}).encode("utf-8"),
                   extra={"Connection": "close"})
        return False

    def body_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    # ------------------------------------------------------------------ verbs
    def do_OPTIONS(self) -> None:
        # Aucune autorisation CORS : le navigateur bloque les requêtes venant d'autres sites.
        if self._guard(write=False):
            self._send(204, b"", extra={"Allow": "GET,POST,PATCH,DELETE,OPTIONS"})

    def do_GET(self) -> None:
        if not self._guard(write=False):
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                return self._api_get(path, query)
            return self._static(path)
        except KeyError as exc:
            self.fail(str(exc), 404)
        except Exception as exc:  # noqa: BLE001
            self.fail(str(exc), 500)

    def do_POST(self) -> None:
        if not self._guard(write=True):
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            self._api_post(parsed.path, self.body_json())
        except KeyError as exc:
            self.fail(str(exc), 404)
        except Exception as exc:  # noqa: BLE001
            self.fail(str(exc), 500)

    do_PATCH = do_POST

    def do_DELETE(self) -> None:
        if not self._guard(write=True):
            return
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if len(parts) == 3 and parts[:2] == ["api", "servers"]:
                manager().delete(parts[2])
                return self.json({"ok": True})
            self.fail("Route inconnue", 404)
        except KeyError as exc:
            self.fail(str(exc), 404)
        except Exception as exc:  # noqa: BLE001
            self.fail(str(exc), 500)

    # -------------------------------------------------------------- API : GET
    def _api_get(self, path: str, query: dict) -> None:
        parts = [p for p in path.split("/") if p][1:]  # retire "api"

        if parts == ["state"]:
            return self.json({
                "ok": True,
                "servers": manager().list(),
                "system": system_info(),
                "jobs": RUNNER.recent(),
                "conf": cfg.load_conf(),
            })

        if parts == ["events"]:
            return self._sse()

        if parts == ["ping"]:  # léger : sert à repérer un panel déjà lancé
            return self.json({"ok": True, "app": cfg.APP_NAME, "version": cfg.APP_VERSION})

        if parts == ["system"]:
            return self.json({"ok": True, "system": system_info()})

        if parts == ["versions"]:
            kind = (query.get("kind") or ["release"])[0]
            limit = int((query.get("limit") or ["60"])[0])
            return self.json({
                "ok": True,
                "latest": deps.latest_release(),
                "versions": deps.list_versions(kind, limit),
            })

        if parts == ["ip"]:
            return self.json({"ok": True, "local": local_ip(), "public": public_ip()})

        if parts == ["properties"]:
            kind = (query.get("kind") or ["speedrun"])[0]
            return self.json({"ok": True, "schema": props.schema_payload(), "defaults": props.defaults_for(kind)})

        if len(parts) == 2 and parts[0] == "jobs":
            job = RUNNER.get(parts[1])
            if not job:
                raise KeyError("Job inconnu")
            return self.json({"ok": True, "job": job.as_dict()})

        if len(parts) >= 2 and parts[0] == "servers":
            srv = manager().get(parts[1])
            if len(parts) == 2:
                return self.json({"ok": True, "server": srv.snapshot()})
            if parts[2] == "logs":
                since = int((query.get("since") or ["0"])[0])
                slot = (query.get("slot") or [srv.live_label])[0]
                proc = srv.slot(slot)
                lines = proc.log.since(since) if since else proc.log.tail(400)
                return self.json({"ok": True, "lines": lines, "seq": proc.log.seq})
            if parts[2] == "settings":
                return self.json({
                    "ok": True,
                    "settings": srv.get_settings(),
                    "raw": props.read(srv.settings_path()),
                    "schema": props.schema_payload(),
                    "running": srv.live.alive,
                })
            if parts[2] == "players":
                return self.json({"ok": True, **srv.get_players()})
            if parts[2] == "backups":
                return self.json({"ok": True, "backups": backups.list_backups(srv.id)})
            if parts[2] == "usage":
                return self.json({"ok": True, **srv.usage()})

        raise KeyError("Route inconnue: %s" % path)

    # ------------------------------------------------------------- API : POST
    def _api_post(self, path: str, body: dict) -> None:
        parts = [p for p in path.split("/") if p][1:]
        mgr = manager()

        if parts == ["servers"]:
            srv = mgr.create(
                name=body.get("name") or "Speedrun",
                version=body.get("version") or "",
                ram_mb=int(body.get("ram_mb") or 0),
                port=int(body.get("port") or 0),
                turbo=bool(body.get("turbo")),
                seed=body.get("seed") or "",
                seed_mode=body.get("seed_mode") or "random",
                settings=body.get("settings") or None,
                whitelist=body.get("whitelist") or None,
                ops=body.get("ops") or None,
                kind=body.get("kind") or "speedrun",
                auto_backup_hours=float(body.get("auto_backup_hours") or 0),
            )
            if body.get("start"):
                RUNNER.submit("start", lambda rep: srv.start(rep), target=srv.id)
            return self.json({"ok": True, "server": srv.snapshot(), "notes": srv.create_notes}, 201)

        if parts == ["conf"]:
            return self.json({"ok": True, "conf": cfg.save_conf(body)})

        if parts == ["java", "install"]:
            feature = int(body.get("feature") or 21)
            job = RUNNER.submit(
                "java",
                lambda rep: deps.install_java(
                    feature,
                    on_progress=lambda p: rep(
                        p.get("message", ""),
                        (p["done"] / p["total"]) if p.get("total") else None,
                    ),
                ),
                target="deps",
            )
            return self.json({"ok": True, "job": job.as_dict()}, 202)

        if parts == ["jar", "download"]:
            version = body.get("version") or deps.latest_release()
            job = RUNNER.submit(
                "jar",
                lambda rep: str(deps.ensure_server_jar(
                    version,
                    on_progress=lambda p: rep(
                        p.get("message", ""),
                        (p["done"] / p["total"]) if p.get("total") else None,
                    ),
                )),
                target="deps",
            )
            return self.json({"ok": True, "job": job.as_dict()}, 202)

        if parts == ["trash", "purge"]:
            from .manager import purge_trash

            purge_trash()
            return self.json({"ok": True})

        if parts == ["quit"]:
            threading.Thread(target=_shutdown_soon, daemon=True).start()
            return self.json({"ok": True, "message": "Extinction du panel..."})

        if len(parts) >= 2 and parts[0] == "servers":
            srv = mgr.get(parts[1])
            action = parts[2] if len(parts) > 2 else "update"

            if action == "update":
                updated, result = mgr.update(srv.id, body)
                return self.json({
                    "ok": True,
                    "server": updated.snapshot(),
                    "restart_needed": result.get("restart_needed", []),
                    "rejected": result.get("rejected", []),
                })

            # dedupe : un double clic ou une touche maintenue ne lance pas deux resets
            # d'affilée (le second effaçait le monde tout neuf).
            if action == "start":
                job = RUNNER.submit("start", lambda rep: srv.start(rep), target=srv.id, dedupe=True)
                return self.json({"ok": True, "job": job.as_dict()}, 202)

            if action == "stop":
                graceful = body.get("graceful", True)
                job = RUNNER.submit("stop", lambda rep: srv.stop(rep, graceful=graceful), target=srv.id,
                                    dedupe=True)
                return self.json({"ok": True, "job": job.as_dict()}, 202)

            if action == "restart":
                job = RUNNER.submit("restart", lambda rep: srv.restart(rep), target=srv.id, dedupe=True)
                return self.json({"ok": True, "job": job.as_dict()}, 202)

            if action in ("reset", "turbo") and srv.kind != "speedrun":
                return self.fail("Reset et mode Turbo n'existent que pour les serveurs speedrun.")

            if action == "reset":
                job = RUNNER.submit("reset", lambda rep: srv.reset(rep), target=srv.id, dedupe=True)
                return self.json({"ok": True, "job": job.as_dict()}, 202)

            if action == "clean":
                job = RUNNER.submit("clean", lambda rep: srv.clean(rep), target=srv.id, dedupe=True)
                return self.json({"ok": True, "job": job.as_dict()}, 202)

            if action == "command":
                cmd = (body.get("command") or "").strip()
                if not cmd:
                    return self.fail("Commande vide")
                ok = srv.command(cmd)
                return self.json({"ok": ok, "error": None if ok else "Serveur non démarré"})

            if action == "turbo":
                srv.set_turbo(bool(body.get("enabled")))
                return self.json({"ok": True, "server": srv.snapshot()})

            if action == "settings":
                result = srv.apply_settings(body.get("settings") or {})
                return self.json({"ok": True, "settings": srv.get_settings(), **result})

            if action == "backups":
                op = parts[3] if len(parts) > 3 else "create"
                if op == "create":
                    job = RUNNER.submit("backup", lambda rep: srv.backup(rep, "manuel"), target=srv.id, dedupe=True)
                    return self.json({"ok": True, "job": job.as_dict()}, 202)
                name = str(body.get("name") or "")
                if op == "restore":
                    backups._path(srv.id, name)  # nom vérifié tout de suite, erreur lisible
                    job = RUNNER.submit("restore", lambda rep: srv.restore(name, rep), target=srv.id, dedupe=True)
                    return self.json({"ok": True, "job": job.as_dict()}, 202)
                if op == "delete":
                    try:
                        backups.delete(srv.id, name)
                    except ValueError as exc:
                        return self.fail(str(exc))
                    return self.json({"ok": True, "backups": backups.list_backups(srv.id)})
                return self.fail("Action de sauvegarde inconnue : %s" % op)

            if action == "players":
                which = body.get("list") or "whitelist"
                move = body.get("action") or "add"
                if which not in ("whitelist", "ops"):
                    return self.fail("Liste inconnue : %s" % which)
                if move not in ("add", "remove"):
                    return self.fail("Action inconnue : %s" % move)
                try:
                    return self.json({"ok": True, **srv.edit_player(which, move, body.get("player") or "")})
                except ValueError as exc:
                    return self.fail(str(exc))

        raise KeyError("Route inconnue: %s" % path)

    # -------------------------------------------------------------------- SSE
    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        sub = BUS.subscribe()
        try:
            self._chunk("retry: 1500\n\n")
            self._chunk("event: hello\ndata: %s\n\n" % json.dumps({
                "servers": manager().list(),
                "system": system_info(),
            }, default=str))
            last_ping = time.time()
            while True:
                payload = sub.get(timeout=1.0)
                if payload:
                    self._chunk(payload)
                elif time.time() - last_ping > 12:
                    last_ping = time.time()
                    self._chunk(": ping\n\n")
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            pass
        finally:
            BUS.unsubscribe(sub)

    def _chunk(self, text: str) -> None:
        data = text.encode("utf-8")
        self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")
        self.wfile.flush()

    # ----------------------------------------------------------------- static
    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            target = cfg.WEB_DIR / "index.html"
        else:
            web_root = cfg.WEB_DIR.resolve()
            target = (web_root / urllib.parse.unquote(path.lstrip("/"))).resolve()
            if not target.is_relative_to(web_root):  # startswith laissait passer « web-xxx/ »
                return self.fail("Chemin interdit", 403)
        if not target.exists() or target.is_dir():
            return self.fail("Fichier introuvable: %s" % path, 404)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # remplacé par tune_listen_socket (SO_REUSEADDR piège sous Windows)
    request_queue_size = 64

    def server_bind(self) -> None:
        cfg.tune_listen_socket(self.socket)
        super().server_bind()


_server_ref: dict = {"server": None}


def _shutdown_soon() -> None:
    time.sleep(0.3)
    manager().shutdown_all()
    srv = _server_ref.get("server")
    if srv:
        srv.shutdown()


def serve(port: int, host: str = "127.0.0.1") -> PanelServer:
    """host reste sur la boucle locale par defaut: le panel pilote des processus,
    il n'a rien a faire ouvert sur le reseau sans que l'utilisateur le demande."""
    cfg.ensure_dirs()
    manager()  # charge les serveurs existants
    httpd = PanelServer((host, port), Handler)
    _server_ref["server"] = httpd
    return httpd


def find_panel_port(preferred: int) -> int:
    for candidate in [preferred] + [preferred + i for i in range(1, 30)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            cfg.tune_listen_socket(sock)
            try:
                sock.bind(("0.0.0.0", candidate))
                return candidate
            except OSError:
                continue
    raise RuntimeError("Aucun port libre pour le panel")
