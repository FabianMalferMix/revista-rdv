# Auditoría de calidad — ¿qué tan MVP es y cómo llevarlo a producción profesional?

> **Fecha:** 2026-07-27 · **Método:** auditoría multi-agente (8 dimensiones, cada hallazgo
> verificado adversarialmente contra el código real; 18 agentes, ~718K tokens, 293 lecturas de
> archivo). Ningún hallazgo resultó refutado. **Alcance:** calidad de código de todo el backend
> Django + plantillas + infra. Sucede a `docs/auditoria-produccion.md` (cuyos bloqueantes de
> lanzamiento ya se corrigieron en lotes); esta evalúa el estado **actual**, más maduro.

## 1. Veredicto ejecutivo

**Madurez global: `beta` (MVP avanzado, cerca de producción).**

Esto **no es un prototipo ni un MVP frágil**: es un monolito Django genuinamente bien construido —
modelo de datos en 3NF real, saneado XSS en la capa de persistencia, autorización por objeto/estado
verificada en servidor, guard de producción que rechaza secretos de ejemplo, TLS automático,
respaldos con restore documentado y 128 tests con CI. **Las 8 dimensiones aterrizan de forma
consistente en `beta`**: la base estructural ya es de producción; lo que falta es endurecimiento
operativo y de correctitud, no reescribir cimientos.

Dicho eso, hay **un bloqueante duro** (corre Django 5.1, EOL desde dic-2025, sin parches de
seguridad) y varios huecos que un sitio profesional no debería llevar a producción: **cero
observabilidad**, contenedor **como root** con dependencias de test, **respaldos off-site solo
documentados** (crítico para algo que se autodefine "archivo permanente"), una **máquina de estados
editorial que no se hace cumplir**, y —fuera de los 8 ejes técnicos— **exposición legal** (sin baja
de suscriptores ni páginas de privacidad). Calibrado al tráfico real (colectivo, tráfico bajo), **no
necesita sobre-ingeniería** (ni object storage ni load testing hoy). **Con 1–2 semanas de trabajo
enfocado queda listo para producción profesional a su escala.**

## 2. Scorecard por dimensión

| Dimensión | Madurez | Titular |
|-----------|:-------:|---------|
| Arquitectura y organización | `beta` | Base sólida (EditorialItem abstracto, máquina de estados centralizada, modelos bien divididos); resta desacoplar el agregador `content` que importa **vistas** de apps hermanas y aplicar el singleton con `load()`. |
| Seguridad | `beta` | Postura fuerte (guard prod, HSTS/cookies, saneado nh3, authz por objeto); falta defensa en profundidad: SRI/self-host de CDN, CSP, anti-fuerza-bruta y `pip-audit` bloqueante. |
| Modelo de datos y BD | `beta` | Diseño relacional a nivel producción (3NF, índices compuestos+GIN, constraints XOR/unique, migración expand/contract ejemplar); solo pulir N+1 y consistencia del `search_vector`. |
| Pruebas y CI | `beta` | 128 tests reales sobre flujo editorial, permisos y XSS; faltan cobertura medida, test del buscador FTS/htmx en vivo, aserciones menos frágiles y CD. |
| Frontend / UX / SEO / a11y | `beta` | a11y y SEO sorprendentemente cuidados (skip link, aria-live, JSON-LD, sitemaps); resta self-host de htmx/TinyMCE, `width/height`+`srcset` y honestidad del lightbox CSS-only. |
| Producción / DevOps / operaciones | `beta` | Despliegue sólido para bajo tráfico (Caddy/TLS, healthcheck, tuning gunicorn), pero **cero observabilidad**, imagen **root** con deps de test y off-site backups sin implementar. |
| Lógica de negocio / asincronía | `beta` | Workflow bien diseñado como librería pero **no enforced**: `status` editable a mano evita guardas y bitácora; falta idempotencia/atomicidad en Celery y hay una feature de comentarios a medio construir. |
| Dependencias / config / mantenibilidad | `beta` | Config dirigida por entorno madura y modelos bien factorizados, pero **Django EOL**, builds no reproducibles (rangos sin lockfile) e imagen prod con tooling de test. |

