# Informe de auditoría de producción — Proyecto «Reseñas»

**Sistema auditado:** revista literaria como archivo permanente. Monolito Django + htmx, dockerizado (PostgreSQL, Redis, Celery, gunicorn, WhiteNoise).
**Fecha:** 2026-07-09
**Método:** revisión multi-agente por dimensiones + verificación adversarial de cada hallazgo (ver Apéndice).

---

## 1. Resumen ejecutivo

«Reseñas» es un **MVP editorial sólido y con decisiones de diseño acertadas**: máquina de estados editorial con rastro de auditoría inmutable, permisos de admin condicionados por estado, almacenamiento privado para los manuscritos, sanitización de HTML con lista blanca, defaults *fail-safe* para el secreto, y una base de tests con CI. La arquitectura de dominio es limpia y el proyecto está claramente pensado para durar.

Sin embargo, **no está listo para producción**. Los problemas no están en el modelo de dominio sino en la **capa de operación y despliegue**: no hay respaldos para un archivo que se declara permanente, PostgreSQL se publica al host con credenciales triviales, los archivos subidos (MEDIA) dejan de servirse en cuanto se apaga DEBUG, y el `docker-compose.prod.yml` no produce un sistema con TLS ni resiliencia. Son fallos silenciosos: no rompen el arranque, rompen la producción.

### Veredicto de production-readiness

> **MVP sólido — NO listo para producción sin cerrar los 3 bloqueantes de lanzamiento (High) y los riesgos operativos de la Fase 0.** El dominio es publicable; la operación no lo es todavía. Con 1–2 semanas de trabajo enfocado en despliegue, respaldos y hardening, el sistema puede lanzarse con confianza.

### Conteo por severidad (hallazgos confirmados)

| Severidad | Cantidad | Naturaleza dominante |
|---|---:|---|
| Bloqueante | 0 | — |
| **Alta** | **3** | Exposición de datos y contenido roto en producción |
| **Media** | **40** | Hardening, operabilidad, arquitectura, SEO/accesibilidad, tests |
| **Baja** | **45** | Higiene, pulido, cobertura fina, micro-optimización |
| **Total** | **88** | |

No se identificaron defectos de severidad *bloqueante* (que impidan por completo operar o corrompan datos en el camino feliz). Los tres hallazgos **Altos** son, en la práctica, los **bloqueantes de lanzamiento**: deben cerrarse antes de exponer el sitio a Internet. En el cuerpo del informe los hallazgos duplicados se fusionan; por eso el número de entradas narradas es menor que el total confirmado.

---

## 2. Riesgos principales

1. **Pérdida total del archivo por falta de respaldos.** El proyecto se define como archivo *permanente* cuyas URLs no deben romperse, pero no hay `pg_dump` ni copia de `media`/`private_media`. Un `down -v`, un fallo de disco o una migración de host borran todo de forma irreversible. Es el mayor riesgo operativo.
2. **Base de datos expuesta a Internet con credenciales adivinables.** El puerto 5432 se publica al host también en producción, con la contraseña por defecto del `.env` de ejemplo. En un host con IP pública, es acceso directo a todos los datos (correos de suscriptores, contenido, referencias a manuscritos).
3. **Contenido visual roto en producción.** MEDIA no tiene ruta de servido con DEBUG=0: todas las portadas, ilustraciones y `og:image` devuelven 404 silenciosamente.
4. **«Producción» sin TLS ni resiliencia.** El override de producción deja gunicorn en HTTP plano en :8000, sin nginx/TLS cableado, sin `restart`, y con el bind-mount que tapa la imagen probada en CI. El despliegue documentado no es reproducible ni seguro.
5. **Admin sin defensa ante fuerza bruta.** El login del panel editorial es la única superficie de autenticación y no tiene bloqueo por intentos, rate limiting ni 2FA. Un compromiso da control total del archivo.
6. **Cadena de suministro por CDN sin SRI/CSP.** TinyMCE (admin) y htmx (todo el sitio) se cargan de CDNs externos sin *integrity* ni *Content-Security-Policy*; un CDN comprometido inyecta JS con la sesión de superusuario.

---

## 3. Hallazgos por severidad

> Formato: **título** · `archivo:línea` · **Impacto** · **Recomendación** · **Esfuerzo** (S ≤ ½ día, M ≈ 1–3 días, L > 3 días).

### 3.1 Alta (bloqueantes de lanzamiento)

**A1. Sin estrategia de respaldos para Postgres, `media` y `private_media`**
`docker-compose.yml:67`
Impacto: el archivo se declara PERMANENTE, pero un borrado accidental del volumen, un fallo de disco o una migración de host provocan pérdida total e irreversible del archivo editorial y de los adjuntos privados de los envíos. No hay red de recuperación.
Recomendación: `pg_dump` diario (sidecar o cron del host) + copia de `media`/`private_media` a almacenamiento externo (S3/restic/borg) con retención y **una prueba de restauración documentada**. Montar los volúmenes en rutas del host bajo respaldo.
Esfuerzo: **M**. *(Nota: catalogado como Media en el detalle técnico, elevado aquí a bloqueante de lanzamiento por ser el mayor riesgo del proyecto.)*

