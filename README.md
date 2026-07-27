# Reseñas — Revista literaria

Plataforma editorial a medida para una revista literaria de reseñas. Backend y frontend
en un **monolito Django + htmx**, PostgreSQL, y todo dockerizado.

## Documentos de diseño

- [Modelo de datos](https://claude.ai/code/artifact/7eaf465d-503b-45f8-80fa-776e14d34eae) (3NF/BCNF)
- [Flujo editorial y permisos](https://claude.ai/code/artifact/8042cdc8-e619-4891-9325-1df5ab8c3073)

## Stack

| Capa | Tecnología |
| --- | --- |
| Backend / Frontend | Django 5 + plantillas + htmx |
| Base de datos | PostgreSQL 16 (búsqueda full-text nativa) |
| Tareas async | Celery + Redis (publicación programada, correos) |
| Contenedores | Docker Compose |

## Estructura

```text
backend/
  config/            Proyecto Django (settings, urls, celery)
  apps/
    media/           MediaAsset (biblioteca de imágenes)
    people/          Contributor, SocialLink, grupos/roles
    reviews/         Work, Publisher, BookAuthor
    content/         Article, Section, Tag, Dossier, Page + flujo editorial
    community/       Comment, NewsletterSubscriber
    submissions/     Submission, Call (portal de envíos)
  templates/         base + vistas htmx
  static/
infra/nginx/         Config de proxy inverso (producción)
```

## Puesta en marcha

```bash
cp .env.example .env
docker compose up --build
```

- Sitio: <http://localhost:8000>
- Admin (bandeja editorial): <http://localhost:8000/admin>

El contenedor `web` aplica migraciones y crea los grupos `admin · editor · autor`
automáticamente al arrancar.

Crear un superusuario:

```bash
docker compose exec web python manage.py createsuperuser
```

Cargar datos de demostración (opcional):

```bash
docker compose exec web python manage.py seed_demo
```

Crea secciones, editoriales, obras, colaboradores y varias reseñas —incluida una
**programada** que Celery publica solo a los pocos minutos—. Usuarios demo `editora`
y `autor1` (contraseña `demo12345`, solo para desarrollo).

Para que un usuario use el panel editorial, marca `is_staff = True` y asígnale el grupo
`editor` o `autor` desde el admin.

### Migraciones

Las migraciones se versionan en el repo; el contenedor solo corre `migrate` al arrancar.
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
(pip-audit) y una comprobación de migraciones al día.

## Calidad de código

Lint, formato e imports con **ruff** (config en [backend/pyproject.toml](backend/pyproject.toml)):

```bash
docker compose run --rm --entrypoint ruff web check .
docker compose run --rm --entrypoint ruff web format .
```

## Producción

**Caddy** (proxy con TLS automático) → gunicorn → PostgreSQL/Redis, con Celery. Estáticos por
**WhiteNoise** y `/media/` servido por Caddy. Guía completa en [docs/despliegue.md](docs/despliegue.md).

```bash
cp .env.prod.example .env   # editar secretos, contraseñas y SITE_ADDRESS (tu dominio)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --entrypoint python web manage.py migrate
```

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
