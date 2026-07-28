# Auditoría de calidad #2 — «Reseñas» (tras Fases 1–3)

> **Fecha:** 2026-07-28 · **Método:** auditoría multi-agente senior (6 dimensiones; cada hallazgo verificado adversarialmente contra el código real `archivo:línea`; 14 agentes, ~700K tokens, 287 lecturas). Sucede a `docs/auditoria-mvp.md` y evalúa el estado **tras** las Fases 1–3.

## 1. Veredicto ejecutivo

Madurez global: beta sólida, muy cerca de producción. Las seis dimensiones convergen en beta y, tras la verificación, no queda ningún hallazgo de severidad alta (todos los candidatos a high se rebajaron a medium): los cimientos —seguridad, modelo de datos y concurrencia de Celery— están genuinamente a nivel producción, con la re-arquitectura A–H completa y 179 tests. Lo que impide declarar "producción" no son fallas estructurales sino un puñado de defectos concretos y acotados: un bug de correctitud alcanzable por el admin (ISBN), dos modos de fallo silencioso en flujos asíncronos (programación sin published_at y correo con fail_silently), una señal de salud engañosa en el deploy por-el-libro y un rate-limit debilitado en multi-worker. Calibrado a la escala real (colectivo de poesía, tráfico bajo, audiencia de pares/gestores), ninguno tumba el sitio y varios son quick wins de esfuerzo S. Resueltos los mediums de correctitud y operación, el proyecto quedaría esencialmente en producción a su escala.

## 2. Scorecard por dimensión

| Dimensión | Madurez | Titular |
|-----------|:-------:|---------|
| Arquitectura, organización y mantenibilidad | `beta` | Monolito bien estratificado con los 2 hallazgos previos resueltos (imports vista-a-vista extraídos a services, singleton SiteProfile con load()); solo resta cohesión (showcase/content como hubs transversales) y una capa de servicios/selectors aplicada de forma despareja. |
| Seguridad | `beta` | Muy por encima del promedio: autorización por objeto Y estado, CSP con nonce y script-src sin unsafe-inline, self-hosting real (cero CDN) y anti-abuso en profundidad; único residuo con vector real es el rate-limit sobre LocMemCache en despliegue multi-worker. |
| Modelo de datos, BD y migraciones | `beta` | La dimensión más sólida: 3NF real, constraints a nivel BD, UniqueConstraint en todos los puentes, FTS por trigger de Postgres y migración expand/contract ejemplar; solo la frena el bug de ISBN que rompe un flujo editorial común. |
| Pruebas, CI/CD y reproducibilidad | `beta` | Reproducibilidad a nivel producción (lockfiles con hashes, pip-audit bloqueante, check --deploy, 179 tests) pero sin CD alguno, sin ejercitar la imagen prod en CI y con config/ (incl. la middleware CSP) fuera del gate de cobertura. |
| Frontend, UX, SEO y accesibilidad | `beta` | Presentación muy por encima de su tamaño (imágenes responsivas anti-CLS, JSON-LD con nonce, MediaAsset defensivo, a11y honesta); huecos acotados: portada sin h1, poema/registro sin og:image de respaldo y podcast sin namespace iTunes. |
| Producción/DevOps y lógica de negocio/asincronía | `beta` | Concurrencia de Celery correcta y probada + endurecimiento operativo real (Docker non-root, healthchecks diferenciados, Redis noeviction, /readyz/, respaldos); tres huecos operativos: healthcheck web falso-unhealthy, programación atascada silenciosa y correo síncrono con fail_silently. |

## 3. Fortalezas (nivel producción)

- Concurrencia de Celery a nivel producción y probada: perform_transition (workflow.py:60-79) y publish_due_items (tasks.py:6-47) usan transaction.atomic + select_for_update + revalidación autoritativa del estado bajo lock, con acks_late/backoff e idempotencia ante doble beat o reintento; el TOCTOU está cerrado y cubierto por tests (test_workflow.py:83,95).
- Autorización por objeto Y estado con bitácora inmutable: permissions.py + workflow.py validan rol+estado y registran cada transición en EditorialTransition; el admin refuerza con get_queryset por dueño, has_change_permission delegado en can_edit_item y status readonly incluso para editores.
- Defensa XSS de verdad: saneo server-side con nh3 sobre lista blanca estricta (Article/Page.save → sanitize.py, link_rel nofollow/noopener), CSP propia con nonce por petición y script-src sin unsafe-inline, y self-hosting real de htmx/TinyMCE sin ninguna referencia a CDN.
- Diseño de datos genuinamente de producción: 3NF real (Publisher/BookAuthor/SocialLink normalizados), CheckConstraint XOR archivo/embed en Recording, UniqueConstraint en todos los puentes M2M, índices compuestos status/-published_at + GIN, FTS mantenido por trigger de Postgres (sigue bulk_update) y una migración expand/contract en 3 pasos reversible.
- Config dirigida por entorno con fail-safe de producción: con DEBUG=0 el arranque falla si SECRET_KEY/POSTGRES_PASSWORD/ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS siguen en valores de ejemplo (settings.py:28-45); cabeceras de transporte a nivel producción (HSTS+preload, cookies seguras, nosniff, X-Frame DENY) hechas bloqueantes por check --deploy --fail-level WARNING en CI.
- Reproducibilidad de builds real: lockfiles pip-compile --generate-hashes instalados con --require-hashes en CI y Dockerfile, pip-audit bloqueante, makemigrations --check y una suite de 179 tests que cubre los flujos que suelen quedar sin test (idempotencia/TOCTOU de Celery, FTS por trigger, CSP/nonce/self-host, anti-abuso, readiness y XSS).
- Frontend por encima de su tamaño: imágenes responsivas reales (responsive_img con srcset Pillow, width/height anti-CLS, decoding async, lazy=False para el LCP), MediaAsset defensivo (sin upscaling, solo lista derivados existentes, tolera imágenes ilegibles), JSON-LD con nonce, 12 sitemaps + robots dinámico y accesibilidad honesta (lightbox no-modal, skip link, :focus-visible, aria-live en el buscador).
- Endurecimiento operativo real: Docker multi-stage non-root uid 1000, healthchecks diferenciados que distinguen cuelgue de caída (worker por inspect ping vía broker, beat por mtime del schedule), Redis noeviction + requirepass obligatorio, /readyz/ que verifica BD+broker con 503, logging JSON, Sentry opt-in sin PII, respaldos con restic off-site + dead-man's-switch y Caddy endurecido.
- Anti-abuso en profundidad: django-axes respaldado por BD (compartido entre workers) con cooloff/reset-on-success, django-ratelimit + honeypot + doble opt-in en subscribe/submit, y límites de request en capas (Caddy corta cuerpos a 12MB en el borde, DATA_UPLOAD_MAX_*), con adjuntos privados fuera de MEDIA_ROOT y doble control @staff_member_required + is_editor.

## 4. Hallazgos confirmados (prioritarios)

Todos los candidatos a `high` se rebajaron a `medium` tras verificar contra el código; ninguno bloquea el sitio a su escala.

### 1. [🟡 medium] ISBN unique+null=True sin coerción ""→None: el 2.º Work sin ISBN provoca IntegrityError (500) en el admin

- **Evidencia:** reviews/models.py:59 CharField(max_length=20, unique=True, null=True, blank=True); Work no define save()/clean() y no hay forms.py ni form custom en el admin. El ModelForm por defecto guarda '' y Django excluye los campos opcionales vacíos de validate_unique(), así que el '' duplicado llega al INSERT y viola el UNIQUE de BD (migración 0001_initial.py:53). Como casi ningún poemario/plaquette lleva ISBN, es un caso frecuente, no un borde.
- **Recomendación:** Coercer ''→None en clean_isbn()/save() o, mejor, sustituir el unique=True plano por un UniqueConstraint parcial (condition=~Q(isbn='')) que expresa la clave candidata opcional.

### 2. [🟡 medium] Publicación programada con fallo silencioso: la transición 'schedule' no exige published_at

- **Evidencia:** workflow.py:24 'schedule' (APPROVED→SCHEDULED) pasa por perform_transition sin tratar published_at; models.py:85 published_at es null=True/blank=True sin CheckConstraint; admin.py:183-185 do_schedule no pasa por ModelForm (status es readonly, es la única vía). tasks.py:23-25 filtra status=SCHEDULED, published_at__lte=now(): con NULL esa comparación nunca es verdadera, la pieza queda SCHEDULED para siempre y jamás se publica, sin error, log ni alerta.
- **Recomendación:** Validar en la transición 'schedule' que published_at no sea None y sea futuro, rechazando con ValueError claro; cubrir con tests (programar sin fecha y con fecha pasada).

### 3. [🟡 medium] Confirmación de suscripción síncrona y con fail_silently: fallos de correo descartados y worker de gunicorn bloqueado

- **Evidencia:** community/views.py:56-69 _send_confirmation usa send_mail(fail_silently=True) en el hilo de la petición (invocado en views.py:51 dentro de subscribe); no hay ninguna tarea Celery de correo (la única shared_task es publish_due_items, tasks.py:6). Un SMTP lento/caído bloquea uno de solo 3 workers hasta 60s; un fallo de entrega se descarta sin excepción mientras el usuario ve 'Te enviamos un correo' y Sentry no lo capta. El comentario del worker (docker-compose.yml:49) atribuye un rol 'correo' que no está cableado.
- **Recomendación:** Mover el envío a una tarea Celery con reintento/backoff y, como mínimo, dejar de tragar el fallo (quitar fail_silently o logger.exception); corregir el comentario del worker si se difiere el cableado.