**A2. PostgreSQL publicado al host con credenciales triviales, también en producción** *(fusiona 4 hallazgos: puerto 5432 expuesto, contraseña por defecto débil, `.env` de ejemplo reutilizado en prod)*
`docker-compose.yml:9,17` · `backend/config/settings.py:11`
Impacto: con IP pública sin firewall estricto, la base (correos de suscriptores, contenido, referencias a manuscritos) queda accesible desde Internet con usuario/clave adivinables. Robo o borrado total. La app ni siquiera necesita el puerto publicado: habla con `db` por la red interna de compose.
Recomendación: **no publicar 5432 en producción** (quitar `ports` de `db` en el override, o bindear a `127.0.0.1` solo en dev). Exigir `POSTGRES_PASSWORD` fuerte, sin default reutilizable, con `.env.prod` separado del de ejemplo. Añadir un guard en `settings` que rechace el arranque con contraseña/DB por defecto cuando `DEBUG=0`.
Esfuerzo: **S**.

**A3. MEDIA no se sirve en producción: toda imagen subida devuelve 404**
`backend/config/urls.py:21`
Impacto: apenas se pasa a `DEBUG=0`, todas las portadas, ilustraciones y `og:image` cargadas por el equipo quedan rotas, sin error en el arranque. WhiteNoise **no** cubre MEDIA.
Recomendación: definir explícitamente el servido de MEDIA: incluir el servicio nginx del ejemplo en `docker-compose.prod.yml` montando el volumen `media` (sirviendo `/static/` + `/media/`), o usar almacenamiento de objetos externo. Añadir un test de humo que verifique que una URL de `MediaAsset` responde 200 en configuración de producción. Documentar la limitación de WhiteNoise.
Esfuerzo: **M**.

---

### 3.2 Media

#### Seguridad y hardening

**M1. «Producción» sin TLS ni resiliencia** *(fusiona: proxy TLS no cableado, gunicorn :8000 expuesto con confianza ciega en `X-Forwarded-Proto`, override no elimina bind-mount, sin restart/healthcheck)*
`docker-compose.prod.yml:8-10` · `docker-compose.yml:29,37`
Impacto: el comando de producción documentado corre gunicorn en HTTP plano en :8000 sin nginx delante; credenciales de admin y cookies de sesión viajan en claro y se puede falsear el esquema. El bind-mount de `./backend` tapa la imagen probada en CI (deploy no reproducible; `collectstatic` escribe en el host). Sin `restart`, cualquier caída (OOM, excepción, deploy fallido) deja el sitio o la publicación programada abajo hasta intervención manual; sin healthcheck, un web que devuelve 500 se considera «up».
Recomendación: incluir nginx (o Caddy con TLS automático) en el override montando `infra/nginx/`, dejar de publicar :8000 y :5432 al host, redefinir `volumes:` de `web`/`worker`/`beat` para dejar solo datos (`media`, `private_media`), añadir `restart: unless-stopped` y un healthcheck HTTP a `web`. Configurar gunicorn `--forwarded-allow-ips` a la IP del proxy.
Esfuerzo: **M**.

**M2. Dependencias JS por CDN externo sin SRI ni CSP** *(fusiona 5 hallazgos: TinyMCE y htmx por CDN, sin SRI, sin Content-Security-Policy, fiabilidad y supply-chain)*
`backend/apps/content/admin.py:26` · `backend/templates/base.html:23`
Impacto: un CDN comprometido (o una versión flotante como `tinymce@7`) inyecta JS arbitrario que, en el admin, corre con la sesión de editores/superusuarios (robo de credenciales, publicar/borrar); en el frontend afecta a todos los lectores. Sin CSP no hay contención. Además: si el CDN falla o está bloqueado, el editor de texto y la búsqueda htmx dejan de funcionar, y cada visitante filtra su IP a un tercero.
Recomendación: **vendorizar** htmx y TinyMCE en `static/` y servirlos por WhiteNoise con hash (o, mínimo, fijar versión con `integrity`+`crossorigin`). Añadir una CSP restrictiva (django-csp), al menos para `/admin/`.
Esfuerzo: **M**.

**M3. Login del admin sin protección de fuerza bruta**
`backend/config/urls.py:12`
Impacto: la única superficie de autenticación queda expuesta a fuerza bruta y *credential stuffing*. Un compromiso otorga control total del archivo.
Recomendación: bloqueo por intentos (django-axes) + rate limiting en `/admin/login/`, contraseñas fuertes y 2FA para editores/admin. Considerar restringir `/admin/` por IP/VPN o moverlo a una ruta no obvia.
Esfuerzo: **M**.

**M4. HSTS y redirección a HTTPS desactivados por defecto**
`backend/config/settings.py:153`
Impacto: un despliegue que olvide setear las variables sirve por HTTP sin TLS forzado ni HSTS, permitiendo *downgrade*/MITM y captura de la cookie de sesión del panel en la primera visita.
Recomendación: invertir el default cuando `DEBUG=0` (activar SSL redirect y HSTS de p.ej. 31536000), permitiendo desactivarlo explícitamente. Documentar como obligatorias `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT` y `DJANGO_HSTS_SECONDS`, y fallar el arranque si `ALLOWED_HOSTS` sigue en default con `DEBUG=0`.
Esfuerzo: **S**.

