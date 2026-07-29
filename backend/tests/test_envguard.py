"""Guard de arranque en producción (hallazgo S-02).

El guard anterior comparaba por igualdad contra los centinelas de DESARROLLO, pero la
plantilla de PRODUCCIÓN usa otros placeholders: un despliegue que seguía la
documentación al pie de la letra arrancaba con la clave y las contraseñas publicadas
en el repositorio, sin una sola advertencia y afirmando lo contrario.
"""

from config.envguard import check_production_env, is_placeholder

# Configuración mínima aceptable, base de las variantes de cada test.
BUENA = {
    "POSTGRES_PASSWORD": "una-contrasena-de-verdad-larga",
    "REDIS_PASSWORD": "otra-contrasena-de-verdad",
    "DJANGO_ALLOWED_HOSTS": "revista.midominio.cl",
}
CLAVE_BUENA = "k7Qm2vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN9qWxYzBv"  # 47… se completa abajo
CLAVE_BUENA = CLAVE_BUENA + "123"  # 50 caracteres, variados
ORIGENES_BUENOS = ["https://revista.midominio.cl"]


def _check(env_extra=None, secret=CLAVE_BUENA, origins=None):
    env = {**BUENA, **(env_extra or {})}
    return check_production_env(env, secret, ORIGENES_BUENOS if origins is None else origins)


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
        for p in _check({"DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,0.0.0.0"})
    )


def test_comodin_en_allowed_hosts_es_rechazado():
    problemas = _check({"DJANGO_ALLOWED_HOSTS": "midominio.cl,*"})
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
        _check({"DJANGO_ALLOWED_HOSTS": "ci.example.com"}, origins=["https://ci.example.com"]) == []
    )


# Entornos DEBUG=0 reales de .github/workflows/ci.yml. Se fijan aquí para que endurecer
# el guard no vuelva a dejar el CI en rojo sin que la suite lo avise antes (lección de
# los PRs #61/#62: validar en condiciones de CI ANTES de mergear).
CI_SECRET = "ci-prod-secret-Kx7mQ9vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN9qW"
ENTORNOS_CI = {
    "build-prod / collectstatic": (
        {
            "POSTGRES_PASSWORD": "ci-strong-db-password",
            "REDIS_PASSWORD": "ci-strong-redis-password",
            "DJANGO_ALLOWED_HOSTS": "ci.example.com",
        },
        ["https://ci.example.com"],
    ),
    "prod-runtime": (
        {
            "POSTGRES_PASSWORD": "ci-strong-db-password",
            "CELERY_BROKER_URL": "redis://qa13-redis:6379/0",
            "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        },
        ["https://localhost"],
    ),
    "backup-restore / migrate": (
        {
            "POSTGRES_PASSWORD": "ci-strong-db-password",
            "REDIS_PASSWORD": "ci-strong-redis-password",
            "DJANGO_ALLOWED_HOSTS": "localhost",
        },
        ["https://localhost"],
    ),
}


def test_los_entornos_debug0_del_ci_pasan_el_guard():
    for nombre, (env, origins) in ENTORNOS_CI.items():
        assert check_production_env(env, CI_SECRET, origins) == [], f"{nombre} quedaría en rojo"