## 3. Fortalezas (lo que ya es nivel producción)

- **Refactor editorial de nivel producción:** base abstracta `EditorialItem` compartida por
  `Article`/`Poem`, bitácora inmutable con `GenericForeignKey` indexada, y máquina de estados
  centralizada y validada en servidor (`workflow.py`).
- **Modelo de datos en 3NF real:** `Publisher`/`BookAuthor` extraídos de `Work`, `SocialLink`
  des-JSON-ificado; índices compuestos `status/-published_at`, GIN sobre `tsvector`,
  `UniqueConstraint` en todos los puentes, `CheckConstraint` XOR usuario/invitado en `Comment`.
- **Migración de datos expand/contract en 3 pasos** (content `0003→0005`), set-based y con
  `backward` implementado — apta para cero-downtime, sirve de referencia.
- **Seguridad de base por encima de un MVP:** guard que aborta el arranque con secretos de ejemplo;
  HSTS 1 año + cookies `Secure` + SSL redirect condicionados a prod; `SECRET_KEY_FALLBACKS`.
- **XSS resuelto en persistencia:** todo HTML autoral pasa por nh3 en `save()`; el poema se guarda
  en texto plano y se autoescapa. Los dos únicos `|safe` están respaldados por saneado en BD.
- **Autorización real por objeto y estado:** `perform_transition` revalida rol+estado en servidor,
  el admin filtra queryset al dueño, `status`/`owner` readonly para no-editores; descarga de
  adjuntos privados con doble control staff+editor.
- **Frontend con a11y y SEO cuidados sin ser exigido:** skip link, `:focus-visible` global, region
  `aria-live` en búsqueda, nav `<details>` con degradación sin JS, canonical/OG/Twitter, JSON-LD
  Article, feeds RSS+podcast y 12 sitemaps.
- **128 tests** que cubren vistas públicas, flujo editorial, permisos, scoping del admin, tarea
  Celery, feed podcast y sanitización; CI con ruff, chequeo de migraciones y validación de config
  con `DEBUG=0`.

## 4. Bloqueantes (no llevar a producción así)

1. **Django 5.1 está EOL desde dic-2025** y el pin `<5.2` bloquea justo la LTS: framework sin
   parches de seguridad en un sitio público que se declara "archivo permanente". *(Único hallazgo
   marcado como bloqueante duro.)*
2. **Imagen Docker corre como root** (sin `USER`) y **arrastra pytest/ruff** (instala
   `requirements-dev.txt`): antipatrón de hardening + superficie de ataque innecesaria.
3. **Cero observabilidad:** sin Sentry/APM, `LOGGING` de una línea sin formato. En producción se
   opera a ciegas — un 500 o una tarea Celery fallida solo se ve si alguien lee logs crudos.
4. **Respaldos off-site y alertas de fallo solo documentados, no implementados:** `backup.sh`
   escribe al mismo host que la BD y ante error solo hace `echo`. Pérdida del host = datos y
   respaldos destruidos juntos; un sidecar que falla en silencio pasa semanas sin backups válidos.
5. **El flujo editorial no se hace cumplir:** `status` es editable a mano en el admin para editores
   y 5 de 9 transiciones solo se alcanzan por el desplegable, saltándose los guardas de
   `workflow.py` y la bitácora inmutable.
6. **(Legal, fuera de los 8 ejes técnicos) Exposición de datos personales:** newsletter sin baja ni
   doble opt-in real, sin páginas de privacidad/cookies, sin `LICENSE` ni política de derechos del
   contenido. Se captan correos y datos de terceros sin base de licitud ni mecanismo de baja.

## 5. Hallazgos por dimensión

Severidad = severidad verificada. `[C]` confirmado · `[P]` parcialmente confirmado.
Los ítems marcados **Bien resuelto** son fortalezas confirmadas (no requieren acción).

### 5.1 Arquitectura y organización — `beta`

