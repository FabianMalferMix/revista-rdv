# Despliegue en producción — Proyecto «Reseñas»

Arquitectura de producción: **Caddy** (proxy inverso con TLS automático) → **gunicorn** (app) →
**PostgreSQL** + **Redis**, con **Celery** (worker + beat). Estáticos por WhiteNoise; **`/media/`
servido por Caddy**; respaldos por el servicio `backup`.

```
Internet ──443──▶ Caddy ──▶ web:8000 (gunicorn)
                    │            ├─ db (postgres, solo red interna)
                    └─ /media/   └─ redis (auth, solo red interna)
```

## Requisitos

- Un host con Docker + Docker Compose.
- Un **dominio** apuntando al host (DNS A/AAAA) y los puertos **80/443** abiertos (Caddy obtiene y
  renueva el certificado TLS de Let's Encrypt automáticamente).

## Configuración

En el host, parte de la plantilla de producción y define valores reales:

```bash
cp .env.prod.example .env      # editar: SECRET_KEY, contraseñas fuertes, dominio…
```

Claves obligatorias (con `DJANGO_DEBUG=0` el arranque se rechaza si faltan o son de ejemplo):
`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CSRF_TRUSTED_ORIGINS`, y `SITE_ADDRESS` = tu dominio (p. ej. `revista.tudominio.cl`).

## Primer despliegue

```bash
COMPOSE="-f docker-compose.yml -f docker-compose.prod.yml"

APP_VERSION=$(git rev-parse --short HEAD) docker compose $COMPOSE up -d --build

docker compose $COMPOSE run --rm --entrypoint python web manage.py createsuperuser
# Si importas medios preexistentes, genera sus derivados responsivos (srcset):
docker compose $COMPOSE run --rm --entrypoint python web manage.py generate_image_derivatives
```

`up` corre primero el servicio `release` (`backend/release.sh`): aplica las migraciones, sincroniza
los grupos y permisos y recoge los estáticos. Solo si termina bien arrancan `web`, `worker` y
`beat`; si falla, no arranca nada (`docker compose $COMPOSE logs release` dice por qué). La imagen
queda etiquetada con el commit (`resenas-app:<commit>`).

Caddy servirá el sitio por HTTPS en tu dominio. `web` no publica ningún puerto al host: solo el
proxy es accesible desde fuera.

## Actualizaciones (redeploy)

```bash
git pull
APP_VERSION=$(git rev-parse --short HEAD) docker compose $COMPOSE up -d --build
# El release migra, sincroniza los grupos y recoge los estáticos antes de arrancar el código
# nuevo. Si falla, el código nuevo no arranca: revisar `docker compose $COMPOSE logs release`.
# Genera los derivados responsivos (srcset) de las imágenes ya existentes.
# Idempotente: solo crea los que falten. Correr tras subir imágenes en masa o
# tras un cambio en MediaAsset.SRCSET_WIDTHS. Las nuevas imágenes los generan al guardarse.
docker compose $COMPOSE run --rm --entrypoint python web manage.py generate_image_derivatives
```

**Las migraciones van en dos pasos.** Mientras el release migra, el código anterior sigue
sirviendo, y si hay que volver atrás, el código anterior corre sobre el esquema nuevo. Por eso un
cambio de esquema primero añade (una columna, una tabla) y, en un despliegue posterior, quita lo
que ya no se usa.

### Volver atrás (rollback)

La imagen de cada despliegue queda en el host como `resenas-app:<commit>`:

```bash
git checkout <commit-anterior>
APP_VERSION=<commit-anterior> docker compose $COMPOSE up -d   # sin --build: usa la imagen guardada
```

Si la versión que se retira trajo una migración que el código anterior no tolera, primero hay que
revertirla, con el código nuevo todavía en marcha:
`docker compose $COMPOSE run --rm --entrypoint python web manage.py migrate <app> <migración-anterior>`.
Las imágenes viejas se limpian a mano (`docker image ls resenas-app`, `docker image rm …`).

`web`, `worker`, `beat`, `db`, `redis` y `proxy` llevan `restart: unless-stopped`: se recuperan
solos ante caídas. `web` tiene healthcheck a `/healthz/`.

## Respaldos

Activa el sidecar de respaldos y revisa [docs/respaldos.md](respaldos.md):

```bash
docker compose $COMPOSE --profile backup up -d backup
```

## Prueba local del stack de producción (sin dominio)

Se puede validar la configuración de producción en local (HTTP, sin certificado) usando un proyecto
aislado y un `.env` de prueba con `SITE_ADDRESS=:80`, `DJANGO_SECURE_SSL_REDIRECT=0` y un puerto de
proxy alternativo (`PROXY_HTTP_PORT`). Este flujo se ejecutó al implementar el lote de despliegue
(home, `/static/`, `/media/`, cabeceras de seguridad y healthcheck verificados).

## Ajustes útiles

- `SENTRY_DSN` — activa error tracking (Django + Celery). Sin él no se activa nada. Con
  `DJANGO_DEBUG=0` los logs salen en **JSON** (agregables por un colector); en dev son texto plano.
- `GUNICORN_WORKERS` — nº de workers (por defecto 3; ~`2·CPU+1`).
- `DJANGO_SECURE_SSL_REDIRECT` / `DJANGO_HSTS_SECONDS` — activos por defecto con `DEBUG=0`.
- `PROXY_HTTP_PORT` / `PROXY_HTTPS_PORT` — si otro proxy/LB va delante de Caddy.
