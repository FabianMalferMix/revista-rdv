# Plan de mejoras por Lotes — Proyecto «Reseñas»

**Propósito:** hoja de ruta ejecutable para cerrar los **89 hallazgos** de la auditoría de producción
([docs/auditoria-produccion.md](auditoria-produccion.md)) y llevar el proyecto a producción real.
El trabajo se organiza en **14 Lotes** del tamaño de un PR, secuenciales y cada uno verificable de forma
independiente.

> **Cómo usar este plan (importante — la memoria de sesión se compacta):**
> Este documento es auto-contenido. Una sesión fresca debe **(1)** leer las secciones *Contexto del proyecto*
> y *Entorno y convenciones* de abajo, **(2)** ir al Lote asignado, que trae su propio contexto, pasos,
> archivos y criterio de done, y **(3)** terminar el Lote con la suite en verde y las verificaciones indicadas.
> Cada Lote cita los hallazgos que cierra con `archivo:línea`; el detalle ampliado de cada hallazgo está en
> el informe de auditoría enlazado arriba.

---

## Contexto del proyecto

**Qué es:** «Reseñas», revista literaria chilena de crítica de libros, concebida como **archivo permanente**
(las URLs no deben romperse nunca). Monolito **Django 5 + plantillas + htmx**, **PostgreSQL 16**, **Celery + Redis**,
**gunicorn + WhiteNoise**, todo dockerizado.

**Documentos de diseño (contexto profundo):**
- Modelo de datos (3NF/BCNF): https://claude.ai/code/artifact/7eaf465d-503b-45f8-80fa-776e14d34eae
- Flujo editorial y permisos: https://claude.ai/code/artifact/8042cdc8-e619-4891-9325-1df5ab8c3073

**Mapa de la arquitectura** (`backend/`):
- `config/` — proyecto Django: `settings.py`, `urls.py`, `celery.py`, `wsgi.py`, `asgi.py`. `DJANGO_SETTINGS_MODULE=config.settings`.
- `apps/` — 6 apps (label = último segmento). Orden de dependencias: `media → people → reviews → content → community → submissions`.
  - **content** (núcleo): `Article`, `Section`, `Tag`, `Dossier`, `Page`, puentes `ArticleContributor`/`ReviewedWork`/`DossierArticle`, auditoría `EditorialTransition`/`EditorialNote`. Además: `workflow.py` (máquina de estados editorial, servicio `perform_transition`), `permissions.py` (permisos por rol+estado), `sanitize.py` (nh3), `tasks.py` (Celery `publish_due_articles`), `feeds.py` (RSS), `sitemaps.py`, `context_processors.py` (nav), `views.py`, `admin.py`, `management/commands/seed_demo.py`.
  - **people**: `Contributor`, `SocialLink`; `management/commands/setup_groups.py` (crea grupos `admin`/`editor`/`autor`).
  - **reviews**: `Work`, `Publisher`, `BookAuthor`; `views.py` (páginas de obra/editorial/autor).
  - **community**: `Comment`, `NewsletterSubscriber` — **hoy solo existen en el admin** (sin capa pública).
  - **submissions**: `Submission`, `Call`; `forms.py`, `views.py` (`submit`, `submission_file`), **storage privado** (`private_media`).
  - **media**: `MediaAsset` (biblioteca de imágenes).
- `templates/` — `base.html` + `content/**`, `reviews/**`, `submissions/**`. `static/css/site.css`, `static/admin/richtext_init.js`.
- `tests/` — 6 archivos (`test_workflow/permissions/models/submissions/views/admin`). **Baseline actual: 48 tests en verde.**
- Raíz: `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`, `Dockerfile` (en `backend/`), `infra/nginx/default.conf` (referencia, **no cableado aún**), `.github/workflows/ci.yml`.

**Lo que ya está sólido (NO romper):** máquina de estados con auditoría inmutable; permisos de admin por estado
(owner + estado editable); storage privado de manuscritos con descarga solo-editores; sanitización nh3 en
`Article.save`/`Page.save`; defaults *fail-safe* de `SECRET_KEY`; tests + CI; SEO base (sitemap/RSS/JSON-LD/honeypot).

---

## Entorno y convenciones (leer siempre)

**Ruta del repo:** `/home/fabian/User/repos/Reseñas`

**Levantar el stack (dev):**
```bash
cp -n .env.example .env
docker compose up -d --build          # dev: http://localhost:8000  ·  admin: /admin
docker compose exec web python manage.py createsuperuser   # si hace falta
docker compose exec web python manage.py seed_demo         # datos de ejemplo
```

**Correr la suite (debe quedar SIEMPRE en verde al cerrar un Lote):**
```bash
docker compose run --rm --entrypoint pytest web
```

