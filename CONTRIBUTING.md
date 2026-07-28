# Contribuir a «Reseñas»

Sitio del colectivo de poesía: monolito **Django 5.2 + htmx + PostgreSQL + Celery/Redis**,
servido tras **Caddy** y dockerizado. Este documento resume cómo levantar el entorno,
las convenciones y el flujo de trabajo.

## Requisitos

- Docker y Docker Compose.
- (Opcional, recomendado) [pre-commit](https://pre-commit.com/) en el host.

## Puesta en marcha (desarrollo)

El `docker-compose.override.yml` se carga solo y monta el código con recarga en caliente.

```bash
docker compose up -d                              # web, worker, beat, db, redis
docker compose exec web python manage.py migrate
docker compose exec web python manage.py setup_groups
docker compose exec web python manage.py seed_demo        # datos de demostración
docker compose exec web python manage.py createsuperuser
```

El sitio queda en <http://127.0.0.1:8000/> (solo escucha en 127.0.0.1).

## Comandos habituales

Todo corre dentro del contenedor `web`:

```bash
docker compose exec web pytest                                   # tests
docker compose exec web ruff check .                             # lint
docker compose exec web ruff format .                            # formato
docker compose exec web python manage.py makemigrations --check --dry-run   # sin drift
docker compose exec web python manage.py check                  # chequeos del framework
docker compose exec web python manage.py generate_image_derivatives  # derivados srcset
```

> El contenedor de desarrollo corre como root: si un comando genera archivos (p. ej.
> migraciones), ajusta la propiedad con
> `docker compose exec web chown -R 1000:1000 /app/apps /app/tests`.

## Dependencias (lockfiles con hashes)

Las dependencias se declaran con rangos en `backend/requirements.in` (runtime) y
`backend/requirements-dev.in` (dev/test), y se **compilan** a lockfiles fijados con
hashes (`requirements.txt` / `requirements-dev.txt`). Tras editar un `.in`:

```bash
docker compose exec web bash -c 'cd /app && \
  python -m piptools compile --generate-hashes --strip-extras -o requirements.txt requirements.in && \
  python -m piptools compile --generate-hashes --strip-extras -o requirements-dev.txt requirements-dev.in'
docker compose build web        # reconstruye con --require-hashes
```

Commitea el `.in` y el `.txt` juntos. Dependabot recompila estos lockfiles
automáticamente (Django se mantiene en la línea 5.2 LTS).

## pre-commit

```bash
pip install pre-commit
pre-commit install            # instala el gancho de git
pre-commit run --all-files    # opcional: corre los hooks sobre todo el repo
```

Los hooks (ruff check + format, más higiene de archivos) usan la misma versión de
ruff que el lockfile, de modo que coincidan con el CI.

## Flujo de contribución (por lote)

1. Rama desde `main`: `git checkout -b <rama>`.
2. Implementa el cambio, con tests.
3. Verifica **todo en verde**:
   - `ruff check .` y `ruff format --check .`
   - `pytest`
   - `python manage.py makemigrations --check --dry-run` (sin drift)
   - `python manage.py check`
4. Commit y Pull Request contra `main`. El CI corre ruff, `pip-audit` (bloqueante),
   migraciones, tests con cobertura (`--cov-fail-under=80`) y `check --deploy`.
5. Merge a `main` (`--no-ff`) y borra la rama.

## Documentación relacionada

- Despliegue: [docs/despliegue.md](docs/despliegue.md)
- Respaldos: [docs/respaldos.md](docs/respaldos.md)
- Auditoría de calidad y hoja de ruta: [docs/auditoria-mvp.md](docs/auditoria-mvp.md)
