"""Ningún campo del log JSON deja pasar el token del boletín, ni siquiera los extra.

`RedactTokensFilter` redactaba `record.msg` y ahí se detenía. Pero `JsonFormatter`
serializa además todos los atributos extra del registro, y `django.request` adjunta el
WSGIRequest entero: su repr() lleva la ruta cruda. En un 404 sobre un enlace de baja el
log salía con el mensaje redactado y el token en claro dos campos más allá.

Los tokens de baja son permanentes y valen por sí solos: quien lea el log puede dar de
baja a cualquiera. Encontrado en las pruebas manuales del §8.6 del barrido, comparando el
log del proxy (limpio) con el de la aplicación (no).
"""

import json
import logging

import pytest

from config.logformat import JsonFormatter

TOKEN = "SECRETO-DE-PRUEBA-abc123xyz"
RUTA = f"/novedades/baja/{TOKEN}/"


class _PeticionFalsa:
    """Imita lo único que importa del WSGIRequest: que su repr() cite la ruta."""

    def __repr__(self):
        return f"<WSGIRequest: GET '{RUTA}'>"


def _formatea(**extra):
    registro = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Not Found: %s",
        args=(RUTA,),
        exc_info=None,
    )
    for clave, valor in extra.items():
        setattr(registro, clave, valor)
    return json.loads(JsonFormatter().format(registro))


def test_el_mensaje_va_redactado():
    assert _formatea()["message"] == "Not Found: /novedades/baja/<redactado>/"


def test_el_objeto_request_no_filtra_el_token():
    """El caso real: `django.request` pasa `extra={'request': <WSGIRequest ...>}`."""
    salida = _formatea(request=_PeticionFalsa(), status_code=404)
    assert TOKEN not in json.dumps(salida)
    assert "<redactado>" in salida["request"]


def test_un_extra_de_texto_tampoco():
    assert TOKEN not in json.dumps(_formatea(ruta_original=RUTA))


def test_la_traza_tampoco():
    try:
        raise ValueError(f"fallo procesando {RUTA}")
    except ValueError:
        import sys

        registro = logging.LogRecord(
            "django.request", logging.ERROR, __file__, 1, "boom", (), sys.exc_info()
        )
        salida = json.loads(JsonFormatter().format(registro))
    assert TOKEN not in json.dumps(salida)


def test_no_se_redacta_lo_que_no_es_un_token():
    """Contra-prueba: la redacción no debe morder rutas ajenas al boletín."""
    salida = _formatea(otra_ruta="/articulo/resena-la-casa-vacia/")
    assert salida["otra_ruta"] == "/articulo/resena-la-casa-vacia/"


@pytest.mark.parametrize("ruta", ["/novedades/confirmar/abc123/", "/novedades/baja/xyz789/"])
def test_ambas_rutas_del_boletin(ruta):
    salida = _formatea(request=type("R", (), {"__repr__": lambda s: f"<R: GET '{ruta}'>"})())
    assert "<redactado>" in salida["request"]