### 4. [🟡 medium] El healthcheck de web queda permanentemente 'unhealthy' en un deploy prod al pie de la letra (Host 127.0.0.1 → 400)

- **Evidencia:** docker-compose.prod.yml:41 sonda urlopen('http://127.0.0.1:8000/healthz/') (Host=127.0.0.1:8000); .env.prod.example:12 fija ALLOWED_HOSTS=revista.tudominio.cl (sin 127.0.0.1) y el guard de prod (settings.py:36-37) exige que no sea el default. Con DEBUG=0 la cadena get_host()→DisallowedHost→400→HTTPError→exit≠0 es determinista. El sitio sigue sirviéndose (Caddy usa el Host real; web no se publica al host; nada gatea sobre la salud), así que el daño es observabilidad engañosa, no caída.
- **Recomendación:** Enviar cabecera Host válida en la sonda (urllib Request headers={'Host': dominio}), o consultar por el nombre de servicio, o añadir 127.0.0.1 a DJANGO_ALLOWED_HOSTS documentándolo como requisito; verificar tras el cambio que el contenedor reporte 'healthy'.

### 5. [🟡 medium] django-ratelimit sobre LocMemCache por proceso: los límites de subscribe/submit se multiplican por worker y se reinician al recargar

- **Evidencia:** No existe bloque CACHES en todo backend/ → la cache 'default' es LocMemCache por proceso; Dockerfile:38 arranca gunicorn --workers 3. subscribe (community/views.py:26, 5/m) y submit (submissions/views.py:19, 10/h) aplican el corte realmente vía request.limited. Con 3 workers el límite efectivo por IP es ~3x el declarado y se pone a cero en cada redeploy; submit admite adjuntos de hasta 10 MB en disco, facilitando abuso de almacenamiento (django-axes no se ve afectado: usa handler de BD).
- **Recomendación:** Definir CACHES apuntando la cache 'default' (o una dedicada) a Redis —ya dependencia obligatoria en prod, URL derivada de REDIS_PASSWORD en settings.py:187-193— para contadores compartidos y persistentes entre workers.

### 6. [🟡 medium] poem_detail (y recording_detail) no caen al og:image por defecto del sitio

- **Evidencia:** poem_detail.html:10 usa solo '{% if poem.og_image %}…{% endif %}' sin rama de respaldo, mientras article_detail.html:10 y event_detail.html:11 sí tienen '{% elif site_profile.og_image %}'; recording_detail.html:10 tampoco tiene fallback. Un poema o registro sin imagen propia queda sin ninguna imagen social (ni la del sitio) y su twitter:card cae a 'summary' — precisamente el contenido central del colectivo y lo más compartido.
- **Recomendación:** Replicar '{% elif site_profile.og_image %}' de article_detail en poem_detail.html:10 y recording_detail.html:10, y poner twitter:card en summary_large_image cuando exista cualquiera de las dos imágenes.

### 7. [🟡 medium] El feed anunciado como 'Podcast RSS' no emite el namespace iTunes

- **Evidencia:** media/feeds.py RecordingsFeed hereda de django.contrib.syndication.views.Feed sin sobreescribir feed_type; solo añade enclosure (url/length/mime), sin itunes:image/author/category/explicit/summary ni itunes:duration. Se rotula 'Podcast RSS' (recording_index.html:8) y '(podcast)' (base.html:11). Apple Podcasts y la mayoría de agregadores rechazan o muestran incompleto un feed sin el namespace iTunes: funciona como RSS con enclosure pero no es distribuible como podcast pese a anunciarse así.
- **Recomendación:** Subclasear feed_type con un generador que declare xmlns:itunes y emita etiquetas de canal (itunes:image/author/category/explicit/summary) e ítem (itunes:duration), o ajustar el rótulo si no se pretende conformidad de podcast.

### 8. [🟡 medium] La portada, la página más enlazada, no tiene <h1>

- **Evidencia:** home.html: el hero (líneas 4-24) abre con <p class="hero-tagline"> y todo lo demás son <h2>; el nombre del sitio en el masthead es un <a class="brand"> (base.html:45), no un heading. grep '<h1' devuelve un h1 en TODAS las demás vistas (article_detail:36, poem_detail:19, recording_detail:18, agenda:7…) y CERO en home.html: rompe el patrón de un h1 por página, con impacto SEO y de navegación por encabezados para lector de pantalla.
- **Recomendación:** Añadir un <h1> en el hero con nombre del colectivo + tagline; si se quiere conservar la estética, un h1 con la clase de .hero-tagline o visualmente oculto (.sr-only, verificando que la utilidad exista en site.css).

### 9. [🟡 medium] No existe pipeline de CD: sin build/tag/push a registry ni ruta de rollback

- **Evidencia:** .github/workflows/ contiene un solo archivo (ci.yml); ningún job de release/deploy ni paso docker/build-push-action. La imagen prod endurecida (Dockerfile stage prod) y docker-compose.prod.yml existen, pero la construcción y publicación de imágenes es 100% manual: todo el rigor de hashes se pierde en el último tramo, sin imágenes inmutables etiquetadas ni ruta de rollback.
- **Recomendación:** Añadir un workflow de release que haga docker build --target prod ./backend, etiquete por git-sha + tag semántico, publique en GHCR y retenga las últimas N imágenes para rollback. A esta escala es opcional, pero cierra la reproducibilidad.

### 10. [🟡 medium] La imagen prod y el lockfile de runtime nunca se ejercitan en CI

- **Evidencia:** ci.yml:50 instala únicamente requirements-dev.txt (superconjunto dev+runtime) y ningún paso ejecuta docker build. El stage prod (Dockerfile:29 pip install --require-hashes -r requirements.txt; usuario non-root/entrypoint en líneas 32-37) jamás se construye ni arranca en CI, de modo que un hash faltante exclusivo de requirements.txt o una regresión de permisos/entrypoint llegarían a producción sin detección.
- **Recomendación:** Añadir un job/paso con docker build --target prod ./backend (barato) y, opcionalmente, levantar el contenedor con curl a /healthz/ como smoke de arranque del runtime real.

### 11. [🟡 medium] El piso de cobertura del 80% excluye config/ (incluida la middleware CSP crítica)

- **Evidencia:** pyproject.toml:13 fija source=['apps'] y ci.yml:76 corre --cov=apps --cov-fail-under=80, así que config/ queda fuera del denominador del gate; config/csp.py (78 LOC) y config/logformat.py SÍ tienen tests pero no cuentan hacia el 80%. Además [tool.coverage.run] no define branch=True: la medición es solo por líneas. Una regresión en la política CSP (seguridad) no movería la aguja del gate.
- **Recomendación:** Agregar 'config' a coverage.run.source y habilitar branch=True; mantener omit para wsgi/asgi/settings triviales si se desea.

## 5. Detalle por dimensión

### 5.1 Arquitectura, organización y mantenibilidad — `beta`

Monolito Django bien estratificado y de módulos pequeños (el mayor módulo de app, content/models.py, tiene 393 líneas; el único módulo grande es el comando de seed con 841). Las capas están claras: vistas delgadas, lógica de consulta en métodos de modelo (Event.upcoming/past, Contributor.members), un módulo de permisos dedicado, una máquina de estados editorial centralizada (workflow.py) compartida por Article y Poem vía la base abstracta EditorialItem, y config 100% dirigida por entorno con un guard de producción que rechaza arrancar con valores inseguros. Los dos hallazgos de arquitectura del audit previo están RESUELTOS: (1) ya no hay imports vista-a-vista entre apps —stats() se extrajo a agenda/services.py y content/showcase lo importan desde la capa de servicios— y (2) el invariante del singleton SiteProfile se aplica con load() en todos los puntos de lectura y el admin bloquea add/delete. Verifiqué por grep que TODO import inter-app es de models/services/permissions, nunca de views. Lo que resta es de cohesión/organización, no de corrección: showcase mezcla identidad global del sitio con catálogo/prensa/aliados; content actúa como hub transversal (sitemaps que importa las 8 apps, endpoints de salud/robots); y la capa de servicios/selectors se aplica de forma despareja (solo agenda la tiene, con lógica de dominio aún incrustada en varias vistas). Nada de esto bloquea producción, pero mantiene la dimensión en beta sólida en vez de producción plena.

**Hallazgos verificados:**

- **[⚪ low] (ajustado) Baja cohesión en showcase: identidad global del sitio convive con catálogo, prensa y aliados**
  - Verificado: showcase/models.py:4 SiteProfile, :67 SiteSocialLink, :82 Publication, :135 WhereToBuy, :154 PressMention, :187 Partner (todas las líneas exactas). SiteProfile.load() se consume por petición en showcase/context_processors.py:10 y lo importan apps hermanas: agenda/services.py:9 y content/views.py:10 hacen 'from apps.showcase.models import ... SiteProfile'.
  - → La extracción a una app siteconfig/core es una mejora razonable, pero de bajo retorno: (1) 'showcase' significa vitrina y agrupa la cara pública del colectivo (identidad + catálogo + prensa + dossier), un bounded-context defendible; el dossier() de la propia app consume SiteProfile intensamente. (2) Mover SiteProfile NO elimina el acoplamiento núcleo->showcase, porque content (home) y agenda (services/views/trayectoria) ya importan Publication desde showcase de todos modos. Priorizar solo si se acomete un reordenamiento mayor de fronteras.
  - _nota:_ Todos los hechos citados son exactos. Bajo a 'low' (estaba en medium): es un smell de cohesión sin impacto de correctitud, el patrón actual es defendible, y la dependencia núcleo->showcase persiste por Publication aunque se extraiga SiteProfile. Coherente con la severidad de los hallazgos hermanos.
