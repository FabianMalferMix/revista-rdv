"""Guard de arranque en producción: rechaza configuraciones inseguras.

Vive fuera de `settings.py` para poder probarlo como función pura, sin recargar los
ajustes de Django. Recibe los valores ya interpretados por `config.env`, los mismos que
usará Django, y no vuelve a leer el entorno por su cuenta.

La validación es positiva: comprueba que cada valor sea aceptable, en vez de compararlo
con una lista de valores de ejemplo conocidos, que es lo que deja pasar una plantilla
nueva.
"""

from pathlib import Path
from urllib.parse import urlsplit

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
# sustituir, en cambio, es silencioso.
PLACEHOLDER_MARKERS = ("cambia-esto", "change-me", "changeme")
# Los valores del correo que traía la plantilla de producción.
EMAIL_TEMPLATE_MARKERS = ("tudominio", "tuproveedor")
EMAIL_TEMPLATE_VALUES = ("secreto", "usuario")

# Umbrales de `security.W009` de Django: se replican aquí para que el arranque y el
# `check --deploy` del CI coincidan.
MIN_SECRET_LENGTH = 50
MIN_SECRET_UNIQUE_CHARS = 5

# Defensas que una variable de entorno puede apagar, con la prueba de que está apagada.
# Con DEBUG=0, apagar una exige nombrar su variable en DJANGO_ALLOW_WEAKENED: así un
# interruptor que se quedó puesto después de una prueba no pasa en silencio.
WEAKENABLE_DEFENSES = {
    "AXES_ENABLED": lambda values: not values["AXES_ENABLED"],
    "RATELIMIT_ENABLE": lambda values: not values["RATELIMIT_ENABLE"],
    "DJANGO_HSTS_SECONDS": lambda values: values["DJANGO_HSTS_SECONDS"] <= 0,
    # Sin Sentry, nadie se entera de un error: la página 500 promete que alguien lo mira.
    "SENTRY_DSN": lambda values: not values["SENTRY_DSN"],
}


def is_placeholder(value):
    """True si el valor parece copiado de una plantilla sin sustituir."""
    lowered = (value or "").strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def weakened_defenses(values):
    """Los nombres de las defensas que la configuración apaga."""
    return [name for name, is_off in WEAKENABLE_DEFENSES.items() if is_off(values)]