**Generar migraciones** (el contenedor corre como **root**, así que hay que devolver la propiedad):
```bash
docker compose exec -T web python manage.py makemigrations <app>
# ⚠️ GOTCHA de propiedad: cualquier archivo que el contenedor escriba en el bind-mount ./backend queda como root.
docker run --rm --entrypoint chown -v "/home/fabian/User/repos/Reseñas/backend":/app resenas-web -R 1000:1000 /app
```
> Corre ese `chown` tras cualquier `makemigrations`/`collectstatic`/`pytest` que deje archivos root en `backend/`.
> Verifica con `find backend -not -user fabian`. Requiere que la imagen `resenas-web` exista (`docker compose build web`).

**Gotchas del entorno que una sesión fresca DEBE conocer:**
- **Migraciones versionadas**: el `entrypoint.sh` solo corre `migrate` (no `makemigrations`). Las migraciones se
  generan a mano (arriba) y se commitean.
- **`.env`**: dev usa `DJANGO_DEBUG=1`. Con `DEBUG=0` el arranque **exige** `DJANGO_SECRET_KEY` propia (guard en settings).
- **`private_media`** es un volumen aparte de `media`; los adjuntos de envíos viven ahí y no se sirven públicamente.
- **Sanitización** de HTML ocurre en `Article.save`/`Page.save` (nh3). El `search_vector` se re-puebla en cada `save()`
  (esto se corrige en el Lote 9).
- **WhiteNoise sirve solo `/static/`, NO `/media/`** (relevante para prod).
- **El repo aún NO es git** → el Lote 0 lo inicializa.

**Disciplina por Lote (Definition of Done):**
1. Implementar los cambios del Lote.
2. `pytest` en verde (añadir/actualizar tests cuando el Lote lo indique).
3. Verificaciones específicas del Lote (curl / smoke / prod) OK.
4. `makemigrations` + `chown` si hubo cambios de modelo; migración commiteada.
5. `find backend -not -user fabian` vacío.
6. **Un commit por Lote** (tras el Lote 0), mensaje: `lote-N: <resumen>`.

**Orden y fases** (alineado con el roadmap del informe):
- **Antes de exponer a Internet (Fase 0):** Lote 0 → 1 → 2 → 3.
- **Fase 1 (hardening/ops, primer mes):** Lote 4 → 5 → 6.
- **Fase 2 (dominio/datos/rendimiento):** Lote 7 → 8 → 9.
- **Fase 3 (arquitectura/público/cobertura):** Lote 10 → 11 → 12 → 13.
- ⚠️ **Excepción de orden:** la parte de **`CustomUser` (Lote 10 / M21)** conviene hacerla **antes del lanzamiento
  o antes de acumular datos reales** (migrar el User con datos en producción es doloroso). Si se puede, adelántala
  a la Fase 0/1 con reseteo de la BD de desarrollo.

---

## Lote 0 — Fundaciones: git, tooling e higiene de repo · [Fase 0] · S–M

**Objetivo:** red de seguridad (git) y guardarraíles automáticos (linter, formato, escaneo) antes de tocar nada,
más higiene de repositorio.

**Hallazgos:** parte de M28 (`.github/workflows/ci.yml:47`); lows de higiene: `celerybeat-schedule` versionado
(`backend/celerybeat-schedule`), `.dockerignore` no aplica al contexto `./backend` (`.dockerignore:1`), comentario
obsoleto «sanitizar (pendiente)» (`article_detail.html:57`), doc de `--reuse-db` (`pytest.ini:6`).

**Contexto:** el repo no está bajo control de versiones; sin un baseline no hay reversibilidad ni PRs revisables.
El `.dockerignore` de la raíz no protege el build porque el contexto de build es `./backend`.

**Pasos:**
1. `git init`; añadir `.gitignore` (ya existe) y hacer **commit baseline** de todo el estado actual (`baseline: estado tras auditoría`).
2. Añadir **ruff** (lint + format) a `requirements-dev.txt`; configurar en `pyproject.toml` (target py312, reglas E/F/I, line-length). Correr `ruff format` y `ruff check --fix` una vez y commitear el resultado.
3. Crear `backend/.dockerignore` (copiar/ajustar el de la raíz: `__pycache__`, `.pytest_cache`, `staticfiles`, `mediafiles`, `private_media`, `*.md`, `.env`).
4. Borrar `backend/celerybeat-schedule` si existe; añadirlo a `.gitignore` y `.dockerignore`.
5. Actualizar el comentario obsoleto en `article_detail.html` (la sanitización SÍ ocurre en el modelo).
6. CI (`ci.yml`): añadir pasos `ruff check` + `ruff format --check` + `pip-audit` (no bloqueante al inicio si hay ruido, luego bloqueante).
7. Documentar en `pytest.ini`/README el uso de `--create-db` tras cambios de esquema.

**Archivos:** `pyproject.toml` (nuevo), `requirements-dev.txt`, `backend/.dockerignore` (nuevo), `.gitignore`, `.dockerignore`, `.github/workflows/ci.yml`, `backend/templates/content/article_detail.html`, `README.md`.

**Verificación / DoD:** `ruff check` limpio; `pytest` verde; CI pasa; repo con commit baseline + commit del Lote.

