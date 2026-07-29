"""Guard de arranque en producción: rechaza configuraciones inseguras (hallazgo S-02).

Vive fuera de `settings.py` para poder probarlo como función pura, sin recargar los
ajustes de Django.

El guard anterior comparaba por IGUALDAD contra los centinelas de DESARROLLO
(`dev-insecure-change-me`, `resenas`), pero la plantilla de PRODUCCIÓN
(`.env.prod.example`) usa otros valores (`CAMBIA-ESTO-…`). Resultado: el operador que
seguía `docs/despliegue.md` al pie de la letra —cambiando solo lo que rompe visiblemente
el sitio— arrancaba con la clave y las contraseñas publicadas en el repositorio, y sin
una sola advertencia, mientras la propia plantilla le aseguraba lo contrario.

Por eso ahora la validación es POSITIVA (comprobar que el valor es aceptable) en vez de
una lista negra de centinelas conocidos.
"""

# Valores por defecto de desarrollo, inseguros en producción.
INSECURE_SECRET = "dev-insecure-change-me"
INSECURE_DB_PASSWORD = "resenas"
DEFAULT_HOSTS = "localhost,127.0.0.1,0.0.0.0"

# Fragmentos que delatan un SECRETO de plantilla sin sustituir. Se comparan en
# minúsculas y por inclusión.
#
# Deliberadamente NO se incluye "example": `example.com` es el dominio reservado por
# la RFC 2606 y es justo lo correcto en hosts de prueba (el propio CI usa
# `ci.example.com`). Y esta comprobación se aplica SOLO a los secretos, no a hosts ni
# orígenes: dejar `revista.tudominio.cl` sin sustituir no es un agujero, el sitio
# simplemente no responde (DisallowedHost), así que se corrige solo. Un secreto sin
# sustituir, en cambio, es silencioso y es exactamente el fallo que se está cerrando.
PLACEHOLDER_MARKERS = ("cambia-esto", "change-me", "changeme")

# Umbrales de `security.W009` de Django: se replican aquí para que el arranque y el
# `check --deploy` del CI coincidan (antes el CI era más estricto que el despliegue).
MIN_SECRET_LENGTH = 50
MIN_SECRET_UNIQUE_CHARS = 5


def is_placeholder(value):
    """True si el valor parece copiado de una plantilla sin sustituir."""
    lowered = (value or "").strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def check_production_env(env, secret_key, csrf_trusted_origins):
    """Devuelve la lista de problemas de configuración para un despliegue con DEBUG=0.

    `env` es un mapeo tipo `os.environ`. Lista vacía significa configuración aceptable.
    """
    problems = []

    # ── Clave secreta ────────────────────────────────────────
    if secret_key == INSECURE_SECRET or is_placeholder(secret_key):
        problems.append("DJANGO_SECRET_KEY (valor de ejemplo)")
    elif len(secret_key) < MIN_SECRET_LENGTH or len(set(secret_key)) < MIN_SECRET_UNIQUE_CHARS:
        problems.append(
            f"DJANGO_SECRET_KEY (débil: exige {MIN_SECRET_LENGTH}+ caracteres "
            f"y {MIN_SECRET_UNIQUE_CHARS}+ distintos)"
        )

    # ── Contraseña de la base de datos ───────────────────────
    db_password = env.get("POSTGRES_PASSWORD", INSECURE_DB_PASSWORD)
    if db_password in ("", INSECURE_DB_PASSWORD) or is_placeholder(db_password):
        problems.append("POSTGRES_PASSWORD")

    # ── Contraseña de Redis ──────────────────────────────────
    # Solo se exige si no se ha fijado una URL de broker explícita, que puede apuntar a
    # un Redis gestionado con sus credenciales embebidas.
    #
    # Residuo conocido y aceptado: quien fije a mano un CELERY_BROKER_URL SIN
    # credenciales evita esta comprobación. Se acepta porque es un acto deliberado,
    # mientras que el fallo que este guard cierra —olvidar sustituir un placeholder
    # siguiendo la documentación— es silencioso y mucho más probable. La plantilla de
    # producción no define CELERY_BROKER_URL, así que el camino documentado sí queda
    # cubierto.
    if not env.get("CELERY_BROKER_URL", ""):
        redis_password = env.get("REDIS_PASSWORD", "")
        if not redis_password or is_placeholder(redis_password):
            problems.append("REDIS_PASSWORD (broker y caché sin autenticar)")

    # ── Hosts permitidos ─────────────────────────────────────
    allowed_hosts = env.get("DJANGO_ALLOWED_HOSTS", "")
    if allowed_hosts in ("", DEFAULT_HOSTS):
        problems.append("DJANGO_ALLOWED_HOSTS")
    elif any(h.strip() == "*" for h in allowed_hosts.split(",")):
        problems.append("DJANGO_ALLOWED_HOSTS (el comodín '*' desactiva la validación de Host)")

    # ── Orígenes de confianza para CSRF ──────────────────────
    # Un origen http:// aquí acepta como legítimo un POST llegado por texto plano.
    if not csrf_trusted_origins:
        problems.append("DJANGO_CSRF_TRUSTED_ORIGINS")
    else:
        insecure_origins = [o for o in csrf_trusted_origins if not o.strip().startswith("https://")]
        if insecure_origins:
            problems.append(
                "DJANGO_CSRF_TRUSTED_ORIGINS (exige https://): " + ", ".join(insecure_origins)
            )

    return problems
