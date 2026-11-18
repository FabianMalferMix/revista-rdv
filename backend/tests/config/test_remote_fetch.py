"""El descargador de imágenes de otro sitio no alcanza la red interna y no espera de más.

La dirección la escribe quien edita, y el servidor la pide desde dentro de la red de Docker. Solo
se pide por https al 443, sin usuario ni contraseña; un nombre con una sola dirección interna no
se pide, y cada redirección se comprueba otra vez. Solo se lee una imagen, sin comprimir y hasta
un tope de bytes, y el plazo corta la conexión aunque el sitio siga mandando. Con un internet de
mentira (tests/remote_sites.py): la petición y la lectura son las de verdad.
"""

import socket
import ssl
import time
from io import BytesIO
from itertools import pairwise

import pytest
from PIL import Image

from config import remote_fetch
from config.remote_fetch import RemoteFetchError, fetch_image
from tests.remote_sites import PUBLIC, drip, redirect, response

SITE = "https://repitentes.example"
URL = "https://fotos.example/recital.png"
MAX = 2**20


def _png():
    buffer = BytesIO()
    Image.new("RGB", (4, 3), (200, 10, 10)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()


def _fetch(url=URL, max_bytes=MAX, seconds=5):
    return fetch_image(url, max_bytes=max_bytes, deadline=time.monotonic() + seconds)


def _refused(url=URL, **kwargs):
    with pytest.raises(RemoteFetchError) as error:
        _fetch(url, **kwargs)
    return str(error.value)


@pytest.fixture(autouse=True)
def _site_url(settings):
    settings.SITE_URL = SITE


def test_the_image_comes_from_the_address_that_was_checked(remote_sites):
    remote_sites.serve(URL, response(PNG))
    assert _fetch() == PNG
    # El nombre se resuelve una vez, y la conexión va a esa dirección, con el certificado del
    # nombre: no hay una segunda resolución que pueda dar otra.
    assert remote_sites.lookups == ["fotos.example"]
    assert [(address, port) for address, port, _ in remote_sites.connections] == [(PUBLIC, 443)]
    assert remote_sites.certificates_for == ["fotos.example"]
    host, target, headers = remote_sites.requests[0]
    assert (host, target) == ("fotos.example", "/recital.png")
    assert headers["Accept-Encoding"] == "identity"
    assert SITE in headers["User-Agent"]
    assert not {"Cookie", "Referer", "Authorization"} & set(headers)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/x.png",
        "https://127.1/x.png",
        "https://2130706433/x.png",
        "https://0.0.0.0/x.png",
        "https://10.0.0.5/x.png",
        "https://172.18.0.3/x.png",
        "https://192.168.1.1/x.png",
        "https://100.64.0.1/x.png",
        "https://169.254.169.254/latest/meta-data/",
        "https://224.0.0.1/x.png",
        "https://[::1]/x.png",
        "https://[::ffff:127.0.0.1]/x.png",
        "https://[::ffff:169.254.169.254]/latest/meta-data/",
        "https://[::ffff:224.0.0.1]/x.png",
        "https://[::7f00:1]/x.png",
        "https://[64:ff9b::7f00:1]/x.png",
        "https://[2002:7f00:1::]/x.png",
        "https://[2001::1]/x.png",
        "https://[fe80::1]/x.png",
        "https://[fd00::1]/x.png",
        "https://[ff02::1]/x.png",
    ],
)
def test_an_internal_address_is_never_asked(remote_sites, url):
    assert _refused(url) == "apunta a una dirección interna"
    assert remote_sites.connections == []


@pytest.mark.parametrize(
    "addresses",
    [["10.0.0.5"], ["172.18.0.3"], ["::1"], [PUBLIC, "127.0.0.1"], ["2606:4700::1", "fd00::1"]],
)
def test_a_name_with_one_internal_address_is_never_asked(remote_sites, addresses):
    remote_sites.serve(URL, response(PNG))
    remote_sites.addresses["fotos.example"] = addresses
    assert _refused() == "apunta a una dirección interna"
    assert remote_sites.connections == []