- **[medium][P] `content` es una app agregadora que importa la capa de VISTAS de apps hermanas.**
  `content/views.py:7` y `showcase/views.py:43` hacen `from apps.agenda.views import stats`: una
  función de dominio vive en el módulo de vistas y la consumen 3 apps. `content` abre fan-out a 5
  apps; `showcase.dossier()` usa imports locales para esquivar un ciclo. → Extraer `stats()` a
  `agenda/services.py`/`selectors.py`; importar siempre modelos/servicios, nunca vistas. *(M)*
- **[low][P] El invariante del singleton `SiteProfile` no se aplica en lectura.** `load()` garantiza
  la fila pero solo se usa en el seed; el context_processor global y todas las vistas usan
  `.first()`, que devuelve `None` en una BD recién levantada → **bug latente de "sitio vacío"**
  (cabecera/pie/identidad en blanco hasta que un admin cree el perfil). → Usar `load()` (cacheado)
  como único accesor. *(S)*
- **[low][P] `showcase` mezcla identidad global + catálogo + prensa + aliados** (cohesión baja): la
  identidad del sitio no pertenece a la misma frontera que un catálogo. → Extraer `SiteProfile` a
  una app `siteconfig`. *(M)*
- **[low][C] Directorios sueltos vacíos en la raíz** (`apps/`, `templates/` fuera de `backend/`),
  no versionados; ensucian la estructura. → Borrarlos. *(S)*
- **[low][C] TinyMCE (admin) por CDN público** en runtime. → Vendorizar. *(S)* *(se cruza con
  Seguridad/Frontend)*
- **Bien resuelto [C]:** organización de modelos (`content/models.py` = **389 LOC**, no 2091 — eso
  es toda la app; el mayor archivo es `seed_demo.py` con ~863), `EditorialItem` abstracto, bitácoras
  con GFK indexado, máquina de estados centralizada, `TextChoices` consistente sin strings mágicos.

### 5.2 Seguridad — `beta`

- **[high][C] Scripts de terceros por CDN sin SRI ni self-host** (htmx en cada página, TinyMCE en el
  admin autenticado). `base.html:24`, `content/admin.py:30`; sin `integrity`, sin CSP. Un compromiso
  de unpkg/jsdelivr inyecta JS arbitrario; en TinyMCE equivale a tomar el panel editorial. →
  Auto-hospedar ambos (coherente con la font ya vendorizada) o mínimo `integrity`+`crossorigin`. *(S)*
- **[medium][C] Sin anti-abuso ni protección contra fuerza bruta.** Admin en `/admin/` sin
  throttling/`django-axes`; `submit` y `subscribe` solo con honeypot, sin límite por IP. → Añadir
  `django-axes` + `django-ratelimit`; límite de tamaño de request en Caddy. *(M)*
- **[low→medium][P] Sin Content-Security-Policy.** Buenas cabeceras (nosniff, X-Frame DENY, HSTS,
  cookies Secure) pero ninguna CSP; hay `{{ ...body|safe }}` (respaldado por nh3, pero sin red de
  seguridad). → CSP restrictiva vía `django-csp`/Caddy. *(M)*
- **[low][P] `pip-audit` no bloquea el CI y no hay Dependabot.** `ci.yml:59` usa `|| true`. → Quitar
  `|| true`; añadir Dependabot + lockfile con hashes. *(S)*
- **[low][C] Validación de adjuntos solo por extensión/tamaño, no por contenido** (magic/MIME).
  Mitigado: van a `private_storage`, solo los descarga un editor con `attachment`. → `python-magic` o
  firma de bytes; opcional antivirus. *(S)*
- **Bien resuelto [C]:** guard de producción (aborta con secretos de ejemplo), postura TLS/cookies/
  HSTS, y XSS+autorización por objeto/estado (los dos `|safe` respaldados por nh3; transiciones y
  permisos verificados en servidor, no en UI).

### 5.3 Modelo de datos y base de datos — `beta`

- **[low][P] `search_vector` se mantiene solo en `Article.save()` con un UPDATE extra:** doble
  escritura en cada guardado (incluye cambios de solo estado), y cualquier ruta que no use `save()`
  (`bulk_update`, `QuerySet.update()`, imports) deja el vector desactualizado. Además **`Poem` no
  tiene `search_vector`** → los poemas quedan fuera del buscador. → Mover a trigger PostgreSQL o
  `GeneratedField`; replicar en `Poem` si se quieren buscables. *(M)*