- **[⚪ low] (confirmado) content funciona como agregador transversal y aloja endpoints de infraestructura ajenos al dominio editorial**
  - Verificado exacto: content/sitemaps.py:4-8 importa de agenda, media, people, reviews y showcase; content/views.py aloja healthz:202, _db_ok:207, _broker_ok:220, readyz:234 y robots:251 (rango 202-258 correcto); config/urls.py:9 'from apps.content.views import healthz, readyz, robots'.
  - → Mover el sitemap agregado, robots y healthz/readyz a una app core/seo transversal (o a config/). Deja content en el dominio editorial. Mejora de orden, no urgente.
  - _nota:_ Evidencia precisa y problema real hoy. Único matiz: 'casi todas las apps' es leve exageración (sitemaps toca 5 de 9 apps). Severidad low correcta: patrón Django defendible sin impacto funcional.
- **[⚪ low] (confirmado) Capa de servicios/selectors aplicada de forma despareja: lógica de dominio incrustada en vistas**
  - Verificado: solo existe backend/apps/agenda/services.py (find no halla otros services.py ni selectors.py). El timeline por año se arma en la vista (agenda/views.py:16-29, dentro de trayectoria()) y la mezcla curada artículos+poemas por position en content/views.py:136-148 (collection_detail). Los imports locales en showcase/views.py:42-44 (agenda.models, agenda.services, people.models) también confirmados.
  - → Extraer los helpers no triviales (timeline de trayectoria, mezcla de colección) a services/ de su app; hoistear los imports de showcase/views.py a nivel de módulo.
  - _nota:_ Confirmado, incluida la sub-afirmación de que los imports locales ya son innecesarios: showcase/models.py solo importa django.db.models, y agenda.services importa showcase.models (no showcase.views), así que subirlos a nivel de módulo no crea ciclo — de hecho content/views.py:8 y agenda/views.py:6 ya importan agenda.services a nivel de módulo sin problema. Low correcta.
- **[⚪ low] (confirmado) Singleton SiteProfile: lecturas redundantes por petición e invariante no forzado en BD**
  - Verificado: models.py:54-64 (save fija self.pk=1, delete() no-op, load() usa get_or_create(pk=1)). En /home, load() se ejecuta exactamente 3 veces: context_processors.py:10, content/views.py:43 (home), y agenda/services.py:16 dentro de stats(), invocada por home vía trajectory_stats() en content/views.py:64. Sin CheckConstraint en Meta; el admin sí bloquea add (has_add_permission, admin.py:23-25) y delete (has_delete_permission=False, :27-28).
  - → Cachear el perfil por request (atributo perezoso o pasarlo por el context ya cargado) para evitar los SELECT repetidos; opcionalmente añadir CheckConstraint(pk=1) para forzar el singleton en BD.
  - _nota:_ Confirmado con precisión: las 3 lecturas por /home y la ausencia de constraint son reales. Riesgo real bajo (el admin protege el caso normal); severidad low correcta.

### 5.2 Seguridad — `beta`

La dimensión de seguridad está muy por encima del promedio: autorización por objeto Y estado bien modelada (permissions.py + workflow.py con transacción atómica y select_for_update que revalida bajo lock, más bitácora inmutable), saneo XSS server-side con nh3 sobre lista blanca estricta, CSP con nonce por petición y script-src sin unsafe-inline, self-hosting real de htmx/TinyMCE (cero CDN), guard de arranque en producción que rechaza secretos de ejemplo, cabeceras completas (HSTS+preload, cookies seguras, nosniff, X-Frame DENY) verificadas por `check --deploy --fail-level WARNING` en CI, y anti-abuso en profundidad (django-axes respaldado por BD + django-ratelimit + honeypot + doble opt-in). La descarga de adjuntos privados tiene doble control (@staff_member_required + is_editor) y almacenamiento fuera de MEDIA_ROOT. Los residuos son concretos y acotados: (1) django-ratelimit se apoya en LocMemCache por proceso, por lo que con 3 workers los límites de subscribe/submit se multiplican y se reinician en cada recarga; (2) la validación de adjuntos es solo por extensión, sin comprobar contenido/MIME; (3) style-src conserva 'unsafe-inline'. Nada de esto es crítico, pero el punto (1) sí debilita el control anti-abuso en el despliegue multi-worker real, por lo que la dimensión es beta sólida, muy cerca de producción.

**Hallazgos verificados:**

- **[🟡 medium] (confirmado) django-ratelimit se apoya en LocMemCache por proceso: los límites de subscribe/submit se multiplican por worker y se reinician al recargar**
  - No existe bloque CACHES en todo backend/ (grep 'CACHES' sin resultados en .py) → la cache 'default' es LocMemCache por proceso. backend/Dockerfile:38 (y :24) ejecutan 'gunicorn --workers 3'. backend/apps/community/views.py:26 (@ratelimit key='ip' rate='5/m' block=False) y :32 (enforce vía getattr(request,'limited')); backend/apps/submissions/views.py:19 (rate='10/h') y :22 (enforce). Comentario settings.py:144-146 reconoce el tradeoff LocMem entre procesos.
  - → Definir CACHES apuntando la cache 'default' (o una dedicada) a Redis —ya dependencia obligatoria en producción, la URL se deriva de REDIS_PASSWORD en settings.py:187-193— para que los contadores de django-ratelimit sean compartidos entre workers y persistentes.
  - _nota:_ Verificado: todos los datos citados son exactos. La evidencia menciona 'ausencia de bloque CACHES' y lo confirmo (no hay CACHES en ningún .py de backend). Dockerfile:38 es la CMD final efectiva (hay una CMD previa en :24, misma configuración). El enforcement es real (no no-op): las vistas comprueban request.limited y cortan. Mantengo medium: técnicamente exacto y con vector de abuso de almacenamiento en submit; es degradación de defensa-en-profundidad, no una brecha directa, y hay mitigaciones parciales, por lo que no supera a medium.
- **[⚪ low] (confirmado) Validación de adjuntos solo por extensión y tamaño, sin verificar contenido/MIME**
  - backend/apps/submissions/forms.py:45-52: clean_file deriva la extensión con f.name.rsplit('.',1)[-1].lower() y compara f.size; no inspecciona bytes ni f.content_type. ALLOWED_EXTENSIONS en forms.py:5.
  - → Añadir verificación de firma/MIME (p. ej. python-magic sobre los primeros bytes) o validar f.content_type contra una lista blanca alineada con ALLOWED_EXTENSIONS, complementando la comprobación de extensión existente.
  - _nota:_ Verificado exacto en forms.py:45-52. Confirmadas además todas las mitigaciones que sostienen la severidad baja: private_storage en el modelo, guard staff_member_required+is_editor en la descarga, as_attachment=True y nosniff global. Severidad low correcta.
- **[⚪ low] (confirmado) CSP conserva style-src 'unsafe-inline' también en páginas públicas**
  - backend/config/csp.py:24: ('style-src', "'self' 'unsafe-inline'"). El ContentSecurityPolicyMiddleware (csp.py:43-78) aplica la política a todas las respuestas dinámicas por igual, sin diferenciar rutas. script-src se construye estricto: 'self' + nonce por petición, sin 'unsafe-inline' (csp.py:72-74).
  - → Considerar política diferenciada: style-src estricto (nonce/hash) en vistas públicas y relajado solo bajo /admin/, o migrar el estilo inline propio a hojas con nonce dejando 'unsafe-inline' acotado al panel de administración.
  - _nota:_ Verificado: la directiva es exacta y el middleware la aplica de forma global (no por ruta), luego el 'unsafe-inline' de estilo también cubre las páginas públicas. El tradeoff está documentado en el propio módulo. Severidad low correcta dado que script-src es estricto.
- **[⚪ low] (confirmado) Bloqueo de fuerza bruta de django-axes solo por IP, sin componente por cuenta**
  - backend/config/settings.py:137: AXES_LOCKOUT_PARAMETERS = ['ip_address']. AXES_FAILURE_LIMIT=5 (settings.py:135), COOLOFF 1h (:136), RESET_ON_SUCCESS (:138).
  - → Evaluar combinar parámetros (p. ej. ['ip_address','username']) o añadir umbral por cuenta, ponderando el efecto colateral de NAT compartido según la base de usuarios del admin.
  - _nota:_ Verificado exacto en settings.py:137. El backend de axes usa el handler de BD por defecto (no la cache), así que este control no se ve afectado por el problema de LocMem del hallazgo 1. Severidad low correcta para el tamaño del sitio.

### 5.3 Modelo de datos, BD y migraciones — `beta`

Es la dimensión más sólida del proyecto: diseño relacional genuinamente de nivel producción. Normalización 3NF real (Publisher/BookAuthor extraídos de Work, SocialLink des-JSON-ificado a 1NF), CheckConstraint XOR archivo/embed en Recording, UniqueConstraint en TODOS los puentes M2M, índices compuestos status/-published_at y GIN sobre search_vector, FTS mantenido por trigger de Postgres que dispara en toda escritura (incluye bulk_update) con backfill de filas existentes, y una migración expand/contract en 3 pasos con backward reversible que sirve de referencia. La bitácora editorial usa GenericForeignKey con GenericRelation (cascade por ORM) y object_id BigInteger que coincide con el BigAutoField del pk. Lo que impide llamarla producción es un bug de integridad concreto y alcanzable por el admin (ISBN unique+null=True sin coerción ""→None: el segundo Work sin ISBN revienta con IntegrityError) más pulido menor (falta índice compuesto en Event, cobertura del search_vector, búsqueda sin LIMIT). Ninguno afecta cimientos; corregido el ISBN queda esencialmente a nivel producción a su escala.