def test_a_public_ipv6_address_is_asked(remote_sites):
    """Control de la anterior: una IPv6 de internet, y una IPv4 de internet escrita como IPv6."""
    remote_sites.serve(URL, response(PNG), address="2606:4700::1")
    assert _fetch() == PNG
    remote_sites.serve("https://[::ffff:5db8:d70e]/a.png", response(PNG), "::ffff:5db8:d70e")
    assert _fetch("https://[::ffff:5db8:d70e]/a.png") == PNG


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://fotos.example/a.png", "la dirección no es https"),
        ("ftp://fotos.example/a.png", "la dirección no es https"),
        ("https://fotos.example:8443/a.png", "la dirección usa un puerto que no es el 443"),
        ("https://fotos.example:80/a.png", "la dirección usa un puerto que no es el 443"),
        ("https://ana:clave@fotos.example/a.png", "la dirección lleva usuario o contraseña"),
        ("https://ana@fotos.example/a.png", "la dirección lleva usuario o contraseña"),
        ("https://fotos.example:puerto/a.png", "la dirección no es válida"),
        ("https://[::1/a.png", "la dirección no es válida"),
        ("https:///a.png", "la dirección no es válida"),
        ("https://fotos example/a.png", "la dirección no es válida"),
        ("https://[fe80::1%25eth0]/a.png", "la dirección no es válida"),
    ],
)
def test_only_https_on_443_without_credentials_is_asked(remote_sites, url, reason):
    assert _refused(url) == reason
    assert remote_sites.lookups == []


def test_the_port_443_written_out_and_a_name_in_unicode_are_asked(remote_sites):
    remote_sites.serve("https://xn--fotos-espaa-beb.example/a.png", response(PNG))
    assert _fetch("https://fotos-españa.example:443/a.png") == PNG
    assert remote_sites.lookups == ["xn--fotos-espaa-beb.example"]


def test_the_address_is_asked_as_written_and_escaped_once(remote_sites):
    """Lo que no puede ir tal cual (el espacio, la raya «—») se escapa; lo que ya viene escapado y
    los signos que la ruta y la consulta admiten van como se escribieron."""
    remote_sites.serve(
        "https://fotos.example/obra%20%E2%80%94%202/foto%E2%80%94,(2)@x.png?id=3&t=x%2Fy",
        response(PNG),
    )
    assert _fetch("https://fotos.example/obra — 2/foto%E2%80%94,(2)@x.png?id=3&t=x%2Fy") == PNG


def test_each_redirect_is_checked_again(remote_sites):
    remote_sites.serve(URL, redirect("https://interna.example/a.png"))
    remote_sites.addresses["interna.example"] = ["10.0.0.7"]
    assert _refused() == "apunta a una dirección interna"
    assert [address for address, *_ in remote_sites.connections] == [PUBLIC]

    remote_sites.serve(URL, redirect("http://fotos.example/a.png"))
    assert _refused() == "la dirección no es https"


def test_a_redirect_is_followed_from_the_address_it_leaves(remote_sites):
    """Control de la anterior: la redirección relativa se resuelve desde la dirección de antes."""
    remote_sites.serve(URL, redirect("/otra/recital.png", status="301 Moved Permanently"))
    remote_sites.serve("https://fotos.example/otra/recital.png", response(PNG))
    assert _fetch() == PNG


def test_more_than_three_redirects_are_refused(remote_sites):
    chain = [f"https://fotos.example/{n}.png" for n in range(5)]
    for here, there in pairwise(chain):
        remote_sites.serve(here, redirect(there))
    remote_sites.serve(chain[3], response(PNG))
    assert _fetch(chain[0]) == PNG  # control: tres redirecciones llegan
    remote_sites.serve(chain[3], redirect(chain[4]))
    remote_sites.serve(chain[4], response(PNG))
    assert _refused(chain[0]) == "redirige más de 3 veces"