def check_production_env(values):
    """Devuelve la lista de problemas de configuración para un despliegue con DEBUG=0.

    `values` reúne los valores ya interpretados, con el nombre de su variable de
    entorno como clave. Lista vacía significa configuración aceptable.
    """
    problems = []

    # ── Clave secreta ────────────────────────────────────────
    secret_key = values["DJANGO_SECRET_KEY"]
    if secret_key == INSECURE_SECRET or is_placeholder(secret_key):
        problems.append("DJANGO_SECRET_KEY (valor de ejemplo)")
    elif len(secret_key) < MIN_SECRET_LENGTH or len(set(secret_key)) < MIN_SECRET_UNIQUE_CHARS:
        problems.append(
            f"DJANGO_SECRET_KEY (débil: exige {MIN_SECRET_LENGTH}+ caracteres "
            f"y {MIN_SECRET_UNIQUE_CHARS}+ distintos)"
        )

    # ── Contraseña de la base de datos ───────────────────────
    db_password = values["POSTGRES_PASSWORD"]
    if db_password in ("", INSECURE_DB_PASSWORD) or is_placeholder(db_password):
        problems.append("POSTGRES_PASSWORD")

    # ── Redis: el broker y la caché, con contraseña ──────────
    # Se miran las URL efectivas, las que usarán Celery y la caché, salgan de REDIS_PASSWORD
    # o de una URL fijada a mano.
    for name in ("CELERY_BROKER_URL", "CACHE_URL"):
        password = urlsplit(values[name]).password or ""
        if not password or is_placeholder(password):
            problems.append(f"{name} (sin contraseña: define REDIS_PASSWORD)")

    # ── Hosts permitidos ─────────────────────────────────────
    allowed_hosts = list(values["DJANGO_ALLOWED_HOSTS"])
    if not allowed_hosts or allowed_hosts == DEFAULT_HOSTS.split(","):
        problems.append("DJANGO_ALLOWED_HOSTS")
    elif "*" in allowed_hosts:
        problems.append("DJANGO_ALLOWED_HOSTS (el comodín '*' desactiva la validación de Host)")

    # ── Orígenes de confianza para CSRF ──────────────────────
    # Un origen http:// aquí acepta como legítimo un POST llegado por texto plano.
    origins = values["DJANGO_CSRF_TRUSTED_ORIGINS"]
    if not origins:
        problems.append("DJANGO_CSRF_TRUSTED_ORIGINS")
    else:
        insecure_origins = [o for o in origins if not o.startswith("https://")]
        if insecure_origins:
            problems.append(
                "DJANGO_CSRF_TRUSTED_ORIGINS (exige https://): " + ", ".join(insecure_origins)
            )

    # ── Correo ───────────────────────────────────────────────
    # Un correo mal configurado no impide arrancar: falla después, en el worker, en cada
    # confirmación, mientras el formulario responde «te enviamos un correo».
    if not values["DEFAULT_FROM_EMAIL"]:
        problems.append(
            "DEFAULT_FROM_EMAIL (el remitente, por ejemplo «Nombre <no-reply@dominio>»)"
        )
    for name in ("DEFAULT_FROM_EMAIL", "EMAIL_HOST", "EMAIL_HOST_PASSWORD"):
        value = (values[name] or "").strip().lower()
        if (
            is_placeholder(value)
            or any(marker in value for marker in EMAIL_TEMPLATE_MARKERS)
            or value in EMAIL_TEMPLATE_VALUES
        ):
            problems.append(f"{name} (valor de ejemplo)")

    # ── Origen de las URL absolutas ──────────────────────────
    problems += _site_url_problems(values)

    # ── Defensas apagadas ────────────────────────────────────
    allowed = values["DJANGO_ALLOW_WEAKENED"]
    unknown = [name for name in allowed if name not in WEAKENABLE_DEFENSES]
    if unknown:
        problems.append(
            "DJANGO_ALLOW_WEAKENED (no son defensas que se puedan apagar: "
            + ", ".join(unknown)
            + ")"
        )
    for name in weakened_defenses(values):
        if name not in allowed:
            problems.append(f"{name} (apaga una defensa: nómbrala en DJANGO_ALLOW_WEAKENED)")

    return problems


def _site_url_problems(values):
    """SITE_URL: un origen https, sin www, servido por Caddy y aceptado por Django."""
    site_url = values["SITE_URL"]
    if not site_url:
        return ["SITE_URL (el origen de las URL absolutas, por ejemplo https://revista.cl)"]
    parts = urlsplit(site_url)
    if parts.scheme != "https" or not parts.hostname:
        return [f"SITE_URL (exige https://dominio): {site_url}"]
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        return [f"SITE_URL (solo el origen, sin ruta): {site_url}"]
    from django.http.request import validate_host

    host = parts.hostname
    problems = []
    if host.startswith("www."):
        problems.append(f"SITE_URL (sin www: {host})")
    if not validate_host(host, values["DJANGO_ALLOWED_HOSTS"]):
        problems.append(f"SITE_URL ({host} no está en DJANGO_ALLOWED_HOSTS)")
    site_address = values["SITE_ADDRESS"]
    if site_address and not site_address.startswith(":") and site_address != host:
        problems.append(f"SITE_URL ({host} no es el dominio que sirve Caddy: {site_address})")
    return problems


def check_storage_separation(media_root, private_media_root):
    """Lo privado no puede quedar dentro de lo que se sirve en /media/."""
    media = Path(media_root).resolve()
    private = Path(private_media_root).resolve()
    if private.is_relative_to(media):
        return [
            f"DJANGO_PRIVATE_MEDIA_ROOT ({private}) queda dentro de MEDIA_ROOT ({media}), "
            "que se sirve en público"
        ]
    return []
