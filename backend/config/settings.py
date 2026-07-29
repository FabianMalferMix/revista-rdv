"""Configuración de Django para el proyecto Reseñas."""

import os
import sys
from pathlib import Path

from celery.schedules import crontab

from config import envguard

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Seguridad ─────────────────────────────────────────────
# Fail-safe: DEBUG apagado por defecto; en producción exige credenciales propias.
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

_INSECURE_SECRET = envguard.INSECURE_SECRET
_DEFAULT_HOSTS = envguard.DEFAULT_HOSTS

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_SECRET)
# Rotación de clave con solapamiento (las sesiones firmadas con claves previas siguen válidas).
SECRET_KEY_FALLBACKS = [
    k for k in os.environ.get("DJANGO_SECRET_KEY_FALLBACKS", "").split(",") if k
]
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", _DEFAULT_HOSTS).split(",")
# El healthcheck del contenedor pega a http://127.0.0.1:8000/healthz/ con Host=127.0.0.1;
# el loopback siempre se permite (web no se publica al host y va tras Caddy, que envía el
# Host real), para que la sonda no dé DisallowedHost→400 sin depender de DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS += [h for h in ("127.0.0.1", "localhost") if h not in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Guard de producción: con DEBUG=0 rechaza arrancar con valores de ejemplo o inseguros.
# La lógica vive en config.envguard (función pura, probada en tests/test_envguard.py):
# valida que cada valor sea ACEPTABLE, en vez de compararlo con una lista de centinelas
# conocidos — que era justo lo que dejaba pasar los placeholders de .env.prod.example.
if not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    _insecure = envguard.check_production_env(os.environ, SECRET_KEY, CSRF_TRUSTED_ORIGINS)
    if _insecure:
        raise ImproperlyConfigured(
            "Configuración insegura con DEBUG=0 — corrige en el entorno: "
            + ", ".join(_insecure)
            + "."
        )

# ── Aplicaciones ──────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    # Apps del proyecto (orden por dependencias: media es la base)
    "apps.media",
    "apps.people",
    "apps.reviews",
    "apps.content",
    "apps.showcase",
    "apps.agenda",
    "apps.community",
    "apps.submissions",
    # Anti-fuerza-bruta en el login del admin.
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # CSP restrictiva con nonce por petición (tras WhiteNoise: no aplica a estáticos).
    "config.csp.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # django-axes: debe ir al final, tras AuthenticationMiddleware.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.content.context_processors.nav",
                "apps.content.context_processors.canonical",
                "apps.showcase.context_processors.site_profile",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Base de datos ─────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "resenas"),
        "USER": os.environ.get("POSTGRES_USER", "resenas"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "resenas"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")),
    }
}

# ── Validación de contraseñas ─────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Anti-abuso ────────────────────────────────────────────
# django-axes (fuerza bruta en /admin/): el backend de axes debe ir primero.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = int(os.environ.get("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = 1  # horas de bloqueo tras superar el límite
AXES_LOCKOUT_PARAMETERS = ["ip_address"]  # bloquea la IP atacante
AXES_RESET_ON_SUCCESS = True
# La IP real del cliente la resuelve config.clientip.client_ip (mismo resolver que
# django-ratelimit): tras Caddy, la entrada derecha de X-Forwarded-For. Este callable
# tiene precedencia en axes, así que NO se usan los AXES_IPWARE_*.
AXES_CLIENT_IP_CALLABLE = "config.clientip.client_ip"
# En tests se desactiva (usan force_login); el test de bloqueo lo reactiva puntualmente.
AXES_ENABLED = os.environ.get("AXES_ENABLED", "0" if "pytest" in sys.modules else "1") == "1"

# django-ratelimit: contadores en la caché por defecto (LocMem en dev, Redis en prod).
# La IP se resuelve con el MISMO callable que axes para que ambos cuenten por la misma
# IP tras el proxy (si divergen, el límite por IP se colapsa en un cubo global — #01).
RATELIMIT_ENABLE = os.environ.get("RATELIMIT_ENABLE", "1") == "1"
RATELIMIT_IP_META_KEY = "config.clientip.client_ip"

# Límites de subida (defensa ante cuerpos de request abusivos; el proxy corta antes).
# El adjunto de envíos permite hasta 10 MB (validado en el form); Caddy corta en 12 MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_DATA_UPLOAD_MAX", str(3 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200

# ── Internacionalización ──────────────────────────────────
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# ── Estáticos y medios ────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"
# Almacenamiento privado (envíos): fuera de MEDIA_ROOT, nunca servido públicamente.
PRIVATE_MEDIA_ROOT = os.environ.get("DJANGO_PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media"))