**M5. Subida pública de manuscritos sin rate limiting ni CAPTCHA (solo honeypot)**
`backend/apps/submissions/views.py:17`
Impacto: un bot que ignore el honeypot puede enviar miles de archivos de 10 MB y llenar el disco de `private_media`, degradando el servicio e inundando la bandeja editorial. DoS por agotamiento de disco realista en un host modesto.
Recomendación: rate limiting por IP (django-ratelimit) en la vista de envío, opcionalmente CAPTCHA; rechazar el envío cuando no hay convocatoria abierta; monitorear el tamaño del volumen.
Esfuerzo: **M**.

**M6. Contenedor corre como root**
`backend/Dockerfile:18`
Impacto: una RCE en la app o una dependencia se ejecuta como root dentro del contenedor, ampliando el impacto de un escape; además genera archivos root en el host.
Recomendación: crear un usuario sin privilegios, `chown` de `/app` y directorios de datos, y `USER app` antes del CMD.
Esfuerzo: **M**.

**M7. Sin error tracking (Sentry) y logging no estructurado**
`backend/config/settings.py:173`
Impacto: los 500 en producción se pierden sin agregación ni alertas; nadie se entera hasta que un usuario reporta. Para un equipo pequeño, la ausencia de alertas es especialmente costosa.
Recomendación: integrar Sentry vía `SENTRY_DSN` opcional y un formatter con timestamp/logger/nivel (idealmente JSON).
Esfuerzo: **M**.

**M8. `setup_groups` reescribe permisos de grupos en cada arranque**
`backend/apps/people/management/commands/setup_groups.py:40`
Impacto: cualquier ajuste manual de permisos hecho por un admin desde el panel se revierte silenciosamente en el siguiente reinicio/deploy. Sorprende al operador y dificulta el control de acceso fino.
Recomendación: sembrado idempotente **no destructivo** (usar `permissions.add(...)` para bootstrap inicial), o correr el comando solo bajo bandera explícita en lugar de en cada arranque del entrypoint.
Esfuerzo: **S**.

**M9. Dependencias con rangos abiertos y sin lockfile/hashes**
`backend/requirements.txt:1`
Impacto: el artefacto desplegado no es reproducible; una reconstrucción puede introducir un patch/minor no probado en un archivo que debe ser estable por años, y abre superficie de supply-chain.
Recomendación: fijar versiones exactas y generar lockfile con hashes (pip-tools/uv), instalar con `--require-hashes`, verificar en CI.
Esfuerzo: **M**.

#### Corrección y modelo de datos

**M10. Regla de «artículo publicado» duplicada y sin guarda de fecha** *(fusiona: `_published()` no filtra por `published_at <= now`; queryset reimplementado en 5+ lugares sin manager)*
`backend/apps/content/views.py:20`
Impacto: se filtran al público artículos con `published_at` futura o nula, encabezando el orden por `-published_at` y emitiendo `pubDate` incorrecto/None en el RSS. Y como la regla está copiada en vistas, feed, sitemap y task, cualquier corrección debe replicarse en 5 sitios con riesgo de desincronización y fuga de contenido no publicado.
Recomendación: definir `ArticleQuerySet.published()` (con `status=PUBLISHED, published_at__lte=now, published_at__isnull=False`) + Manager, y consumirlo desde todas las superficies. Que `publish` reescriba `published_at=now` al publicar manualmente antes de la fecha programada.
Esfuerzo: **M**.

**M11. Editores pueden saltarse la máquina de estados desde el admin**
`backend/apps/content/admin.py:119`
Impacto: editar `status`/`published_at` directamente en el ModelForm pierde el rastro de auditoría (el propósito de `EditorialTransition`), permite estados inconsistentes (PUBLISHED sin `published_at`) y rompe la única fuente de verdad de las transiciones.
Recomendación: `status` y `published_at` readonly para todos en el admin; forzar los cambios solo por las acciones que llaman a `workflow.perform_transition`. Como alternativa, validar en `save_model` que todo cambio de estado pase por la máquina.
Esfuerzo: **M**.

**M12. Unicidad de email sensible a mayúsculas: suscriptores duplicados**
`backend/apps/community/models.py:63`
Impacto: `A@x.com` y `a@x.com` evaden el `unique`, produciendo suscriptores duplicados, envíos repetidos y opt-in incoherente. La garantía de unicidad no existe en la práctica.
Recomendación: normalizar a minúsculas al guardar y/o usar `CITextField` (con `CITextExtension` en migración reversible) para la columna única.
Esfuerzo: **M**.