- **[low][P] N+1 en la grilla de integrantes:** `Contributor.members()` no hace
  `select_related('photo')` y la tarjeta accede a `m.photo.file.url` (afecta a 3 vistas). → Un
  `select_related('photo')` lo cierra. *(S)*
- **[low][C] Galería: `e.photos.first`/`e.photos.count` en la plantilla esquivan el `prefetch`**
  (`gallery.html`) → re-consulta por evento. → Usar `photos.all`/`|length`/`photos.0`. *(S)*
- **[low][C] El enlace genérico (bitácora) carece de FK a nivel de BD sobre `object_id`** (límite
  del GFK). El borrado hacia adelante sí está cubierto por `GenericRelation`; el riesgo son huérfanos
  ante SQL crudo. → Documentar el compromiso o consolidar a 2 FKs anulables con `CheckConstraint`. *(M)*
- **Bien resuelto [C]:** 3NF real, índices compuestos + GIN, `UniqueConstraint` en todos los puentes,
  `CheckConstraint` XOR, ISBN `unique`+`null`, `on_delete` coherente, y la migración expand/contract
  en 3 pasos (set-based, con `backward`) — nivel producción.

### 5.4 Pruebas y CI — `beta`

- **[medium][P] Sin medición de cobertura** (no hay `pytest-cov`, ni umbral en CI). Con 128 tests no
  se sabe qué ramas quedan sin ejercitar. → `pytest-cov` + `--cov-fail-under`. *(S)*
- **[medium][C] El buscador FTS/htmx en vivo no tiene prueba de vista** (solo ORM + markup del
  overlay). → `client.get` con query coincidente/vacía y exclusión de borradores. *(S)*
- **[medium][C] CI incompleto:** `pip-audit` no bloqueante y `manage.py check` **sin `--deploy`**
  (no corre las `security.W*`). → `pip-audit` bloqueante + `check --deploy --fail-level WARNING`. *(S)*
- **[low][P] Aserciones frágiles acopladas al copy y a bytes UTF-8** (`b'evento realizado'`,
  `b'hist\xc3\xb3rico'`). Un cambio de redacción/i18n rompe tests sin bug. → Decodificar respuestas y
  anclar a `data-testid`/`resp.context`. *(L)*
- **[low][P] Sin e2e/comportamiento para htmx/JS** (overlay, lightbox, nav se prueban por markup). →
  `pytest-playwright` para 2–3 flujos. *(L)*
- **[low][P] Sin CD ni pruebas de rendimiento/carga.** → Job de CI que construya la imagen prod +
  smoke a `/healthz/`. *(M)*
- **[low][C] Fábricas manuales duplicadas** (`n = Model.objects.count()`) frágiles ante paralelo. →
  `factory_boy` con `Sequence`. *(M)*

### 5.5 Frontend / UX / SEO / a11y — `beta`

- **[high][C] Dependencias JS por CDN sin SRI ni self-host** (htmx en cada página, TinyMCE en admin).
  → Self-host en `static/` (WhiteNoise ya los serviría con hash). *(S)*
- **[medium][C] Lightbox CSS-only (`:target`) con `aria-modal="true"` falso:** sin trampa de foco,
  sin cierre con Escape, fondo tabulable. Promesa incumplida a lectores de pantalla. → Quitar
  `role=dialog`/`aria-modal` (tratarlo como vista ampliada) **o** añadir JS progresivo (foco,
  Escape, `inert`). *(M)*
- **[low][P] Imágenes sin `width/height` ni `srcset`** → CLS y peso en móvil (poster/portada/cover
  de ancho fluido; imágenes de cuerpo al tamaño original). → Declarar dimensiones + derivados
  responsivos con Pillow. *(M)*
- **[low][P] Datos estructurados limitados** (solo JSON-LD Article; sin Organization/Event/
  BreadcrumbList ni `og:image` por defecto). → Añadirlos. *(M)*