**Hallazgos verificados:**

- **[🟡 medium] (confirmado) ISBN unique+null=True sin coerción ""→None: el 2º Work sin ISBN revienta con IntegrityError**
  - backend/apps/reviews/models.py:59 (isbn = CharField(max_length=20, unique=True, null=True, blank=True)); el modelo Work no define save() ni clean() (grep sin coincidencias); no existe forms.py en backend/apps/reviews/ (solo admin, models, urls, views, migrations); WorkAdmin (reviews/admin.py:20-27) no define `form` custom, solo search_fields/list_display/prepopulated. Migración 0001_initial.py:53 confirma el UNIQUE + null a nivel BD.
  - → Coercer ''→None (clean_isbn()/save() o un campo custom), o mejor sustituir el `unique=True` plano por un UniqueConstraint parcial (condition=~Q(isbn='')) que expresa la semántica de clave candidata opcional. Confirmado tal cual el hallazgo original.
  - _nota:_ Confirmado en severidad y sustancia. La única vía que podría haberlo refutado —que el ModelForm del admin mostrara un error de validación amigable en vez de un 500— queda descartada: Django excluye los campos opcionales vacíos de validate_unique(), así que el '' duplicado alcanza la BD y el constraint dispara IntegrityError. Medium es apropiado (rompe un flujo editorial habitual, aunque solo en el admin, no en el sitio público).
- **[⚪ low] (confirmado) Event carece de índice compuesto (published, starts_at) pese a ser su patrón de consulta caliente**
  - backend/apps/agenda/models.py:63-70: upcoming() filtra published=True + starts_at__gte y ordena por 'starts_at'; past() filtra published=True + starts_at__lt. starts_at tiene db_index=True (:25); published (:42) es BooleanField sin index; Meta (:45-48) solo define ordering/verbose_name, sin `indexes`. Contraste real: Article.Meta (content/models.py:138) y Poem.Meta (:229) sí tienen models.Index(fields=['status','-published_at']).
  - → Añadir models.Index(fields=['published','starts_at']) (o variante con -starts_at para el orden descendente de past()) en Event.Meta.indexes, replicando el criterio de los EditorialItem. Confirmado.
  - _nota:_ Evidencia exacta. Es deuda de consistencia real, no un bug. Low es la severidad correcta.
- **[⚪ low] (ajustado) Cobertura del search_vector: omite epigraph del poema (válido) e indexa HTML crudo del artículo (sobredimensionado)**
  - backend/apps/content/migrations/0009_search_vector_triggers.py:22-25: el trigger de Poem cubre solo title, body — NO epigraph (definido en content/models.py:201 como texto autoral). :11-13: el trigger de Article cubre title, subtitle, body, donde body es HTML saneado por clean_html (content/models.py:152) que preserva etiquetas (<p>,<a>,<img>,<blockquote>… ver sanitize.ALLOWED_TAGS).
  - → Incluir epigraph en el trigger de Poem si se considera contenido buscable (fix real y de bajo costo). Para Article, NO hace falta desetiquetar por ruido de URLs: el parser ya descarta tags/entidades; a lo sumo documentar que el vector se calcula sobre el HTML saneado. Recomendación recortada respecto de la original.
  - _nota:_ Ajustado: la mitad válida es el epígrafe no indexado (recall); la mitad del HTML/URLs está sobredimensionada porque el propio comportamiento del parser de Postgres que el hallazgo cita ('descarta los tokens de etiqueta') también descarta los atributos href/src dentro del tag y las entidades. Severidad se mantiene en low; el impacto real se reduce a un pequeño hueco de recall en el epígrafe.
- **[⚪ low] (confirmado) Buscador sin LIMIT en BD: trae todos los matches, los fusiona y ordena en Python; arrastra prefetch de authors no usado**
  - backend/apps/content/views.py:167-194: `articles` y `poems` se filtran por search_vector y se anotan con rank, sin slice en BD; se concatenan en una lista Python y se hace sorted(items, key=rank, reverse=True)[:10]. Ambos parten de _published()/_published_poems() (:26-35) que traen select_related('section') + prefetch_related('authors'); la vista de búsqueda solo lee slug, title, get_type_display() y rank — nunca toca authors ni section.
  - → Aplicar .order_by('-rank')[:N] a cada queryset en BD (el top-N global es subconjunto de la unión de los top-N por tipo, así que el merge+[:10] sigue siendo correcto) y usar .only('slug','title','type') sin el prefetch de authors para búsqueda. Confirmado.
  - _nota:_ Evidencia exacta; el prefetch de authors es gasto real e inútil aquí. Low es correcto: es optimización preventiva, no un fallo.
- **[⚪ low] (confirmado) La bitácora editorial no tiene integridad referencial ni append-only a nivel BD; token de newsletter sin unique/índice**
  - backend/apps/content/models.py:349-350 (docstring 'Rastro inmutable') y :356-358/:382-384 (EditorialTransition/EditorialNote con content_type FK + object_id PositiveBigIntegerField vía GenericForeignKey — sin FK real a Article/Poem). El cascade por ORM existe (EditorialItem declara GenericRelation en :91-92), pero no hay constraint de BD ni trigger que impida UPDATE/DELETE ni object_id colgados por escrituras fuera del ORM. community/models.py:14: token = CharField(max_length=64, blank=True) sin unique ni db_index; se genera con secrets.token_urlsafe(32) (community/views.py:48) y se busca con .filter(token=token).first() (:19).
  - → Documentar explícitamente el tradeoff del GFK; para inmutabilidad real, readonly_fields en el admin y/o trigger que rechace UPDATE/DELETE; añadir db_index (y opcionalmente unique) a NewsletterSubscriber.token. Confirmado.
  - _nota:_ Confirmado; toda la evidencia verifica. Matiz: el sub-punto del token es muy menor — el scan es sobre tabla pequeña y la colisión con token_urlsafe(32) es despreciable, de modo que el índice es más higiene que necesidad. El bloque es un paquete de tradeoffs de diseño correctamente etiquetado como low / 'a tener presente', no fallos activos.

### 5.4 Pruebas, CI/CD y reproducibilidad — `beta`

La mitad de "CI + reproducibilidad" está a nivel producción: lockfiles con hashes instalados con --require-hashes en CI y Dockerfile (229 hashes en requirements.txt, 350 en requirements-dev.txt), pip-audit bloqueante con un único ignore documentado (dev-only), check --deploy --fail-level WARNING con env de producción real, makemigrations --check, umbral de cobertura al 80%, Dependabot (pip+actions+docker con agrupación y pines LTS), pre-commit con ruff fijado a la versión del lockfile, y servicios reales (postgres:16/redis:7 con healthchecks). La suite es amplia y bien pensada: 179 tests en 27 archivos que cubren flujo editorial+bitácora, permisos por estado, CSP/nonce/self-host, FTS-htmx (incluido el trigger que sigue bulk-update), anti-abuso (axes+ratelimit), idempotencia/TOCTOU de Celery, readiness y sanitización XSS. Lo que baja la nota de producción a beta es que el CD no existe en absoluto (sin build/tag/push/registry/rollback), la imagen prod y el lockfile de runtime nunca se ejercitan en CI, el piso de cobertura excluye config/ (incluida la middleware CSP crítica), no hay e2e y hay fragilidad de aserciones (bytes UTF-8 crudos + acoplamiento a copy).

**Hallazgos verificados:**

- **[🟡 medium] (ajustado) No existe pipeline de CD: sin build/tag/push a registry ni rollback**
  - .github/workflows/ contiene un solo archivo (ci.yml). No hay ningun workflow de release/deploy ni paso docker/build-push-action; un grep de deploy/registry/ghcr/build-push en .github/ solo hace match con texto de ci.yml ('push:' trigger en la linea 4 y 'check --deploy' en la 88), no con un job de despliegue real. Existe docker-compose.prod.yml y Dockerfile con stage prod endurecido, pero la construccion/publicacion de imagenes es 100% manual.
  - → Agregar un workflow de release que haga `docker build --target prod ./backend`, etiquete por git-sha y tag semantico, publique en un registry (p.ej. GHCR) y retenga las ultimas N imagenes para rollback. El compose de prod ya asume la imagen endurecida.
  - _nota:_ El hecho es real y verificado: no hay CD alguno. Rebajo de high a medium: para un sitio de un colectivo de poesia (audiencia de pares/gestores, despliegue por compose a pequena escala) la ausencia de imagenes inmutables etiquetadas y ruta de rollback es una brecha legitima de reproducibilidad, pero no un riesgo alto de produccion. La observacion 'todo el rigor de hashes se pierde en el ultimo tramo' es correcta y pertinente.
