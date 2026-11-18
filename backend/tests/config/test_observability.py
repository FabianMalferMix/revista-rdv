"""El registro en JSON (config/logformat.py): cada registro sale como JSON válido, con la hora,
el nivel, el logger y el mensaje ya formateado; la traza de una excepción va en `exc_info`."""

import json
import logging
import sys

from config.logformat import JsonFormatter


def _record(**kwargs):
    defaults = {
        "name": "apps.content",
        "level": logging.WARNING,
        "pathname": "x.py",
        "lineno": 1,
        "msg": "algo pasó: %s",
        "args": ("detalle",),
        "exc_info": None,
    }
    defaults.update(kwargs)
    return logging.LogRecord(**defaults)


def test_json_formatter_emits_valid_json_with_core_fields():
    out = json.loads(JsonFormatter().format(_record()))
    assert out["level"] == "WARNING"
    assert out["logger"] == "apps.content"
    assert out["message"] == "algo pasó: detalle"
    assert "time" in out


def test_json_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = _record(level=logging.ERROR, msg="fallo", args=(), exc_info=sys.exc_info())
    out = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in out["exc_info"]