- **[low][C] Búsqueda htmx sin estado de error** de red/servidor. → `hx-on::response-error`. *(S)*
- **[low][C] UI 100% en español sin gettext** — decisión de producto razonable (colectivo chileno);
  deuda solo si se requiere multilingüe. *(L, aceptable)*

### 5.6 Producción / DevOps / operaciones — `beta`

- **[high][C] Cero observabilidad:** `LOGGING` de una línea sin formato; sin Sentry/APM/OTel/métricas.
  → `sentry-sdk` (Django+Celery) por `SENTRY_DSN`; LOGGING JSON; uptime externo a `/healthz/`. *(M)*
- **[high][C] Imagen Docker corre como root e instala deps de test en prod.** → multi-stage, `USER`
  no-root, solo `requirements.txt` en la imagen final. *(S)*
- **[high][C] Respaldos off-site y alertas solo documentados, no implementados** (`backup.sh` al
  mismo host; ante fallo solo `echo`). Crítico para un "archivo permanente". → `restic`/`aws s3 sync`
  real + notificación de fallo (webhook/healthchecks.io). *(M)*
- **[medium][C] Sin CD, sin zero-downtime, sin rollback; migraciones manuales en el deploy** (`git
  pull; up -d --build`). → Publicar imagen por tag a un registry, desplegar por tag (rollback);
  documentar reversión + migraciones expand/contract. *(L)*
- **[medium][C] Redis `allkeys-lru` sirve de broker de Celery** → riesgo de evicción de tareas
  encoladas. → `noeviction` para broker/resultados (o Redis/db dedicada); `allkeys-lru` solo caché. *(S)*
- **[medium][C] Healthcheck solo de liveness; `worker` y `beat` sin sonda.** `/healthz/` no toca BD;
  un worker colgado o un beat que dejó de programar no se detecta. → Endpoint de readiness (BD+broker)
  + healthchecks a worker (`celery inspect ping`) y beat. *(S)*
- **[low][P] Media en volumen local** (durabilidad y escala; ata a una sola instancia). → `django-
  storages` (S3/B2) **solo si crece**; mientras, priorizar el off-site del media. *(L)*

### 5.7 Lógica de negocio / correctitud / asincronía — `beta`

- **[medium][C] El flujo editorial no se hace cumplir:** `status`/`published_at` readonly **solo**
  para no-editores → un editor fija `status='published'` a mano, saltándose `perform_transition`
  (guardas + bitácora). 5 de 9 transiciones solo se alcanzan por el desplegable. El docstring
  ("validado en servidor, nunca en la UI") no se sostiene. → `status`/`published_at` readonly
  **siempre**; enrutar todo cambio por acciones que llamen a `perform_transition`; añadir las 5
  acciones faltantes. *(M)*
- **[low][P] `publish_due_items` sin idempotencia ni locking** → doble beat/reintento duplica la
  bitácora; TOCTOU con acciones manuales. → `transaction.atomic` + `select_for_update` + re-verificar
  bajo lock; `acks_late` con reintentos. *(M)*
- **[low][C] `perform_transition` es read-check-write sin atomicidad** → carreras entre editores/
  tarea; estado y bitácora pueden divergir. → Envolver en `transaction.atomic` + `select_for_update`. *(S)*
- **[low][C] Feature de comentarios a medio construir:** modelo + moderación existen, pero sin vista
  pública, sin render, `can_moderate_comments` sin usar y **`Comment.body` sin sanear** (trampa de
  XSS almacenado si alguien conecta el render). → Completarla (saneo en `save()`, render solo
  APPROVED) o retirarla; mínimo sanear `body` ya. *(M)*
- **[low][C] `Article.save` recomputa y re-UPDATE-a el vector en cada transición** aun con
  `update_fields`. → Saltar recálculo si `update_fields` no toca el texto; UPDATE dentro de
  `atomic`. *(S)*