- **[🟡 medium] (confirmado) La imagen prod y el lockfile de runtime nunca se ejercitan en CI**
  - ci.yml:50 instala unicamente `pip install --require-hashes -r backend/requirements-dev.txt` (superconjunto dev+runtime) y en ningun paso del workflow se ejecuta `docker build`. El stage prod del Dockerfile (linea 29) hace `pip install --require-hashes -r requirements.txt` y define usuario non-root/entrypoint (lineas 32-37) que jamas se construyen ni arrancan en CI.
  - → Anadir un job/paso en CI con `docker build --target prod ./backend` (barato) y, opcionalmente, levantar el contenedor y hacer curl a /healthz/ para un smoke de arranque del runtime real.
  - _nota:_ Confirmado exactamente. El superconjunto dev enmascara un hash faltante o conflicto de resolucion exclusivo de requirements.txt, y regresiones del stage prod (permisos, entrypoint, non-root) llegarian a produccion sin deteccion. Severity medium adecuada.
- **[🟡 medium] (confirmado) El piso de cobertura del 80% excluye config/ (incluida la middleware CSP critica)**
  - pyproject.toml:13 fija `source = ["apps"]` y ci.yml:76 corre `pytest --cov=apps ... --cov-fail-under=80`, por lo que config/ queda fuera del denominador del gate. config/csp.py son 78 LOC (verificado con wc) y esta ejercitado por tests/test_security_csp.py (importa ContentSecurityPolicyMiddleware); config/logformat.py por tests/test_observability.py (importa JsonFormatter). Ademas [tool.coverage.run] NO define branch=True (verificado: sin clave 'branch' en pyproject.toml), asi que la medicion es solo por lineas.
  - → Agregar "config" a coverage.run.source y habilitar branch=True; mantener exclusiones de wsgi/asgi/settings triviales via omit si se desea.
  - _nota:_ Confirmado en todos los puntos. Aunque csp.py y logformat.py SI tienen tests, no cuentan hacia el gate del 80%, de modo que una regresion en la politica CSP (seguridad) no moveria la aguja. La falta de branch=True es real. Severity medium se sostiene por el caracter de seguridad de la CSP.
- **[⚪ low] (ajustado) Aserciones fragiles: literales de bytes UTF-8 crudos y acoplamiento a copy de la UI**
  - Los 4 casos citados son exactos: test_ia.py:43 `b"Poes\xc3\xada desde el desierto."`, test_search.py:79 `b"Rese\xc3\xb1a bulk"`, test_antiabuse.py:33 `b"Demasiados intentos"`, test_antiabuse.py:47 `b"demasiadas propuestas"`. Un grep de `b"...\x.."` en tests/ arroja 26 coincidencias, pero 2 son firmas binarias legitimas y NO copy fragil: test_seed_photos.py:31 `b"\xff\xd8\xff"` (firma JPEG) y test_submissions.py:41 `b"MZ\x90"` (magic de .exe). El patron mas limpio `.encode()` aparece 18 veces en la suite, confirmando la mezcla inconsistente.
  - → Usar `.encode()`/decodificar `resp.content` y comparar strings, o assertContains; extraer las cadenas de copy de la UI (avisos de rate-limit, etc.) a constantes compartidas con plantillas/vistas.
  - _nota:_ Real, mantengo low. Ajusto el conteo: son ~24 aserciones de copy con escapes UTF-8 crudos, no 26 — dos de las coincidencias son magic-bytes binarios correctos que no deben tocarse. El acoplamiento a texto exacto de UI (test_antiabuse) y los literales `\xc3\x..` ilegibles son la fragilidad real.
- **[⚪ low] (confirmado) Herramientas del gate de CI instaladas sin hashes, rompiendo la reproducibilidad del propio CI**
  - ci.yml:49 `python -m pip install --upgrade pip` y ci.yml:60 `pip install pip-audit` se instalan sin fijar version ni hash, fuera del flujo --require-hashes. Verificado que pip-audit NO figura en ningun lockfile (requirements.in/.txt ni requirements-dev.in/.txt).
  - → Fijar pip-audit (y opcionalmente pip) en requirements-dev.in o en un constraints file e instalarlo con hashes junto al resto del lockfile.
  - _nota:_ Confirmado. La auditoria pip-audit es bloqueante (ci.yml:67) pero la herramienta que la ejecuta se resuelve a la ultima version sin verificar, lo que hace no-determinista el propio gate de seguridad. Severity low correcta (impacto en reproducibilidad del CI, no de produccion).
- **[⚪ low] (confirmado) Sin pruebas end-to-end/navegador para los flujos htmx**
  - Busqueda de playwright/selenium/cypress en todo el backend (*.py, *.txt, *.in, *.toml, *.yml) devuelve vacio. Los flujos htmx (busqueda en vivo, alta de newsletter, rate-limit) se verifican solo a nivel de cuerpo de respuesta en tests/test_search.py y tests/test_antiabuse.py; no hay driver de navegador.
  - → Anadir un smoke e2e delgado (p.ej. playwright) sobre 2-3 flujos criticos: busqueda en vivo, suscripcion y detalle publicado.
  - _nota:_ Confirmado. Regresiones de integracion htmx/JS (targets de swap, atributos hx-*, orden de eventos) no se detectan con asserts de bytes sobre resp.content. Severity low es adecuada para el tamano del proyecto (esfuerzo L); es una brecha de confianza real de navegador, no un defecto activo.

### 5.5 Frontend, UX, SEO y accesibilidad — `beta`

La capa de presentación está muy por encima del promedio para un proyecto de este tamaño: plantillas semánticas, imágenes responsivas de verdad (inclusion tag responsive_img con srcset generado por Pillow, width/height anti-CLS, decoding async y escape lazy=False para el LCP), JSON-LD para Organization/Article/Event con nonce CSP, 12 sitemaps + robots.txt dinámico, feeds RSS y de audio, dark mode, print styles, skip link, :focus-visible global, buscador htmx con región aria-live y un lightbox 'honesto' bien razonado. El diseño defensivo del modelo MediaAsset (srcset() solo lista derivados existentes, ensure_derivatives tolerante a fallos y sin upscaling) es nivel producción. Lo que la mantiene en 'beta' y no en 'producción' son huecos concretos y acotados: la portada (la página más importante) no tiene <h1>; el buscador en vivo no tiene ningún estado de error de red pese a ser un foco explícito; el og:image por defecto se aplica en artículo y evento pero NO en poema (el contenido central del sitio); y el feed anunciado como 'Podcast RSS' no emite el namespace iTunes que exigen Apple/Spotify. Ninguno es estructural: son ajustes S/M sobre una base sólida.

**Hallazgos verificados:**

- **[🟡 medium] (confirmado) La portada no tiene <h1>**
  - backend/templates/content/home.html: el hero (líneas 4-24) abre con <p class="hero-tagline"> y todo lo demás son <h2>/<h2 class="subhead"> (líneas 30,35,48,59,71,79,91,104). El nombre del sitio en el masthead es un <a class="brand"> (base.html:45), no un heading. grep '<h1' sobre backend/templates/ devuelve un h1 en TODAS las demás vistas (article_detail:36, poem_detail:19, recording_detail:18, agenda:7, etc.) y CERO en home.html.
  - → Añadir un <h1> en el hero con nombre del colectivo + tagline; si se quiere conservar la estética, un h1 con la clase de .hero-tagline o un h1 visualmente oculto (.sr-only). Nota: verificar que exista una utilidad .sr-only en site.css antes de recomendarla (no la revisé aquí).
  - _nota:_ Verificado línea por línea: home.html no contiene ningún h1 y todas las demás plantillas sí. El problema es real hoy. Severidad medium adecuada por ser la página principal y por la inconsistencia con el patrón del resto del sitio.
- **[🟡 medium] (confirmado) poem_detail no cae al og:image por defecto del sitio**
  - backend/templates/content/poem_detail.html:10 usa solo '{% if poem.og_image %}…{% endif %}' sin rama de respaldo. En cambio article_detail.html:10 y event_detail.html:11 sí tienen '{% elif site_profile.og_image %}…{% endif %}'. El twitter:card de poem_detail:13 cae a 'summary' cuando no hay og_image.
  - → Replicar '{% elif site_profile.og_image %}' de article_detail.html en poem_detail.html:10, y poner twitter:card en summary_large_image cuando exista cualquiera de las dos imágenes.
  - _nota:_ Confirmado: la rama elif existe en article y event pero no en poem. Dato adicional relevante: recording_detail.html:10 TAMPOCO tiene el fallback (usa solo recording.poster), así que el mismo patrón falta en dos plantillas de contenido primario, no solo en poem. Severidad medium se sostiene por ser contenido central + patrón sibling establecido.
- **[🟡 medium] (confirmado) El feed 'Podcast RSS' no emite el namespace iTunes**
  - backend/apps/media/feeds.py: RecordingsFeed hereda de django.contrib.syndication.views.Feed, no sobreescribe feed_type y solo añade enclosure (item_enclosure_url/length/mime_type). No hay itunes:image/author/category/explicit/summary ni itunes:duration. Se rotula 'Podcast RSS' en recording_index.html:8 y '(podcast)' en base.html:11.
  - → Subclasear feed_type con un generador que declare xmlns:itunes y emita etiquetas de canal (itunes:image/author/category/explicit/summary) e ítem (itunes:duration), o usar una utilidad de feed podcast. Alternativa: ajustar el rótulo si no se pretende conformidad.
  - _nota:_ Verificado en feeds.py y en los dos rótulos ('Podcast RSS' y 'podcast'). El mismatch entre lo anunciado y lo emitido es real. Medium adecuado: mismatch funcional (no distribuible como podcast) más que estético.
