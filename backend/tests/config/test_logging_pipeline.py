"""El token del boletín no sale en claro de ningún proceso que escriba logs.

`redact_path` tapa el token de las rutas del boletín, con el dominio o sin él, y deja como están
las rutas que no lo llevan; el filtro de registro lo tapa en el mensaje. La redacción sigue a
las rutas del URLconf: renombrar la de confirmación, o añadir otra ruta con token, no deja el
token en claro sin tocar nada más, y si no puede leerlas, tapa la línea entera. Y llega a todos
los procesos: a los extras anidados que adjunta Celery, al worker y a beat, que escriben con el
formato y el filtro de Django, y a gunicorn. Un mensaje que no se puede formatear tampoco deja
nada en claro: en su lugar sale un aviso con el lugar de la llamada. Y no escriben los handlers
que Django pone por su cuenta: la consola de desarrollo y la línea de runserver salen por la
raíz, redactadas, y un error no llega por correo a ADMINS, aunque se llene.
"""

import json
import logging
import logging.config
import os
import subprocess
import sys
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core.mail import mail_admins
from django.core.servers.basehttp import WSGIRequestHandler
from django.urls import reverse
from django.utils.log import configure_logging

from config import redaction
from config.celery import app as celery_app
from config.logformat import JsonFormatter
from config.redaction import RedactTokensFilter, redact_path

BACKEND_DIR = settings.BASE_DIR
# Valor anodino, para que gitleaks no lo tome por una credencial.
VALUE = "no-es-una-credencial"


def test_a_renamed_token_route_is_still_redacted(settings):
    settings.ROOT_URLCONF = "tests.urls_renamed_token_routes"
    for name in ("community:confirm", "community:one_click_unsubscribe"):
        path = reverse(name, args=[VALUE])
        assert not path.startswith("/novedades/")
        assert redact_path(f"GET {path} 404") == f"GET {path.replace(VALUE, '<redactado>')} 404"


def test_redaction_fails_closed_if_the_routes_cannot_be_read(monkeypatch, settings):
    settings.ROOT_URLCONF = "tests.urls_renamed_token_routes"

    def broken():
        raise RuntimeError("URLconf roto")

    monkeypatch.setattr(redaction, "token_route_prefixes", broken)
    monkeypatch.setattr(redaction, "_patterns", {})
    assert redact_path("GET /boletin/salir/abc/") == redaction.SIN_PATRON


def test_se_redacta_el_token_de_las_rutas_del_boletin():
    # Las rutas salen del URLconf, como la redacción: si se renombran, la prueba las sigue.
    for nombre in ("community:unsubscribe", "community:confirm"):
        ruta = reverse(nombre, args=["SECRETO-123"])
        esperada = ruta.replace("SECRETO-123", "<redactado>")
        assert redact_path(ruta) == esperada
        assert redact_path(f"https://sitio.cl{ruta}") == f"https://sitio.cl{esperada}"


def test_no_se_toca_lo_que_no_lleva_secreto():
    for ruta in ["/textos/", "/buscar/?q=umbral", "/novedades/", "/admin/"]:
        assert redact_path(ruta) == ruta


def test_el_filtro_de_logging_redacta_el_mensaje():
    registro = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Not Found: %s",
        args=(reverse("community:unsubscribe", args=["SECRETO-123"]),),
        exc_info=None,
    )
    assert RedactTokensFilter().filter(registro) is True
    assert "SECRETO-123" not in registro.getMessage()
    assert "<redactado>" in registro.getMessage()


def test_nested_extras_from_celery_are_redacted():
    """Celery adjunta los argumentos de la tarea como un diccionario con listas dentro."""
    url = reverse("community:unsubscribe", args=[VALUE])
    record = logging.LogRecord(
        "celery.worker.strategy", logging.INFO, __file__, 1, "Task received", (), None
    )
    record.data = {"args": (f"https://revista.example.org{url}",), "kwargs": {"urls": [url]}}
    line = JsonFormatter().format(record)
    assert VALUE not in line
    assert json.loads(line)["data"]["kwargs"]["urls"] == ["/novedades/baja/<redactado>/"]


