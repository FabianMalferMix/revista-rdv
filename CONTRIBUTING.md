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

Además de ruff y gitleaks, los ganchos revisan la higiene de los archivos (espacios, YAML y
archivos de más de 2 MB), la sintaxis de los guiones de `backend/static/js/` (`node --check`) y
los identificadores de decisión en el código. El CI los corre todos en el job `hygiene`, salvo
ruff y gitleaks, que tienen sus propios jobs. Sin pre-commit instalado, el recuento de
identificadores se corre con `python3 tools/ci/decision_refs.py`: su línea base
(`tools/ci/decision_refs_baseline.json`) solo puede bajar, y tras quitar alguno se baja con
`--update`.

## Flujo de trabajo

1. **Una rama por cambio.** Cada cambio es un ticket de [docs/backlog-codigo.md](docs/backlog-codigo.md),
   o un pedido del dueño, en su propia rama desde `main`, en kebab-case descriptivo:
   `git switch -c <rama>`.
2. **El cambio y sus pruebas.** Las pruebas comprueban comportamiento (ver «Reglas del código»).
3. **Todo en verde:**
   - `ruff check .` y `ruff format --check .`
   - `pytest`
   - `python manage.py makemigrations --check --dry-run` (sin drift)
   - `python manage.py check`
4. **Commit.** Cada archivo se añade por su nombre, nunca una carpeta entera: en `docs/` hay un
   documento personal que no es del repositorio. Mensaje: `rama: qué cambia (Bxx)`, y en el
   cuerpo, el porqué del cambio, que es lo que no va en los comentarios del código.
5. **Pull Request** contra `main`, titulado `rama — qué cambia (Bxx)`, con la lista de
   [.github/pull_request_template.md](.github/pull_request_template.md) en el cuerpo. El CI corre
   ruff, `pip-audit` (bloqueante), migraciones, tests con cobertura (`--cov-fail-under=80`),
   `check --deploy` y gitleaks. pip-audit y gitleaks solo corren allí: el PR está listo cuando el
   CI está en verde, no cuando pasan las pruebas locales.
6. **Lo visual.** Si el cambio se ve, el dueño lo revisa antes de fusionar: a 951 px, que es su
   ventana, y en el teléfono, con alternativas si hay más de una manera.
7. **Fusión** con commit de fusión (no squash) y se borra la rama. En el mismo PR se actualizan
   «Estado» y el avance del backlog.

## Reglas del código

`CLAUDE.md` las resume para los agentes; aquí va cada una con un ejemplo del propio código.
Algunas describen el destino del backlog: mientras su ticket no esté hecho, se sigue el patrón
vigente más cercano y no se agrava la deuda.

1. **Dónde va cada cosa.**
   - Las consultas reutilizables son métodos de QuerySet.
   - Los cambios de estado, servicios (`services.py`, `workflow.py`).
   - Los cálculos visuales, templatetags.
   - Las señales, `signals.py`, conectado desde `ready()`.
   - Lo transversal, `config/`.

   Bien: `perform_transition` (`apps/content/workflow.py`) concentra los cambios de estado
   editorial, con su bloqueo y su bitácora. Mal: el alta, la confirmación y la baja del boletín
   viven en `apps/community/views.py`.
2. **Lo publicable.** La regla de visibilidad vive en el modelo, y no se reescribe en cada vista,
   sitemap o feed; toda relación hacia algo publicable la respeta. Bien: `Poem.published_recording`
   (`apps/content/models.py`) devuelve el registro solo si está publicado. Mal: `Recording.event` se
   muestra sin mirar si el evento está publicado.
3. **Un dato, una fuente.** Si un valor debe coincidir en varias capas, se decide en un lugar y
   viaja: atributos `data-`, propiedades CSS, `reverse()`. Si no se puede, una prueba de la
   relación entre la fuente y la copia. Mal: el número de integrantes que se ven en la portada está
   en `A_LA_VISTA` (`apps/content/views.py`), en `site.css`, en `integrantes.js` y en los `sizes`, y
   una prueba fija cada copia por separado. Bien: las rutas se resuelven con `{% url %}` y
   `reverse()` en todo el sitio.
