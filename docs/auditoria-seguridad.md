# Auditoría de seguridad — «Reseñas»

> Auditoría independiente desde la perspectiva de un **Ingeniero en Ciberseguridad Senior**, ejecutada con orquestación multi-agente: 10 auditores en paralelo por dimensión (authz, inyección, XSS/CSP, subidas, capa web, secretos, infraestructura, cadena de suministro, DoS, privacidad), **refutación adversarial** de cada hallazgo por un revisor escéptico independiente que abre el código citado y busca activamente la mitigación, y un **crítico de completitud** sobre las superficies que ningún finder tocó. En paralelo, verificación manual con PoC ejecutable de los puntos críticos.

- **Fecha:** 2026-07-29
- **Alcance:** todo el repositorio — 9 apps Django, `config/`, plantillas, `infra/` (Caddy, respaldos), los tres `docker-compose`, el `Dockerfile`, el CI y **el historial completo de git**.
- **Esfuerzo:** 21 agentes, 678 lecturas/comprobaciones, 1,77 M tokens.
- **Hallazgos:** 99 brutos → **22 refutados** en la verificación adversarial → 82 confirmados → **67 tras deduplicar** entre dimensiones.
- **Reparto final:** **1 alto, 7 medios, 29 bajos, 30 informativos.** Sin críticos.
- **Controles verificados como correctos:** 149.

## Veredicto

**No existe ninguna vía de compromiso por parte de un atacante anónimo de internet.** Se buscó explícitamente y no se encontró: sin bypass de autenticación, sin inyección SQL, sin SSRF, sin XXE, sin deserialización insegura, sin `csrf_exempt`, sin fuga de contenido no publicado en las vistas públicas (una sola excepción, S-05), sin secretos en el historial de git.

La postura es **sólida en todo lo que se diseñó deliberadamente** y **débil en las costuras**: los dos puntos donde el tráfico *no pasa por Django* (`/media/` servido por Caddy, `/static/` por WhiteNoise) y el punto donde el operador *sigue la documentación al pie de la letra* y aun así queda inseguro.

Hay **una escalada de privilegios real y demostrada**: desde el rol `editor` —que el proyecto crea explícitamente como cuenta *no* superusuaria— se llega a superusuario. Rompe la garantía del modelo de permisos de Django, según la cual un staff sin `auth.change_user` no puede promocionarse. Es el único hallazgo que condiciona el despliegue.

**Madurez de seguridad: alta.** Tres auditorías previas absorbidas, CI con cinco compuertas (pip-audit bloqueante, gitleaks, bandit, trivy, `check --deploy`), CSP propia con nonce, saneo `nh3`, anti-fuerza-bruta, rate-limit con IP resuelta tras proxy, almacenamiento privado para envíos, imagen de producción no-root con `--require-hashes`. Las debilidades no son de ignorancia sino de **cobertura**: los controles existen pero no alcanzan a los caminos que rodean a Django.

## Nota de calibración (leer antes de discutir severidades)

El hallazgo **S-01 fue puntuado *low* por los diez verificadores automáticos**, en las cinco dimensiones donde apareció. **Lo elevo a alto por decisión propia.** El motivo del desacuerdo es una regla que yo mismo introduje en el prompt de refutación —«si el atacante necesita ser staff, la severidad casi nunca es alta»— y que los verificadores aplicaron mecánicamente al rol `editor`.

Esa regla es correcta para un superusuario y **errónea aquí**: `editor` es un rol de confianza intermedia que `setup_groups.py` crea precisamente para *no* dar acceso total, y el modelo de permisos de Django está construido sobre la premisa de que un staff sin `auth.change_user` no puede promocionarse a superusuario. Un hallazgo que rompe esa frontera es una escalada de privilegios, no un endurecimiento pendiente. Se documenta el desacuerdo para que quien revise pueda juzgarlo por sí mismo.

## Estado por dimensión

| Dimensión | Confirmados | Estado |
|---|---|---|
| authz | 4 | **La dimensión más fuerte del proyecto.** La máquina de estados editorial (`workflow.py`) valida transiciones en el servidor, revalida bajo `select_for_update()` cerrando la carrera entre editores, mantiene `status` como readonly *siempre* (también para editores) y deja bitácora inmutable. `EditorialItemAdmin` filtra el queryset por dueño y compone permisos por objeto y estado. Los hallazgos son de refuerzo (parámetros de axes, permisos que no componen con los del modelo), no de ruptura. |
| injection | 3 | Sin inyección SQL: la búsqueda usa `SearchQuery` parametrizado, no hay `raw()`/`extra()`/`cursor.execute` con entrada de usuario, y las funciones de trigger plpgsql no concatenan entrada. Sin inyección de comandos: los scripts shell usan `set -eu` y no interpolan entrada externa. Un 500 real por byte NUL en la búsqueda. |
| xss | 5 | `nh3` con lista blanca estricta, aplicado en `save()` de los dos únicos modelos renderizados con `\|safe`. CSP propia con nonce por petición y `object-src`/`base-uri`/`form-action`/`frame-ancestors` correctos. El problema no es la CSP sino **dónde no llega**: ni a `/static/` ni a `/media/`. |
| uploads | 9 | El formulario público de envíos es ejemplar (extensión + tamaño + bytes mágicos, a almacenamiento privado). El admin es lo contrario: **cero validadores en todo el proyecto**. `ImageField` se salva por el validador que Django trae de serie; los tres `FileField` no. |
| websec | 1 | Cabeceras correctas, CSRF forzado, `SameSite` heredando el `Lax` seguro de Django 5.2, open redirect ya cerrado en una auditoría previa, `ALLOWED_HOSTS` validado. Prácticamente limpia: de 8 candidatos, 7 fueron refutados. |
| secrets | 9 | Historial de git limpio (solo placeholders y valores de prueba de CI). El guard de arranque es una buena idea **mal implementada**: compara contra los centinelas de desarrollo, no contra los de la plantilla de producción. |
| infra | 15 | Imagen de producción endurecida (no-root, `--require-hashes`, multi-stage), red interna sin puertos publicados salvo el proxy, Redis autenticado obligatorio en el compose de producción. Las carencias son de aislamiento (sin límites de recursos ni `cap_drop`), de higiene del borde (sin cabeceras en `/media/`, sin timeouts) y de operación (respaldos legibles, restauración sin confirmación). |
| supply | 11 | Lockfiles con `--generate-hashes`, pip-audit **bloqueante**, dependabot en tres ecosistemas. **Cero CVEs** en las dependencias fijadas (verificado contra OSV). El punto ciego real son las dos librerías JS vendorizadas, que ningún escáner ve. |
| dos | 8 | Rate-limit correcto donde existe (con la IP bien resuelta tras Caddy), pero solo cubre 2 de los endpoints públicos. La búsqueda —el endpoint más caro— no tiene ninguno. |
| privacy | 12 | Doble opt-in, minimización deliberada (lista latente), purga programada, `send_default_pii=False`, sin analítica de terceros. Las brechas son de ciclo de vida del dato: lo que *no* se borra nunca y lo que se registra sin querer. |