---

## Lote 1 — Respaldos y retención del archivo · [Fase 0] · M

**Objetivo:** que ningún dato se pierda jamás. Es el mayor riesgo del proyecto.

**Hallazgos:** **A1** (`docker-compose.yml:67`).

**Contexto:** el sistema se declara *archivo permanente* pero no hay respaldo de PostgreSQL ni de `media`/`private_media`.
Un `docker compose down -v`, un fallo de disco o una migración de host = pérdida total irreversible.

**Pasos:**
1. Script `infra/backup/backup.sh`: `pg_dump` comprimido de la BD + `tar` de los volúmenes `media` y `private_media`, con timestamp y **retención** (p.ej. 7 diarios + 4 semanales).
2. Programar el backup: servicio *sidecar* en un `docker-compose.prod.yml` (contenedor con cron) **o** cron del host documentado. Destino: almacenamiento **externo** (S3/restic/borg), no el mismo disco.
3. Script `infra/backup/restore.sh` y **documentar + ejecutar una prueba de restauración** (restaurar en un stack limpio y verificar que el sitio levanta con los datos).
4. Documentar la política (frecuencia, retención, ubicación, cómo restaurar) en `docs/` o README.

**Archivos:** `infra/backup/` (nuevo), `docker-compose.prod.yml`, README/docs.

**Verificación / DoD:** ejecutar `backup.sh` y luego `restore.sh` en un stack limpio (`down -v` + up) y confirmar que
el contenido vuelve. Dejar la prueba documentada.

---

## Lote 2 — Hardening de secretos, BD y Redis · [Fase 0] · S

**Objetivo:** que la base y Redis no sean accesibles ni adivinables desde Internet, y forzar TLS en producción.

**Hallazgos:** **A2** (`docker-compose.yml:9,17` · `settings.py:11`); **M4** (`settings.py:153`); lows: Redis sin auth
(`settings.py:130`), `SECRET_KEY_FALLBACKS` (`settings.py:12`), Redis sin persistencia/`maxmemory` (`docker-compose.yml:20`).

**Contexto:** el puerto 5432 se publica al host también en producción, con la contraseña por defecto del `.env` de
ejemplo; la app no necesita ese puerto (habla con `db` por la red interna). HSTS/SSL están apagados por defecto.

**Pasos:**
1. **No publicar puertos internos en prod:** en `docker-compose.prod.yml` sobrescribir `db`/`redis`/`web` para no exponer `5432`/`6379` (y publicar `8000` solo hacia el proxy, ver Lote 3). En dev, bindear `5432` a `127.0.0.1` en vez de `0.0.0.0`.
2. **Credenciales:** crear `.env.prod.example` separado; exigir `POSTGRES_PASSWORD` fuerte. Añadir **guard en `settings.py`**: con `DEBUG=0`, rechazar el arranque si `POSTGRES_PASSWORD`/`ALLOWED_HOSTS` siguen en su valor de ejemplo (mismo patrón que el guard de `SECRET_KEY`).
3. **M4:** con `DEBUG=0`, **invertir defaults**: `SECURE_SSL_REDIRECT=True` y `SECURE_HSTS_SECONDS=31536000` por defecto (permitiendo desactivar por env). Fallar si `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` quedan en default con `DEBUG=0`.
4. **Redis:** `requirepass` vía env, nunca exponer 6379; fijar `maxmemory` + política (`allkeys-lru`) y/o `appendonly yes` para no perder tareas.
5. **`SECRET_KEY_FALLBACKS`** desde env para permitir rotación con solapamiento.

**Archivos:** `docker-compose.yml`, `docker-compose.prod.yml`, `backend/config/settings.py`, `.env.example`, `.env.prod.example` (nuevo).

**Verificación / DoD:** `pytest` verde; con `DEBUG=0` + password de ejemplo el arranque **falla** (probar con
`manage.py check`); con clave/valores propios, pasa. `docker compose ... config` sin 5432/6379 publicados en prod.

---

## Lote 3 — Despliegue real: proxy TLS, MEDIA, resiliencia · [Fase 0] · M–L

**Objetivo:** un `docker-compose.prod.yml` que produzca un sistema **con TLS, que sirva las imágenes y se recupere solo**.

**Hallazgos:** **A3** (`config/urls.py:21`); **M1** (`docker-compose.prod.yml:8-10` · `docker-compose.yml:29,37`);
lows: gunicorn sin `--max-requests`/`--timeout`/access-log (`Dockerfile:19`), `entrypoint.sh` migrate incondicional
(`entrypoint.sh:5`), bind-mount de código en prod (`docker-compose.prod.yml:9`).

**Contexto:** WhiteNoise **no** sirve `/media/`, así que con `DEBUG=0` toda portada/`og:image` da 404 silencioso.
El override actual deja gunicorn en HTTP plano :8000 sin proxy, sin `restart`, con el bind-mount tapando la imagen.