- **[⚪ low] (ajustado) El buscador en vivo no tiene estado de error de red**
  - backend/templates/base.html:46-56: el input lleva hx-get/hx-trigger/hx-target/hx-indicator pero ningún hx-on::responseError ni htmx:sendError. grep de 'responseError|hx-on|sendError|htmx:response|htmx:send|htmx:error' sobre backend/templates/ (excluyendo el vendor) = 0 resultados; no hay handler global. Ante 5xx o fallo de red htmx no hace swap por defecto y #search-results (región aria-live) queda con contenido previo/vacío sin mensaje.
  - → Añadir un handler mínimo (hx-on="htmx:responseError: …; htmx:sendError: …") que pinte un mensaje discreto en #search-results (p. ej. 'No se pudo buscar, reintenta').
  - _nota:_ El hecho es correcto y verificado, pero la severidad medium estaba inflada: es un fallo silencioso de una función auxiliar de mejora progresiva, solo en escenarios de error. Ajustado a low. Que la búsqueda dependa por completo de htmx se solapa con el hallazgo del fallback sin JS.
- **[⚪ low] (confirmado) El buscador no tiene fallback sin JavaScript ni página de resultados**
  - backend/templates/base.html:46 el <form role="search"> apunta a action={% url 'content:home' %} por GET con name="q". La vista home (backend/apps/content/views.py:42-69) NO lee request.GET['q'] (solo _paginate usa 'page'); grep confirma que 'q' solo se usa en search() (views.py:163). search() (views.py:161-199) renderiza content/partials/_search_results.html, un partial, no una página completa.
  - → Hacer que home (o una ruta /buscar/) renderice resultados de página completa cuando llega q, reutilizando la consulta FTS de search(); el partial htmx sigue igual para la mejora progresiva.
  - _nota:_ Confirmado leyendo la vista home completa y search(). Home no procesa q en absoluto. Low es correcto: es una brecha de mejora progresiva.
- **[⚪ low] (confirmado) Los campos del formulario de envío no enlazan errores ni ayuda por ARIA**
  - backend/templates/submissions/submit.html:17 <form … novalidate>; el bucle de campos (líneas 25-33) renderiza el widget con '{{ field }}', el help_text en <small> (línea 31) y los errores en <p class="error"> (línea 32) adyacentes, pero el input no lleva aria-invalid ni aria-describedby apuntando a esos textos. La asociación label/for sí está resuelta (línea 27, for="{{ field.id_for_label }}").
  - → Renderizar cada campo con aria-invalid cuando tenga errores y aria-describedby apuntando a los id del help y de los mensajes de error (ids estables por campo). Como el template usa '{{ field }}', esto probablemente requiere ajustar el widget en el Form (attrs) o el partial de render.
  - _nota:_ Confirmado en el template. La observación de que label/for está bien es correcta. Low adecuado.
- **[⚪ low] (confirmado) Falta soporte de prefers-reduced-motion**
  - backend/static/css/site.css:50 (.htmx-indicator … transition:opacity .2s) y :75 (.skip … transition:top .15s). grep de 'prefers-reduced-motion' sobre site.css = 0 resultados; grep de 'animation' = 0 (no hay @keyframes). No existe ningún bloque @media (prefers-reduced-motion: reduce).
  - → Añadir @media (prefers-reduced-motion: reduce){ *{transition:none!important; animation:none!important} } al final de site.css.
  - _nota:_ Confirmado: solo esas dos transiciones y cero @media reduce. Low correcto (hueco a11y menor).
- **[⚪ low] (confirmado) Poemas y registros no tienen JSON-LD**
  - grep 'ld+json' sobre backend/templates/ solo encuentra base.html (Organization), content/article_detail.html (Article) y agenda/event_detail.html (Event). backend/templates/content/poem_detail.html y backend/templates/media/recording_detail.html no incluyen ningún bloque application/ld+json.
  - → Añadir CreativeWork (author, datePublished) en poem_detail y PodcastEpisode/AudioObject (associatedMedia/contentUrl, duración) en recording_detail, con el mismo patrón de nonce y |escapejs ya usado en article_detail/event_detail.
  - _nota:_ Confirmado por grep. Low adecuado: los datos estructurados son una mejora, no un requisito funcional.
- **[⚪ low] (confirmado) srcset() consulta storage.exists() en cada render, sin caché**
  - backend/apps/media/models.py:104 srcset() itera SRCSET_WIDTHS=(480,960,1440) (models.py:15) y por cada ancho menor que la imagen llama self.file.storage.exists(name) (línea 115) — hasta 3 exists() por imagen y por render. La inclusion tag responsive_img (backend/apps/media/templatetags/images.py) invoca asset.srcset() en cada uso, y las grillas iteran N imágenes. No hay caché del resultado.
  - → Persistir qué derivados existen al guardar (campo/manifiesto) en lugar de stat-ear en cada render, o cachear el resultado de srcset() por asset.
  - _nota:_ Verificado: exists() en el bucle de srcset (además de en la generación de derivados). 'Hasta 3 veces' es exacto para imágenes con width > 1440. Low correcto; el propio hallazgo reconoce que es riesgo latente con el storage actual.
- **[⚪ low] (confirmado) El canonical incluye la query string completa**
  - backend/templates/base.html:9 <link rel="canonical" href="{{ request.build_absolute_uri }}">, que arrastra todos los GET (incluidos utm_*). Además og:url (base.html:15) tiene el mismo problema.
  - → Construir el canonical desde request.build_absolute_uri(request.path) (más, si acaso, un whitelist como page) para descartar tracking; mismo tratamiento para og:url (base.html:15).
  - _nota:_ Confirmado en base.html:9. Dato adicional: og:url en base.html:15 usa idéntico build_absolute_uri, así que el mismo tracking se filtra también a Open Graph. Low correcto (matiz SEO).

### 5.6 Producción/DevOps y lógica de negocio/asincronía — `beta`

Dimensión mayoritariamente madura. La corrección de concurrencia de Celery está resuelta de forma sólida y probada: tanto perform_transition (workflow.py:60-79) como publish_due_items (tasks.py:6-47) usan transaction.atomic + select_for_update + re-verificación autoritativa del estado bajo lock, cerrando el TOCTOU entre editores y entre el beat y una publicación manual; la tarea añade acks_late + autoretry_for(OperationalError) + backoff y es idempotente ante doble beat/reintento (tests en test_workflow.py:83,95). El endurecimiento operativo es real: Docker multi-stage non-root uid 1000 con --require-hashes, healthchecks bien pensados que distinguen cuelgue de caída (worker por 'celery inspect ping' vía broker, beat por mtime del schedule), Redis noeviction + requirepass obligatorio en prod, /readyz/ que verifica BD+broker con 503, logging JSON, Sentry opt-in sin PII, respaldos con off-site restic y dead-man's-switch, y una cadena de suministro con lockfiles+hashes, pip-audit bloqueante y check --deploy en CI. No encontré carreras/TOCTOU pendientes en el workflow ni en la tarea. Lo que separa esta dimensión de 'produccion' son tres huecos operativos concretos: el healthcheck de web queda permanentemente 'unhealthy' en un despliegue prod hecho al pie de la letra (Host 127.0.0.1 no está en ALLOWED_HOSTS → 400), la publicación programada tiene un estado atascado silencioso (schedule no valida published_at), y el correo es síncrono con fail_silently (la función 'correo' del worker no está implementada). Ninguno tumba el sitio, pero sí anulan señales/flujos que el propio endurecimiento pretendía garantizar.

**Hallazgos verificados:**

- **[🟡 medium] (ajustado) El healthcheck de web queda permanentemente 'unhealthy' en un despliegue prod al pie de la letra (Host 127.0.0.1 no está en ALLOWED_HOSTS → 400)**
  - docker-compose.prod.yml:41 sonda `urllib.request.urlopen('http://127.0.0.1:8000/healthz/')` (Host que se envía = 127.0.0.1:8000). backend/config/settings.py:22 ALLOWED_HOSTS viene de env; settings.py:36-37 el guard de prod obliga a que DJANGO_ALLOWED_HOSTS NO sea el default, y .env.prod.example:12 lo fija en `revista.tudominio.cl` (sin 127.0.0.1). Con DEBUG=0 (compose línea 32), Django valida el Host. La exención de redirect SSL en settings.py:208 (SECURE_REDIRECT_EXEMPT healthz/readyz) confirma que se pensó la sonda interna, pero no se exentó la validación de host.
  - → Corregir la sonda para no depender de la validación de host: enviar cabecera Host válida (urllib con Request(headers={'Host': dominio})), o consultar por el nombre de servicio, o añadir 127.0.0.1 a DJANGO_ALLOWED_HOSTS en .env.prod.example documentándolo como requisito de la sonda, o exentar /healthz/ de la validación de host. Verificar tras el cambio que el contenedor reporta 'healthy'.
  - _nota:_ Confirmado en el código; la cadena get_host()→DisallowedHost→400→HTTPError→exit≠0 es determinista y ocurre siempre en un deploy siguiendo .env.prod.example. Celery/Django reales: Django 5.2.16 (CommonMiddleware.process_request llama get_host() incondicionalmente en 5.x). Ajusto la severidad de high a medium porque el impacto está acotado a una señal de salud falsa: el servicio no cae, nada gatea sobre la salud, y restart:unless-stopped no reinicia por unhealthy.
