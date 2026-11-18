"""Trae desde el servidor una imagen de otro sitio, sin que la dirección alcance la red interna.

La dirección la escribe quien edita en el panel, y el servidor la pide desde dentro de la red de
Docker, donde la base de datos, Redis y Caddy contestan a quien les hable. Por eso solo se pide por
https al puerto 443, sin usuario ni contraseña en la dirección. El nombre se resuelve con plazo y
todas sus direcciones tienen que ser de internet; la conexión va a una de esas mismas direcciones
(el nombre no se resuelve dos veces), con el certificado comprobado para el nombre, y cada
redirección se comprueba entera de nuevo. Solo vale una respuesta 200 de tipo `image/*`, sin
comprimir y con un tope de bytes, que se mira en la cabecera y mientras se lee. Un plazo cubre la
conexión, el saludo TLS, las cabeceras y el cuerpo: cuando se acaba, un vigilante corta la conexión.
No se mandan cookies ni Referer.
"""

import contextlib
import re
import socket
import ssl
import threading
import time
from http.client import HTTPException, HTTPSConnection
from ipaddress import ip_address
from urllib.parse import quote, urljoin, urlsplit

from django.conf import settings

MAX_REDIRECTS = 3
_REDIRECTS = {301, 302, 303, 307, 308}
_CHUNK = 64 * 1024
# Lo que la ruta y la consulta llevan sin escapar (RFC 3986), y «%», para no escapar dos veces lo
# que ya viene escapado.
_PATH_SAFE = "/%:@!$&'()*+,;=-._~"
_QUERY_SAFE = _PATH_SAFE + "?"
# Un nombre ya pasado a ASCII: letras, cifras, puntos y guiones, y los «:» de una IPv6.
_HOST = re.compile(r"[a-z0-9._:-]+")
# Los formatos que admite la biblioteca, primero: un sitio que elige el formato según lo que se le
# pide manda uno de ellos antes que otro.
_ACCEPT = "image/webp, image/png, image/jpeg, image/*;q=0.8"

# Por donde se sale a la red. Las pruebas los sustituyen, y backend/conftest.py hace fallar la
# prueba que no lo hace.
_getaddrinfo = socket.getaddrinfo
_create_connection = socket.create_connection


def _wrap(raw, host):
    """La conexión TLS sobre `raw`, con el certificado comprobado para `host`. El saludo se hace
    después, con el vigilante ya en marcha."""
    context = ssl.create_default_context()
    return context.wrap_socket(raw, server_hostname=host, do_handshake_on_connect=False)


class RemoteFetchError(Exception):
    """La imagen no se pudo traer. El mensaje dice por qué, para quien edita."""


def fetch_image(url, *, max_bytes, deadline):
    """Los bytes de la imagen de `url`, o RemoteFetchError con el motivo.

    `deadline` es un instante de `time.monotonic()`: lo que no termina antes se corta.
    """
    for _ in range(MAX_REDIRECTS + 1):
        location, content = _get(url, max_bytes, deadline)
        if location is None:
            return content
        url = urljoin(url, location)
    raise RemoteFetchError(f"redirige más de {MAX_REDIRECTS} veces")


def _get(url, max_bytes, deadline):
    """Una petición: (la dirección a la que redirige, None) o (None, los bytes de la imagen)."""
    host, target = _parse(url)
    addresses = _public_addresses(_resolve(host, deadline))
    sock = _connect(addresses, host, deadline)
    connection = HTTPSConnection(host, 443)
    connection.sock = sock
    expired = threading.Event()
    watchdog = threading.Timer(max(deadline - time.monotonic(), 0), _cut, (sock, expired))
    watchdog.daemon = True
    watchdog.start()
    try:
        result = _exchange(connection, sock, target, max_bytes)
    except RemoteFetchError as exc:
        if expired.is_set():
            raise RemoteFetchError("tardó demasiado") from exc
        raise
    finally:
        watchdog.cancel()
        watchdog.join()
        connection.close()
        sock.close()
    # Una respuesta sin Content-Length termina cuando se cierra la conexión: cortada por el
    # vigilante, parecería entera.
    if expired.is_set():
        raise RemoteFetchError("tardó demasiado")
    return result


def _exchange(connection, sock, target, max_bytes):
    try:
        sock.do_handshake()
        connection.request(
            "GET",
            target,
            headers={
                "Accept": _ACCEPT,
                "User-Agent": f"Mozilla/5.0 (compatible; +{settings.SITE_URL})",
                "Connection": "close",
            },
        )
        with connection.getresponse() as response:
            if response.status in _REDIRECTS:
                location = response.getheader("Location")
                if not location:
                    raise RemoteFetchError("redirige sin decir adónde")
                return location, None
            return None, _image_body(response, max_bytes)
    except ssl.SSLCertVerificationError as exc:
        raise RemoteFetchError("su certificado no es válido") from exc
    except (OSError, HTTPException) as exc:
        raise RemoteFetchError("la conexión se cortó") from exc