**Pasos:**
1. Añadir servicio **nginx** (o Caddy con TLS automático) al `docker-compose.prod.yml`, montando `infra/nginx/` y el volumen `media`; que sirva `/static/` (WhiteNoise o el volumen) y **`/media/`**, y termine TLS. Dejar de publicar `web:8000` al host (solo al proxy).
2. En el override de prod: **quitar el bind-mount `./backend:/app`** del `web`/`worker`/`beat` (dejar solo volúmenes de datos `media`/`private_media`), añadir `restart: unless-stopped` y un **healthcheck HTTP** a `web`.
3. gunicorn: `--forwarded-allow-ips` a la IP del proxy, `--workers` parametrizable, `--timeout`, `--max-requests`(+jitter), access-log.
4. **Migraciones fuera del entrypoint** para prod: correr `migrate` como paso de despliegue (job) explícito, no en cada arranque (evita carreras al escalar y migraciones destructivas automáticas). Mantener el entrypoint de dev.
5. **Smoke test A3:** verificar que una URL de `MediaAsset` responde 200 en configuración de producción (test o script). Documentar la limitación de WhiteNoise con MEDIA.

**Archivos:** `docker-compose.prod.yml`, `infra/nginx/default.conf`, `backend/Dockerfile`, `backend/entrypoint.sh`, `backend/config/urls.py` (o settings, para MEDIA en prod).

**Verificación / DoD:** levantar el stack de prod (con `SECRET_KEY` real) y comprobar: home 200, `/static/...` 200,
**`/media/<algo>` 200**, headers de seguridad presentes, `restart` y healthcheck activos. `pytest` verde.

> **Cierre de Fase 0:** con Lotes 0–3, ningún dato se pierde ni se expone y el contenido se ve. Recién aquí es
> defendible exponer el sitio a Internet.

---

## Lote 4 — Imagen de producción endurecida · [Fase 1] · M

**Objetivo:** imagen mínima, no-root y reproducible.

**Hallazgos:** **M6** (`Dockerfile:18`), **M9** (`requirements.txt:1`); lows: prod con deps de test / sin multi-stage
(`Dockerfile:10`).

**Contexto:** el contenedor corre como root (una RCE escala a root y genera archivos root en el host) y la imagen
incluye deps de test; los rangos de versiones abiertos hacen el artefacto no reproducible.

**Pasos:**
1. **Dockerfile multi-stage:** stage de build (deps) + stage runtime slim; instalar solo `requirements.txt` en prod (deps de test solo en una imagen/variante de CI/dev).
2. **Usuario no-root:** crear `app` (uid 1000 para coincidir con el host), `chown` de `/app` y directorios de datos, `USER app` antes del `CMD`.
3. **Lockfile con hashes:** adoptar `pip-tools`/`uv` para pinear versiones exactas con hashes; instalar con `--require-hashes`; verificar en CI.
4. Ajustar `entrypoint.sh`/permisos para el usuario no-root (que pueda escribir `staticfiles`/logs si aplica).

**Archivos:** `backend/Dockerfile`, `backend/requirements*.txt` (+ lockfile), `backend/entrypoint.sh`, `.github/workflows/ci.yml`.

**Verificación / DoD:** la imagen corre como `app` (`docker compose exec web id` → uid 1000); build reproducible;
`pytest` verde; stack dev y prod levantan igual. (Nota: como el uid coincide con el host, ojo con el `chown` gotcha.)

---

## Lote 5 — Seguridad de aplicación: auth, CDN/CSP, rate limiting · [Fase 1] · M–L

**Objetivo:** proteger la única superficie de auth (admin) y cerrar supply-chain y abuso de la subida pública.

**Hallazgos:** **M3** (`config/urls.py:12`), **M2** (`admin.py:26` · `base.html:23`), **M5** (`submissions/views.py:17`);
lows: validación de adjunto por extensión (`submissions/forms.py:41`), htmx/TinyMCE por CDN (`base.html:23`).

**Contexto:** el login del admin no tiene defensa anti fuerza bruta; htmx y TinyMCE se cargan de CDN sin SRI ni CSP
(un CDN comprometido inyecta JS con sesión de superusuario); la subida de manuscritos solo tiene honeypot.

**Pasos:**
1. **M3:** `django-axes` (bloqueo por intentos) + rate limiting en `/admin/login/`; 2FA para editores/admin (`django-otp`/`django-two-factor-auth`). Opcional: restringir `/admin/` por IP/VPN o ruta no obvia.
2. **M2:** **vendorizar** htmx y TinyMCE en `static/` (servidos por WhiteNoise con hash) o, mínimo, fijar versión con `integrity`+`crossorigin`. Añadir **CSP** (`django-csp`) restrictiva, al menos para `/admin/`.
3. **M5:** `django-ratelimit` por IP en la vista `submit`; rechazar envío si no hay convocatoria abierta; monitorear tamaño de `private_media`.
4. **Adjuntos:** complementar la validación de extensión con **magic bytes** (p.ej. `python-magic`); mantener el trato como no confiable (ya van a storage privado + `as_attachment` + `nosniff`).

