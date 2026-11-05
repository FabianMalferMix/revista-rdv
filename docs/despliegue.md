# Despliegue en producción — Proyecto «Reseñas»

Arquitectura de producción: **Caddy** (proxy inverso con TLS automático) → **gunicorn** (app) →
**PostgreSQL** + **Redis**, con **Celery** (worker + beat). **Caddy sirve `/static/` y `/media/`**
directamente desde sus volúmenes; respaldos por el servicio `backup`.

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
`DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_ADDRESS` = tu dominio sin www (p. ej.
`revista.tudominio.cl`) y `SITE_URL` = el mismo dominio con https
(`https://revista.tudominio.cl`). Las URL absolutas (canonical, Open Graph, sitemap, feeds,
enlaces del boletín) salen de `SITE_URL`, nunca del Host de la petición. Crea también el
registro DNS de `www`: Caddy obtiene su certificado y lo redirige al dominio sin www.

`docker-compose.prod.yml` fija `DJANGO_ENVIRONMENT=production` en release, web, worker y beat:
los comandos de desarrollo (`seed_demo`, `datos_de_desarrollo`…) se niegan a correr ahí, y la
imagen de producción ni siquiera los trae (`apps/devtools` queda fuera en `backend/.dockerignore`).

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

## Avisos

Tres avisos cubren lo que puede fallar sin que nadie lo vea. Las cuentas se crean al lanzar.

- **Errores: Sentry.** Crea un proyecto de Django en Sentry (el plan gratuito basta) y pon su
  DSN en `SENTRY_DSN`; con `DJANGO_DEBUG=0` el sitio no arranca sin él. Antes de salir, cada
  evento pierde el cuerpo de la petición, las variables de cada marco, las cabeceras que
  repiten la URL, los tokens del boletín y las direcciones de correo
  (`backend/config/sentry.py` y `backend/config/redaction.py`, con sus pruebas).
- **Caída del sitio y de las tareas: un monitor que visita `/readyz/`.** Un servicio de
  monitoreo externo (por ejemplo UptimeRobot o Better Stack) que pida
  `https://<dominio>/readyz/` cada pocos minutos y avise si no responde 200. `/readyz/`
  responde 503 si falla la base, el broker, el latido de las tareas (la publicación
  programada deja una marca cada minuto; si tiene más de cinco, se pararon beat o el
  worker), si hay piezas programadas vencidas sin publicar, migraciones sin aplicar o menos
  del 5 % de disco libre en los medios. El JSON de la respuesta dice qué comprobación falla,
  y el log de `web`, por qué.
- **Respaldo: healthchecks.io.** `BACKUP_PING_URL` (ver «Respaldos»).

Docker marca un contenedor como `unhealthy`, pero Compose no lo reinicia: no se usa un
reiniciador automático, porque exigiría montar el socket de Docker (equivale a ser root en
el servidor). El monitor avisa y una persona decide.

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

- `SENTRY_DSN` — error tracking (Django + Celery), obligatorio con `DJANGO_DEBUG=0` (ver
  «Avisos»). Con `DJANGO_DEBUG=0` los logs salen en **JSON** (agregables por un colector); en
  dev son texto plano.
- `GUNICORN_WORKERS` y `GUNICORN_THREADS` — procesos de gunicorn (por defecto 3; ~`2·CPU+1`) e
  hilos por proceso (por defecto 4). El resto de sus opciones está en `backend/gunicorn.conf.py`.
- `CELERY_CONCURRENCY` — procesos del worker (por defecto 2, unos 40 MB cada uno). Sin
  fijarlo, Celery abriría uno por CPU del servidor y podría pasar de `WORKER_MEM_LIMIT`.
- `DB_STATEMENT_TIMEOUT_MS` (15000) y `DB_CONNECT_TIMEOUT` (5 s) — plazos de cada consulta y de
  cada conexión a la base. Con gthread, el `--timeout` de gunicorn no corta una petición
  colgada: estos plazos sí. Las migraciones del release corren sin plazo de consulta.
- `DJANGO_SECURE_SSL_REDIRECT` / `DJANGO_HSTS_SECONDS` — activos por defecto con `DEBUG=0`
  (apagar HSTS exige `DJANGO_ALLOW_WEAKENED`).
- `PROXY_HTTP_PORT` / `PROXY_HTTPS_PORT` — si otro proxy/LB va delante de Caddy.