**M13. `ReviewedWork.is_primary` sin constraint de «una sola obra principal por artículo»**
`backend/apps/content/models.py:170`
Impacto: una reseña puede terminar con dos o más obras «principales», rompiendo plantillas/lógica que asumen una (cover/canonical/SEO).
Recomendación: `UniqueConstraint(fields=["article"], condition=Q(is_primary=True), name="uniq_primary_work_per_article")`.
Esfuerzo: **S**.

#### Rendimiento

**M14. `search_vector` se recalcula con un UPDATE extra en cada `save()` y solo se puebla ahí** *(fusiona 4 hallazgos)*
`backend/apps/content/models.py:133`
Impacto: doble escritura y re-tokenización full-text del cuerpo completo en cada transición de estado y en cada corrida del beat, creando contención de escritura/vacuum en la tabla más grande. Además, cualquier escritura que no pase por `save()` (`QuerySet.update`, `bulk_create`, seeds, importaciones) deja artículos **invisibles en el buscador** sin error visible.
Recomendación: mover el mantenimiento a la base de datos con un `GeneratedField`/trigger `tsvector` (migración `RunSQL` reversible), eliminando el UPDATE en Python. Si se mantiene en `save()`, condicionarlo a que `title/subtitle/body` realmente cambiaron. Incluir `excerpt` y aplicar pesos (título=A, subtítulo=B, cuerpo=C). Añadir un comando `reindex_search` idempotente.
Esfuerzo: **M**.

**M15. Listas de editorial/autor/obra/dosier sin paginación**
`backend/apps/reviews/views.py:39`
Impacto: en un archivo que crece por años, la página de una editorial prolífica o un autor muy reseñado materializa cientos de artículos (con su prefetch) en una sola respuesta, sin tope. Degradación progresiva de latencia y memoria justo en páginas indexables y de larga vida.
Recomendación: envolver con el mismo `_paginate()` de `content/views.py` para que `_article_list.html` reciba siempre un `Page`. Aplicar también a `dossier_detail`.
Esfuerzo: **M**.

**M16. N+1 en `article_detail` sobre `reviewed_works → publisher`** *(fusiona 2)*
`backend/apps/content/views.py:37`
Impacto: N+1 clásico en la página más visitada (detalle de artículo). Con varias obras reseñadas por artículo, cada vista suma queries evitables.
Recomendación: en `article_detail` usar una consulta específica con `.prefetch_related('reviewed_works__publisher', 'tags')` (o `Prefetch` de `reviewed_work_links`) además de `authors`/`section`, en vez de reutilizar `_published()`.
Esfuerzo: **S**.

**M17. Sin framework de caché pese a tener Redis disponible**
`backend/config/settings.py:129`
Impacto: cada request —incluida la búsqueda en vivo que dispara full-text por cada pulsación— golpea Postgres sin caché. Es la mejora más barata para un sitio de lectura casi estática.
Recomendación: configurar `CACHES` con `RedisCache`, caché de fragmentos (`{% cache %}`) en nav y listados, y `cache_page` en sitemap/feed.
Esfuerzo: **M**.

#### Arquitectura

**M18. El orden de firma (byline) ignora `ArticleContributor.position`**
`backend/apps/content/models.py:88`
Impacto: en artículos con varios autores, el byline público y el RSS los muestran en orden alfabético, no editorial. En un archivo permanente es un error de atribución que persiste en todas las páginas y en el feed; el campo `position` da falsa sensación de control.
Recomendación: exponer `article.ordered_authors()` que ordene por `articlecontributor__position` (o `Prefetch` con ese `order_by`) y usarlo en plantillas y feed.
Esfuerzo: **M**.

**M19. Ningún modelo define `get_absolute_url`; construcción de URLs duplicada**
`backend/apps/content/models.py:60`
Impacto: al ser archivo permanente, cambiar un patrón de URL exige tocar feeds, sitemaps y N plantillas de forma coordinada, con alto riesgo de romper enlaces. Los editores no pueden previsualizar desde el admin.
Recomendación: añadir `get_absolute_url()` con `reverse(...)` a cada modelo enrutable; usarlo desde feeds, sitemaps y plantillas. Habilita «view on site» en el admin.
Esfuerzo: **S**.

**M20. La app `community` solo existe en el admin (feature muerta)**
`backend/apps/community/models.py:1`
Impacto: los lectores no pueden comentar ni suscribirse pese a que el modelo lo soporta y `seed_demo` crea comentarios/suscriptores. Da falsa impresión de disponibilidad y la moderación en el admin no tiene salida pública.
Recomendación: decidir explícitamente: (a) completar la capa pública (vistas+forms de comentario con moderación y alta de newsletter, render de comentarios aprobados en `article_detail`), o (b) documentarlo como fuera de alcance y no cablearlo.
Esfuerzo: **L**.

**M21. Sin `AUTH_USER_MODEL` propio en un proyecto pensado como archivo permanente**
`backend/config/settings.py:25`
Impacto: la recomendación oficial de Django es fijar un User custom al inicio; migrar más tarde, con datos en producción y FKs pobladas (owner, actor, reviewer, uploaded_by), es doloroso y arriesgado. El costo de no hacerlo solo crece.
Recomendación: mientras la base está joven, definir un `CustomUser` (aunque herede vacío de `AbstractUser`) y `AUTH_USER_MODEL`. Si se decide no hacerlo, documentarlo como decisión consciente.
Esfuerzo: **M**.