**Archivos:** `settings.py` (middleware, CSP, axes), `requirements.txt`, `base.html`, `content/admin.py`, `static/` (assets vendorizados), `submissions/views.py`, `submissions/forms.py`, `urls.py` (2FA).

**Verificación / DoD:** tests de rate limit/lockout (o smoke); el sitio funciona **sin** llamadas a CDN externos
(revisar el HTML: no quedan `unpkg`/`jsdelivr`); CSP presente en headers; `pytest` verde.

---

## Lote 6 — Observabilidad, correo y bootstrap de permisos · [Fase 1] · M

**Objetivo:** enterarse de los errores en producción y no revertir permisos en cada deploy.

**Hallazgos:** **M7** (`settings.py:173`), **M8** (`setup_groups.py:40`).

**Contexto:** los 500 se pierden sin agregación ni alertas; `setup_groups` reescribe permisos en cada arranque,
revirtiendo ajustes manuales del admin.

**Pasos:**
1. **M7:** integrar **Sentry** vía `SENTRY_DSN` opcional (activo solo si está definido); `LOGGING` con formatter estructurado (timestamp/logger/nivel, idealmente JSON) a stdout.
2. **M8:** hacer `setup_groups` **idempotente no destructivo**: usar `permissions.add(...)` para bootstrap inicial en vez de `set(...)`, **o** correrlo solo bajo bandera explícita (no en cada arranque del entrypoint).
3. Revisar que el correo real (SMTP) esté completo para la newsletter (backend, `DEFAULT_FROM_EMAIL`, TLS).

**Archivos:** `settings.py`, `requirements.txt`, `people/management/commands/setup_groups.py`, `entrypoint.sh`.

**Verificación / DoD:** con `SENTRY_DSN` set, un error de prueba llega a Sentry; sin él, no rompe. Un permiso
añadido a mano a un grupo **sobrevive** a un reinicio. `pytest` verde.

---

## Lote 7 — Dominio: publicación correcta y workflow blindado · [Fase 2] · M

**Objetivo:** una sola fuente de verdad para «artículo publicado» y que el estado solo cambie por el workflow.

**Hallazgos:** **M10** (`content/views.py:20`), **M11** (`content/admin.py:119`); lows de workflow: `schedule` sin
`published_at` (`workflow.py:60`), task no idempotente/atómica (`tasks.py:10`), `perform_transition` sin transacción
(`workflow.py:59`), task duplica lógica de publish (`tasks.py:15`).

**Contexto:** la regla de publicado está copiada en 5+ sitios y **no filtra `published_at <= now`**, así que se filtran
artículos con fecha futura/nula (fuga de contenido no publicado, `pubDate` incorrecto en RSS). Editar `status` en el
admin salta la auditoría.

**Pasos:**
1. **M10:** `ArticleQuerySet.published()` (`status=PUBLISHED, published_at__lte=now, published_at__isnull=False`) + Manager; consumirlo desde `views.py`, `feeds.py`, `sitemaps.py`, `reviews/views.py` y la task. Eliminar los `_published()` duplicados.
2. **M11:** `status` y `published_at` **readonly para todos** en el admin; forzar los cambios solo por las acciones que llaman a `workflow.perform_transition` (o validar en `save_model` que todo cambio de estado pase por la máquina).
3. **Workflow lows:** `perform_transition` dentro de `transaction.atomic()`; `schedule` exige `published_at` futura; `publish_due_articles` usa `perform_transition` (no reimplementa) y es atómica/idempotente (`select_for_update(skip_locked=True)` o `update()` condicional).

**Archivos:** `content/models.py` (manager), `content/views.py`, `content/feeds.py`, `content/sitemaps.py`, `apps/reviews/views.py`, `content/tasks.py`, `content/workflow.py`, `content/admin.py`.

**Verificación / DoD:** test de que un artículo con `published_at` futura **no** aparece en home/feed/sitemap; test de
que editar `status` en el admin no salta la auditoría; tests de la task reforzados (ver Lote 13). `pytest` verde.

---

## Lote 8 — Integridad de datos: constraints, unicidad, índices · [Fase 2] · S–M

**Objetivo:** que el modelo garantice de verdad lo que promete.

**Hallazgos:** **M12** (`community/models.py:63`), **M13** (`content/models.py:170`), **M27** (`submissions/models.py:49`);
lows de datos: `NewsletterSubscriber.token` (`community/models.py:67`), `Comment.parent` CASCADE (`community/models.py:17`),
XOR sin `guest_email` (`community/models.py:41`), índice `Article.type` (`models.py:66`), desempate `created_at`
(`models.py:117`).

**Contexto:** `A@x.com` y `a@x.com` evaden el `unique` (suscriptores duplicados); una reseña puede tener 2 obras
«principales»; manuscritos retirados persisten en disco al borrar el registro.