@pytest.fixture
def restore_logging():
    """Devuelve cada logger a como estaba: estas pruebas vuelven a configurar el log."""
    loggers = [logging.getLogger()] + [
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    saved = [(lg, lg.handlers[:], lg.level, lg.propagate, lg.disabled) for lg in loggers]
    yield
    for logger, handlers, level, propagate, disabled in saved:
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled


def test_a_worker_line_comes_out_as_redacted_json(settings, capsys, restore_logging):
    """Como en producción: Celery configura el log del worker y una tarea registra un extra
    con una URL con token."""
    production = deepcopy(settings.LOGGING)
    production["handlers"]["console"]["formatter"] = "json"
    settings.LOGGING = production
    celery_app.log.already_setup = False
    celery_app.log.setup_logging_subsystem()

    root = logging.getLogger()
    assert any(isinstance(f, RedactTokensFilter) for h in root.handlers for f in h.filters)
    url = reverse("community:confirm", args=[VALUE])
    logging.getLogger("celery.app.trace").warning("Task failed", extra={"data": {"args": [url]}})
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert VALUE not in line
    assert json.loads(line)["data"]["args"] == ["/novedades/confirmar/<redactado>/"]


def test_a_message_that_cannot_be_formatted_leaves_nothing_in_clear(
    settings, capsys, restore_logging
):
    """Con el formato de desarrollo, el filtro es lo único que redacta. A un mensaje le falta un
    argumento: sale un aviso con el lugar de la llamada, y la línea siguiente, bien formada,
    sale redactada como siempre."""
    development = deepcopy(settings.LOGGING)
    development["handlers"]["console"]["formatter"] = "plain"
    logging.config.dictConfig(development)

    url = reverse("community:unsubscribe", args=[VALUE])
    logger = logging.getLogger("apps.community.views")
    logger.warning("Baja de %s por %s", url)
    logger.warning("Baja de %s", url)
    err = capsys.readouterr().err
    assert VALUE not in err
    notice, control = err.strip().splitlines()[-2:]
    assert f"{redaction.UNFORMATTABLE_MARK} (" in notice
    assert "test_logging_pipeline.py:" in notice
    assert control.endswith("WARNING apps.community.views Baja de /novedades/baja/<redactado>/")


def _start_logging_like_django(settings, *, debug):
    """Configura el log como `django.setup()`: primero el DEFAULT_LOGGING de Django, con sus
    propios handlers, y encima el LOGGING del sitio. Con el formato de cada entorno: texto
    plano con DEBUG, como en desarrollo, y JSON sin él, como en producción."""
    site = deepcopy(settings.LOGGING)
    site["handlers"]["console"]["formatter"] = "plain" if debug else "json"
    settings.DEBUG = debug
    configure_logging(settings.LOGGING_CONFIG, site)


def _json_line(err, logger):
    """La última línea JSON que escribió un logger."""
    lines = [json.loads(line) for line in err.splitlines() if line.startswith("{")]
    return [line for line in lines if line["logger"] == logger][-1]


@pytest.mark.django_db
def test_the_development_console_writes_a_newsletter_link_redacted(
    client, settings, capsys, restore_logging
):
    """Django cuelga del logger `django` su propia consola, que con DEBUG escribe sin el filtro.
    El 404 de un enlace de baja que no existe sale redactado."""
    _start_logging_like_django(settings, debug=True)
    assert client.get(reverse("community:unsubscribe", args=[VALUE])).status_code == 404
    err = capsys.readouterr().err
    assert VALUE not in err
    assert "WARNING django.request Not Found: /novedades/baja/<redactado>/" in err


@pytest.mark.django_db
def test_the_production_console_writes_a_newsletter_link_redacted(
    client, settings, capsys, restore_logging
):
    """Sin DEBUG, la línea sale en JSON, con la ruta redactada en el mensaje y en la petición
    que Django le adjunta."""
    _start_logging_like_django(settings, debug=False)
    assert client.get(reverse("community:confirm", args=[VALUE])).status_code == 404
    err = capsys.readouterr().err
    assert VALUE not in err
    line = _json_line(err, "django.request")
    assert line["message"] == "Not Found: /novedades/confirmar/<redactado>/"
    assert line["request"] == "<WSGIRequest: GET '/novedades/confirmar/<redactado>/'>"


def _serve_like_runserver(path):
    """Atiende un GET con el manejador de peticiones de runserver, que escribe la línea de cada
    una en `django.server`. La petición llega por un búfer, sin socket, y la responde con un 404
    una aplicación mínima."""

    def app(environ, start_response):
        start_response("404 Not Found", [("Content-Length", "0")])
        return [b""]

    request = BytesIO(f"GET {path} HTTP/1.1\r\nHost: testserver\r\n\r\n".encode())
    # La respuesta se descarta: lo que se mira es la línea del log.
    connection = SimpleNamespace(
        makefile=lambda *args, **kwargs: request, sendall=lambda data: None
    )
    server = SimpleNamespace(base_environ={}, get_app=lambda: app)
    WSGIRequestHandler(connection, ("127.0.0.1", 50000), server)


def test_the_runserver_line_writes_a_newsletter_link_redacted(settings, capsys, restore_logging):
    """Django cuelga de `django.server` su propio handler, sin el filtro y sin propagar a la
    raíz. La línea de un enlace de baja sale redactada."""
    _start_logging_like_django(settings, debug=True)
    _serve_like_runserver(reverse("community:unsubscribe", args=[VALUE]))
    err = capsys.readouterr().err
    assert VALUE not in err
    assert 'WARNING django.server "GET /novedades/baja/<redactado>/ HTTP/1.1" 404 0' in err


@pytest.mark.django_db
def test_an_error_on_a_newsletter_link_sends_no_email_to_admins(
    client, monkeypatch, settings, capsys, mailoutbox, restore_logging
):
    """Con ADMINS lleno y sin DEBUG, Django mandaría cada error por correo, con la ruta en el
    asunto y la petición entera en el cuerpo. No sale ningún correo, y el error queda en el
    log, redactado."""
    _start_logging_like_django(settings, debug=False)
    settings.ADMINS = [("Redacción", "redaccion@example.org")]

    def fails(field, token):
        raise RuntimeError("la base no responde")

    monkeypatch.setattr("apps.community.views._por_token", fails)
    client.raise_request_exception = False
    assert client.get(reverse("community:unsubscribe", args=[VALUE])).status_code == 500
    assert mailoutbox == []
    err = capsys.readouterr().err
    assert VALUE not in err
    line = _json_line(err, "django.request")
    assert line["message"] == "Internal Server Error: /novedades/baja/<redactado>/"
    # Control: con este ADMINS, un correo a los administradores sí sale.
    mail_admins("Prueba", "Un correo a los administradores.")
    assert len(mailoutbox) == 1


def _log_like_gunicorn(*calls):
    """Ejecuta las llamadas en otro proceso, con el log configurado como lo hace gunicorn (lee
    gunicorn.conf.py de su directorio de trabajo), y devuelve lo que escribió en stderr."""
    script = (
        "import django, logging, logging.config, runpy; django.setup(); "
        "logging.config.dictConfig(runpy.run_path('gunicorn.conf.py')['logconfig_dict']); "
        "log = logging.getLogger('gunicorn.error'); " + "; ".join(calls)
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-500:]
    return result.stderr


def test_gunicorn_logs_json_with_redaction():
    """Un error al atender una petición sale en JSON y sin el token."""
    err = _log_like_gunicorn(f"log.error('Error handling request %s', '/novedades/baja/{VALUE}/')")
    line = json.loads(err.strip().splitlines()[-1])
    assert line["logger"] == "gunicorn.error"
    assert line["message"] == "Error handling request /novedades/baja/<redactado>/"


def test_gunicorn_turns_a_message_that_cannot_be_formatted_into_a_notice():
    """gunicorn no lleva el filtro: el formateador JSON es lo único que redacta. Un mensaje al
    que le falta un argumento sale como aviso, y la línea siguiente sale redactada."""
    err = _log_like_gunicorn(
        f"log.error('Error handling request %s %s', '/novedades/baja/{VALUE}/')",
        f"log.error('Error handling request %s', '/novedades/baja/{VALUE}/')",
    )
    assert VALUE not in err
    notice, control = (json.loads(line) for line in err.strip().splitlines()[-2:])
    assert notice["message"].startswith(f"{redaction.UNFORMATTABLE_MARK} (")
    assert control["message"] == "Error handling request /novedades/baja/<redactado>/"
