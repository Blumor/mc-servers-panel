"""Point d'entrée: python -m mcpanel [--port 8765] [--no-browser]"""
from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
import webbrowser

from . import config as cfg
from .http_api import find_panel_port, serve
from .manager import local_ip, manager

BANNER = r"""
   __  __  ___    ___                    _
  |  \/  |/ __|  / __| _ __  ___ ___ _ _| |__ _  _ _ _
  | |\/| | (_ |  \__ \| '_ \/ -_) -_) '_| '_ \ || | ' \
  |_|  |_|\___|  |___/| .__/\___\___|_| |_.__/\_,_|_||_|
                      |_|   PANEL v%s
""" % cfg.APP_VERSION


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mcpanel", description=cfg.APP_NAME)
    parser.add_argument("--port", type=int, default=0, help="port du panel (défaut: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    parser.add_argument("--lan", action="store_true",
                        help="rendre le panel accessible depuis le réseau local (aucun mot de passe : "
                             "à n'utiliser que sur un réseau de confiance)")
    parser.add_argument("--host-info", action="store_true", help="affiche l'IP locale et quitte")
    args = parser.parse_args(argv)

    cfg.ensure_dirs()
    conf = cfg.load_conf()

    if args.host_info:
        print(local_ip())
        return 0

    wanted = args.port or int(conf.get("panel_port") or cfg.DEFAULT_PANEL_PORT)
    port = find_panel_port(wanted)
    if port != wanted:
        print("[panel] port %d occupé, bascule sur %d" % (wanted, port))
    cfg.save_conf({"panel_port": port})

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    httpd = serve(port, host)
    url = "http://localhost:%d/" % port

    print(BANNER)
    print("  Panel      : %s" % url)
    if args.lan:
        print("  Sur le LAN : http://%s:%d/  (ouvert, sans mot de passe)" % (local_ip(), port))
    print("  Serveurs   : %d configuré(s)" % len(manager().servers))
    print("  Arrêt      : Ctrl+C\n")

    if conf.get("auto_open_browser", True) and not args.no_browser:
        threading.Thread(target=_open_later, args=(url,), daemon=True).start()

    stop = threading.Event()

    def handle_sig(*_a):
        if stop.is_set():
            return
        stop.set()
        print("\n[panel] arrêt des serveurs Minecraft...")
        threading.Thread(target=_graceful_exit, args=(httpd,), daemon=True).start()

    signal.signal(signal.SIGINT, handle_sig)
    try:
        signal.signal(signal.SIGTERM, handle_sig)
    except (AttributeError, ValueError):
        pass

    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        handle_sig()
    finally:
        httpd.server_close()
    print("[panel] au revoir.")
    return 0


def _graceful_exit(httpd) -> None:
    try:
        manager().shutdown_all()
    finally:
        httpd.shutdown()


def _open_later(url: str) -> None:
    time.sleep(0.8)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
