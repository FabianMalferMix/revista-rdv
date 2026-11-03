"""Guard de arranque en producción.

Con DEBUG=0 el sitio no arranca con secretos de plantilla, hosts por defecto, orígenes
sin https ni defensas apagadas sin autorización. Las pruebas de la función usan valores
ya interpretados; las del final cargan `config.settings` en un proceso aparte, para
comprobar que el guard recibe lo mismo que usa Django.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from config.envguard import (
    WEAKENABLE_DEFENSES,
    check_production_env,
    check_storage_separation,
    is_placeholder,
)

CLAVE_BUENA = "k7Qm2vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN9qWxYzBv"  # 47… se completa abajo
CLAVE_BUENA = CLAVE_BUENA + "123"  # 50 caracteres, variados
ORIGENES_BUENOS = ["https://revista.midominio.cl"]

# Configuración mínima aceptable, ya interpretada, base de las variantes de cada test.
BUENA = {
    "DJANGO_SECRET_KEY": CLAVE_BUENA,
    "POSTGRES_PASSWORD": "una-contrasena-de-verdad-larga",
    "REDIS_PASSWORD": "otra-contrasena-de-verdad",
    "CELERY_BROKER_URL": "",
    "DJANGO_ALLOWED_HOSTS": ["revista.midominio.cl"],
    "DJANGO_CSRF_TRUSTED_ORIGINS": ORIGENES_BUENOS,
    "AXES_ENABLED": True,
    "RATELIMIT_ENABLE": True,
    "DJANGO_HSTS_SECONDS": 31536000,
    "DJANGO_ALLOW_WEAKENED": [],
}


def _check(values_extra=None, secret=CLAVE_BUENA, origins=None):
    values = {**BUENA, **(values_extra or {}), "DJANGO_SECRET_KEY": secret}
    if origins is not None:
        values["DJANGO_CSRF_TRUSTED_ORIGINS"] = origins
    return check_production_env(values)


def test_configuracion_correcta_no_da_problemas():
    assert _check() == []


def test_placeholder_de_la_plantilla_de_produccion_es_rechazado():
    """EL fallo original: estos son los valores literales que traía .env.prod.example."""
    problemas = _check(
        {"POSTGRES_PASSWORD": "CAMBIA-ESTO-por-una-contrasena-fuerte"},
        secret="CAMBIA-ESTO-por-una-clave-larga-y-secreta",
    )
    assert any("DJANGO_SECRET_KEY" in p for p in problemas)
    assert any("POSTGRES_PASSWORD" in p for p in problemas)


def test_secretos_vacios_de_la_plantilla_son_rechazados():
    # La plantilla ahora los deja vacíos: el guard debe atraparlos igual.
    problemas = _check({"POSTGRES_PASSWORD": "", "REDIS_PASSWORD": ""}, secret="")
    assert any("DJANGO_SECRET_KEY" in p for p in problemas)
    assert any("POSTGRES_PASSWORD" in p for p in problemas)
    assert any("REDIS_PASSWORD" in p for p in problemas)


def test_clave_secreta_corta_o_poco_variada_es_rechazada():
    assert any("débil" in p for p in _check(secret="corta"))
    assert any("débil" in p for p in _check(secret="a" * 60))  # larga pero un solo carácter


def test_centinelas_de_desarrollo_siguen_rechazados():
    assert any("DJANGO_SECRET_KEY" in p for p in _check(secret="dev-insecure-change-me"))
    assert any("POSTGRES_PASSWORD" in p for p in _check({"POSTGRES_PASSWORD": "resenas"}))
    assert any(
        "DJANGO_ALLOWED_HOSTS" in p
        for p in _check({"DJANGO_ALLOWED_HOSTS": ["localhost", "127.0.0.1", "0.0.0.0"]})
    )


def test_comodin_en_allowed_hosts_es_rechazado():
    problemas = _check({"DJANGO_ALLOWED_HOSTS": ["midominio.cl", "*"]})
    assert any("comodín" in p for p in problemas)


def test_origen_csrf_sin_https_es_rechazado():
    problemas = _check(origins=["http://revista.midominio.cl"])
    assert any("https" in p for p in problemas)


def test_redis_sin_password_es_rechazado_salvo_broker_explicito():
    assert any("REDIS_PASSWORD" in p for p in _check({"REDIS_PASSWORD": ""}))
    # Con una URL de broker explícita (Redis gestionado con sus credenciales), no se exige.
    sin_redis = _check({"REDIS_PASSWORD": "", "CELERY_BROKER_URL": "redis://user:pw@ext:6379/0"})
    assert not any("REDIS_PASSWORD" in p for p in sin_redis)


def test_example_com_no_se_considera_placeholder():
    """Regresión: `example.com` es el dominio reservado por la RFC 2606 y es el uso
    CORRECTO en entornos de prueba — el propio CI usa `ci.example.com`. Una versión
    anterior de este guard lo marcaba como placeholder y habría dejado el CI en rojo."""
    assert not is_placeholder("ci.example.com")
    assert (
        _check({"DJANGO_ALLOWED_HOSTS": ["ci.example.com"]}, origins=["https://ci.example.com"])
        == []
    )


@pytest.mark.parametrize("name", sorted(WEAKENABLE_DEFENSES))
def test_each_weakened_defense_is_refused_unless_named(name):
    off = {"AXES_ENABLED": False, "RATELIMIT_ENABLE": False, "DJANGO_HSTS_SECONDS": 0}[name]
    refused = _check({name: off})
    assert any(p.startswith(name) for p in refused), refused
    # Nombrarla en DJANGO_ALLOW_WEAKENED es la autorización explícita.
    assert _check({name: off, "DJANGO_ALLOW_WEAKENED": [name]}) == []


def test_allow_weakened_rejects_names_it_does_not_know():
    """Una errata en la autorización no puede pasar por buena."""
    problems = _check({"RATELIMIT_ENABLE": False, "DJANGO_ALLOW_WEAKENED": ["RATELIMIT"]})
    assert any(p.startswith("DJANGO_ALLOW_WEAKENED") and "RATELIMIT" in p for p in problems)
    # Y la defensa sigue sin autorizar.
    assert any(p.startswith("RATELIMIT_ENABLE") for p in problems)


def test_private_media_inside_public_media_is_refused(tmp_path):
    media = tmp_path / "mediafiles"
    assert check_storage_separation(media, media / "submissions")
    assert check_storage_separation(media, media)
    # Control positivo: dos carpetas hermanas, como en el compose.
    assert check_storage_separation(media, tmp_path / "private_media") == []


def test_private_storage_has_no_public_url():
    from apps.submissions.models import private_storage

    with pytest.raises(ValueError, match="no tienen URL pública"):
        private_storage().url("submissions/2026/11/manuscrito.pdf")


# ── Los settings reales, en un proceso aparte ─────────────────
# Importar `config.settings` aplica el guard: así se comprueba que recibe los valores que
# usa Django, interpretados por config/env.py. Cada caso tarda alrededor de un segundo.
BACKEND_DIR = Path(__file__).resolve().parent.parent
CI_SECRET = "ci-prod-secret-Kx7mQ9vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN9qW"


def _load_settings(env, expression="'ok'"):
    """Importa config.settings con `env` como único entorno e imprime `expression`."""
    return subprocess.run(
        [sys.executable, "-c", f"import config.settings as s; print({expression})"],
        cwd=BACKEND_DIR,
        env={"PATH": os.environ["PATH"], "DJANGO_DEBUG": "0", **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


# Entornos DEBUG=0 reales de .github/workflows/ci.yml. Se fijan aquí para que endurecer
# el guard no deje el CI en rojo sin que la suite lo avise antes.
ENTORNOS_CI = {
    "test / check --deploy": {
        "DJANGO_SECRET_KEY": CI_SECRET,
        "POSTGRES_PASSWORD": "ci-strong-db-password",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "DJANGO_ALLOWED_HOSTS": "ci.example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://ci.example.com",
    },
    "build-prod / collectstatic": {
        "DJANGO_SECRET_KEY": CI_SECRET,
        "POSTGRES_PASSWORD": "ci-strong-db-password",
        "REDIS_PASSWORD": "ci-strong-redis-password",
        "DJANGO_ALLOWED_HOSTS": "ci.example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://ci.example.com",
    },
    "prod-runtime": {
        "DJANGO_SECRET_KEY": CI_SECRET,
        "POSTGRES_PASSWORD": "ci-strong-db-password",
        "CELERY_BROKER_URL": "redis://qa13-redis:6379/0",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://localhost",
        "DJANGO_SECURE_SSL_REDIRECT": "0",
    },
    "backup-restore / migrate": {
        "DJANGO_SECRET_KEY": CI_SECRET,
        "POSTGRES_PASSWORD": "ci-strong-db-password",
        "REDIS_PASSWORD": "ci-strong-redis-password",
        "DJANGO_ALLOWED_HOSTS": "localhost",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://localhost",
    },
}


@pytest.mark.parametrize("nombre", sorted(ENTORNOS_CI))
def test_los_entornos_debug0_del_ci_pasan_el_guard(nombre):
    result = _load_settings(ENTORNOS_CI[nombre])
    assert result.returncode == 0, f"{nombre} quedaría en rojo: {result.stderr[-500:]}"


def test_settings_refuse_a_weakened_defense_unless_authorized():
    env = {**ENTORNOS_CI["build-prod / collectstatic"], "RATELIMIT_ENABLE": "off"}
    refused = _load_settings(env)
    assert refused.returncode != 0
    assert "RATELIMIT_ENABLE (apaga una defensa" in refused.stderr

    allowed = _load_settings(
        {
            **env,
            "DJANGO_ALLOW_WEAKENED": "RATELIMIT_ENABLE",
            "DJANGO_ALLOWED_HOSTS": "revista.cl, www.revista.cl",
        },
        "s.RATELIMIT_ENABLE, s.ALLOWED_HOSTS",
    )
    assert allowed.returncode == 0, allowed.stderr[-500:]
    # La defensa queda apagada, como se pidió, y los hosts sin los espacios de la lista.
    assert allowed.stdout.startswith("False ['revista.cl', 'www.revista.cl'")
    assert "defensas apagadas" in allowed.stderr


def test_settings_name_the_variable_of_an_unknown_boolean():
    env = {**ENTORNOS_CI["build-prod / collectstatic"], "AXES_ENABLED": "verdadero"}
    result = _load_settings(env)
    assert result.returncode != 0
    assert "AXES_ENABLED='verdadero'" in result.stderr