**Pasos:**
1. **M12:** normalizar email a minúsculas al guardar y/o `CITextField` (con `CITextExtension` en migración) para la columna única.
2. **M13:** `UniqueConstraint(fields=["article"], condition=Q(is_primary=True), name="uniq_primary_work_per_article")`.
3. **M27:** borrar archivos al eliminar/reemplazar (`django-cleanup` o señales `post_delete`/`pre_save` que llamen a `storage.delete`) para `Submission.file` y `MediaAsset.file`; documentar el flujo de «retiro de envío» y ligarlo a la retención del Lote 1.
4. **Lows:** `token` obligatorio+único+indexado (`secrets.token_urlsafe`); `Comment.parent` → `SET_NULL` + constraint de artículo compartido (o borrado lógico); extender el `CheckConstraint` XOR a `guest_email`; índice compuesto `(type, status, -published_at)`; extender el orden/índice con `-created_at`.

**Archivos:** `community/models.py`, `content/models.py`, `submissions/models.py`, `media/models.py`, migraciones (¡`chown`!).

**Verificación / DoD:** tests de unicidad case-insensitive, de obra-principal-única, y de borrado de archivo al eliminar
`Submission`. Migraciones reversibles. `pytest` verde.

---

## Lote 9 — Rendimiento: full-text, paginación, N+1, caché · [Fase 2] · M

**Objetivo:** quitar la escritura redundante del buscador y acotar el coste de las páginas de archivo.

**Hallazgos:** **M14** (`content/models.py:133`), **M15** (`reviews/views.py:39`), **M16** (`content/views.py:37`),
**M17** (`settings.py:129`); lows: buscador sobre-consulta (`views.py:103`), `CONN_HEALTH_CHECKS` (`settings.py:85`).

**Contexto:** `search_vector` hace un `UPDATE` extra y re-tokeniza el cuerpo en **cada** `save()` (incl. transiciones y
el beat), y cualquier escritura que no pase por `save()` deja artículos **invisibles en el buscador**. Las páginas de
editorial/autor/obra/dosier no paginan. No hay caché pese a tener Redis.

**Pasos:**
1. **M14:** mover el `tsvector` a la BD con `GeneratedField`/trigger (`RunSQL` reversible), eliminando el `UPDATE` en Python; pesos (título=A, subtítulo=B, cuerpo=C), incluir `excerpt`; comando `reindex_search` idempotente. (Si se mantiene en `save()`, condicionar a que `title/subtitle/body` cambiaron.)
2. **M15:** envolver las listas de `reviews/views.py` y `dossier_detail` con el `_paginate()` de `content/views.py` (que `_article_list.html` reciba siempre un `Page`).
3. **M16:** en `article_detail`, consulta específica con `.prefetch_related('reviewed_works__publisher', 'tags')` además de `authors`/`section` (no reutilizar `_published()`).
4. **M17:** `CACHES` con `RedisCache`; `{% cache %}` en nav y listados; `cache_page` en sitemap/feed.
5. **Lows:** buscador con queryset mínimo (`.only(...)`); `'CONN_HEALTH_CHECKS': True` en la BD.

**Archivos:** `content/models.py` + migración (trigger), `content/management/commands/reindex_search.py` (nuevo), `apps/reviews/views.py`, `content/views.py`, `settings.py`, plantillas (fragment cache).

**Verificación / DoD:** un `Article.objects.update(...)` deja el artículo **buscable** (test); las páginas de editorial/
autor paginan; conteo de queries de `article_detail` estable; caché activa. `pytest` verde.

---

## Lote 10 — Arquitectura Django: User, URLs, byline, i18n · [Fase 3 · adelantar CustomUser] · M

**Objetivo:** decisiones estructurales que son baratas ahora y caras después.

**Hallazgos:** **M21** (`settings.py:25`), **M19** (`content/models.py:60`), **M18** (`content/models.py:88`);
lows: `Page.status` reutiliza `DossierStatus` (`models.py:234`), `USE_I18N` incoherente (`settings.py:100`).

**Contexto:** Django recomienda `AUTH_USER_MODEL` propio desde el inicio; migrarlo con datos es doloroso. Ningún
modelo tiene `get_absolute_url` (cambiar una URL exige tocar feeds/sitemaps/plantillas). El byline ignora
`ArticleContributor.position` (orden alfabético en vez de editorial).

**Pasos:**
1. **M21 (⚠️ hacer antes de datos reales):** definir `apps/people` (o `accounts`) `CustomUser(AbstractUser)` y `AUTH_USER_MODEL`. Requiere **resetear la BD de dev** (`down -v`) y regenerar migraciones. Si se decide NO hacerlo, documentarlo como decisión consciente.
2. **M19:** `get_absolute_url()` con `reverse()` en `Article`, `Section`, `Tag`, `Dossier`, `Page`, `Contributor`, `Work`, `Publisher`, `BookAuthor`; usarlo en feeds, sitemaps y plantillas; habilita «view on site».
3. **M18:** `article.ordered_authors()` que ordene por `articlecontributor__position` (o `Prefetch` con ese `order_by`); usarlo en plantillas y feed.
4. **Lows:** `PublishStatus` compartido y neutral (reemplaza `DossierStatus` en `Page`/`Dossier`); resolver `USE_I18N` (o `False` monolingüe, o instrumentar i18n de verdad con `LocaleMiddleware`+`gettext`).

