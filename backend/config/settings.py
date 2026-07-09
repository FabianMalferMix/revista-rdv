"""Configuración de Django para el proyecto Reseñas."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Seguridad ─────────────────────────────────────────────
# Fail-safe: DEBUG apagado por defecto; en producción exige una SECRET_KEY propia.
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

_INSECURE_SECRET = "dev-insecure-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_SECRET)
if not DEBUG and SECRET_KEY == _INSECURE_SECRET:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "Define un DJANGO_SECRET_KEY propio y secreto cuando DEBUG=0."
    )

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0"
).split(",")

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
    "apps.community",
    "apps.submissions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
PRIVATE_MEDIA_ROOT = os.environ.get(
    "DJANGO_PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")
)

# En producción WhiteNoise sirve los estáticos comprimidos y con hash; en desarrollo
# se usa el almacenamiento simple (el manifiesto exigiría collectstatic).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Celery ────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "publicar-articulos-programados": {
        "task": "apps.content.tasks.publish_due_articles",
        "schedule": 60.0,  # cada minuto
    },
}

# ── Seguridad ─────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    # Detrás de un proxy que termina TLS (nginx, etc.).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Activar cuando sirvas por HTTPS (requiere que el proxy fije X-Forwarded-Proto).
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
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
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "Reseñas <no-reply@resenas.cl>"
)

# ── Logging a stdout ──────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
}
