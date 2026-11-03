"""Configuración de Django para el proyecto Reseñas."""

import logging
import sys
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from config import envguard
from config.env import env_bool, env_float, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Seguridad ─────────────────────────────────────────────
# Fail-safe: DEBUG apagado por defecto; en producción exige credenciales propias (el guard
# de producción, al final de este archivo).
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY", envguard.INSECURE_SECRET)
# Rotación de clave con solapamiento (las sesiones firmadas con claves previas siguen válidas).
SECRET_KEY_FALLBACKS = env_list("DJANGO_SECRET_KEY_FALLBACKS")
_ALLOWED_HOSTS_FROM_ENV = env_list("DJANGO_ALLOWED_HOSTS", envguard.DEFAULT_HOSTS)
# El healthcheck del contenedor pega a http://127.0.0.1:8000/healthz/ con Host=127.0.0.1;
# el loopback siempre se permite (web no se publica al host y va tras Caddy, que envía el
# Host real), para que la sonda no dé DisallowedHost→400 sin depender de DJANGO_ALLOWED_HOSTS.
ALLOWED_HOSTS = _ALLOWED_HOSTS_FROM_ENV + [
    h for h in ("127.0.0.1", "localhost") if h not in _ALLOWED_HOSTS_FROM_ENV
]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
# El origen de las URL absolutas (canonical, Open Graph, JSON-LD, sitemap, robots y feeds):
# sale de aquí y no del Host de cada petición (config/origin.py). Con DEBUG=0 es
# obligatorio, en https y sin www; en desarrollo, el servidor local.
SITE_URL = env_str("SITE_URL", "http://localhost:8000" if DEBUG else "").rstrip("/")

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
    # Apps del proyecto. El orden no expresa dependencias: las apps se importan entre sí.
    "apps.media",
    "apps.people",
    "apps.reviews",
    "apps.content",
    "apps.showcase",
    "apps.agenda",
    "apps.community",
    "apps.submissions",
    # La marca de base de desarrollo, que exige la exportación de los datos de desarrollo.
    "apps.devtools",
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
                "config.context_processors.version_estaticos",
                "config.context_processors.origin",
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
        "NAME": env_str("POSTGRES_DB", "resenas"),
        "USER": env_str("POSTGRES_USER", "resenas"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", envguard.INSECURE_DB_PASSWORD),
        "HOST": env_str("POSTGRES_HOST", "db"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DJANGO_CONN_MAX_AGE", 60),
        # Una conexión reutilizada se comprueba antes de usarla: si la base se reinició, la
        # petición abre otra en vez de responder 500.
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            # Sin plazo, psycopg espera hasta 130 s a una base que no contesta.
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 5),
            # Una consulta que pasa de este plazo se cancela con un error, en vez de retener un
            # hilo de gunicorn mientras dure: con gthread, --timeout no corta una petición
            # colgada. libpq usa estas `options` en lugar de PGOPTIONS, así que lo que el
            # entorno ponga ahí se suma detrás y manda: el release lo usa para migrar con
            # lock_timeout y sin este plazo (release.sh).
            "options": (
                f"-c statement_timeout={env_int('DB_STATEMENT_TIMEOUT_MS', 15000)} "
                f"{env_str('PGOPTIONS')}"
            ).strip(),
        },
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
AXES_FAILURE_LIMIT = env_int("AXES_FAILURE_LIMIT", 5)
AXES_COOLOFF_TIME = 1  # horas de bloqueo tras superar el límite
# Bloquea la combinación de cuenta e IP: quien prueba contraseñas contra una cuenta queda
# fuera desde su conexión, sin dejar fuera a la dueña de la cuenta desde otra ni a las demás
# cuentas de la misma IP. Y un acierto reinicia solo su propia combinación: con el bloqueo
# por IP, cualquier login correcto desde esa IP borraba los fallos contra todas las cuentas.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# Sin esto, axes responde «Account locked: too many login attempts» en inglés, y en
# una pantalla PÚBLICA: la ve cualquiera que llegue a /admin/login/.
AXES_LOCKOUT_TEMPLATE = "axes_lockout.html"
# La IP real del cliente la resuelve config.clientip.client_ip (mismo resolver que
# django-ratelimit): tras Caddy, la entrada derecha de X-Forwarded-For. Este callable
# tiene precedencia en axes, así que NO se usan los AXES_IPWARE_*.
AXES_CLIENT_IP_CALLABLE = "config.clientip.client_ip"
# En tests se desactiva (usan force_login); el test de bloqueo lo reactiva puntualmente.
AXES_ENABLED = env_bool("AXES_ENABLED", "pytest" not in sys.modules)