**Archivos:** `apps/*/models.py`, `settings.py`, feeds/sitemaps/plantillas, migraciones (¡reset si CustomUser!).

**Verificación / DoD:** `pytest` verde tras el swap de User (revisar fixtures/`conftest.py`); `get_absolute_url`
resuelve en todos los modelos; byline en orden editorial (test).

---

## Lote 11 — Decisión sobre la app `community` (comentarios/newsletter públicos) · [Fase 3] · L (o S si se documenta)

**Objetivo:** eliminar la feature muerta: o se completa la capa pública, o se documenta como fuera de alcance.

**Hallazgos:** **M20** (`community/models.py:1`).

**Contexto:** `Comment`/`NewsletterSubscriber` existen y `seed_demo` los crea, pero **no hay vistas ni forms públicos**:
los lectores no pueden comentar ni suscribirse; la moderación del admin no tiene salida.

**Pasos (elegir una rama):**
- **(a) Completar:** form de comentario (htmx) con pre-moderación en `article_detail`, render de comentarios `approved`, alta de newsletter con **doble opt-in** por correo (usa el `token` del Lote 8), rate limiting (Lote 5). Con tests.
- **(b) Documentar fuera de alcance:** dejar claro en README/docs que la capa pública no está cableada; opcional: ocultar del seed o marcar.

**Archivos:** `community/views.py`+`forms.py`+`urls.py`+plantillas (rama a), o README/docs (rama b).

**Verificación / DoD:** rama (a): un lector puede comentar (queda `pending`) y suscribirse (queda `pending` hasta
confirmar), con tests; rama (b): decisión documentada y seed coherente. `pytest` verde.

---

## Lote 12 — Experiencia pública: SEO, accesibilidad, error pages · [Fase 3] · S–M

**Objetivo:** que el sitio no rompa enlaces, sea compartible y accesible.

**Hallazgos:** **M22** (`config/urls.py:11`), **M23** (`base.html:30`), **M24** (`article_detail.html:58`),
**M25** (`base.html:15`), **M26** (`base.html:49`); lows: JSON-LD incompleto (`article_detail.html:16`),
`lastmod` solo en artículos (`sitemaps.py:23`), sin skip-link (`base.html:26`), buscador sin mínimo/CLS (`base.html:31`),
sin RSS por sección (`feeds.py:7`).

**Contexto:** portadas nunca se muestran (pese a exigir `alt_text`); no hay 404/500 propias; el canonical incluye
`?q=` (contenido duplicado indexable); resultados htmx sin `aria-live`.

**Pasos:**
1. **M22:** `templates/404.html` y `500.html` que extiendan `base.html` (Django los usa auto); test del 404. Considerar 403/400.
2. **M23:** el form del buscador apunta a una página de resultados que procese `q` (degrada sin JS); canonical **sin querystring** (`request.path` + host).
3. **M24:** renderizar `cover_image` (`<figure><img alt loading=lazy width height>`) en `article_detail` y miniatura en `_article_card`.
4. **M25:** imagen de marca por defecto (1200×630) en `static/`, emitida como `og:image` en `base.html` (el detalle la sobrescribe).
5. **M26:** `aria-live="polite"`, `aria-atomic`, `role="region"` + `aria-label` en `#search-results`.
6. **Lows:** JSON-LD completo (image/logo/breadcrumb + `WebSite`+`Organization` en `base.html`); `lastmod` en todos los sitemaps; skip-link visible-on-focus; mínimo `len>=2` en el buscador + panel superpuesto (evitar CLS); feed RSS por slug de sección.

**Archivos:** `templates/404.html`+`500.html` (nuevos), `base.html`, `content/article_detail.html`, `_article_card.html`, `content/views.py` (búsqueda/canonical), `sitemaps.py`, `feeds.py`, `static/` (og default), `site.css`.

**Verificación / DoD:** 404 renderiza con identidad de la revista; portada visible; `og:image` presente; canonical sin
`?q=`; `aria-live` en el buscador. `pytest` verde.

---

## Lote 13 — Cobertura de tests y CI completo · [Fase 3] · S–M

**Objetivo:** cerrar los huecos de cobertura y hacer el CI un guardarraíl real.

**Hallazgos:** **M29** (`content/models.py:248`), **M30** (`community/admin.py:14`), **M31** (`tests/test_workflow.py:73`),
completar **M28** (cobertura); lows de test: feed sin test (`feeds.py:12`), sitemap sin test (`sitemaps.py:13`),
`seed_demo` sin guard/idempotencia (`seed_demo.py:38`), `--reuse-db` (`pytest.ini:6`), robots/nav sin test
(`views.py:116`), búsqueda sin test (`views.py:97`), asserts sobre bytes UTF-8 (`test_views.py:24`).

