"""El feed de podcast no comparte estado entre peticiones (hallazgo S-36).

`RecordingsFeed` guarda la request en `self` para poder construir la URL absoluta del
enclosure (Django no aplica `add_domain` a los `<enclosure>` y `item_enclosure_url` no
recibe la request). Eso solo es seguro si la instancia no se comparte — y `urls.py`
creaba UNA sola para todo el proceso.

Era inofensivo mientras gunicorn corría con workers de tipo sync, una petición por
proceso. Dejó de serlo al pasar a `gthread` con 4 hilos en la remediación de S-07: dos
peticiones concurrentes en el mismo worker se pisaban la request y el enclosure podía
salir con el host de la otra. Un caso de libro de una corrección que invalida el
supuesto documentado de otra.
"""

import threading

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import resolve, reverse

from apps.media.models import Recording

pytestmark = pytest.mark.django_db
HOSTS = ["uno.example.com", "dos.example.com"]


@pytest.fixture
def registro():
    return Recording.objects.create(
        slug="lectura",
        title="Lectura",
        kind=Recording.Kind.AUDIO,
        published=True,
        file=SimpleUploadedFile("lectura.mp3", b"ID3\x04\x00\x00\x00"),
    )


def test_la_url_no_apunta_a_una_instancia_compartida():
    """Estructural y determinista: la vista debe ser un invocable que instancie por
    petición, no una instancia de Feed creada al importar urls.py."""
    from apps.media.feeds import RecordingsFeed, recordings_feed

    vista = resolve(reverse("recordings_feed")).func
    assert not isinstance(vista, RecordingsFeed), (
        "urls.py registra una instancia compartida: dos peticiones concurrentes se "
        "pisarán la request guardada en self"
    )
    assert vista is recordings_feed


@override_settings(ALLOWED_HOSTS=HOSTS)
@pytest.mark.parametrize("host", HOSTS)
def test_el_enclosure_usa_el_host_de_su_peticion(registro, host):
    resp = Client().get(reverse("recordings_feed"), HTTP_HOST=host)
    assert resp.status_code == 200
    assert f"http://{host}/media/".encode() in resp.content
    otro = next(h for h in HOSTS if h != host)
    assert otro.encode() not in resp.content


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)  # los hilos usan su propia conexión: sin
@override_settings(ALLOWED_HOSTS=HOSTS)  # transacción real no verían el registro
def test_dos_peticiones_concurrentes_no_se_contaminan(registro):
    """Ejercita de verdad la condición de carrera: dos hilos piden el feed a la vez con
    Host distinto y cada respuesta debe llevar SOLO su propio host."""
    barrera = threading.Barrier(len(HOSTS))
    resultados = {}

    def pedir(host):
        from django.db import connection

        try:
            barrera.wait(timeout=10)
            resultados[host] = Client().get(reverse("recordings_feed"), HTTP_HOST=host).content
        finally:
            connection.close()

    hilos = [threading.Thread(target=pedir, args=(h,)) for h in HOSTS]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=20)

    assert set(resultados) == set(HOSTS), "algún hilo no completó la petición"
    for host, contenido in resultados.items():
        otro = next(h for h in HOSTS if h != host)
        assert f"http://{host}/media/".encode() in contenido
        assert otro.encode() not in contenido, f"la respuesta de {host} trae el host de {otro}"