# django-ratelimit: contadores en la caché por defecto (LocMem en dev, Redis en prod).
# La IP se resuelve con el MISMO callable que axes para que ambos cuenten por la misma
# IP tras el proxy (si divergen, el límite por IP se colapsa en un cubo global — #01).
RATELIMIT_ENABLE = env_bool("RATELIMIT_ENABLE", True)
RATELIMIT_IP_META_KEY = "config.clientip.client_ip"

# Límites de subida (defensa ante cuerpos de request abusivos; el proxy corta antes).
# El adjunto de envíos permite hasta 10 MB (validado en el form); Caddy corta en 12 MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DJANGO_DATA_UPLOAD_MAX", 3 * 1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200

# ── Internacionalización ──────────────────────────────────
# Django 6.0 cambiará el esquema que `forms.URLField` asume para una URL sin protocolo:
# de http a https. Optar ya por el nuevo comportamiento silencia el
# RemovedInDjango60Warning —que `filterwarnings = error` de pytest.ini convertiría en
# fallo al subir de versión— y de paso es la opción segura: quien teclee «vimeo.com/123»
# en el panel obtiene https, no texto plano.
FORMS_URLFIELD_ASSUME_HTTPS = True

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
# Almacenamiento privado (envíos): fuera de MEDIA_ROOT, nunca servido públicamente. Si
# cayera dentro, Caddy serviría los manuscritos en /media/: el arranque se niega, también
# en desarrollo.
PRIVATE_MEDIA_ROOT = env_str("DJANGO_PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media"))
# El audio y los PDF que solo se sirven publicados (config/protected_media.py): en producción
# los entrega Caddy con X-Accel-Redirect; en desarrollo, sin Caddy delante, Django.
PROTECTED_MEDIA_ACCEL = not DEBUG
_storage_problems = envguard.check_storage_separation(MEDIA_ROOT, PRIVATE_MEDIA_ROOT)
if _storage_problems:
    raise ImproperlyConfigured("; ".join(_storage_problems) + ".")

# En producción collectstatic deja los estáticos con hash y comprimidos (manifiesto de
# WhiteNoise) y los sirve Caddy desde su volumen; en desarrollo se usa el almacenamiento
# simple (el manifiesto exigiría collectstatic).
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
_REDIS_HOST = env_str("REDIS_HOST", "redis")
_REDIS_PORT = env_str("REDIS_PORT", "6379")
_REDIS_PASSWORD = env_str("REDIS_PASSWORD")
_REDIS_AUTH = f":{_REDIS_PASSWORD}@" if _REDIS_PASSWORD else ""
_REDIS_BASE = f"redis://{_REDIS_AUTH}{_REDIS_HOST}:{_REDIS_PORT}"
_BROKER_URL_FROM_ENV = env_str("CELERY_BROKER_URL")
CELERY_BROKER_URL = _BROKER_URL_FROM_ENV or f"{_REDIS_BASE}/0"
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", f"{_REDIS_BASE}/1")
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

# Límites de tiempo de cada tarea: sin ellos, un SMTP que acepta la conexión y no
# responde ocupa un proceso del worker indefinidamente. El blando lanza
# SoftTimeLimitExceeded dentro de la tarea, que termina como fallo salvo que ella misma
# lo capture o lo reintente; el duro mata el proceso. Se completa con EMAIL_TIMEOUT, más
# abajo.
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 30)
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 60)
# acks_late confirma el mensaje cuando la tarea termina, no cuando llega: si cae el
# worker entero, Redis reentrega lo que quedó sin confirmar pasado su visibility_timeout
# (1 h). Una tarea que falla, que agota su límite de tiempo o cuyo proceso muere se
# confirma igual y no vuelve a la cola (task_acks_on_failure_or_timeout y
# task_reject_on_worker_lost, en sus valores por defecto).
# prefetch 1 evita que un worker acapare tareas que no va a poder atender.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Sin esto, el worker abre un proceso por CPU del servidor, sin relación con su carga (una
# tarea por minuto y algún correo) ni con su límite de memoria (WORKER_MEM_LIMIT): con
# muchas CPU, superaba el límite en reposo. Cada proceso se renueva tras 200 tareas.
CELERY_WORKER_CONCURRENCY = env_int("CELERY_CONCURRENCY", 2)
CELERY_WORKER_MAX_TASKS_PER_CHILD = 200

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
# Las sondas internas pegan por HTTP a /healthz/ y /readyz/: que no se redirijan a HTTPS.
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$", r"^readyz/?$"]