**Contexto:** superficies globales (feed, sitemap, robots, nav, búsqueda) sin test; la task del beat solo tiene
camino-feliz; `seed_demo` podría inyectar contenido falso en el archivo si se corre en prod.

**Pasos:**
1. **M29:** tests de sanitización de `Page.body` (script/`on*`/`javascript:`) + formato permitido conservado.
2. **M30:** tests de que cada acción de `CommentAdmin` fija el `status` esperado y del `IntegrityError` del XOR.
3. **M31:** `assert published == 1`; caso negativo (SCHEDULED futuro sigue SCHEDULED); asertar `EditorialTransition`.
4. **Lows:** tests de feed (200/XML, publicado presente, borrador ausente), sitemap (integración), robots (`Disallow: /admin/`), nav, y vista de búsqueda (`?q=`, orden `-rank`, solo publicados). `seed_demo`: `CommandError` si `not DEBUG` salvo `--force` + test de doble corrida (idempotencia). Documentar `--create-db` tras migraciones. Refactor de asserts de bytes UTF-8 → `resp.context` o decodificar.
5. **M28 (cierre):** activar `pytest --cov=apps --cov-fail-under=<n>` en CI (fijar `n` al nivel actual y subirlo con el tiempo); dejar `pip-audit`/`ruff` bloqueantes.

**Archivos:** `tests/*.py` (varios, incl. nuevos `test_feeds`/`test_sitemaps`/`test_seed`), `seed_demo.py`, `pytest.ini`, `.github/workflows/ci.yml`.

**Verificación / DoD:** suite ampliada en verde; CI corre lint+format+cobertura(gate)+`pip-audit`; `seed_demo` rechaza
correr en prod sin `--force`.

---

## Matriz de cobertura (hallazgo → Lote)

| Lote | Hallazgos cubiertos |
|---|---|
| **0** Fundaciones | M28 (parcial: ruff/pip-audit), lows: celerybeat versionado, `.dockerignore` backend, comentario obsoleto, `--reuse-db` doc |
| **1** Respaldos | **A1** |
| **2** Secretos/BD/Redis | **A2**, **M4**, lows: Redis auth, `SECRET_KEY_FALLBACKS`, Redis persistencia/maxmemory |
| **3** Despliegue real | **A3**, **M1**, lows: gunicorn flags, entrypoint migrate, bind-mount prod |
| **4** Imagen prod | **M6**, **M9**, low: multi-stage/deps de test |
| **5** Seguridad app | **M2**, **M3**, **M5**, lows: adjunto magic bytes, htmx/TinyMCE vendor |
| **6** Observabilidad | **M7**, **M8** |
| **7** Publicación/workflow | **M10**, **M11**, lows: schedule sin fecha, task idempotente/atómica, `perform_transition` transacción, task duplica publish |
| **8** Integridad de datos | **M12**, **M13**, **M27**, lows: token newsletter, `Comment.parent` CASCADE, XOR `guest_email`, índice `type`, desempate `created_at` |
| **9** Rendimiento | **M14**, **M15**, **M16**, **M17**, lows: buscador `.only()`, `CONN_HEALTH_CHECKS` |
| **10** Arquitectura | **M18**, **M19**, **M21**, lows: `PublishStatus`, `USE_I18N` |
| **11** community | **M20** |
| **12** Público/SEO/a11y | **M22**, **M23**, **M24**, **M25**, **M26**, lows: JSON-LD completo, `lastmod`, skip-link, buscador mínimo/CLS, RSS por sección |
| **13** Tests/CI | **M28** (cierre), **M29**, **M30**, **M31**, lows: feed test, sitemap test, seed guard+idempotencia, `--reuse-db`, robots/nav test, búsqueda test, asserts UTF-8 |

**Esfuerzo total estimado:** Fase 0 (Lotes 0–3) ≈ 4–6 días · Fase 1 (4–6) ≈ 1 semana · Fase 2 (7–9) ≈ 1 semana ·
Fase 3 (10–13) ≈ 1–1½ semanas. Las fases 1–3 pueden solaparse según capacidad.

---

## Apéndice — Reglas de oro para cada sesión

1. **La Fase 0 (Lotes 0–3) es no negociable antes de exponer el sitio a Internet.**
2. **Termina cada Lote en verde** (`pytest`) y con sus verificaciones; **un commit por Lote**.
3. **Cuidado con la propiedad root** tras `makemigrations`/`collectstatic`/`pytest`: corre el `chown` de la sección
   *Entorno y convenciones* y verifica con `find backend -not -user fabian`.
4. **No rompas lo que ya está sólido** (workflow+auditoría, permisos por estado, storage privado, sanitización nh3,
   guard de `SECRET_KEY`).
5. Ante duda sobre un hallazgo, consulta su detalle en [docs/auditoria-produccion.md](auditoria-produccion.md).