---

## Hallazgo ALTO

### S-01. XSS almacenado en `/media/` → escalada de `editor` a superusuario

- **Dimensiones:** uploads · xss · websec · infra · injection (5 hallazgos fusionados)
- **CWE-434** (Unrestricted Upload of File with Dangerous Type) · **A01:2021 Broken Access Control**
- **Ubicación:** `backend/apps/media/models.py:138` + `infra/caddy/Caddyfile:17-20`

La cadena tiene dos mitades independientes, ambas **verificadas con PoC ejecutable**.

**Mitad 1 — se puede subir HTML arbitrario.** `grep -rn "validators" backend/apps` no devuelve **ninguna** coincidencia: no existe un solo validador en el proyecto. Ejecutado contra el `ModelForm` real del admin:

```text
Recording.file  acepta evil.html -> True    (contenido: <script>alert(document.domain)</script>)
MediaAsset.file acepta evil.html -> False   ("Envíe una imagen válida")
```

`MediaAsset` se salva porque `forms.ImageField` trae `validate_image_file_extension` de serie; `models.FileField` **no hereda ningún validador** (comprobado en la imagen real: `FileField.default_validators == []`). Los tres campos sin validar son `Recording.file`, `showcase.Publication.pdf` y `SiteProfile.dossier_pdf`.

**Mitad 2 — Caddy lo sirve ejecutable y sin ninguna defensa.** Levantando un Caddy efímero con el Caddyfile del proyecto y pidiendo el fichero:

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8     <- ejecutable, en el origen del sitio
                                           <- sin X-Content-Type-Options
                                           <- sin Content-Security-Policy
                                           <- sin Content-Disposition