if not DEBUG:
    # Detrás de un proxy que termina TLS (nginx, etc.).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HTTPS forzado y HSTS activos por defecto en producción. Apagar HSTS exige nombrarlo
    # en DJANGO_ALLOW_WEAKENED (guard de producción, al final).
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ── Correo ────────────────────────────────────────────────
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
# Sin timeout, smtplib espera indefinidamente a un servidor que acepta la conexión y
# luego calla: bastaba para inmovilizar los slots del worker.
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 20)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "Reseñas <no-reply@resenas.cl>")

# ── Logging a stdout (JSON en producción, texto plano legible en desarrollo) ──
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {"()": "config.logformat.JsonFormatter"},
    },
    # Los enlaces del boletín llevan el token en la ruta: se redacta antes de escribir
    # nada al log (S-20).
    "filters": {"redact_tokens": {"()": "config.redaction.RedactTokensFilter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
            "filters": ["redact_tokens"],
        }
    },
    "root": {
        "handlers": ["console"],
        "level": env_str("DJANGO_LOG_LEVEL", "INFO"),
    },
}

SENTRY_DSN = env_str("SENTRY_DSN")

# ── Guard de producción ───────────────────────────────────
# Con DEBUG=0 rechaza arrancar con valores de ejemplo, secretos débiles o defensas
# apagadas sin autorización. La lógica vive en config.envguard (función pura, probada en
# tests/test_envguard.py) y recibe los mismos valores que usa Django.
if not DEBUG:
    _effective = {
        "DJANGO_SECRET_KEY": SECRET_KEY,
        "POSTGRES_PASSWORD": DATABASES["default"]["PASSWORD"],
        "REDIS_PASSWORD": _REDIS_PASSWORD,
        "CELERY_BROKER_URL": _BROKER_URL_FROM_ENV,
        "DJANGO_ALLOWED_HOSTS": _ALLOWED_HOSTS_FROM_ENV,
        "DJANGO_CSRF_TRUSTED_ORIGINS": CSRF_TRUSTED_ORIGINS,
        "SITE_URL": SITE_URL,
        # El dominio que sirve Caddy (docker-compose.prod.yml): solo se lee para compararlo.
        "SITE_ADDRESS": env_str("SITE_ADDRESS"),
        "AXES_ENABLED": AXES_ENABLED,
        "RATELIMIT_ENABLE": RATELIMIT_ENABLE,
        "DJANGO_HSTS_SECONDS": SECURE_HSTS_SECONDS,
        "SENTRY_DSN": SENTRY_DSN,
        "DJANGO_ALLOW_WEAKENED": env_list("DJANGO_ALLOW_WEAKENED"),
    }
    _problems = envguard.check_production_env(_effective)
    if _problems:
        raise ImproperlyConfigured(
            "Configuración insegura con DEBUG=0 — corrige en el entorno: "
            + ", ".join(_problems)
            + "."
        )
    _weakened = envguard.weakened_defenses(_effective)
    if _weakened:
        # El log aún no está configurado: sale por el manejador de último recurso, a stderr.
        logging.getLogger("config.envguard").warning(
            "Arranca con defensas apagadas (DJANGO_ALLOW_WEAKENED): %s", ", ".join(_weakened)
        )

# ── Observabilidad: Sentry ────────────────────────────────
# Obligatorio con DEBUG=0 (guard de producción). sentry-sdk habilita solo las integraciones
# de Django y Celery: basta con arrancarlo aquí, que importan los dos procesos. Sin DSN
# (desarrollo, pruebas) no hace nada.
if SENTRY_DSN:
    from config.sentry import init_sentry

    init_sentry(
        SENTRY_DSN,
        environment=env_str("SENTRY_ENVIRONMENT", "production" if not DEBUG else "dev"),
        release=env_str("SENTRY_RELEASE") or None,
        traces_sample_rate=env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
    )