- **[🟡 medium] (confirmado) La publicación programada tiene un estado atascado silencioso: 'schedule' no valida published_at**
  - backend/apps/content/workflow.py:24 transición 'schedule' ({APPROVED}→SCHEDULED) que recorre la ruta genérica perform_transition (líneas 60-79) sin tratar published_at (published_at solo se autoasigna al pasar a PUBLISHED, líneas 69-70). backend/apps/content/admin.py:183-185 do_schedule ejecuta _run→perform_transition directamente (la acción masiva no pasa por ModelForm; además `status` es readonly en el admin, get_readonly_fields:146-153, así que programar SIEMPRE va por la acción). backend/apps/content/models.py:85 published_at es null=True/blank=True y no hay CheckConstraint que lo ate a SCHEDULED (los constraints en models.py son únicos de tablas puente). backend/apps/content/tasks.py:23-25 filtra status=SCHEDULED, published_at__lte=now().
  - → Validar en la transición 'schedule' (dentro de perform_transition para ese nombre) que published_at no sea None y sea futuro; rechazar con ValueError claro. Cubrir con tests: programar sin fecha y con fecha pasada.
  - _nota:_ Confirmado. Verifiqué que no existe clean() ni CheckConstraint que impida SCHEDULED con published_at NULL, y que la acción del admin no pasa por validación de formulario (status es readonly, la transición es la única vía). Severidad medium adecuada.
- **[🟡 medium] (confirmado) El correo es síncrono y se traga los fallos (fail_silently); la función 'correo' del worker no está implementada**
  - backend/apps/community/views.py:56-69 _send_confirmation usa send_mail(..., fail_silently=True) (línea 68) y se invoca en el hilo de la petición (línea 51 dentro de subscribe). docker-compose.yml:49 comenta 'Worker de Celery (correo, publicación programada)'. grep confirma que en backend/apps/community NO hay shared_task/.delay/apply_async; la única tarea Celery del backend es publish_due_items (backend/apps/content/tasks.py:6). docker-compose.prod.yml:19-22 gunicorn con --workers 3 (default) y --timeout 60.
  - → Mover el envío a una tarea Celery (con reintento/backoff) y, como mínimo, dejar de tragar el fallo: registrar logger.exception o quitar fail_silently para que Sentry lo capture. Corregir el comentario del worker si se difiere el cableado.
  - _nota:_ Confirmado punto por punto: fail_silently=True presente, send_mail síncrono en la vista, cero tareas Celery de correo, comentario del worker engañoso, y worker/timeout tal como se citan. Severidad medium adecuada.
- **[⚪ low] (confirmado) Los healthchecks no tienen remediación automática: un worker/beat colgado-pero-vivo se queda caído hasta intervención manual**
  - docker-compose.prod.yml restart: unless-stopped en todos los servicios (líneas 35, 51, 65, 76, 84, 102) junto a healthchecks de worker (52-59) y beat (66-73). grep confirma que NO hay servicio autoheal/willfarrell en ningún compose.
  - → Añadir un sidecar tipo autoheal (reinicia contenedores unhealthy) o desplegar bajo un orquestador con gating de salud; si se mantiene compose plano, documentar que la salud debe vigilarse externamente (p. ej. monitor de uptime contra /readyz/).
  - _nota:_ Confirmado. Verifiqué la ausencia total de autoheal en los compose y las políticas restart:unless-stopped. Es correcto que Docker Compose no reinicia por estado unhealthy. Severidad low adecuada.
- **[⚪ low] (confirmado) Backend de resultados de Celery retenido sin uso y broker_connection_retry_on_startup sin fijar**
  - backend/config/settings.py:193 CELERY_RESULT_BACKEND definido (redis .../1), 195-200 beat cada 60s (publish_due_items), y ausencia de CELERY_TASK_IGNORE_RESULT / CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP en settings.py. requirements.txt:21 celery==5.6.3.
  - → Fijar CELERY_TASK_IGNORE_RESULT=True (o ignore_result=True en la tarea) y CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=True.
  - _nota:_ Confirmado, incluida la versión (celery==5.6.3, la mención a '5.6' es exacta). Matiz: backend y broker son la misma instancia Redis pero DBs distintas (1 vs 0); ambos bajo la política noeviction del compose. Es un nit real de mantenimiento; low adecuada.