```

El bloque `handle_path /media/*` cortocircuita a Django: **el middleware `ContentSecurityPolicyMiddleware` y el `SecurityMiddleware` nunca ven estas respuestas.** La CSP restrictiva del proyecto no cubre nada aquí.

- **Cadena de explotación:** `setup_groups.py:10` incluye `media` en `EDITOR_APPS`, así que el grupo `editor` obtiene `media.add_recording`. Un editor sube `evil.html` como fichero de un registro, obtiene la URL pública `/media/recordings/AAAA/MM/evil.html` y la hace visitar a un administrador (o la enlaza desde la propia ficha del registro). El JS se ejecuta en el origen del sitio y sin CSP. La cookie `sessionid` es `HttpOnly`, lo que impide robarla, pero **no impide** hacer `fetch('/admin/auth/user/add/')` con credenciales, leer el token CSRF del DOM y crear un superusuario.
- **Impacto:** ruptura de la frontera de privilegios `editor` → superusuario, es decir, control total del panel editorial, de la base de datos vía admin y de los adjuntos privados de los envíos. Además, cualquiera con `showcase.*` (grupo admin) tiene el mismo primitivo por los dos PDF.
- **Corrección (dos capas, ambas necesarias):**
  1. **Aplicación:** `validators=[FileExtensionValidator(allowed_extensions=[...])]` en los tres `FileField` (audio/vídeo para `Recording.file`, solo `pdf` para los dos de showcase), más comprobación de bytes mágicos reutilizando el enfoque ya presente en `backend/apps/submissions/forms.py:11-30`.
  2. **Borde:** dentro de `handle_path /media/*` del Caddyfile, emitir `header { X-Content-Type-Options nosniff; Content-Security-Policy "default-src 'none'; sandbox"; Referrer-Policy no-referrer; X-Frame-Options DENY }`. Esta capa es la que además **protege lo ya subido**, sin migración de datos.
  3. **Regresión:** extender el job `prod-runtime` del CI para afirmar esas cabeceras sobre una URL real de `/media/` servida por Caddy.

---

## Hallazgos MEDIOS

### S-02. El guard de producción no detecta los placeholders de su propia plantilla

- **Dimensión:** secrets · **CWE-1188** · **A05:2021 Security Misconfiguration**
- **Ubicación:** `backend/config/settings.py:33-51`

El guard compara por **igualdad** contra los centinelas de *desarrollo* (`_INSECURE_SECRET = "dev-insecure-change-me"`, `_INSECURE_DB_PASSWORD = "resenas"`). Pero la plantilla de producción no usa esos valores, sino `CAMBIA-ESTO-por-una-clave-larga-y-secreta` y `CAMBIA-ESTO-por-una-contrasena-fuerte`.

El operador que sigue `docs/despliegue.md` copia `.env.prod.example` y cambia lo que rompe visiblemente el sitio (dominio, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`). Los tres secretos se quedan en `CAMBIA-ESTO-…`, `${REDIS_PASSWORD:?}` del compose se satisface porque la variable está definida y no vacía, y **el stack arranca sin una sola advertencia** — mientras la propia plantilla le asegura en su línea 6 que «el arranque SE RECHAZA si siguen en su valor de ejemplo».

- **Impacto:** `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` y `REDIS_PASSWORD` de ese despliegue son valores públicos del repositorio. La explotación remota inmediata está acotada (las sesiones son de BD, no firmadas; `db` y `redis` no publican puertos), pero el control de seguridad más visible del proyecto falla exactamente en el camino que la documentación prescribe, y deja la puerta abierta a escalada total ante cualquier movimiento lateral. El peor caso posible en términos de falsa confianza operativa.
- **Corrección:** validación positiva en vez de comparación con centinelas — rechazar cualquier valor que contenga `CAMBIA-ESTO`, `change-me`, `example`; añadir `REDIS_PASSWORD` al guard; validar longitud/entropía de la clave con los mismos umbrales que `security.W009` (`len < 50` o `len(set(...)) < 5`); rechazar `*` en `ALLOWED_HOSTS` y orígenes `http://` en `CSRF_TRUSTED_ORIGINS`. Complementariamente, dejar los secretos **vacíos** en la plantilla, de modo que el chequeo de valor vacío ya los atrape. Test: cargar settings con cada valor de `.env.prod.example` y afirmar `ImproperlyConfigured`.

### S-03. `seed_demo` crea cuentas staff con contraseña publicada y sin guarda de producción

- **Dimensión:** uploads/authz · **CWE-798** · **A07:2021 Identification and Authentication Failures**
- **Ubicación:** `backend/apps/content/management/commands/seed_demo.py:645-648`

`_user()` crea `editora` y `autor1` con `is_staff=True` y `user.set_password("demo12345")`. El `handle()` **no comprueba `settings.DEBUG`** ni exige ninguna bandera, y el comando se anuncia como «Carga datos de demostración (idempotente)», lo que invita a ejecutarlo para poblar un entorno.

- **Impacto:** si se ejecuta alguna vez contra producción, quedan dos cuentas de panel con una contraseña que está en el repositorio. `editora` pertenece al grupo `editor`, así que **encadena directamente con S-01** hasta superusuario. django-axes no aporta defensa alguna: la contraseña es *conocida*, basta un único intento y el límite de 5 fallos nunca se toca.
- **Corrección:** abortar al inicio de `handle()` con `CommandError` si `not settings.DEBUG`, salvo `--force` explícito; y generar la contraseña con `get_random_string()` imprimiéndola por stdout en vez de fijarla en el código. Test que afirme el fallo con `DEBUG=0`.

### S-04. La búsqueda FTS no acota la entrada, no lleva `LIMIT` en SQL ni rate limit, y revienta con un byte NUL

- **Dimensión:** dos · injection · **CWE-770 / CWE-20** · **A04:2021 Insecure Design**
- **Ubicación:** `backend/apps/content/views.py:170-211`

Tres defectos en el endpoint público más caro del sitio, que además es el único sin protección anti-abuso (`@ratelimit` solo existe en `community/views.py:41` y `submissions/views.py:19`):

1. **Sin `LIMIT` en SQL.** El recorte `[:10]` de la línea 203 se aplica en Python, *después* de iterar los dos querysets completos: el SQL sale sin límite y se materializan instancias completas de `Article` **incluido el `TextField` `body`**.
2. **Sin rate limit ni caché.** Cada petición paga el coste íntegro: dos escaneos FTS + `SearchRank` sobre todas las filas que casan, contra 3 workers sync.
3. **500 no capturado.** Verificado contra la app real:

```text
q=NUL         -> EXCEPCION DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes
q=8000 chars  -> HTTP 200   (el vector de "consulta larga" NO existe)
```

- **Impacto:** `GET /buscar/?q=%00` es un 500 alcanzable por cualquier anónimo. Y con un término frecuente del corpus (visible en `/sitemap.xml`) en bucle, la amplificación por petición satura los tres workers con coste trivial para el atacante; el consumo de memoria crece linealmente con el archivo y sin cota.
- **Corrección:** `q = request.GET.get("q", "").replace("\x00", "")[:120].strip()` y descartar si mide menos de 3 caracteres; aplicar `.order_by("-rank")[:10]` a cada queryset **antes** de iterarlo y `.defer("body")`; `@ratelimit(key="ip", rate="30/m", method="GET", block=False)`; `try/except DatabaseError` como red de seguridad. Tests: `?q=%00` → 200, y presupuesto de filas en `test_performance.py`.

### S-05. El detalle de poema publica una grabación no publicada

- **Dimensión:** crítico de completitud · **CWE-200** · **A01:2021 Broken Access Control**
- **Ubicación:** `backend/templates/content/poem_detail.html:28-37`

Es el **único consumidor de `Recording` que no filtra por `published`**. Todos los demás sí lo hacen: `media/views.py:8` (`_published()`), `media/feeds.py:72` (`published=True`) y el índice. La vista `poem_detail` hace `select_related("recording")` sin condición, y la plantilla renderiza `poem.recording.file.url` y `poem.recording.embed_url`.

- **Impacto:** publicación anticipada de material embargado por la vía más directa posible — la URL aparece en el HTML de una página indexada, sin necesidad de adivinar nombres de fichero. También rompe la reversibilidad de «despublicar»: quitar `published` a un registro no lo retira de la ficha del poema. Es distinto de S-01: aquí el enlace se regala, e incluye el caso `embed_url`, que ni siquiera pasa por `/media/`.
- **Corrección:** filtrar en la capa de datos, no en la plantilla — pasar `recording = poem.recording if poem.recording and poem.recording.published else None` al contexto (o una property `published_recording` en el modelo). Aplicar lo mismo en `backend/templates/content/partials/_poem_card.html:6`, que marca «con registro» sin comprobar el estado. Test: poema publicado + `Recording(published=False)` → `assertNotContains` de ambas URLs.

### S-06. Los respaldos quedan legibles por todo el host y sin cifrar

- **Dimensión:** infra · uploads · **CWE-732** · **A01:2021 Broken Access Control**
- **Ubicación:** `infra/backup/backup.sh:16-27`

El script no fija `umask`, así que `mkdir -p "$DEST"` crea el directorio 0755 y `pg_dump` escribe `db.dump` con 0644, en un bind-mount del host (`BACKUP_DIR`). El contenido es la base de datos completa —correos de suscriptores, PII de envíos, hashes de contraseñas— más `private_media.tar.gz` con los manuscritos que el proyecto se esfuerza en mantener fuera de `MEDIA_ROOT`. El cifrado en reposo solo existe si se activa restic (off-site); el respaldo local siempre es texto plano.

Relacionado, en el mismo componente: `restore.sh` toma `latest` por defecto y ejecuta `pg_restore --clean` y `rm -rf /volumes/media/*` **sin confirmación alguna**; un `sh /scripts/restore.sh` sin argumentos destruye el estado actual.

- **Corrección:** `umask 077` justo tras `set -eu` y `chmod 700 "$DEST"` tras el `mkdir`; para el cifrado local, hacer restic obligatorio o canalizar el dump por `age`/`gpg --symmetric`. En `restore.sh`, exigir `RESTORE_CONFIRM=SI-DESTRUIR-$POSTGRES_DB` (o prompt con TTY) y tomar un dump de seguridad automático antes de restaurar. Documentar que `BACKUP_DIR` debe ser un directorio 700 de un usuario dedicado.

### S-07. Tres workers sync tras un Caddy sin timeouts: DoS con tres conexiones

- **Dimensión:** dos · **CWE-400** · **A04:2021 Insecure Design**
- **Ubicación:** `docker-compose.prod.yml:14-30` + `infra/caddy/Caddyfile`

gunicorn corre con `--workers 3` en modo **sync** (un proceso por petición, sin hilos) y el Caddyfile no declara ningún timeout de lectura ni buffering de petición. Una petición lenta ocupa un proceso entero de principio a fin.

- **Impacto:** denegación de servicio total con **tres conexiones TCP** desde un único host, sin ancho de banda ni botnet (slowloris clásico). Agravante: el healthcheck del contenedor también pasa por gunicorn, así que se marcará `unhealthy` y Docker reiniciará `web` en bucle.
- **Corrección:** en el Caddyfile, bloque global `servers { timeouts { read_body 30s read_header 10s write 60s idle 120s } }` y `request_buffers 12MB`, para que Caddy absorba el cuerpo completo antes de tocar a gunicorn; subir el paralelismo con `--threads 4` (worker `gthread`) para que una petición lenta no bloquee un proceso; bajar `--timeout` a 30 s y añadir `--graceful-timeout`.

### S-08. Ningún contenedor declara límites de recursos ni endurecimiento

- **Dimensión:** infra · dos · **CWE-770** · **A05:2021 Security Misconfiguration**
- **Ubicación:** `docker-compose.prod.yml` (todos los servicios)

No hay `mem_limit`/`cpus`/`pids_limit` en ningún servicio, ni `security_opt: no-new-privileges`, ni `cap_drop`, ni `read_only`.

- **Impacto:** nada aísla un pico de `web` de `db` y `redis`, que comparten host: el OOM killer puede matar la base de datos, convirtiendo una degradación en indisponibilidad total con pérdida de conexiones. Multiplica el impacto de S-04 y S-07. La ausencia de `cap_drop`/`no-new-privileges` amplía lo que un RCE hipotético en cualquier contenedor podría hacer.
- **Corrección:** `mem_limit`/`cpus` en cada servicio dimensionados para que la suma quede por debajo de la RAM del host (p. ej. web 768m, db 1g, redis 384m, proxy 128m); `security_opt: ["no-new-privileges:true"]` y `cap_drop: [ALL]` con `cap_add: [NET_BIND_SERVICE]` solo en el proxy; `read_only: true` con `tmpfs` para lo que necesite escribir.

---

## Hallazgos BAJOS

Agrupados por área. Todos verificados contra el código; ninguno es explotable por un anónimo sin condiciones adicionales.

### Control de acceso y datos

| # | Hallazgo | Ubicación | Corrección |
|---|---|---|---|
| S-09 | Los ficheros de `/media/` se sirven sin comprobar `published`: material no publicado es descargable si se adivina el nombre | `infra/caddy/Caddyfile:17` | Servir lo no público por Django con `X-Accel-Redirect` hacia una zona `internal`, o anteponer `secrets.token_hex(8)` en `upload_to` (hace inadivinable la ruta) |
| S-10 | `AXES_RESET_ON_SUCCESS` con bloqueo solo por IP: un login válido borra el contador de fallos de toda la IP | `backend/config/settings.py:144` | `AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"], "username"]` para que el reset solo limpie esa cuenta |
| S-11 | El campo `uploaded_by` de `MediaAsset` es un `<select>` plano: el rol `autor` enumera todas las cuentas y puede falsificar la autoría | `backend/apps/media/admin.py:7` | `readonly_fields += ["uploaded_by"]` y asignarlo en `save_model` desde `request.user` |
| S-12 | `setup_groups` usa `permissions.set(...)` y corre en cada arranque: revierte en silencio cualquier permiso retirado a mano | `backend/apps/people/management/commands/setup_groups.py:41` | `permissions.add(*perms)` (aditivo, nunca quita) y reservar el reemplazo para una bandera `--reset` que el entrypoint no use |

### Privacidad y ciclo de vida del dato

| # | Hallazgo | Ubicación | Corrección |
|---|---|---|---|
| S-13 | Borrar un envío o un recurso desde el admin deja el **fichero huérfano en disco** — y en todos los respaldos posteriores | `backend/apps/submissions/models.py:49` | Señal `post_delete` (y `pre_save` al reemplazar) para `Submission.file`, `MediaAsset.file` + derivadas, `Recording.file` y los PDF; o `django-cleanup` |
| S-14 | Las imágenes originales se publican con el **EXIF intacto** (GPS, fecha, modelo); solo las derivadas quedan limpias | `backend/apps/media/models.py:71` | Reescribir el original con Pillow sin metadatos tras `ImageOps.exif_transpose()`; test con un JPEG con bloque GPS conocido |
| S-15 | El token de suscripción no caduca, no es de un solo uso y se reutiliza al volver a suscribirse | `backend/apps/community/views.py:62` | Token nuevo en cada alta, `token_created_at` con caducidad de 48 h, borrarlo al confirmar; mejor aún, `TimestampSigner` y no persistir el secreto |
| S-16 | Confirmar y dar de baja **mutan estado por GET**: una pasarela de correo que visita enlaces confirma la suscripción sola | `backend/apps/community/views.py:84` | Página intermedia con formulario y ejecución en POST; para el un-clic de correo, `List-Unsubscribe-Post` con exención de CSRF acotada **solo** a la baja |
| S-17 | El alta distingue al suscriptor ya confirmado en el mensaje flash: oráculo de pertenencia | `backend/apps/community/views.py:58` | Mismo mensaje neutro en las tres ramas y mismo trabajo observable (encolar siempre, decidir dentro) |
| S-18 | La purga no cubre suscriptores dados de baja ni envíos sin resolver, pese a que la política promete borrarlos | `.../purge_stale_data.py:27` | Ampliar `purge_stale_data` a `UNSUBSCRIBED` pasados N días y a `Submission` en `RECEIVED`/`IN_REVIEW` antiguos |
| S-19 | La página de cookies afirma que no se comparte nada con terceros, pero los iframes de Vimeo/YouTube cargan solos | `backend/templates/media/partials/_player.html:5` | Click-to-play con carátula local y aviso, que es lo coherente con lo ya prometido; o actualizar `/cookies/` declarando proveedores |
| S-20 | Los tokens de confirmación/baja quedan en el access log de gunicorn, en el log JSON y en las URLs enviadas a Sentry | `backend/config/settings.py:293` | `before_send`/`before_breadcrumb` que redacten el path de `/novedades/(confirmar\|baja)/`; sacar el secreto de la ruta |
| S-21 | El correo del suscriptor se interpola en `logger.exception` cuando falla el broker | `backend/apps/community/views.py:81` | Registrar `sub.pk` en vez de `sub.email` |

### Disponibilidad y resiliencia

| # | Hallazgo | Ubicación | Corrección |
|---|---|---|---|
| S-22 | Con Redis caído, django-ratelimit propaga la excepción del backend: newsletter y envíos devuelven **500** | `backend/config/settings.py:227` | `django-redis` con `IGNORE_EXCEPTIONS`, o capturar y decidir la política explícitamente (recomendado: fail-closed con 429 amable) |
| S-23 | Sin `EMAIL_TIMEOUT` ni `time_limit` en Celery: un SMTP que no responde cuelga los slots del worker indefinidamente | `backend/config/settings.py:206` | `EMAIL_TIMEOUT=20`, `CELERY_TASK_SOFT_TIME_LIMIT=30`, `CELERY_TASK_TIME_LIMIT=60` |
| S-24 | Una sola instancia Redis con `maxmemory 256mb` y `noeviction` sirve de caché de rate-limit **y** de broker: presupuestos acoplados | `docker-compose.prod.yml:81` | Separar instancias (broker `noeviction`, caché `allkeys-lru`) o subir `maxmemory` y no dejar la caché en `noeviction` |
| S-25 | Derivadas de imagen generadas en el hilo de la petición, sin `MAX_IMAGE_PIXELS`: bomba de descompresión | `backend/apps/media/models.py:72` | Fijar `Image.MAX_IMAGE_PIXELS`, validar dimensiones antes de aceptar y mover `ensure_derivatives()` a una tarea Celery |
| S-26 | Los adjuntos de `/enviar/` no tienen cuota global y la purga nunca alcanza el estado `RECEIVED`: crecimiento sin cota | `backend/apps/submissions/views.py:19` | Rechazar el POST si no hay convocatoria abierta, cuota global además de la de IP, y comprobar espacio libre |
| S-27 | Todos los estáticos (CSS, htmx y los cientos de ficheros de TinyMCE) atraviesan los 3 workers de gunicorn | `infra/caddy/Caddyfile:22` | Volumen `staticfiles` compartido con el proxy y `handle_path /static/*` con `file_server` + `Cache-Control immutable` |

### Operación e infraestructura

| # | Hallazgo | Ubicación | Corrección |
|---|---|---|---|
| S-28 | `docker-compose.override.yml` se carga por defecto: un `docker compose up -d` sin `-f` en producción recrea el stack en modo desarrollo (imagen `dev`, root, `runserver`) | `docker-compose.override.yml:6` | `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` en `.env.prod.example` y documentado como obligatorio |
| S-29 | El `.env` completo se inyecta en todos los servicios: `web`/`worker`/`beat` reciben credenciales de respaldo off-site y de SMTP que no necesitan | `docker-compose.yml:39` | Segmentar en `.env`, `.env.backup` (RESTIC/AWS) y `.env.mail`, cada uno referenciado solo por quien lo usa |
| S-30 | El guard no valida longitud ni entropía de `SECRET_KEY`, y `check --deploy` solo corre en CI, nunca en el despliegue | `backend/config/settings.py:38` | Umbrales de `security.W009` en el guard, e invocar `check --deploy --fail-level WARNING` desde `entrypoint.sh` con `DEBUG=0` |

### Cadena de suministro

| # | Hallazgo | Ubicación | Corrección |
|---|---|---|---|
| S-31 | **TinyMCE 7.9.3 y htmx 2.0.3 vendorizados sin ningún canal de aviso**: no los cubre dependabot, ni pip-audit, ni trivy | `.github/dependabot.yml` | `backend/static/vendor/VERSIONS.md` con versión, fecha, URL y sha256 de cada bundle, y un paso de CI que detecte drift |
| S-32 | htmx 2.0.3 (oct-2024) va 7 releases de parche y ~21 meses por detrás de 2.0.10; sin CVE conocido | `backend/templates/base.html:38` | Actualizar a la última 2.0.x verificando el sha256 del release oficial |
| S-33 | El CI descarga y ejecuta código remoto sin fijar: trivy por `curl \| sh` desde la rama `main` de terceros, y gitleaks sin verificar checksum | `.github/workflows/ci.yml:181,195` | Binarios de release fijados por versión con `sha256sum -c`, o la acción oficial fijada por SHA; fijar también `pip-audit`/`bandit` por versión |
| S-34 | Imagen base `python:3.12-slim` sin digest, y la entrada docker de dependabot es inerte por construcción (el tag no tiene componente de parche) | `backend/Dockerfile:7` | `FROM python:3.12-slim@sha256:<digest>`, con lo que dependabot sí puede proponer actualizaciones |
| S-35 | Las imágenes de compose (`postgres:16`, `redis:7-alpine`, `caddy:2-alpine`) no las cubre ningún ecosistema de dependabot ni trivy | `docker-compose.prod.yml:89` | Entrada `package-ecosystem: docker` con `directory: /` en dependabot |
| S-36 | El feed de podcast guarda la request en `self`, pero la instancia se crea una sola vez en `urls.py` y la comparte todo el proceso | `backend/apps/media/feeds.py:68` | No guardar estado en la instancia: usar `get_object(self, request, ...)` y la firma con `obj` que Django propaga |

---

## Hallazgos INFORMATIVOS

Endurecimiento y deuda documental. Ninguno describe un defecto explotable; se listan para que la decisión de no abordarlos sea consciente.

**Configuración y guard (5):** el guard no exige `REDIS_PASSWORD` (la protección efectiva recae solo en `${REDIS_PASSWORD:?}` del compose) · el comentario de `settings.py:197` afirma que `REDIS_PASSWORD` es la «única fuente» de la URL de Celery, pero `CELERY_BROKER_URL` del entorno tiene precedencia · el guard valida presencia pero no forma de `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` (acepta `*` y `http://`) · `SITE_ADDRESS` cae en silencio a `:80` (sin TLS) y no aparece en `.env.prod.example` · la allowlist de `.gitleaks.toml` es global y sin anclar, así que los patrones de CI suprimen coincidencias en todo el repositorio.

**CSP y saneo (4):** la CSP y `Permissions-Policy` no se emiten en `/static/` (WhiteNoise cortocircuita) ni en `/media/` (Caddy) · el saneo `nh3` es una convención de la capa Python (solo `Model.save()`), no una invariante de la BD: las migraciones de datos lo esquivan · ningún test afirma el filtrado de `javascript:`/`data:`/`on*`/`<iframe>`, y `url_schemes` se deja al default de nh3 en vez de fijarlo · `style-src 'unsafe-inline'` se emite también en el sitio público, donde el CSS propio ya va en un fichero estático.

**Infraestructura (7):** `REDIS_PASSWORD` se pasa por argv y por el healthcheck en vez de por fichero de configuración (visible en `docker inspect`) · imágenes base por tag mutable sin digest · `ci.yml` no declara `permissions:` · el sidecar de respaldos corre como root, monta los volúmenes en lectura-escritura y recibe el `.env` completo · el Caddyfile no normaliza `X-Forwarded-Proto` con `header_up` (sin impacto demostrable, pero conviene ser explícito) · no hay access log en el borde y el de gunicorn registra siempre la IP interna del proxy · los healthchecks no tienen actuador: Compose no reinicia contenedores `unhealthy` · `backend/.dockerignore` no excluye `tests/`, `conftest.py`, `pytest.ini` ni `.coverage`, que entran en la imagen de producción.

**Cadena de suministro (5):** `dependency-review-action` es `continue-on-error`, así que su veredicto es decorativo · **TinyMCE 7.9.3 es GPLv2-or-later dentro de un árbol cuyo `LICENSE` declara «todos los derechos reservados»** sin excepción para terceros (cuestión de licenciamiento, no de seguridad, pero conviene resolverla) · los hooks de pre-commit se fijan por tag mutable · el CI solo corre en `push`/`pull_request`: pip-audit y trivy no se ejecutan si el repositorio está quieto · las acciones se fijan por tag mayor (`@v7`) en vez de por SHA.

**Aplicación (5):** `has_change_permission`/`has_delete_permission` de `EditorialItemAdmin` deciden solo por grupo y no componen con los permisos de modelo (revocar un permiso en el admin no surte efecto) · la validación de bytes mágicos comprueba solo un prefijo de 8 bytes: acepta políglotas y cualquier ZIP como `.docx` (riesgo residual contenido por el almacenamiento privado) · con el rate-limit superado, `/enviar/` aún parsea el multipart y escribe el adjunto en disco temporal antes de rechazar · `/readyz/` devuelve sin autenticación el estado de BD y broker (ya documentado como diferido #27) · django-axes acumula IPs sin ninguna purga programada.

**Privacidad documental (3):** no se guarda prueba del consentimiento (fecha de aceptación, versión del texto legal); `confirmed_at` es el único rastro · el canal de ejercicio de derechos depende de un correo que puede estar sin configurar, y no se declara a Sentry como encargado del tratamiento · los tokens en la ruta quedan en el log de acceso sin política de retención ni rotación de ficheros.

---

## Controles verificados como correctos

Lo que se atacó y resistió. Se documenta para que futuras auditorías no lo re-descubran desde cero:

- **Flujo editorial** — transiciones validadas en el servidor, revalidación bajo `select_for_update()` que cierra la carrera entre editores y con la publicación programada, `status` readonly *siempre*, bitácora `EditorialTransition` inmutable, queryset filtrado por dueño para no-editores.
- **Filtrado de publicación** — consistente en todas las vistas, feeds y sitemaps (única excepción: S-05).
- **Inyección** — sin SQL crudo con entrada de usuario; `SearchQuery` parametrizado; funciones de trigger plpgsql que no concatenan entrada; scripts shell con `set -eu` y sin interpolación externa; sin `pickle`/`yaml.load`/`eval`.
- **XSS** — `nh3` con lista blanca estricta en `save()` de los dos únicos modelos renderizados con `|safe`; `embed_src` solo puede emitir URLs de dominios fijos con un id de `[\w-]`; sin DOM XSS en el JS propio.
- **Envíos públicos** — extensión + tamaño + bytes mágicos, almacenamiento fuera de `MEDIA_ROOT`, descarga tras `staff_member_required` + `is_editor`, honeypot y rate limit.
- **Capa web** — CSRF forzado; `SameSite` heredando el `Lax` seguro de Django 5.2; open redirect cerrado con `url_has_allowed_host_and_scheme`; `ALLOWED_HOSTS` validado; HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy` presentes en las respuestas de Django.
- **Secretos** — historial de git limpio: solo placeholders y valores de prueba de CI (verificado con `--diff-filter=A` sobre todas las ramas y pickaxe de `BEGIN PRIVATE KEY`, `ghp_`, `AKIA`, `xoxb-`); `.env` nunca versionado.
- **Dependencias** — **0 vulnerabilidades** en las 12 dependencias principales, verificado contra la API de OSV; lockfiles con `--generate-hashes`; pip-audit bloqueante en CI.
- **Contenedores** — imagen de producción no-root (uid 1000), multi-stage, sin herramientas de compilación; `db` y `redis` sin puertos publicados; Redis con contraseña obligatoria en el compose de producción.
- **Clases buscadas y no encontradas** — SSRF y XXE (no hay peticiones salientes ni parseo XML de entrada), prototype pollution (el único JS propio son 18 líneas de init sin merge de objetos), cache poisoning (no hay ninguna capa de caché HTTP), mass assignment (ningún `ModelForm` con `fields = "__all__"`).

## Falsos positivos descartados

22 hallazgos fueron refutados en la verificación adversarial. Los más instructivos, para no volver a levantarlos:

- **`gunicorn 22.0.0` / CVE-2024-6827.** El refutador consultó fuentes autoritativas en vivo y determinó que la vulnerabilidad **está corregida en 22.0.0**, no la afecta. Confirmado de forma independiente contra OSV. *Este era un falso positivo que mi propio conocimiento previo habría publicado.*
- **`SameSite` no declarado.** El default de Django 5.2 es `Lax`, que es el valor seguro. Apoyarse en un default correcto no es un defecto.
- **Mismo token para confirmar y dar de baja.** Ambas URLs viajan en el mismo mensaje de correo: quien ve una ve la otra. No otorga capacidad nueva.
- **DoS de `/sitemap.xml`.** El finder afirmó 13 querysets sin `LIMIT` **e inventó las citas de línea**. `django.contrib.sitemaps.Sitemap` expone `limit = 50000` y pagina.
- **`embed_src` con regex sin anclar.** Cierto que hace `.search()` en cualquier parte de la URL, pero la salida siempre es un dominio fijo con un id restringido a `[\w-]`: no hay ruptura de atributo ni de URL.
- **`X-Forwarded-Proto` no normalizado.** La cadena no es alcanzable en el despliegue nominal (queda como endurecimiento informativo).
- **`/readyz/` como amplificador de DoS** y **traversal en `restore.sh`**: sin atacante real; el segundo requiere ser el operador.

---

## Estado de ejecución

> Actualizado al cierre de la ola S3. **Olas S0, S1, S2 y S3 completas** (lotes `sec-1` …
> `sec-17`), mergeadas en `main` con `--no-ff`. Suite: **249 → 343 tests**, cobertura 93 %
> (piso: 80 %). Compuertas verificadas en local sobre el estado final: ruff,
> `makemigrations --check`, bandit (severidad medium/high = 0), gitleaks (sin fugas),
> `caddy validate`, `docker compose config`.
>
> *Fe de erratas:* los mensajes de los commits `sec-11`, `sec-12` y `sec-13` citan 331, 343
> y 350 tests. Son incorrectos —se leyeron de los puntos de progreso de pytest en vez de la
> línea de resumen—. La cifra real al cierre de S2 era **329**.

| Ítem | Lote | Estado |
|---|---|---|
| **S-01** XSS almacenado en `/media/` → escalada | `sec-1` | ✅ Cerrado en las dos capas (validadores + cabeceras de borde), con PoC antes/después |
| **S-02** Guard no detecta placeholders | `sec-2` | ✅ Validación positiva en `config/envguard.py` |
| **S-03** `seed_demo` sin guarda, contraseña publicada | `sec-3` | ✅ Guarda de `DEBUG` + contraseña aleatoria |
| **S-05** Grabación inédita en la ficha de poema | `sec-4` | ✅ `Poem.published_recording` |
| **S-04** Buscador sin `LIMIT` ni rate limit; 500 con NUL | `sec-5` | ✅ Los tres defectos |
| **S-07** Slowloris con 3 conexiones | `sec-6` | ✅ Timeouts en Caddy + `gthread` |
| **S-08** Sin límites de recursos ni endurecimiento | `sec-7` | ✅ Límites, `cap_drop`, `no-new-privileges` |
| **S-22** 500 con Redis caído | `sec-8` | ✅ `config/cache.ResilientRedisCache` |
| **S-23** Sin `EMAIL_TIMEOUT` ni límites de tarea | `sec-8` | ✅ |
| **S-06** Respaldos legibles y sin cifrar | `sec-9` | ✅ `umask 077` + `chmod 700`; `restore.sh` exige confirmación |
| **S-13** Ficheros huérfanos al borrar | `sec-10` | ✅ Señales `post_delete`/`pre_save` en los 5 campos con archivo |
| **S-14** EXIF con GPS en los originales | `sec-10` | ✅ `MediaAsset.strip_metadata()` |
| **S-15** Tokens sin caducidad ni un solo uso | `sec-11` | ✅ `confirm_token` (48 h, un uso) separado del de baja |
| **S-16** Confirmar/dar de baja por GET | `sec-11` | ✅ Mutación por POST + un-clic RFC 8058 |
| **S-17** Oráculo de pertenencia en el alta | `sec-11` | ✅ Respuesta neutra en las cuatro ramas |
| **S-18** Purga incompleta de PII | `sec-12` | ✅ Cubre bajas y registros de axes (90 días) |
| **S-20** Tokens en logs y en Sentry | `sec-12` | 🟡 Redactados en el log de Django y en Sentry; el log de acceso de **gunicorn** sigue expuesto (ver abajo) |
| **S-21** Correo del suscriptor en el log | `sec-11` | ✅ Se registra el `pk` |
| **S-19** Embeds de terceros sin consentimiento | `sec-13` | ✅ Click-to-play; la portada ya no contacta con YouTube/Vimeo |
| **S-33** CI sin `permissions`, código remoto sin verificar | `sec-14` | ✅ `contents: read`, checksums sha256, versiones fijadas, `schedule` semanal |
| **S-31** Vendorizado sin canal de aviso | `sec-15`, `sec-17` | ✅ `VERSIONS.md` con sha256 + 8 tests anti-drift; `NOTICE.md` con licencias |
| **S-32** htmx desactualizado | `sec-15` | ✅ 2.0.3 → 2.0.10, verificado por integridad sha512 de npm |
| **S-34** Imágenes por tag mutable | `sec-16` | ✅ Cinco referencias por digest + test que impide desfijarlas |
| **S-24** Redis único caché+broker | — | 🟡 Parcial: una escritura rechazada ya no da 500; separar instancias queda pendiente |
| **S-27** Estáticos servidos por gunicorn | — | ⏳ Exige un volumen compartido entre `web` y `proxy`; lote propio |
| **S-35** Imágenes de compose fuera de Dependabot | — | ⏳ Abierto a propósito (ver abajo) |

**S-35 se dejó abierto deliberadamente.** El ecosistema `docker` de Dependabot analiza
Dockerfiles; que admita ficheros compose depende de la versión de Dependabot y no se pudo
verificar contra el esquema oficial (la descarga falló). Añadir una entrada a ciegas con un
nombre de ecosistema inválido **detendría todas las actualizaciones**, que es peor que la
carencia. Mitigación vigente: las tres imágenes van fijadas por digest (un cambio silencioso
es imposible), `tests/test_image_pinning.py` impide desfijarlas y el CI programado pasa trivy
semanalmente sobre la imagen construida. Para cerrarlo: comprobar si esta instalación admite
`package-ecosystem: docker-compose`.

**Licencia de TinyMCE — decisión pendiente del colectivo.** `sec-17` aplica la opción de
coste cero (documentar en `NOTICE.md` y acotar `LICENSE`). Quedan como alternativas la
licencia comercial de TinyMCE o sustituirlo por un editor permisivo. Conviene revisarlo con
un abogado, igual que el texto de privacidad. Nota importante para no malinterpretarlo:
GPLv2 **no** es AGPL, así que usar TinyMCE no obliga a liberar el código propio.

**Residuo consciente de S-20.** El log de acceso de gunicorn (`--access-logfile -`) sigue
escribiendo la ruta completa, y ahí viaja el token de baja. Lo emite su propio logger, que no
admite un formato que redacte. Cerrarlo exige una de tres: mover el log de acceso al borde
(Caddy) y quitar el de gunicorn, sustituir su `logger-class`, o —solución de fondo— sacar el
secreto de la ruta y pasarlo en el cuerpo del POST. Anotado para S4.

**Hallazgos NUEVOS descubiertos durante la remediación** (no estaban en la auditoría):

- **`seed_demo` llevaba roto contra una base limpia** desde la migración `media.0004`:
  `get_or_create` insertaba el registro de audio con `file=''` y `embed_url=''`, violando
  la restricción `recording_file_or_embed`. No lo cubría ninguna prueba porque nada lo
  ejecutaba. Corregido en `sec-3`.
- **Deprecación de Django 6.0 latente**: construir un form con `Recording.embed_url`
  (`URLField`) emite `RemovedInDjango60Warning` por `assume_scheme`, que
  `filterwarnings = error` convierte en error. Hoy no la dispara ningún test, pero
  romperá al subir a Django 6. Se resuelve con `FORMS_URLFIELD_ASSUME_HTTPS = True`
  —que además asume `https` en vez de `http`, mejor por defecto—. Pendiente, ola S4.
- **El Caddyfile no lo validaba ni lo probaba nada.** Ahora el job `prod-runtime` corre
  `caddy validate` y verifica las cabeceras de `/media/` sirviendo un archivo real.
- **El job `backup-restore` no ejecutaba los scripts de respaldo**: imitaba `pg_dump` con
  los mismos flags, así que nada cubría `backup.sh` ni `restore.sh`. Ahora corre `backup.sh`
  de verdad, afirma los permisos de los tres artefactos y comprueba que `restore.sh` se
  niega a destruir sin confirmación.
- **La señal `pre_save` de `sec-10` introdujo una consulta de más** en cada alta, porque
  `SiteProfile` fuerza `pk=1` por ser singleton y la comprobación por `pk` la tomaba por
  actualización. La detectó el presupuesto anti-N+1 de `test_performance.py`; se corrigió
  usando `_state.adding`. Es el argumento a favor de mantener esos presupuestos.
- **El Dockerfile del sidecar de respaldos no lo cubría ninguna entrada de Dependabot**,
  pese a manejar la base de datos completa. Corregido en `sec-16`.
- **htmx era 0BSD y Fraunces OFL** — sin obligaciones problemáticas. El único componente
  con copyleft es TinyMCE: el inventario de `NOTICE.md` acota el problema a un solo punto
  en vez de dejarlo como una duda difusa sobre todo el árbol.

## Plan de remediación

Cinco olas, ordenadas por **riesgo residual eliminado por unidad de esfuerzo**. Cada ola es un lote independiente con el flujo habitual del proyecto (rama → tests → PR → merge `--no-ff`), y deja el CI verde.

### Ola S0 — Cierra la escalada de privilegios · *bloqueante antes de exponer a producción*

| Lote | Hallazgos | Alcance |
|---|---|---|
| `sec-1` | **S-01** | `FileExtensionValidator` + firma de bytes en `Recording.file`, `Publication.pdf` y `SiteProfile.dossier_pdf`; bloque `header` en `handle_path /media/*` del Caddyfile; aserción de esas cabeceras en el job `prod-runtime` |
| `sec-2` | **S-02**, S-30 | Guard por validación positiva (placeholders, entropía, `REDIS_PASSWORD`, forma de hosts/CSRF); secretos vacíos en la plantilla; test que carga `.env.prod.example` y exige `ImproperlyConfigured` |
| `sec-3` | **S-03** | Guarda de `DEBUG` con `--force` en `seed_demo` y contraseña aleatoria; test del fallo con `DEBUG=0` |
| `sec-4` | **S-05** | Filtrar `published` en `poem_detail` y en `_poem_card.html`; test de no-filtración |

*Por qué primero:* `sec-1` + `sec-3` eliminan la única cadena hasta superusuario, y `sec-2` cierra la falsa confianza del arranque. Son cuatro lotes pequeños —del orden de 40 líneas de producción— con el mayor retorno de todo el plan.

### Ola S1 — Superficie pública anónima

| Lote | Hallazgos | Alcance |
|---|---|---|
| `sec-5` | **S-04** | Acotar y sanear `q`, `LIMIT` en SQL, `defer("body")`, `@ratelimit`, `try/except DatabaseError`; tests del NUL y presupuesto de filas |
| `sec-6` | **S-07**, S-27 | Timeouts y `request_buffers` en Caddy, `--threads` en gunicorn, estáticos servidos en el borde |
| `sec-7` | **S-08** | Límites de memoria/CPU/PIDs, `no-new-privileges`, `cap_drop`, `read_only` en el compose de producción |
| `sec-8` | S-22, S-23, S-24 | Tolerancia a Redis caído, `EMAIL_TIMEOUT` y límites de tiempo de tarea, presupuestos de Redis separados |

### Ola S2 — Ciclo de vida del dato y privacidad

| Lote | Hallazgos | Alcance |
|---|---|---|
| `sec-9` | **S-06** | `umask 077` + `chmod 700` en `backup.sh`; confirmación explícita en `restore.sh`; aserción de permisos en el job `backup-restore` |
| `sec-10` | S-13, S-14 | Señales `post_delete`/`pre_save` para todos los ficheros; limpieza de EXIF en los originales |
| `sec-11` | S-15, S-16, S-17 | Tokens con caducidad y un solo uso; confirmación/baja por POST con `List-Unsubscribe-Post`; respuesta neutra que cierra el oráculo |
| `sec-12` | S-18, S-20, S-21, +axes | Ampliar la purga a bajas y envíos antiguos; purga de `AccessAttempt`; redacción de tokens y PII en logs y Sentry |
| `sec-13` | S-19 | Click-to-play en los embeds, coherente con lo que ya promete la página de cookies |

### Ola S3 — Cadena de suministro y CI

| Lote | Hallazgos | Alcance |
|---|---|---|
| `sec-14` | S-33, +`permissions:` | `permissions: contents: read` a nivel de workflow; binarios de release fijados y verificados por sha256; `pip-audit`/`bandit` con versión fijada |
| `sec-15` | **S-31**, S-32 | `VERSIONS.md` de lo vendorizado con sha256, paso de CI anti-drift, y htmx al día |
| `sec-16` | S-34, S-35, +`schedule` | Digests en las imágenes base, dependabot para las imágenes de compose, disparador semanal del CI |
| `sec-17` | TinyMCE GPL | Decidir entre excluir `backend/static/vendor/` en `LICENSE` declarando GPLv2+ (coste casi nulo), licencia comercial, o sustituir el editor |

### Ola S4 — Endurecimiento e higiene

Agrupa los 30 informativos y el resto de bajos (S-09 a S-12, S-25, S-26, S-28, S-29, S-36) en lotes temáticos: `COMPOSE_FILE` obligatorio y `SITE_ADDRESS` fail-fast; segmentación del `.env`; endurecimiento del sidecar de respaldos; access log en el borde; `.dockerignore`; CSP en estáticos y `style-src` sin `unsafe-inline` en el sitio público; saneo también en la capa de formulario más tests de protocolos peligrosos; correcciones del admin (`uploaded_by`, permisos que compongan, `setup_groups` aditivo).

### Criterios transversales

- **Cada lote lleva su test de regresión.** La suite tiene 249 tests; ninguna corrección de S0/S1/S2 debería entrar sin uno que falle antes y pase después.
- **Validar en condiciones de CI antes de mergear** (runner limpio, sin `staticfiles/`, imagen y BD frescas) y verificar el CI en GitHub tras el merge. Lección ya aprendida en PRs #61/#62.
- **Los cambios del Caddyfile no los cubre la suite**: verificarlos en el job `prod-runtime`, que ya levanta la imagen real con `DEBUG=0`.
- **Actualizar `docs/deferidos-y-decisiones.md`** con lo que se decida no hacer, para que la próxima auditoría no lo vuelva a levantar.