#### Frontend, SEO y accesibilidad

**M22. Sin páginas 404/500 propias**
`backend/config/urls.py:11`
Impacto: cualquier enlace antiguo/borrado o un fallo puntual muestra al lector y al crawler la página gris de Django, sin identidad de la revista ni ruta de recuperación, en un sitio cuyo objetivo es que las URLs no se rompan.
Recomendación: crear `templates/404.html` y `500.html` que extiendan `base.html` (con nav y buscador); Django los usa automáticamente. Añadir un test del 404. Considerar 403/400.
Esfuerzo: **S**.

**M23. El buscador rompe sin JS y genera URLs `?q=` duplicadas indexables**
`backend/templates/base.html:30`
Impacto: sin JS (o si htmx no carga), enviar el buscador lleva a la portada sin resultados: no degrada. Y los crawlers descubren infinitas variantes de la home (`?q=`, tracking) con contenido idéntico, provocando contenido duplicado y desperdicio de crawl budget.
Recomendación: apuntar el form a una página de resultados que procese `q` (o que `home()` maneje `q`). Emitir el canonical sin querystring (`request.path` + host) para que cada recurso tenga un único canónico limpio.
Esfuerzo: **M**.

**M24. `cover_image` nunca se muestra pese a exigir `alt_text` obligatorio**
`backend/templates/content/article_detail.html:58`
Impacto: se sube y describe una portada que jamás aparece; el listado y el detalle quedan sin apoyo visual y el `alt_text` exigido no cumple función.
Recomendación: renderizar `cover_image` como `<figure><img alt="{{ ... }}" loading="lazy" width height>` en `article_detail.html` (y miniatura en `_article_card.html`), con caption/credit si existen.
Esfuerzo: **M**.

**M25. Falta `og:image` por defecto**
`backend/templates/base.html:15`
Impacto: compartir cualquier URL sin portada (home, secciones) produce una tarjeta sin imagen, reduciendo el CTR de un contenido que vive de la difusión.
Recomendación: añadir una imagen de marca por defecto (1200×630) en `static/` y emitirla como `og:image` en `base.html`, que `article_detail` sobrescribe cuando hay portada.
Esfuerzo: **S**.

**M26. Resultados del buscador htmx sin `aria-live`**
`backend/templates/base.html:49`
Impacto: los lectores de pantalla no reciben feedback de que aparecieron N resultados; el buscador en vivo es invisible para ese usuario.
Recomendación: `aria-live="polite"`, `aria-atomic="true"` y `role="region"` con `aria-label` en `#search-results`; opcionalmente anunciar el recuento.
Esfuerzo: **S**.

#### Datos y privacidad

**M27. Archivos en disco nunca se borran al eliminar `Submission`/`MediaAsset`**
`backend/apps/submissions/models.py:49`
Impacto: manuscritos de autores que pidieron retirar su envío persisten en `private_media` pese a borrar el registro (riesgo legal/confianza); los volúmenes crecen sin cota, complicando respaldos.
Recomendación: limpieza de archivos al borrar/reemplazar (señales `post_delete`/`pre_save` que llamen a `storage.delete`, o `django-cleanup`). Incluir `private_media` en la política de retención y documentar el flujo de «retiro de envío».
Esfuerzo: **M**.

#### Tests y CI

**M28. CI no ejecuta linter, formato, tipos, cobertura ni escaneo de dependencias**
`.github/workflows/ci.yml:47`
Impacto: regresiones de estilo/tipos entran sin freno; una dependencia con CVE (Django, Pillow, psycopg2, nh3 manejan HTML/imágenes/SQL) nunca se detecta; el equipo no ve qué queda sin cubrir.
Recomendación: añadir `ruff check` + `ruff format --check`, `pytest --cov=apps --cov-fail-under=<n>` y `pip-audit`. Opcionalmente `mypy` laxo.
Esfuerzo: **S**.

**M29. Sanitización de `Page.body` sin test aunque se renderiza con `|safe`**
`backend/apps/content/models.py:248`
Impacto: una regresión que rompa `clean_html` en `Page.save` abre XSS almacenado en páginas institucionales, sin que ningún test lo detecte.
Recomendación: replicar los tests de sanitización de `Article` para `Page` (`<script>`, `on*`, `href="javascript:"`) y verificar que el formato permitido se conserva.
Esfuerzo: **S**.

**M30. Moderación de comentarios y borde XOR sin cobertura**
`backend/apps/community/admin.py:14`
Impacto: la moderación es el único control anti-spam del contenido comunitario; un cambio en las acciones o en el `CheckConstraint` podría dejar pasar comentarios inconsistentes sin señal.
Recomendación: tests de que cada acción de `CommentAdmin` actualiza el `status` esperado, y de que crear `Comment` con `user` y `guest_name` a la vez lanza `IntegrityError`.
Esfuerzo: **S**.