- **[low][P] Singleton `SiteProfile`:** `delete()` no-op es evadible por `QuerySet.delete()` (borrado
  en bloque del admin) → un editor puede borrar la identidad del sitio; `save()` fuerza `pk=1`
  (sobrescritura silenciosa). → `has_delete_permission=False` + add condicional en el admin. *(S)*
- **[low][C] Validaciones `clean()` no garantizadas en BD** (`Recording` exige file|embed_url solo
  vía form; `create()` directo lo salta). → `CheckConstraint`. *(S)*

### 5.8 Dependencias / config / mantenibilidad — `beta`

- **[high][C] BLOQUEANTE — Django 5.1 EOL:** el pin `<5.2` excluye la LTS. → `Django>=5.2,<5.3`,
  correr los 128 tests + `check --deploy`; evaluar `psycopg2-binary → psycopg3`. *(S)*
- **[medium][P] Builds no reproducibles:** rangos abiertos sin lockfile/hashes; deploy con `--build`.
  → `pip-tools`/`uv` con lock + hashes en el Dockerfile. *(M)*
- **[medium][C] Imagen de producción instala deps de test/lint** (`requirements-dev.txt`). →
  multi-stage. *(S)*
- **[medium][C] `pip-audit` no bloquea el CI** (`|| true`). → Quitarlo; `--ignore-vuln` puntual. *(S)*
- **[low][P] Sin type hints ni mypy/pyright ni pre-commit.** → Tipado incremental (models/workflow/
  permissions/views) + `mypy` con `django-stubs` (primero informativo) + pre-commit. *(L)*
- **[low][C] Docs de diseño en enlaces efímeros (claude.ai) y sin `CONTRIBUTING`.** → Portar a
  Markdown en `docs/`; añadir `CONTRIBUTING.md`. *(S)*
- **Bien resuelto [C]:** config dirigida por entorno con guard de producción, modelos bien
  factorizados, y la ausencia de API REST es **decisión de alcance correcta** (monolito
  server-rendered, sin consumidor SPA/móvil).

## 6. Ángulos fuera de los 8 ejes técnicos (crítico de completitud)

La auditoría técnica no cubre estos frentes, verificados aparte contra el repo — varios son **P0
legales** y deberían entrar en Fase 1:

- **[P0] Newsletter sin baja ni doble opt-in real (GDPR / Ley chilena 19.628).** El modelo promete
  `pending/confirmed/unsubscribed` + `token`, pero `community/views.py` admite "sin doble opt-in" y
  solo existe `novedades/` (alta). No hay confirmación ni baja → se recolectan correos sin consentimiento
  verificable ni mecanismo de baja (obligatorio en cualquier envío).
- **[P0] Sin páginas legales** (privacidad, cookies, aviso legal). El sitio capta email, datos de
  integrantes (fotos, bios) y adjuntos de terceros (manuscritos) sin política ni base de licitud.
- **[P0] Sin `LICENSE` ni política de derechos del CONTENIDO** (portadas, prensa, fotos de eventos,
  poemas) — más grave para un "archivo permanente".
- **[P1] Correo transaccional sin auditar:** SPF/DKIM/DMARC, proveedor, rebotes; de él dependen la
  newsletter y el password-reset del admin.
- **[P1] La "prueba de restauración" es autoafirmada, no automatizada** ni con RTO/RPO definidos.
- **[P1] Límites de subida solo en el form; sin `DATA_UPLOAD_MAX_*` en Django ni tope en Caddy/gunicorn.**
- **[P2] Migración del contenido REAL a producción: sin plan** (solo existe `seed_demo`).
- **[P2] Continuidad / DR / factor bus:** host único, sin runbook de recuperación total ni propiedad
  documentada de dominio/DNS/correo.
- **[P2] Coste recurrente** (VPS, correo, off-site, Sentry) no estimado — un colectivo debe poder sostenerlo.
- **[P3] a11y y Core Web Vitals evaluados por inspección, no medidos** (falta axe/Lighthouse; el
  `aria-modal` falso demuestra que la inspección deja huecos).

## 7. Hoja de ruta a producción profesional

### Fase 1 — Bloqueantes / must-fix (antes de exponer)
*Cerrar el bloqueante duro y los huecos que hacen irresponsable el lanzamiento. Trabajo contenido,
alto impacto.*

