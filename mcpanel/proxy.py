"""Proxy TCP transparent pour le mode TURBO.

Les joueurs se connectent toujours au même port (25565). Derrière, le panel
garde deux serveurs: le vivant et un remplaçant déjà démarré avec un monde
neuf. Un reset bascule le proxy sur le remplaçant, ce qui évite d'attendre le
démarrage de la JVM et la génération du monde: reconnexion en ~1 seconde.

Note: le serveur voit alors 127.0.0.1 comme IP client, il faut donc
`prevent-proxy-connections=false` dans server.properties (le panel le force).
"""
from __future__ import annotations

import socket
import threading
import time

from . import config as cfg

BUFFER = 65536


class TurboProxy:
    def __init__(self, listen_port: int, on_event=None) -> None:
        self.listen_port = listen_port
        self.backend_port: int | None = None
        self.on_event = on_event
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._conns: set[socket.socket] = set()
        self._lock = threading.RLock()
        self._running = threading.Event()
        self.connections_served = 0
        self.last_swap: float | None = None
        self.error: str | None = None

    # ----------------------------------------------------------------- cycle
    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cfg.tune_listen_socket(sock)
            try:
                sock.bind(("0.0.0.0", self.listen_port))
            except OSError as exc:
                sock.close()
                self.error = "Port %d occupé, impossible d'activer le turbo (%s)" % (self.listen_port, exc)
                raise RuntimeError(self.error) from exc
            sock.listen(64)
            sock.settimeout(0.5)
            self._sock = sock
            self.error = None
            self._running.set()
            self._thread = threading.Thread(target=self._accept_loop, name="turbo-accept", daemon=True)
            self._thread.start()
        self._emit("Proxy turbo actif sur le port %d" % self.listen_port)

    def stop(self) -> None:
        self._running.clear()
        with self._lock:
            sock, self._sock = self._sock, None
            thread, self._thread = self._thread, None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)  # réveille accept() tout de suite
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        # Tant que la boucle d'accept attend encore sur l'ancien socket, le noyau le garde
        # ouvert : relancer le proxy juste derrière (restart, reset) échouait « port occupé ».
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)
        self.drop_clients()

    def set_backend(self, port: int | None, drop: bool = True) -> None:
        """Bascule la cible. drop=True coupe les sessions en cours (reconnexion client)."""
        with self._lock:
            changed = port != self.backend_port
            self.backend_port = port
            if changed:
                self.last_swap = time.time()
        if changed and drop:
            self.drop_clients()
            self._emit("Bascule turbo vers le backend :%s" % port)

    def drop_clients(self) -> None:
        with self._lock:
            conns = list(self._conns)
            self._conns.clear()
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    # ------------------------------------------------------------------ loop
    def _accept_loop(self) -> None:
        while self.running:
            sock = self._sock
            if not sock:
                break
            try:
                client, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    time.sleep(0.2)
                continue
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        backend = self.backend_port
        if not backend:
            self._close(client)
            return
        try:
            upstream = socket.create_connection(("127.0.0.1", backend), timeout=8)
        except OSError:
            self._close(client)
            return
        # Le délai ne vaut que pour la connexion : laissé en place, il coupait la session
        # dès que le serveur se taisait 8 s (lag, chargement d'un pack de ressources...).
        upstream.settimeout(None)

        for s in (client, upstream):
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass

        with self._lock:
            self._conns.add(client)
            self._conns.add(upstream)
            self.connections_served += 1

        t1 = threading.Thread(target=self._pipe, args=(client, upstream), daemon=True)
        t2 = threading.Thread(target=self._pipe, args=(upstream, client), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with self._lock:
            self._conns.discard(client)
            self._conns.discard(upstream)
        self._close(client)
        self._close(upstream)

    @staticmethod
    def _pipe(src: socket.socket, dst: socket.socket) -> None:
        try:
            while True:
                data = src.recv(BUFFER)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    @staticmethod
    def _close(sock: socket.socket) -> None:
        try:
            sock.close()
        except OSError:
            pass

    def _emit(self, message: str) -> None:
        if self.on_event:
            self.on_event(message)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "listen_port": self.listen_port,
            "backend_port": self.backend_port,
            "connections": self.connections_served,
            "error": self.error,
        }
