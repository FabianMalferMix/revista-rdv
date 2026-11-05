# Reseñas — sitio de Repitentes del Verso

El sitio del colectivo de poesía **Repitentes del Verso**: sus textos y poemas, los registros
de sus lecturas, la agenda y la trayectoria, el catálogo de publicaciones, la prensa y el
dossier, el boletín y las convocatorias. Backend y frontend en un **monolito Django + htmx**,
con PostgreSQL, Celery y Redis, tras Caddy y todo en Docker.

## Documentos de diseño

- [Modelo de datos](https://claude.ai/code/artifact/7eaf465d-503b-45f8-80fa-776e14d34eae) (3NF/BCNF)
- [Flujo editorial y permisos](https://claude.ai/code/artifact/8042cdc8-e619-4891-9325-1df5ab8c3073)

## Stack

| Capa | Tecnología |
| --- | --- |
| Backend / Frontend | Django 5.2 LTS + plantillas + htmx |
| Base de datos | PostgreSQL 16 (búsqueda full-text nativa) |
| Tareas async | Celery + Redis (publicación programada, correos) |
| Proxy | Caddy (TLS automático; sirve `/static/` y `/media/`) |
| Contenedores | Docker Compose |

## Estructura

Una app por cada línea de `INSTALLED_APPS`: `backend/tests/test_readme.py` falla si se instala
una app sin anotarla aquí o si esta lista nombra una carpeta que no existe.

```text
backend/
  config/               Proyecto Django: settings, urls, Celery, CSP y redacción de logs
  apps/
    media/              MediaAsset (imágenes) y Recording (registros de audio y vídeo)
    people/             Contributor (integrantes y colaboradores) y SocialLink
    reviews/            Work, Publisher y BookAuthor (las obras reseñadas)
    content/            Article, Poem, Collection, Section, Tag y Page, con el flujo editorial
    showcase/           SiteProfile, Publication, WhereToBuy, PressMention y Partner; el dossier
    agenda/             Event, EventPhoto y Milestone; la trayectoria
    community/          NewsletterSubscriber (el boletín, con doble confirmación)
    submissions/        Call y Submission (convocatorias y envíos)
    devtools/           las herramientas de desarrollo y DevelopmentMarker (no van a producción)
  templates/            base y vistas htmx
  static/               css, js, fuentes, imágenes y bibliotecas de terceros (vendor/)
  tests/                la suite de pytest
  datos_de_desarrollo/  la copia del contenido de desarrollo (ver más abajo)
  release.sh            migraciones, grupos y estáticos antes de arrancar (servicio release)
infra/
  caddy/                Caddyfile: proxy con TLS, /static/ y /media/
  backup/               respaldos (base, medios y restic) y restauración
tools/
  ux/                   capturas y métricas de la interfaz
  ci/                   comprobaciones del CI (sintaxis de JS, identificadores de decisión)
```

## Puesta en marcha

```bash
cp .env.example .env
docker compose up --build
```

- Sitio: <http://localhost:8000>
- Admin (bandeja editorial): <http://localhost:8000/admin>

Antes de que arranquen `web`, `worker` y `beat`, el servicio `release` aplica las migraciones
y crea los grupos `admin · editor · autor`.

### Los datos de desarrollo

Una base recién creada está vacía. Se puebla con un solo comando, el único camino para poblar
desarrollo: carga la copia del contenido de desarrollo que trae el repositorio
(`backend/datos_de_desarrollo/`). Después, la cuenta del panel:

```bash
docker compose exec web python manage.py datos_de_desarrollo cargar
docker compose exec web python manage.py createsuperuser
```

`cargar` copia los archivos, carga las filas, pone la identidad del colectivo (nombre, lema,
correo, manifiesto y redes, de `backend/apps/devtools/identity.py`) y rehace las copias de las
imágenes a otros tamaños. Corre las fechas: lo que estaba a N días de la exportación queda a N
días de hoy, así que las próximas actividades, la convocatoria abierta y los últimos textos siguen
siéndolo. No toca lo que dejan las migraciones: las páginas legales conservan su texto vigente.
En una base de desarrollo que ya tiene contenido no hace nada (para empezar de cero:
`docker compose down -v` y volver a levantar), y se niega en una base con contenido que no se
declara de desarrollo. El mismo comando usan `tools/ux/preparar-entorno.sh` y el job `navegador`
del CI.

Como todas las herramientas de desarrollo (`backend/apps/devtools/`), **se niega a correr con
`DEBUG=0`** y donde el entorno se declara de producción (`DJANGO_ENVIRONMENT=production`, que fija
`docker-compose.prod.yml`), aunque DEBUG esté encendido; ninguna opción se lo salta. Se instalan
con `DEBUG=1` o con `DJANGO_DEV_TOOLS=1` (ver `.env.example`), y la imagen de producción ni
siquiera las trae.

Solo viaja lo que el sitio ya muestra: lo publicado, lo que lo acompaña y las imágenes y el
catálogo que eso nombra, más tres piezas sin publicar que enseñan el flujo editorial en el panel,
y los textos y poemas largos de prueba (prefijo `zz-largo-`). **No** viajan las cuentas de
usuario, las sesiones, los registros de acceso y del panel, los suscriptores del boletín, los
envíos a convocatorias ni el historial editorial. Por eso, para probar los roles, se crean desde el
panel las cuentas que hagan falta: `is_staff = True` y el grupo `editor` o `autor`. Los medios,
fondos, librerías y editoriales de la demostración son ficticios.

### Cambiar los datos de desarrollo

Se cambian en el sitio de desarrollo (el panel, o las dos herramientas de abajo) y se exportan,
en una base marcada como de desarrollo (`cargar` la marca; si no, `datos_de_desarrollo marcar`):

```bash
docker compose exec web python manage.py datos_de_desarrollo exportar
```

`exportar` reescribe la copia con la fecha de la exportación, y se niega si la identidad de la base
no es la de `identity.py`: la copia no la lleva, así que se cambia en ese módulo.

Material visual genérico (marcadores con proporciones reales, dibujados con Pillow) para lo que se
añada sin imagen antes de que llegue el material del colectivo; la copia ya trae el de lo que hay:

```bash
docker compose exec web python manage.py seed_material_generico
```

Idempotente y seguro: nunca reemplaza una imagen cuyo crédito no sea de marcador. Qué pedir y
cómo reemplazar cada pieza: [docs/contenido-visual.md](docs/contenido-visual.md). Cada pieza
siembra su azar (la composición y el grano) con su propia clave: dibujarla otra vez, también con
`--regenerar`, da los mismos bytes, y una pieza nueva no cambia los de las demás.

Los textos y poemas largos de prueba (una reseña de once minutos, un ensayo de quince, una crítica
con todos los casos límite, una letanía de más de cien versos, un poema en prosa…) los escribe y
los quita una orden:

```bash
docker compose exec web python manage.py seed_textos_largos            # siembra o pone al día
docker compose exec web python manage.py seed_textos_largos --borrar   # los quita
```

La lámina de la portada (la obra de la primera vista mientras el colectivo no elige la suya, en
`backend/static/img/portada/`) sale de sus maestras sin pérdida, que están en
`backend/apps/devtools/management/commands/lamina/`, cortadas en franjas para que ningún archivo
pase de 2 MB. Una orden rehace sus quince copias con parámetros fijos, y rehacerlas da los mismos
bytes (`backend/tests/test_lamina.py` lo comprueba); con `--check`, solo las compara:

```bash
docker compose exec --user "$(id -u):$(id -g)" web python manage.py generate_lamina_variants
```

### Migraciones

Las migraciones se versionan en el repo; el servicio `release` las aplica en cada
`docker compose up`.
Cuando cambies los modelos, genera la migración y ajusta la propiedad de los archivos
(el contenedor de **desarrollo** corre como root; la imagen de **producción** usa un
usuario no-root, ver `backend/Dockerfile`):

```bash
docker compose exec web python manage.py makemigrations
sudo chown -R "$USER" backend/apps/*/migrations   # solo si quedaron como root
```

## Tests

```bash
docker compose run --rm --entrypoint pytest web
```

Cubren el flujo editorial, los permisos por rol y estado, el formulario de envíos y las
vistas públicas. El pipeline de CI ([.github/workflows/ci.yml](.github/workflows/ci.yml))
los corre en cada push y pull request, junto con lint (ruff), auditoría de dependencias
(pip-audit), una comprobación de migraciones al día y, en el job `navegador`, ESLint y una
prueba de humo que ejecuta los guiones del sitio en Chrome a 951 y a 375 px.

## Calidad de código

Lint, formato e imports con **ruff** (config en [backend/pyproject.toml](backend/pyproject.toml)):

```bash
docker compose run --rm --entrypoint ruff web check .
docker compose run --rm --entrypoint ruff web format .
```

## Interfaz: capturas y métricas

`tools/ux/` mide lo que se ve: cuánto del ancho usa el texto, tamaños reales, imágenes
deformadas, objetivos pulsables y scroll horizontal, en 1440, 390 y 1920 px. Nació como
instrumento del rediseño UX/UI de octubre de 2026, que se cuenta más abajo.

```bash
npm ci --prefix tools/ux                      # una vez; usa el Chrome del sistema
node tools/ux/capture.js tools/ux/out/prueba  # capturas + métricas de las páginas de pages.txt
node tools/ux/browser-smoke.js                # prueba de humo: los guiones, a 951 y a 375 px
python3 tools/ux/metrics.py tabla tools/ux/out/prueba
python3 tools/ux/smoke.py                     # todos los enlaces internos responden
```

Detalle en [tools/ux/README.md](tools/ux/README.md). No forma parte del despliegue.

El rediseño se hizo en 25 pasos, del 2026-10-08 al 2026-10-14. Su plan y la verificación del
cierre (criterio a criterio, con capturas de antes y después) se retiraron del árbol el
2026-10-27 y siguen en git: `git show 38fdf03:docs/plan-ejecucion-ux.md` y
`git show 38fdf03:docs/auditoria-ux-ui-verificacion.md`. Sus decisiones están en
[docs/deferidos-y-decisiones.md](docs/deferidos-y-decisiones.md), y las métricas de antes y de
después, versionadas en `tools/ux/linea-base/` y `tools/ux/final/`. Para
trabajar sobre el diseño en una máquina nueva, un guion levanta el stack, lo puebla con
`datos_de_desarrollo cargar` (el mismo camino de arriba), instala las herramientas de `tools/ux` y
pasa la prueba de humo:

```bash
bash tools/ux/preparar-entorno.sh
```

## Producción

**Caddy** (proxy con TLS automático) → gunicorn → PostgreSQL/Redis, con Celery. Caddy sirve
`/static/` y `/media/` directamente desde sus volúmenes. Guía completa en
[docs/despliegue.md](docs/despliegue.md).

```bash
cp .env.prod.example .env   # editar secretos, contraseñas, SITE_ADDRESS y SITE_URL (tu dominio)
APP_VERSION=$(git rev-parse --short HEAD) \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`up` migra, sincroniza los grupos y recoge los estáticos (servicio `release`) antes de arrancar el
código nuevo, y si eso falla no arranca nada.

Con `DEBUG=0` el arranque exige credenciales propias; cookies seguras, HSTS y redirección a HTTPS
quedan activas por defecto. `web` no publica puertos (solo el proxy). Todos los servicios llevan
`restart: unless-stopped` y healthcheck.

**Respaldos:** el contenido es un archivo permanente — configura los respaldos automáticos
y prueba la restauración siguiendo [docs/respaldos.md](docs/respaldos.md).

## SEO

- Feed RSS en `/feed/`, sitemap en `/sitemap.xml`, `robots.txt`.
- Open Graph / Twitter Cards y JSON-LD (schema.org `Article`) en cada artículo.

## Roles

- **admin** — control total (usuarios, configuración).
- **editor** — revisa, corrige, publica; modera comentarios y envíos.
- **autor** — escribe y envía a revisión sus propios borradores.

El ciclo de vida de un artículo (8 estados) y la matriz de permisos están en el
documento de flujo editorial enlazado arriba, e implementados en
[backend/apps/content/workflow.py](backend/apps/content/workflow.py).