def test_a_redirect_without_its_address_is_refused(remote_sites):
    remote_sites.serve(URL, response(status="302 Found", headers={"Content-Type": None}))
    assert _refused() == "redirige sin decir adónde"


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({"Content-Type": "text/html"}, "no es una imagen"),
        ({"Content-Type": None}, "no es una imagen"),
        ({"Content-Type": "application/octet-stream"}, "no es una imagen"),
        ({"Content-Encoding": "gzip"}, "llega comprimida"),
        ({"Content-Length": str(MAX + 1)}, "pesa más de 1 MB"),
    ],
)
def test_what_is_not_an_image_is_refused_without_reading_it(remote_sites, headers, reason):
    """El sitio manda las cabeceras y se queda mandando: si se leyera el cuerpo, se esperaría
    hasta el plazo."""
    fields = {"Content-Type": "image/png", "Content-Length": "10000", **headers}
    remote_sites.serve(URL, drip(response(headers=fields)))
    started = time.monotonic()
    assert _refused(seconds=10) == reason
    assert time.monotonic() - started < 5


def test_an_answer_that_is_not_200_is_refused(remote_sites):
    remote_sites.serve(URL, response(PNG, "404 Not Found"))
    assert _refused() == "respondió con el código 404"
    remote_sites.serve(URL, response(PNG, "206 Partial Content"))
    assert _refused() == "respondió con el código 206"


def test_the_byte_cap_holds_also_without_content_length(remote_sites):
    remote_sites.serve(URL, response(b"x" * MAX))
    assert _fetch() == b"x" * MAX  # control: lo que llega justo al tope pasa
    remote_sites.serve(URL, response(b"x" * (MAX + 1), headers={"Content-Length": None}))
    assert _refused() == "pesa más de 1 MB"


def test_an_image_cut_short_is_refused(remote_sites):
    remote_sites.serve(URL, response(PNG[:20], headers={"Content-Length": str(len(PNG))}))
    assert _refused() == "llegó incompleta"


@pytest.mark.parametrize(
    "head",
    [
        b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n",
        response(headers={"Content-Length": "10000"}),
        # Sin Content-Length, el cuerpo termina cuando se cierra la conexión: cortado por el
        # plazo, parecería entero.
        response(headers={"Content-Length": None}),
    ],
    ids=["cabeceras", "cuerpo", "cuerpo-sin-longitud"],
)
def test_the_deadline_cuts_a_site_that_keeps_sending(remote_sites, head):
    remote_sites.serve(URL, drip(head, every=0.05))
    started = time.monotonic()
    assert _refused(seconds=0.5) == "tardó demasiado"
    assert time.monotonic() - started < 3


def test_the_deadline_covers_resolving_the_name(remote_sites):
    remote_sites.hanging.add("fotos.example")
    started = time.monotonic()
    assert _refused(seconds=0.3) == "tardó demasiado"
    assert time.monotonic() - started < 3
    assert remote_sites.connections == []


def test_a_name_that_does_not_exist(remote_sites):
    assert _refused("https://no-existe.example/a.png") == "el nombre del sitio no existe"


def test_the_next_address_is_tried_when_one_does_not_answer(remote_sites):
    remote_sites.serve(URL, response(PNG))
    remote_sites.addresses["fotos.example"] = ["2606:4700::1", PUBLIC]
    remote_sites.refused.add("2606:4700::1")
    assert _fetch() == PNG
    remote_sites.refused.add(PUBLIC)
    assert _refused() == "no contestó"


def test_the_certificate_is_checked_for_the_name():
    """La conexión de verdad pide un certificado válido para el nombre, con las autoridades del
    sistema."""
    ours, theirs = socket.socketpair()
    with theirs, remote_fetch._wrap(ours, "fotos.example") as tls:
        assert tls.server_hostname == "fotos.example"
        assert tls.context.verify_mode == ssl.CERT_REQUIRED
        assert tls.context.check_hostname


def test_a_certificate_that_is_not_valid_is_said(remote_sites, monkeypatch):
    class BadCertificate:
        def __init__(self, raw):
            self.raw = raw

        def do_handshake(self):
            raise ssl.SSLCertVerificationError("certificate verify failed")

        def __getattr__(self, name):
            return getattr(self.raw, name)

    remote_sites.serve(URL, response(PNG))
    monkeypatch.setattr(remote_fetch, "_wrap", lambda raw, host: BadCertificate(raw))
    assert _refused() == "su certificado no es válido"


def test_a_test_that_forgets_the_fake_internet_fails():
    """backend/conftest.py: sin `remote_sites`, la prueba falla antes de salir a la red."""
    with pytest.raises(pytest.fail.Exception, match="salir a la red"):
        _fetch()