**M31. `publish_due_articles`: aserto débil, sin caso negativo ni verificación del rastro**
`backend/tests/test_workflow.py:73`
Impacto: la única lógica corrida por Celery Beat cada minuto queda con cobertura de solo-camino-feliz; un bug de límite (publicar antes de tiempo o publicar borradores) pasaría los tests.
Recomendación: `assert published == 1`; añadir un SCHEDULED con `published_at` futura y asertar que sigue SCHEDULED; asertar la `EditorialTransition` creada.
Esfuerzo: **S**.

---

### 3.3 Baja

Agrupadas por tema; todas de bajo impacto a la escala actual, valiosas como higiene.

**Corrección / workflow**
- **`schedule` no fija ni exige `published_at`** — `workflow.py:60` — un artículo programado sin fecha nunca se publica ni es visible, sin error. Exigir `published_at` futura como precondición. **S**
- **`publish_due_articles` no es idempotente/atómico** — `tasks.py:10` — carga-y-guarda sin bloqueo puede duplicar publicaciones y filas de auditoría. Usar `update()` condicional atómico o `select_for_update(skip_locked=True)`. **S**
- **`perform_transition` no envuelve estado + auditoría en transacción** — `workflow.py:59` — posible divergencia entre estado e historial inmutable. `transaction.atomic()`. **S**
- **La task duplica la lógica de `publish` en vez de usar el workflow** — `tasks.py:15` — la publicación automática divergirá si se añaden side-effects al workflow. Llamar a `perform_transition`. **S**

**Modelo de datos**
- **`NewsletterSubscriber.token`: default vacío, sin unique ni índice** — `community/models.py:67` — el doble opt-in puede confirmar/dar de baja al suscriptor equivocado. Token obligatorio, único, indexado, generado con `secrets.token_urlsafe`; nunca buscar por token vacío. **S**
- **`Comment.parent` con CASCADE** — `community/models.py:17` — moderar un comentario borra el subárbol completo; sin garantía de mismo artículo. `SET_NULL` o borrado lógico + constraint de artículo compartido. **M**
- **`CheckConstraint` XOR no cubre `guest_email`** — `community/models.py:41` — datos de invitado incoherentes; extender la rama y normalizar en `save`/`clean`. **S**
- **Falta índice en `Article.type`** — `models.py:66` — listados/feeds por tipo escanean la tabla. Índice compuesto `(type, status, -published_at)`. **S**
- **Orden por defecto usa desempate `created_at` no cubierto por el índice** — `models.py:117` — extender a `(status, -published_at, -created_at)` o aceptar el costo. **S**

**Seguridad (residual)**
- **Validación de adjuntos solo por extensión** *(fusiona 2)* — `submissions/forms.py:41` — riesgo acotado (storage privado, `as_attachment`, `nosniff`); complementar con magic bytes y tratar adjuntos como no confiables. **M**
- **Redis sin autenticación** — `settings.py:130` — bajo mientras el puerto no se exponga; definir `requirepass` para producción y nunca publicar 6379. **S**
- **Rotar `SECRET_KEY` invalida todas las sesiones** — `settings.py:12` — soportar `SECRET_KEY_FALLBACKS` para rotación con solapamiento. **S**
- **Comentario obsoleto «sanitizar (pendiente)» junto a `|safe`** *(fusiona 2)* — `article_detail.html:57` — no es vuln (la sanitización está en el modelo), pero induce a error. Actualizar el comentario; considerar re-sanear datos previos a nh3. **S**

**Rendimiento**
- **Buscador en vivo sobre-consulta** — `views.py:103` — prefetch/select_related que el parcial descarta, por cada pulsación. Queryset mínimo con `.only(...)`. **S**
- **gunicorn sin `--max-requests`/`--timeout`/access-log** *(fusiona 2)* — `Dockerfile:19`, `docker-compose.prod.yml:10` — sin reciclado de workers ni protección ante requests colgadas. Añadir flags y parametrizar `--workers`. **S**
- **htmx/TinyMCE desde CDN en vez de WhiteNoise** *(ver M2)* — `base.html:23` — latencia y punto único de fallo externo. Vendorizar. **S**
- **`CONN_MAX_AGE=60` sin `CONN_HEALTH_CHECKS`** — `settings.py:85` — 500 esporádicos tras reinicios de la BD. `'CONN_HEALTH_CHECKS': True`. **S**