- **[⚪ low] (confirmado) /readyz/ es público y sin límite de tasa: expone el estado de la infraestructura y toca BD/broker en cada llamada**
  - backend/config/urls.py:15 path('readyz/', readyz) sin autenticación ni throttling. backend/apps/content/views.py:234-248 readyz llama _db_ok (SELECT 1, líneas 207-217) y _broker_ok (redis.from_url + PING, líneas 220-231) en cada request. infra/caddy/Caddyfile: `reverse_proxy web:8000` captura todo salvo /media/*, así que /readyz/ queda expuesto públicamente por el proxy.
  - → Restringir /readyz/ a la red interna en Caddy o exigir token/limitar por tasa; mantener /healthz/ público y barato para la sonda del contenedor.
  - _nota:_ Confirmado: verifiqué en el Caddyfile que el proxy reenvía todo a web (no restringe /readyz/), y que readyz efectivamente ejecuta SELECT 1 y PING sin protección. Severidad low adecuada.

## 6. Ángulos fuera del alcance técnico (crítico de completitud)

- Legal/privacidad no es una de las 6 dimensiones ni aparece en top_findings, pese a ser un sitio que capta PII (correos de suscriptores, y nombre+correo+manuscrito en envios). No se evalua: base de licitud/consentimiento, retencion/borrado (los PENDING que nunca confirman y los Submission RECHAZADOS se guardan indefinidamente, sin purga), ni que la pagina 'privacidad' (migracion 0007_legal_pages) cita solo la Ley 19.628 y NO la Ley 21.719 de proteccion de datos vigente en 2026. Ademas el formulario de envios (submit.html) NO lleva la nota de consentimiento/enlace a privacidad que si tiene el de suscripcion (test_newsletter.py:70), y es el formulario con datos mas sensibles.
- Correo transaccional / entregabilidad no auditado: SPF/DKIM/DMARC, alineacion del dominio de DEFAULT_FROM_EMAIL (settings.py:231 'no-reply@resenas.cl'), cabecera List-Unsubscribe (+ One-Click RFC 8058) y manejo de rebotes. Todo el doble opt-in depende de que el correo de confirmacion llegue a la bandeja; si cae en spam, el flujo entero se rompe silenciosamente. La sintesis solo trata el correo desde la concurrencia/fail_silently, no desde la deliverability.
- DR/continuidad se afirma como fortaleza (restic off-site + dead-man's-switch + restore.sh) pero sin evidencia de un restore EJERCITADO ni RTO/RPO declarados; docs/respaldos.md:85 marca la prueba de restauracion como 'obligatoria' y aun asi el propio repo tiene backups/ locales (db.dump + private_media.tar.gz) que la .gitignore prohibe. La continuidad se asume, no se verifica.
- Rendimiento MEDIDO y e2e ausentes: mas alla del fix N+1 de imagenes no hay presupuesto de consultas, ni carga (locust/k6), ni Lighthouse/axe automatizado; 'anti-CLS' y 'a11y honesta' se asientan sin medicion. Tampoco hay test e2e del camino asincrono completo (beat -> publish_due_items -> pieza visible), justamente donde viven dos de los fallos silenciosos hallados.
- Coste/sostenibilidad (VPS + SMTP + off-site + Sentry) no estimado; es relevante para un colectivo y esta flagged en la auditoria previa del propio proyecto (docs/auditoria-mvp.md:271) pero ausente de esta sintesis.
- Seguridad de la cadena de CI mas alla de pip-audit: no hay SAST (bandit/semgrep/CodeQL), ni escaneo de secretos (gitleaks/trufflehog), ni dependency-review de GitHub en PRs, y CI corre en una sola version de Python (sin matriz). La dimension de pruebas/CI elogia la reproducibilidad pero no nota estas ausencias.
- i18n solo cosmetico: USE_I18N=True (settings.py:156) con una unica locale 'es' hard-codeada, sin gettext/LocaleMiddleware/carpeta locale; no es un defecto a esta escala pero la sintesis no lo evalua en ningun sentido.

**Hallazgos adicionales del crítico:**

- [🟡 medium] **El 'newsletter' capta y confirma suscriptores pero NO tiene ningun camino de envio (feature a medio construir + minimizacion de datos)** — Construir el camino de envio (comando/accion con List-Unsubscribe y envio via Celery) o, si se difiere, documentarlo y minimizar la captura hasta entonces.
- [🟡 medium] **El doble opt-in queda anulado por confirmacion via GET: escaneres de enlaces de correo auto-confirman suscripciones no solicitadas** — Confirmar via POST (boton en una landing GET) o token firmado de corta vida; anadir List-Unsubscribe y List-Unsubscribe-Post.
- [🟡 medium] **Unicidad de correo sensible a mayusculas y sin normalizar: suscriptores duplicados y baja incompleta** — Normalizar a minusculas en save()/clean() o migrar la columna unica a CITextField (CITextExtension en migracion).
- [⚪ low] **Sin notificacion a editores al recibir un envio, ni acuse ni auto-servicio de retiro para el autor** — Notificar a editores (mail_admins o lista de editores) al crear un Submission, idealmente via Celery, y opcionalmente un acuse al autor.
- [⚪ low] **Amplificacion de correo de confirmacion (subscription bombing) y token sin expiracion** — Anadir TTL al token y un throttle por-email ademas del por-IP; ajustar el mensaje si no hay expiracion real.
- [⚪ low] **Falta la cabecera Permissions-Policy (endurecimiento de borde no cubierto)** — Emitir Permissions-Policy restrictiva (p. ej. geolocation=(), camera=(), microphone=()) desde Caddy o el SecurityMiddleware.

## 7. Hoja de ruta (síntesis)

- Quick wins de correctitud (prioridad alta, esfuerzo S): coercer ISBN ''→None con UniqueConstraint parcial; exigir published_at futuro en la transición 'schedule' con test de regresión; corregir la sonda de salud de web (cabecera Host válida o consulta por servicio) para que reporte 'healthy'.
- Robustez del correo (S–M): mover la confirmación de suscripción a una tarea Celery con reintento/backoff o, como mínimo, quitar fail_silently/loguear la excepción para que Sentry la capte; corregir el comentario engañoso del worker.
- Anti-abuso multi-worker (S): definir CACHES apuntando la cache 'default' a Redis (ya obligatorio en prod) para que los contadores de django-ratelimit sean compartidos y persistentes entre los 3 workers.
- Frontend de alto retorno (S): añadir h1 en la portada, fallback a site_profile.og_image en poem_detail y recording_detail, y namespace iTunes en el feed 'Podcast' (o ajustar el rótulo si no se busca conformidad).
- Endurecer el gate de CI (S–M): añadir docker build --target prod + smoke a /healthz/ para ejercitar la imagen y el lockfile de runtime; incluir 'config' en la cobertura con branch=True; fijar pip-audit con hash.
- CD ligero (M, opcional a esta escala): workflow de release que construya/etiquete/publique la imagen prod en GHCR con retención para rollback, cerrando el último tramo de reproducibilidad tras el rigor de hashes.
- Pulido diferible, bajo retorno a tráfico bajo (evitar sobre-ingeniería): índice compuesto Event(published, starts_at), LIMIT en el buscador FTS, epigraph en el trigger de Poem, prefers-reduced-motion, JSON-LD en poemas/registros, canonical/og:url sin query string, unificar la capa de servicios/selectors; extraer siteconfig/core solo si se acomete un reordenamiento mayor de fronteras.

## 8. Plan de remediación estratégico

**Principios.** Agrupar hallazgos por cohesión (un lote = un cambio revisable), ordenar por **ROI/riesgo** (correctitud antes que pulido), respetar el flujo por lote (rama → verificación `ruff`+`pytest`+`--check`+smoke → PR → merge `--no-ff`), y **separar** lo que puedo hacer ya de lo que necesita **decisión de producto**, **texto legal** o **infraestructura** del usuario. Calibrado a la escala real (colectivo, tráfico bajo): se evita sobre-ingeniería.

### 8.1 Mapeo hallazgo → lote

| # | Hallazgo | Onda/Lote | Esfuerzo | Necesita |
|---|----------|-----------|:--------:|----------|
| 1 | ISBN `unique+null` sin `""→None` (500 en admin) | **A** correctitud | S | — |
| 2 | `schedule` no exige `published_at` (atasco silencioso) | **A** correctitud | S | — |
| 3 | Healthcheck web falso-`unhealthy` (Host inválido) | **A** correctitud | S | — |
| 5 | rate-limit sobre LocMem (multi-worker) | **B** seguridad/op | S | — |
| 4 | Correo síncrono con `fail_silently` | **B** seguridad/op | S–M | — |
| 7 | Portada sin `<h1>` | **C** frontend/SEO | S | — |
| 6 | `poem/recording_detail` sin fallback `og:image` | **C** frontend/SEO | S | — |
| 8 | Feed "Podcast" sin namespace iTunes | **C** frontend/SEO | S–M | decisión menor |
| — | Consentimiento/privacidad en form de envíos | **D** legal | S | — |
| — | Retención/borrado de PII (PENDING/rechazados) | **D** legal | M | — |
| — | Política cita Ley 19.628, falta **21.719** | **D** legal | S | **texto/abogado** |
| — | Newsletter sin camino de envío + opt-in por GET + email case-sensitive | **E** newsletter | M | **decisión de producto** |
| 10 | Imagen prod + lockfile runtime no se ejercitan en CI | **F** CI | S–M | — |
| 11 | Cobertura excluye `config/` (CSP), sin `branch` | **F** CI | S | — |
| 9 | Sin CD (build/tag/push/rollback) | Diferible | M | **infra (registry)** |
| — | Deliverability SPF/DKIM/DMARC + List-Unsubscribe | Diferible | M | **DNS/SMTP** |
| — | DR: restore ejercitado + RTO/RPO | Diferible | M | proceso |
| — | Rendimiento medido (Lighthouse/axe/k6), coste | Diferible | M | proceso |
| — | CI security (bandit/gitleaks/dependency-review) | Diferible | S–M | — |
| — | Menores (índice Event, LIMIT FTS, Permissions-Policy, reduced-motion, epigraph trigger, i18n, siteconfig) | Diferible | S–L | — |

### 8.2 Ondas (ejecutables por lote, en este orden)

**Onda A — Correctitud (S, prioridad máxima).** Bugs reales alcanzables por el admin o el flujo asíncrono, hoy sin señal.
- **A1 · ISBN:** coercer `""→None` en `clean()/save()` de `Work` y sustituir `unique=True` por `UniqueConstraint(condition=~Q(isbn=''))` (clave candidata opcional bien expresada) + test del 2.º Work sin ISBN.
- **A2 · schedule:** validar en `perform_transition('schedule')` que `published_at` no sea `None` y sea futuro → `ValueError` claro; test de regresión (programar sin fecha y con fecha pasada).
- **A3 · healthcheck web:** enviar cabecera `Host` válida en la sonda (`urllib` `headers={'Host': ...}`) o consultar por nombre de servicio; verificar que el contenedor reporte `healthy`.
- *Riesgo bajo, valor alto. Uno o dos lotes.*

**Onda B — Seguridad y operación (S–M).**
- **B1 · CACHES→Redis:** definir `CACHES['default']` sobre Redis (ya obligatorio en prod, URL derivada de `REDIS_PASSWORD`) → contadores de `django-ratelimit` compartidos y persistentes entre workers. Aislar en tests (LocMem) para hermeticidad.
- **B2 · correo robusto:** mover `_send_confirmation` a una tarea Celery con reintento/backoff (cablea el rol "correo" del worker); como mínimo quitar `fail_silently` + `logger.exception`. Corregir el comentario del worker.

**Onda C — Frontend/SEO (S).** Alto retorno, alineado con la audiencia (pares/gestores/prensa).
- **C1** `<h1>` en la portada (respetando la estética: h1 con clase del hero o visualmente oculto).
- **C2** `{% elif site_profile.og_image %}` en `poem_detail.html` y `recording_detail.html` (+ `twitter:card=summary_large_image` cuando exista imagen).
- **C3** feed podcast con namespace iTunes (`itunes:image/author/category/explicit/summary` + `itunes:duration`) **o** ajustar el rótulo si no se busca conformidad de podcast *(decisión menor tuya)*.

**Onda D — Legal/privacidad (S–M).** Importante por captación de PII; el **código** es rápido, el **texto legal es tuyo/abogado**.
- **D1** nota de consentimiento + enlace a privacidad en `submit.html` (paridad con el de suscripción).
- **D2** comando de **purga/retención** (borrar PENDING no confirmados y Submissions rechazados tras N días) + documentar la política.
- **D3** actualizar la página de privacidad a la **Ley 21.719** (dejo borrador; **revisar con abogado** antes de publicar).

**Onda E — Newsletter (M, requiere tu decisión de producto).** Hoy capta y confirma suscriptores pero **no hay envío**. Opciones:
- **(a) Completar:** comando/acción de admin que envíe la novedad por Celery, con `List-Unsubscribe` + One-Click (RFC 8058); confirmar por **POST** (no GET) para frenar auto-confirmación de escáneres; normalizar email a minúsculas (o `CITextField`); TTL al token + throttle por email.
- **(b) Minimizar:** documentar que es lista latente y reducir la captación hasta que exista el envío.
- *Dime (a) o (b) y lo ejecuto.*

**Onda F — Endurecer CI (S–M).**
- **F1** `docker build --target prod ./backend` + smoke a `/healthz/` en CI (ejercita imagen y lockfile de runtime).
- **F2** añadir `config` a `coverage.run.source` + `branch=True`.
- **F3** *(opcional)* `dependency-review` en PRs + secret-scan (gitleaks) + SAST ligero.

### 8.3 Diferibles (bajo retorno a tráfico bajo o dependientes de tu infra)

- **CD ligero** (imagen por tag a GHCR + retención para rollback) — necesita registry/credenciales.
- **Correo/entregabilidad** (SPF/DKIM/DMARC, rebotes) — necesita DNS del dominio + proveedor SMTP.
- **DR**: ejercitar un restore real + declarar RTO/RPO.
- **Rendimiento medido** (Lighthouse/axe CI, carga con k6) y **coste** estimado (VPS+SMTP+off-site+Sentry).
- **Menores**: índice `Event(published, starts_at)`, `LIMIT` explícito en el buscador FTS, `epigraph` en el trigger de `Poem`, `prefers-reduced-motion`, cabecera `Permissions-Policy`, `canonical`/`og:url` sin query string, i18n con `gettext`, extraer `siteconfig`.

### 8.4 Secuencia recomendada

1. **Onda A** (correctitud) — arrancar ya, sin dependencias.
2. **Onda C** (frontend/SEO) — quick wins visibles.
3. **Onda B** (Redis cache + correo robusto).
4. **Onda D** (legal: código ahora; texto legal en paralelo contigo/abogado).
5. **Onda F** (CI hardening).
6. **Onda E** (newsletter) — cuando decidas (a)/(b).
7. **Diferibles** — según prioridad e infra disponible.