def _image_body(response, max_bytes):
    """El cuerpo de una respuesta que trae una imagen entera, sin pasar de `max_bytes`. Lo que no
    es una imagen se rechaza por sus cabeceras, sin leerlo."""
    if response.status != 200:
        raise RemoteFetchError(f"respondió con el código {response.status}")
    kind = (response.getheader("Content-Type") or "").split("/", 1)[0].strip().lower()
    if kind != "image":
        raise RemoteFetchError("no es una imagen")
    if (response.getheader("Content-Encoding") or "identity").strip().lower() != "identity":
        raise RemoteFetchError("llega comprimida")
    too_big = f"pesa más de {max_bytes // 2**20} MB"
    if response.length is not None and response.length > max_bytes:
        raise RemoteFetchError(too_big)
    content = bytearray()
    while chunk := response.read(_CHUNK):
        content += chunk
        if len(content) > max_bytes:
            raise RemoteFetchError(too_big)
    # Si la conexión se cierra antes de lo que anunció Content-Length, http.client da el cuerpo
    # por terminado sin avisar: lo que falta queda en `length`.
    if response.length:
        raise RemoteFetchError("llegó incompleta")
    return bytes(content)


def _parse(url):
    """El nombre del sitio y lo que se le pide (la ruta y la consulta, escapadas), o el motivo por
    el que la dirección no se pide."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:  # un puerto que no es un número, un IPv6 mal cerrado
        raise RemoteFetchError("la dirección no es válida") from exc
    if parts.scheme != "https":
        raise RemoteFetchError("la dirección no es https")
    if parts.username is not None or parts.password is not None:
        raise RemoteFetchError("la dirección lleva usuario o contraseña")
    if port not in (None, 443):
        raise RemoteFetchError("la dirección usa un puerto que no es el 443")
    try:
        host = (parts.hostname or "").encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise RemoteFetchError("la dirección no es válida") from exc
    if not _HOST.fullmatch(host):
        raise RemoteFetchError("la dirección no es válida")
    target = quote(parts.path or "/", safe=_PATH_SAFE)
    if parts.query:
        target += "?" + quote(parts.query, safe=_QUERY_SAFE)
    return host, target


def _resolve(host, deadline):
    """Las direcciones del nombre, con el plazo que getaddrinfo no tiene."""
    outcome = {}

    def resolve():
        try:
            outcome["infos"] = _getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except BaseException as exc:  # lo relanza el hilo que espera, sea cual sea
            outcome["error"] = exc

    timeout = _remaining(deadline)
    lookup = threading.Thread(target=resolve, daemon=True)
    lookup.start()
    lookup.join(timeout)
    if lookup.is_alive():
        raise RemoteFetchError("tardó demasiado")
    error = outcome.get("error")
    if isinstance(error, OSError):
        raise RemoteFetchError("el nombre del sitio no existe") from error
    if error is not None:
        raise error
    return outcome["infos"]


def _public_addresses(infos):
    """Las direcciones del nombre, sin repetir, si todas son de internet: con una sola de la red
    interna, al nombre no se le pide nada."""
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise RemoteFetchError("el nombre del sitio no existe")
    if not all(map(_is_public, addresses)):
        raise RemoteFetchError("apunta a una dirección interna")
    return addresses


def _is_public(address):
    """Si una dirección es de internet. Una IPv6 que lleva dentro una IPv4 (::ffff:a.b.c.d) vale lo
    que esa IPv4, que es como la lee `ipaddress`; las otras maneras de llevarla (6to4, NAT64) no
    cuentan como de internet."""
    try:
        ip = ip_address(address)
    except ValueError:
        return False
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def _connect(addresses, host, deadline):
    """La conexión TLS, todavía sin el saludo, con la primera dirección que contesta."""
    for address in addresses:
        try:
            raw = _create_connection((address, 443), timeout=_remaining(deadline))
        except OSError:
            continue
        try:
            return _wrap(raw, host)
        except OSError as exc:
            raw.close()
            raise RemoteFetchError("la conexión se cortó") from exc
    raise RemoteFetchError("no contestó")


def _remaining(deadline):
    """Los segundos que quedan hasta `deadline`, o «tardó demasiado» si no queda ninguno."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RemoteFetchError("tardó demasiado")
    return remaining


def _cut(sock, expired):
    """Corta la conexión al acabarse el plazo: lo que la esperaba (el saludo, las cabeceras, el
    cuerpo) recibe un error o un final, y `expired` dice por qué."""
    expired.set()
    with contextlib.suppress(OSError):
        # El método de socket.socket: el de SSLSocket desmonta la sesión TLS, que el hilo de la
        # petición puede estar usando a la vez.
        socket.socket.shutdown(sock, socket.SHUT_RDWR)
