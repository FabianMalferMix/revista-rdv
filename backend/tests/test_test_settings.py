"""Lo que la suite fija a propósito vive en config/settings_test.py, y no en settings.py según
quién lo importe: antes, settings.py miraba si pytest estaba cargado."""

import importlib

import pytest
from django.conf import settings
from django.template import TemplateSyntaxError, engines

from config.celery import app


def test_the_production_settings_do_not_look_for_pytest():
    produccion = importlib.import_module("config.settings")
    assert produccion.AXES_ENABLED is True
    assert getattr(produccion, "CELERY_TASK_ALWAYS_EAGER", False) is False
    assert settings.AXES_ENABLED is False and settings.CELERY_TASK_ALWAYS_EAGER is True


def test_an_exception_in_a_task_reaches_the_test_that_queued_it():
    """En modo eager, una tarea que falla devolvía un resultado fallido y la prueba seguía."""

    @app.task
    def falla():
        raise RuntimeError("la tarea falló")

    with pytest.raises(RuntimeError, match="la tarea falló"):
        falla.delay()


def test_a_misspelled_variable_breaks_the_template_that_paints_it():
    """En producción se pinta vacía y en silencio."""
    plantilla = engines["django"].from_string("{{ perfil.nombre }} — {{ perfil.nombr }}")
    with pytest.raises(TemplateSyntaxError, match="perfil.nombr"):
        plantilla.render({"perfil": {"nombre": "Repitentes"}})
    # Control: lo que no existe a propósito, en un {% if %}, sigue sin romper nada.
    assert engines["django"].from_string("{% if falta %}x{% endif %}ok").render({}) == "ok"
