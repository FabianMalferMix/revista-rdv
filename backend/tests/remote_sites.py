"""Un internet de mentira para el descargador de imágenes de otro sitio (config/remote_fetch.py).

Cada nombre resuelve a las direcciones que se le dan, y cada conexión es un par de sockets locales
con un hilo que contesta como lo haría el sitio. Solo se salta el TLS: la petición, la lectura de
la respuesta, los topes y el vigilante del plazo son los de verdad. Lo pide la fixture
`remote_sites` (backend/conftest.py).
"""

import socket
import threading
import time
from urllib.parse import urlsplit

from config import remote_fetch

# Una dirección de internet, para los sitios que no dicen otra.
PUBLIC = "93.184.215.14"


def response(body=b"", status="200 OK", headers=None):
    """Una respuesta HTTP entera: por omisión, un PNG con su Content-Length. Una cabecera en None
    no se manda."""
    fields = {"Content-Type": "image/png", "Content-Length": str(len(body)), **(headers or {})}
    head = [f"HTTP/1.1 {status}"] + [f"{k}: {v}" for k, v in fields.items() if v is not None]
    return ("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + body


def redirect(location, status="302 Found"):
    return response(status=status, headers={"Location": location, "Content-Type": None})


def drip(head, every=0.1, seconds=5):
    """Una respuesta que llega byte a byte, sin terminar: las cabeceras `head` y después un byte
    cada `every` segundos, hasta que el descargador corta o pasan `seconds`."""

    def send(server):
        server.sendall(head)
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            server.sendall(b"x")
            time.sleep(every)

    return send


class _Socket(socket.socket):
    """El lado del descargador: un socket que hace como si ya hubiera saludado por TLS."""

    def do_handshake(self):
        pass


class FakeInternet:
    def __init__(self, monkeypatch):
        self.addresses = {}  # nombre → sus direcciones
        self.answers = {}  # "https://nombre/ruta?consulta" → bytes, o función(socket del sitio)
        self.refused = set()  # direcciones donde nadie contesta
        self.hanging = set()  # nombres cuya resolución no termina hasta el final de la prueba
        self.lookups = []  # los nombres que se resolvieron
        self.connections = []  # (dirección, puerto, plazo) de cada conexión
        self.certificates_for = []  # el nombre para el que se pidió cada certificado
        self.requests = []  # (Host, lo pedido, cabeceras) de cada petición
        self._released = threading.Event()
        self._threads = []
        self._sockets = []
        monkeypatch.setattr(remote_fetch, "_getaddrinfo", self._getaddrinfo)
        monkeypatch.setattr(remote_fetch, "_create_connection", self._create_connection)
        monkeypatch.setattr(remote_fetch, "_wrap", self._wrap)

    def serve(self, url, answer, address=PUBLIC):
        """Que `url` conteste `answer`. Su nombre resuelve a `address` si no tenía direcciones."""
        self.addresses.setdefault(urlsplit(url).hostname, [address])
        self.answers[url] = answer

    def close(self):
        self._released.set()
        for sock in self._sockets:
            sock.close()
        for thread in self._threads:
            thread.join(5)
        assert not any(thread.is_alive() for thread in self._threads), "un sitio no terminó"

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _getaddrinfo(self, host, port, type=0, **kwargs):
        self.lookups.append(host)
        if host in self.hanging:
            self._released.wait(10)
            raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")
        if host not in self.addresses:
            # Una dirección escrita con números (127.1, 2130706433…) se lee como lo hace el
            # sistema, sin preguntar a nadie; un nombre que no se dio no existe.
            return socket.getaddrinfo(host, port, type=type, flags=socket.AI_NUMERICHOST)
        return [
            (socket.AF_INET6, type, 6, "", (address, port, 0, 0))
            if ":" in address
            else (socket.AF_INET, type, 6, "", (address, port))
            for address in self.addresses[host]
        ]

    def _create_connection(self, address, timeout=None):
        self.connections.append((*address, timeout))
        if address[0] in self.refused:
            raise ConnectionRefusedError(111, "Connection refused")
        ours, theirs = socket.socketpair()
        client = _Socket(fileno=ours.detach())
        client.settimeout(timeout)
        self._sockets += [client, theirs]
        thread = threading.Thread(target=self._answer, args=(theirs,), daemon=True)
        self._threads.append(thread)
        thread.start()
        return client

    def _wrap(self, raw, host):
        self.certificates_for.append(host)
        return raw

    def _answer(self, server):
        with server:
            try:
                request = b""
                while b"\r\n\r\n" not in request:
                    chunk = server.recv(4096)
                    if not chunk:
                        return
                    request += chunk
                lines = request.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
                target = lines[0].split(" ")[1]
                headers = dict(line.split(": ", 1) for line in lines[1:])
                self.requests.append((headers.get("Host"), target, headers))
                answer = self.answers.get(
                    f"https://{headers.get('Host')}{target}",
                    response(b"No existe.", "404 Not Found", {"Content-Type": "text/plain"}),
                )
                if callable(answer):
                    answer(server)
                else:
                    server.sendall(answer)
            except OSError:
                pass  # el descargador cortó la conexión: el sitio deja de contestar