1. **Subir a Django `>=5.2,<5.3` (LTS)**, correr los 128 tests + `check --deploy`; evaluar
   `psycopg2-binary → psycopg3`. *(S · bloqueante)*
2. **Dockerfile multi-stage:** `USER` no-root con permisos en media/private_media; solo
   `requirements.txt` en la imagen final. *(S)*
3. **Integrar `sentry-sdk`** (Django+Celery) por `SENTRY_DSN` + uptime externo a `/healthz/`; LOGGING
   JSON. *(M)*
4. **Respaldo off-site real** (`restic`/`aws s3 sync`) + notificación de fallo, no un `echo`. *(M)*
5. **Hacer cumplir el workflow:** `status`/`published_at` readonly **siempre**; todo cambio por
   acciones → `perform_transition`; añadir las 5 acciones faltantes. *(M)*
6. **Corregir el bug de "sitio vacío":** `SiteProfile.load()` (cacheado) como único accesor. *(S)*
7. **Legal (P0):** baja + doble opt-in del newsletter; páginas de privacidad/cookies; `LICENSE` +
   política de derechos del contenido. *(M)*

### Fase 2 — Robustez y operación (semanas siguientes)
*De "funciona en producción" a "operación profesional".*

- Self-host de htmx y TinyMCE; **CSP** restrictiva. *(S–M)*
- CI: `pip-audit` bloqueante, `check --deploy --fail-level WARNING`, Dependabot, **lockfile con
  hashes**. *(S–M)*
- Redis `noeviction` para el broker de Celery. *(S)*
- **Idempotencia/atomicidad** en `perform_transition` y `publish_due_items` (`atomic` +
  `select_for_update` + `acks_late`). *(M)*
- Readiness endpoint (BD+broker) + healthchecks a worker/beat. *(S)*
- Anti-abuso proporcionado: `django-axes` + `django-ratelimit`; límite de request en Caddy. *(M)*
- Decidir la feature de comentarios (completar con saneo, o retirar). *(M)*
- Cobertura medida (`pytest-cov --cov-fail-under`) + test de la vista de búsqueda FTS/htmx. *(S)*
- Extender CI a **CD** (imagen por tag + rollback). *(L)*
- Correo: configurar/verificar SPF/DKIM/DMARC; automatizar la prueba de restore con RTO/RPO. *(M)*

### Fase 3 — Escala y pulido (deuda planificada)
*No urgente al tráfico actual; evitar sobre-ingeniería.*

- Extraer `stats()` a `agenda/services.py`; importar siempre servicios/modelos entre apps. *(M)*
- Extraer `SiteProfile` a `siteconfig`; proteger el singleton en el admin. *(M)*
- `search_vector` por trigger/`GeneratedField`; hacer los poemas buscables. *(M)*
- Cerrar N+1 evitables (`select_related('photo')`, caché de prefetch en la galería). *(S)*
- Imágenes: `width/height` + `srcset` (Pillow). *(M)*
- Lightbox honesto (quitar `aria-modal` o añadir JS de foco/Escape/`inert`). *(M)*
- Type hints + `mypy` (django-stubs) + pre-commit; `factory_boy`. *(L)*
- `CheckConstraint` en `Recording`; validar invariantes en `clean()` desde `save()`. *(S)*
- Portar docs de diseño a `docs/` + `CONTRIBUTING.md`; borrar los directorios raíz vacíos. *(S)*
- Datos estructurados (Organization/Event/BreadcrumbList, `og:image` por defecto). *(M)*
- **Solo si el tráfico/durabilidad lo exige:** media a object storage; e2e ligero
  (`pytest-playwright`). *(L)*

---

*Método: 8 auditores senior (uno por dimensión) leyeron el código real y produjeron hallazgos con
evidencia `archivo:línea`; un revisor adversarial verificó cada hallazgo contra el código (ninguno
refutado; varias severidades ajustadas); un sintetizador y un crítico de completitud cerraron el
informe. Calibrado a la escala real del proyecto (colectivo, tráfico bajo).*