**Arquitectura / operación**
- **`Page.status` reutiliza `DossierStatus`** — `models.py:234` — acoplamiento oculto entre modelos no relacionados. `PublishStatus` compartido y neutral. **S**
- **`USE_I18N=True` sin LocaleMiddleware ni gettext, texto hardcodeado** — `settings.py:100` — lo peor de ambos mundos. Decidir: `USE_I18N=False` (monolingüe) o instrumentar i18n de verdad. **S**
- **`celerybeat-schedule` versionado** — `backend/celerybeat-schedule:1` — artefacto de runtime en repo/imagen. Borrar y agregar a `.gitignore`/`.dockerignore`. **S**
- **`entrypoint.sh` corre `migrate` incondicional en cada arranque** — `entrypoint.sh:5` — riesgo de 500/carreras al escalar; migraciones destructivas automáticas. Separar migraciones como job de despliegue; adoptar expand/contract. **M**
- **Override no quita el bind-mount de código** *(ver M1)* — `docker-compose.prod.yml:9`. **S**
- **Imagen de producción con deps de test, sin multi-stage** — `Dockerfile:10` — superficie e imagen mayores. Multi-stage o build-arg. **S**
- **`.dockerignore` en la raíz no aplica al contexto `./backend`** — `.dockerignore:1` — falsa protección. Mover/duplicar a `backend/.dockerignore`. **S**
- **Redis sin persistencia ni `maxmemory`** — `docker-compose.yml:20` — pérdida silenciosa de tareas al reiniciar/OOM; sin cota de RAM. Fijar `maxmemory`+política (o `appendonly`) y hacer tareas idempotentes. **S**

**SEO / accesibilidad / frontend**
- **JSON-LD de artículo incompleto y ausente en el resto** — `article_detail.html:16` — sin image/logo/breadcrumb ni WebSite+Organization. Completar y añadir en `base.html`. **M**
- **Solo `ArticleSitemap` declara `lastmod`** — `sitemaps.py:23` — sin señal de frescura para secciones/dosieres/páginas/obras. Añadir `lastmod`. **S**
- **Sin enlace «saltar al contenido»** — `base.html:26` — WCAG 2.4.1 ausente. `<a class="skip" href="#main">` visible-on-focus. **S**
- **Buscador sin longitud mínima y con desplazamiento (CLS)** — `base.html:31` — queries de 1 carácter y salto visual. Mínimo `len>=2` y panel superpuesto. **S**
- **Un único RSS global, sin feeds por sección** — `feeds.py:7` — pérdida de fidelización. Feed parametrizado por slug de sección. **M**

**Tests (cobertura fina)**
- **Feed RSS sin test** — `feeds.py:12` — riesgo de fuga de borradores o caída silenciosa. GET a `reverse('feed')`, verificar 200/XML, publicado presente, borrador ausente. **S**
- **`sitemap.xml` sin test** — `sitemaps.py:13` — riesgo de 500 total o inclusión de borradores. Test de integración. **S**
- **`seed_demo` sin guard de producción ni test de idempotencia** — `seed_demo.py:38` — inyectar contenido falso en el archivo permanente. `CommandError` si no DEBUG salvo `--force`; test de doble corrida. **S**
- **`--reuse-db` sin recreación ante cambios de esquema** — `pytest.ini:6` — flaky local vs CI. Documentar `--create-db` tras migraciones. **S**
- **`robots.txt` y context processor de nav sin test** — `views.py:116` — superficies globales. Test de `Disallow: /admin/` y de nav. **S**
- **Vista de búsqueda htmx sin test de vista** — `views.py:97` — orden por `-rank`, filtro de publicados y parcial sin cubrir. GET con `?q=`. **S**
- **Asserts sobre bytes UTF-8 crudos** — `test_views.py:24` — frágiles ante cambios de plantilla. Decodificar o asertar sobre `resp.context`. **S**

---

## 4. Lo que ya está sólido

El proyecto tiene fundamentos de calidad que conviene reconocer y preservar:

- **Máquina de estados editorial con rastro de auditoría inmutable** (`EditorialTransition`): buena separación de servicio (`workflow.perform_transition`) del modelo. El problema no es el diseño, sino que un par de rutas lo esquivan.
- **Permisos de admin condicionados por estado**: el control de quién puede hacer qué según el estado del artículo está bien planteado.
- **Almacenamiento privado para los manuscritos**: los adjuntos van a `private_media` y solo se sirven a editores autenticados, con `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff`. La postura por defecto es correcta.
- **Sanitización de HTML con lista blanca (nh3)** en `Article.save`/`Page.save`, y **búsqueda full-text parametrizada** (`SearchQuery`), sin concatenación de SQL. La superficie de XSS/inyección está bien cubierta en el camino principal.
- **Defaults *fail-safe* para `SECRET_KEY`**: el arranque falla si no se provee en producción; el patrón correcto que solo falta replicar en `ALLOWED_HOSTS` y en la contraseña de la BD.
- **Base de tests + CI ya en marcha**: existe la infraestructura; se trata de ampliar cobertura y añadir linters/escaneo, no de partir de cero.
- **SEO y sindicación presentes**: sitemap, RSS, JSON-LD y honeypot anti-spam ya existen; los hallazgos son de completitud, no de ausencia total.
- **Arquitectura de dominio limpia y orientada a durar**: modelos bien nombrados, timestamps disponibles, separación por apps. La base es la correcta para un archivo permanente.

---

## 5. Roadmap priorizado a producción