# En producción WhiteNoise sirve los estáticos comprimidos y con hash; en desarrollo
# se usa el almacenamiento simple (el manifiesto exigiría collectstatic).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            # Manifiesto + compresión WhiteNoise, exceptuando el subárbol de TinyMCE
            # (se sirve sin hash para no romper su carga perezosa relativa).
            else "config.staticfiles.VendoredStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Celery / Redis ────────────────────────────────────────
# La URL se deriva de REDIS_PASSWORD (única fuente): con contraseña incluye la auth.
_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
_REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
_REDIS_AUTH = f":{_REDIS_PASSWORD}@" if _REDIS_PASSWORD else ""
_REDIS_BASE = f"redis://{_REDIS_AUTH}{_REDIS_HOST}:{_REDIS_PORT}"
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", f"{_REDIS_BASE}/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", f"{_REDIS_BASE}/1")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "publicar-piezas-programadas": {
        "task": "apps.content.tasks.publish_due_items",
        "schedule": 60.0,  # cada minuto (artículos y poemas)
    },
    "purgar-pii-caducada": {
        "task": "apps.submissions.tasks.purge_stale_pii",
        "schedule": crontab(hour=4, minute=30, day_of_week=1),  # lunes 04:30 (minimización)
    },
}
# En tests las tareas corren en el acto (síncronas): permite verificar el correo
# de confirmación por Celery sin worker. En dev/prod es asíncrono normal.
CELERY_TASK_ALWAYS_EAGER = "pytest" in sys.modules

# Límites de tiempo por tarea (S-23): sin ellos, un SMTP que acepta la conexión pero
# no responde dejaba el slot del worker ocupado indefinidamente. El soft dispara una
# excepción capturable (permite el reintento); el duro mata el proceso como último
# recurso. Se completa con EMAIL_TIMEOUT, más abajo.
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "30"))
CELERY_TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "60"))
# Con acks_late, una tarea que muere por time limit se reencola en vez de perderse;
# prefetch 1 evita que un worker acapare tareas que no va a poder atender.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# ── Caché ─────────────────────────────────────────────────
# Redis en producción: los contadores de django-ratelimit se comparten entre los
# workers de gunicorn y persisten entre recargas (db 2, distinta del broker/resultados).
# En dev/tests, LocMem (hermético, sin dependencia externa; conftest limpia por test).
if DEBUG:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {
        "default": {
            # Backend tolerante: con Redis caído, django-ratelimit propagaba
            # ConnectionError y los formularios públicos devolvían 500 (S-22).
            "BACKEND": "config.cache.ResilientRedisCache",
            "LOCATION": f"{_REDIS_BASE}/2",
        }
    }

# Política explícita cuando el contador de rate limit no está disponible: limitar
# (fail-closed). Quedarse sin control anti-abuso es peor que rechazar temporalmente un
# envío, y con Redis caído el sitio ya está degradado (Celery tampoco encola).
RATELIMIT_FAIL_OPEN = False

# ── Cabeceras de seguridad ────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# CSP restrictiva (config.csp): con DJANGO_CSP_REPORT_ONLY=1 solo reporta, no bloquea.
CSP_REPORT_ONLY = os.environ.get("DJANGO_CSP_REPORT_ONLY", "0") == "1"
# Las sondas internas pegan por HTTP a /healthz/ y /readyz/: que no se redirijan a HTTPS.
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$", r"^readyz/?$"]

if not DEBUG:
    # Detrás de un proxy que termina TLS (nginx, etc.).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HTTPS forzado y HSTS activos por defecto en producción (opt-out por env).
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ── Correo ────────────────────────────────────────────────
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
# Sin timeout, smtplib espera indefinidamente a un servidor que acepta la conexión y
# luego calla: bastaba para inmovilizar los slots del worker (S-23).
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Reseñas <no-reply@resenas.cl>")

# ── Logging a stdout (JSON en producción, texto plano legible en desarrollo) ──
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {"()": "config.logformat.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}

# ── Observabilidad: Sentry (opt-in por SENTRY_DSN) ────────
# Con SENTRY_DSN definido se captura error tracking; sentry-sdk auto-habilita las
# integraciones de Django y Celery (basta con inicializar aquí, importado por ambos
# procesos vía DJANGO_SETTINGS_MODULE). Sin DSN no hace nada (dev/tests intactos).
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "dev"),
        release=os.environ.get("SENTRY_RELEASE") or None,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
    )
