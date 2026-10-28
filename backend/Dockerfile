# Imagen multi-stage:
#   · `dev`  — incluye pytest/ruff y corre como root (bind-mount de desarrollo).
#   · `prod` — solo dependencias de runtime y usuario NO-root (stage por defecto).
# El stage por defecto (último) es `prod`, de modo que `docker build ./backend`
# y el compose de producción obtienen la imagen endurecida.

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
# pip al día (corrige CVEs del propio pip) y compatible con --require-hashes.
RUN pip install --upgrade pip
COPY requirements.txt requirements-dev.txt ./

# ── Desarrollo ────────────────────────────────────────────
FROM base AS dev
# Lockfile con hashes: instalación reproducible y verificada.
RUN pip install --require-hashes -r requirements-dev.txt
COPY . .
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

# ── Producción ────────────────────────────────────────────
FROM base AS prod
# Solo runtime, desde el lockfile con hashes (build reproducible y verificado).
RUN pip install --require-hashes -r requirements.txt
# Usuario sin privilegios (uid 1000): los volúmenes nuevos heredan su propiedad,
# de modo que gunicorn puede escribir en mediafiles/private_media/staticfiles.
RUN useradd --system --create-home --uid 1000 app \
    && mkdir -p /app/mediafiles /app/private_media /app/staticfiles
COPY --chown=app:app . .
RUN chown -R app:app /app
USER app
# Las migraciones, los grupos y los estáticos no se hacen al arrancar: los hace release.sh,
# desde el servicio `release` del compose, antes de que arranquen web, worker y beat.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
