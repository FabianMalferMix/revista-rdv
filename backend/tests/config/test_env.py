"""Las variables de entorno se leen con un solo criterio (config/env.py).

Quien despliega escribe `true`, `TRUE` o `yes` tanto como `1`: todas esas formas tienen
que significar lo mismo, y una palabra que no se entiende tiene que detener el arranque
diciendo qué variable la trae.
"""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_choice, env_float, env_int, env_list, env_str

ENVIRONMENTS = ("development", "production")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        (" On ", True),
        ("0", False),
        ("off", False),
        ("False", False),
        ("no", False),
    ],
)
def test_env_bool_understands_every_spelling(raw, expected):
    # El valor por defecto es el contrario: si la lectura cayera en él, la prueba fallaría.
    assert env_bool("AXES_ENABLED", not expected, environ={"AXES_ENABLED": raw}) is expected


def test_env_bool_rejects_an_unknown_word_naming_the_variable():
    with pytest.raises(ImproperlyConfigured, match="AXES_ENABLED='verdadero'"):
        env_bool("AXES_ENABLED", True, environ={"AXES_ENABLED": "verdadero"})


def test_empty_variable_means_the_default():
    """La plantilla deja variables vacías (`EMAIL_PORT=`): valen lo mismo que ausentes."""
    assert env_int("EMAIL_PORT", 587, environ={"EMAIL_PORT": ""}) == 587
    assert env_bool("EMAIL_USE_TLS", True, environ={"EMAIL_USE_TLS": "  "}) is True
    assert env_str("DEFAULT_FROM_EMAIL", "a@b.cl", environ={"DEFAULT_FROM_EMAIL": ""}) == "a@b.cl"
    # Control positivo: un valor escrito sí se usa.
    assert env_int("EMAIL_PORT", 587, environ={"EMAIL_PORT": "465"}) == 465


@pytest.mark.parametrize(
    ("reader", "raw"),
    [(env_int, "587a"), (env_float, "cero coma uno")],
)
def test_numbers_that_do_not_parse_name_the_variable(reader, raw):
    with pytest.raises(ImproperlyConfigured, match="EMAIL_PORT"):
        reader("EMAIL_PORT", 0, environ={"EMAIL_PORT": raw})


def test_env_list_drops_spaces_and_empty_items():
    environ = {"DJANGO_ALLOWED_HOSTS": "revista.cl, www.revista.cl,,"}
    assert env_list("DJANGO_ALLOWED_HOSTS", environ=environ) == ["revista.cl", "www.revista.cl"]
    # El valor por defecto se escribe como la variable, y se lee igual.
    assert env_list("DJANGO_ALLOWED_HOSTS", "a.cl, b.cl", environ={}) == ["a.cl", "b.cl"]


def test_env_choice_understands_its_values_in_any_case():
    environ = {"DJANGO_ENVIRONMENT": " Production "}
    assert env_choice("DJANGO_ENVIRONMENT", ENVIRONMENTS, "development", environ) == "production"
    # Control: sin la variable vale el valor por defecto, que es el otro.
    assert env_choice("DJANGO_ENVIRONMENT", ENVIRONMENTS, "development", {}) == "development"


def test_env_choice_rejects_an_unknown_value_naming_the_variable():
    """Una errata en la declaración de producción no puede valer en silencio por desarrollo."""
    with pytest.raises(ImproperlyConfigured, match="DJANGO_ENVIRONMENT='produccion'"):
        env_choice(
            "DJANGO_ENVIRONMENT", ENVIRONMENTS, "development", {"DJANGO_ENVIRONMENT": "produccion"}
        )


def test_env_str_keeps_secrets_untouched():
    """Una contraseña se usa tal cual: recortarla la cambiaría."""
    environ = {"EMAIL_HOST_PASSWORD": " con espacios "}
    assert env_str("EMAIL_HOST_PASSWORD", environ=environ) == " con espacios "