### Fase 0 — Bloqueantes de lanzamiento (cerrar ANTES de exponer a Internet) · ~3–5 días
Objetivo: que ningún dato se pierda ni se exponga, y que el contenido se vea.
1. **Respaldos automatizados + prueba de restauración** (A1) · M
2. **No publicar 5432/8000/6379; contraseña fuerte de BD; `.env.prod` separado; guard con `DEBUG=0`** (A2, parte de M1) · S
3. **Servir MEDIA en producción** vía nginx + test de humo (A3) · M
4. **Cablear la cadena TLS/proxy real**: nginx con TLS, `restart: unless-stopped`, healthcheck, quitar bind-mount (M1) · M
5. **Forzar HTTPS/HSTS y `ALLOWED_HOSTS`/`CSRF` obligatorios con `DEBUG=0`** (M4) · S

### Fase 1 — Hardening y operabilidad (primeras 1–2 semanas post-lanzamiento) · ~1 semana
6. **Protección de fuerza bruta + 2FA en el admin** (M3) · M
7. **SRI/vendorizado + CSP para CDN** (M2) · M
8. **Rate limiting en subida de manuscritos** (M5) · M
9. **Sentry + logging estructurado** (M7) · M
10. **Contenedor no-root; multi-stage; migraciones fuera del entrypoint** (M6, deps varias) · M
11. **Lockfile con hashes + `pip-audit`/ruff/cobertura en CI** (M9, M28) · S–M
12. **Limpieza de archivos huérfanos + política de retención** (M27) · M

### Fase 2 — Robustez del dominio y datos · ~1 semana
13. **`ArticleQuerySet.published()` + guarda de fecha** (M10) · M
14. **Bloquear cambios de estado fuera del workflow en el admin; transacciones e idempotencia en task** (M11 + bajos de workflow) · M
15. **Constraints y unicidad**: email case-insensitive (M12), obra principal única (M13), token de newsletter, XOR de comentarios · S–M
16. **`search_vector` por trigger/`GeneratedField` + `reindex_search`** (M14) · M
17. **Paginación en listas de detalle + N+1 + caché Redis** (M15, M16, M17) · M
18. **Byline por `position`; `get_absolute_url`; `CustomUser`** (M18, M19, M21) · S–M

### Fase 3 — Experiencia pública, SEO y cobertura · ~1 semana
19. **Páginas 404/500; buscador que degrade + canonical limpio; `og:image` por defecto; render de `cover_image`; `aria-live` y skip-link** (M22–M26 + a11y bajos) · S–M
20. **Decisión sobre la app `community`** (completar o documentar como fuera de alcance) (M20) · L
21. **Ampliar tests**: sanitización de `Page`, moderación, task, feed/sitemap, búsqueda, seed idempotente (M29–M31 + bajos de test) · S c/u
22. **Pulido**: JSON-LD completo, `lastmod`, feeds por sección, i18n coherente, higiene de repo/imagen · S–M

> **Regla de oro:** la Fase 0 es no negociable para un lanzamiento público. Las Fases 1–3 pueden solaparse según capacidad del equipo, pero la Fase 1 debería completarse dentro del primer mes de operación.

---

## 6. Apéndice — Dimensiones auditadas y método

### Dimensiones cubiertas
- **Corrección** (máquina de estados, publicación programada, idempotencia, atomicidad).
- **Seguridad** (exposición de puertos, credenciales, TLS/HSTS, supply-chain/CDN, fuerza bruta, subida de archivos, sanitización).
- **Modelo de datos** (constraints, unicidad, índices, integridad referencial, full-text).
- **Arquitectura Django** (managers/querysets, `get_absolute_url`, User custom, capas completas, acoplamiento).
- **Rendimiento** (N+1, paginación, caché, escrituras redundantes, tuning de gunicorn).
- **DevOps / operación** (respaldos, restart/healthcheck, proxy/TLS, root, reproducibilidad, observabilidad).
- **Testing / CI** (cobertura de superficies públicas, linters, escaneo de dependencias, robustez de la suite).
- **Frontend / SEO / accesibilidad** (páginas de error, canonical, Open Graph, JSON-LD, WCAG, degradación sin JS).
- **Privacidad** (retención y borrado de manuscritos, unicidad de suscriptores, doble opt-in).

### Método
Revisión **multi-agente**: agentes especializados por dimensión inspeccionaron el código fuente, la configuración de Docker/compose, los settings de Django, los templates y la suite de tests, generando hallazgos candidatos con `archivo:línea`, impacto y recomendación.

Cada candidato pasó por **verificación adversarial**: un segundo pase intentó refutar el hallazgo (¿existe una mitigación que el primer agente pasó por alto? ¿el impacto está sobreestimado a esta escala?). Solo los hallazgos que sobrevivieron a la refutación se marcaron como CONFIRMADOS; varios se reclasificaron a la baja al reconocer mitigaciones reales (p.ej. storage privado + `nosniff` que acotan la validación por extensión, o la sanitización correcta que desmiente el comentario «pendiente»).

**Convención de severidad:** Alta = exposición de datos o contenido roto en producción; Media = hardening, operabilidad, arquitectura o cobertura con impacto tangible; Baja = higiene, pulido o micro-optimización con impacto acotado a la escala actual. El conteo refleja los **88 hallazgos confirmados**; en el cuerpo del informe los duplicados se fusionan para facilitar la ejecución, por lo que el número de entradas narradas es menor que el total.