4. **Idioma.** Los identificadores nuevos de Python y de JavaScript van en inglés. En castellano
   van los textos visibles y el vocabulario del diseño: clases CSS y nombres de componentes
   (tirada, estante, pliego, cápsula), que se usan tal cual también dentro de nombres en inglés,
   como `tirada_items`. Lo existente no se renombra, salvo los nombres trampa que lista el backlog.
5. **Comentarios.** Dicen qué hace el código hoy y qué restricción lo explica. Bien: el comentario
   del feed de registros en `config/urls.py` explica por qué se instancia por petición (gunicorn
   usa hilos). Mal: los comentarios que cuentan qué se hizo en cada sesión o citan una decisión o
   un ticket («D23», «paso 18»): esa historia va en el commit, y el CI falla si un archivo suma
   identificadores de esos (`tools/ci/decision_refs.py`). Una garantía de seguridad o de
   privacidad se escribe como prueba, no como comentario.
6. **Errores.** Nada de `except Exception: return` sin registro: lo esperado, `logger.warning`
   sin traza; lo inesperado, `logger.exception`. Los controles de privacidad fallan cerrados, y un
   proceso solo declara éxito cuando lo verificó. Mal: en `infra/backup/backup.sh`,
   `tar … 2>/dev/null || echo "(media vacío)"` convierte cualquier fallo en «vacío», y el respaldo
   informa éxito.
7. **Lo que sale del sistema.** Exportaciones, logs, Sentry y archivos servidos llevan listas
   blancas por fila y por campo, y a las tareas se les pasan identificadores, no datos personales.
   Bien: `datos_de_desarrollo exportar` declara qué filas y qué campos de cada modelo viajan, y un
   campo nuevo sin clasificar hace fallar la exportación hasta que alguien decide si es público.
8. **URL públicas.** Son permanentes: renombrar una ruta exige dejar la vieja con
   `RedirectView(permanent=True)`; el slug de lo publicado no se cambia, y el GUID de un ítem de
   feed, nunca. Antes del lanzamiento, `dosieres/` pasó a `colecciones/` sin redirección y no costó
   nada. Después, el mismo cambio rompería los enlaces de la prensa, de los dossiers enviados y de
   los lectores de feeds.
9. **Tareas y migraciones.**
   - Cada tarea declara sus límites de tiempo, su política de reintento y si es idempotente, y se
     encola con `delay_on_commit`.
   - Toda migración de datos usa `apps.get_model` y lleva su prueba.
   - Los cambios de esquema van en dos pasos (primero añadir, después quitar), para que el código
     anterior siga funcionando mientras se despliega.
   - Los permisos de un modelo nuevo se reparten a los roles de forma explícita.

   Bien: `publish_due_items` (`apps/content/tasks.py`) es idempotente ante un doble beat o un
   reintento.
10. **Pruebas.** Comprueban lo que ve o hace una persona.
    - Un `.css` o un `.js` solo se lee para afirmar una invariante.
    - Toda prueba de «no aparece» lleva un control positivo en la misma respuesta.
    - Los permisos se prueban por HTTP, con los grupos reales.

    Bien: `tests/test_contraste_paleta.py` calcula el contraste desde los tokens. Mal: afirmar que
    `site.css` contiene `repeat(5, minmax(0, 1fr))`, porque un cambio cosmético la rompe y una
    regresión real la pasa. Si una prueba falla tras un cambio de diseño, no se copia el valor
    nuevo sin preguntarse qué vigilaba.
11. **Herramientas de desarrollo.** No viven en las apps de producción ni se protegen con
    `--force`, y hay un solo camino para poblar desarrollo. Mal: `seed_demo` está en
    `apps/content`, y con `--force` corre también con `DEBUG=0`.

## Documentación relacionada

- Despliegue: [docs/despliegue.md](docs/despliegue.md)
- Respaldos: [docs/respaldos.md](docs/respaldos.md)
- Auditoría de código y su backlog: [docs/auditoria-codigo.md](docs/auditoria-codigo.md) y
  [docs/backlog-codigo.md](docs/backlog-codigo.md)
- Decisiones y diferidos, con su porqué: [docs/deferidos-y-decisiones.md](docs/deferidos-y-decisiones.md)
