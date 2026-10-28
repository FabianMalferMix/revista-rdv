# Auditoría de código — «Reseñas» (Repitentes del Verso)

> **Fecha:** 2026-10-27 · **Commit auditado:** `38fdf03`
> **Alcance:** todo el repositorio. Las ocho apps de `backend/apps/` (media, people, content, reviews, agenda, showcase, community, submissions), `backend/config/`, plantillas, `site.css` y JS propio, la suite de pruebas, la infraestructura (compose, Dockerfile, `entrypoint.sh`, Caddy, respaldos, CI), `tools/ux/` y los datos de desarrollo. Se sumaron dos auditorías complementarias: accesibilidad de los componentes propios en un navegador con el JS en marcha, y permanencia de las URL públicas y de los identificadores de los feeds.
> **Método:** catorce dimensiones revisadas por agentes independientes, con lectura de código y mediciones de solo lectura sobre el stack de desarrollo (shell de Django, `curl`, Playwright). Cada hallazgo pasó por una verificación adversarial antes de redactarse y se cruzó con el registro de decisiones del proyecto, `docs/deferidos-y-decisiones.md`.
> **Resultado:** 113 hallazgos verificados: **10 de severidad alta, 66 media y 37 baja**. Ninguno quedó refutado.

## 1. Veredicto

El código es mejor de lo que cabría temer de un sitio construido casi por completo por agentes y sin revisión humana. Las piezas que se trabajaron a conciencia están a nivel profesional: el flujo editorial es transaccional y está probado bajo concurrencia, la CSP es estricta y se respeta en todo el sitio público, los contenedores y la cadena de suministro están endurecidos, el CI levanta la imagen de producción, restaura un respaldo y valida Caddy, y `ruff` no encuentra nada. Hay 985 pruebas con un 95 % de cobertura, casi ninguna función compleja y ningún TODO olvidado. No es código descuidado.

La debilidad está entre las piezas, no dentro de ellas. Cada sesión resolvió bien su problema local y nadie consolidó después. Por eso las reglas que más importan viven repetidas a mano y sin nada que las ate: qué es «público» se reescribe a mano en unas 50 consultas, con cuatro vocabularios distintos (AGE-1, WEB-1), los permisos de los roles quedaron congelados en el primer commit (AGE-2), el orden de firma de las coautorías no se aplica en ninguna página (DAT-1), y las medidas de la portada están copiadas en Python, CSS, JS y atributos `sizes` (FRO-1). Los comentarios narran la historia de cada sesión y varios ya afirman lo contrario de lo que hace el código, que es grave en un proyecto donde el siguiente lector es otro agente que los obedece (AGE-3, SEG-2, TAR-1). La suite da una seguridad parcial: casi una de cada cuatro pruebas lee el texto de `site.css` o de los guiones, de modo que un cambio cosmético la pone en rojo y una regresión real de comportamiento pasa en verde (PRU-2), mientras cinco de las nueve transiciones editoriales y todos los estados ocultos salvo el borrador no se prueban nunca (PRU-1).

Los riesgos más concretos son de operación y de privacidad. El despliegue documentado arranca el código nuevo antes de migrar (OPE-1); el respaldo informa éxito aunque no haya copiado los medios (RES-2); si la limpieza de metadatos falla, el original de una foto se publica con su GPS (RES-1); y la exportación de los datos de desarrollo llevaría borradores reales al repositorio público (HER-1). La búsqueda, además, ordena por un rango calculado sobre el vector reanalizado en inglés (REN-1). Ninguno de estos casos ha causado daño todavía (tráfico bajo, datos de demostración) y casi todos se corrigen con cambios pequeños.

En resumen: base profesional, evolución frágil. Para llegar a un código robusto no hace falta reescribir. Hace falta cerrar la docena de huecos concretos del tramo urgente, dar una fuente única a la visibilidad, los roles y las constantes de maquetación, cambiar las pruebas que copian texto por pruebas de comportamiento (con navegador donde haga falta) y fijar unas pocas reglas de trabajo que los agentes lean antes de tocar el código (sección 6).

## 2. Lo que está bien hecho

Estas decisiones se sostienen. Conviene conservarlas y, en varios casos, extenderlas al resto del código; ninguna debería «arreglarse».

- **Flujo editorial central, transaccional y probado bajo concurrencia.** Una sola tabla de transiciones con origen, destino y roles; cada transición se revalida con `select_for_update()` dentro de `transaction.atomic()`, y el cambio de estado y su bitácora se escriben en la misma transacción. El panel deja `status` en solo lectura y la guarda real está en el servidor. La publicación programada es idempotente ante un doble beat o un reintento. Evidencia: `backend/apps/content/workflow.py:19-29, 49-90`; `backend/apps/content/admin.py:193-212`; `backend/apps/content/tasks.py:28-46`; `backend/tests/test_concurrency.py`. Es el patrón que conviene copiar para la visibilidad (AGE-1).
- **Editar y borrar componen con los permisos de Django.** `has_change_permission` y `has_delete_permission` exigen primero el permiso de modelo y después la regla de rol y estado, con pruebas de los casos negativos. Evidencia: `backend/apps/content/admin.py:179-191`; `backend/tests/test_admin_hardening.py:72-98`. Falta llevarlo a las transiciones y a la descarga de envíos (DOM-2).
- **Consultas acotadas y conscientes del N+1.** La búsqueda por nombre une cuatro tablas en una sola `UNION ALL` tipada con tope por parte; `ultima_publicacion()` resuelve tres tablas en una consulta; la búsqueda de texto lleva `LIMIT` y `only()` hasta el SQL. Medido: portada 19 consultas, dossier 13, índices entre 4 y 6, sin crecer con el volumen salvo en las vistas de WEB-4; hay presupuestos de consultas y pruebas de escalado N contra M. Evidencia: `backend/apps/content/services.py:11-30, 46-62, 65-116`; `backend/apps/content/views.py:426-439`; `backend/tests/test_performance.py:25-64`; `backend/tests/test_imagenes_del_modelo.py:165-199`.
- **Búsqueda endurecida.** Consulta recortada a 120 caracteres y sin bytes NUL, límite de 60 peticiones por minuto, y un `DatabaseError` cae a «sin resultados» en vez de un 500. Probada con `%00`, 5.000 caracteres, comillas, emoji y espacios de ancho cero: siempre 200 y tres consultas de búsqueda. Evidencia: `backend/apps/content/views.py:396-471`.
- **La infraestructura transversal está aislada en `config/`.** `envguard` valida en positivo (que cada valor sea aceptable, no que difiera de una lista de centinelas), es una función pura y tiene pruebas (sus huecos están en SEG-5 y OPE-6); el resolvedor de IP es común a axes y ratelimit; la caché Redis traduce sus errores a la ruta de degradación que django-ratelimit ya entiende. Evidencia: `backend/config/envguard.py:45-99`; `backend/config/settings.py:38-47`; `backend/config/cache.py:36-74`; `backend/tests/test_envguard.py`; `.github/workflows/ci.yml:113-123`.
- **CSP estricta, respetada en todo el sitio público.** `script-src 'self'` con nonce que solo se genera si la plantilla lo usa, `object-src 'none'`, `frame-ancestors 'none'`; `'unsafe-inline'` en estilos solo bajo el panel. Ninguna plantilla pública tiene atributos `style` ni manejadores `on*`. Evidencia: `backend/config/csp.py:23-48, 80-118`; `backend/tests/test_security_csp.py`.
- **Lo subido se aísla en el borde y se prueba con el Caddy real.** Todo `/media/` sale con `nosniff` y `Content-Security-Policy: default-src 'none'; sandbox`; el CI levanta Caddy con el Caddyfile de producción y comprueba las cabeceras. Evidencia: `infra/caddy/Caddyfile:44-58`; `.github/workflows/ci.yml:320-351`.
- **El formulario público de envíos está bien cerrado.** Lista explícita de campos, extensión, tamaño y firma por formato, índice del ZIP de docx/odt leído sin descomprimir, honeypot y límite por IP; el adjunto va a un almacenamiento privado fuera de `MEDIA_ROOT` y solo lo descarga un editor. Evidencia: `backend/apps/submissions/forms.py:7-125`; `backend/apps/submissions/models.py:7-9, 55`; `backend/apps/submissions/views.py:48-57`.
- **Doble opt-in del boletín bien diseñado.** Token de baja permanente y token de confirmación de un solo uso que caduca a las 48 h; las mutaciones solo ocurren por POST (los escáneres de enlaces no confirman ni dan de baja); baja en un clic según RFC 8058; respuestas iguales para no revelar quién está suscrito; si el broker cae, no hay 500. Lo que falta es que el panel no permita saltárselo (DOM-5). Evidencia: `backend/apps/community/models.py:6-50`; `backend/apps/community/views.py:22-159`; `backend/apps/community/tasks.py:30-36`.
- **Cadena de suministro y contenedores endurecidos.** Lockfiles con `--require-hashes`, imágenes fijadas por digest (con prueba), usuario sin privilegios, `cap_drop: ALL`, `no-new-privileges`, límites por servicio; en el CI, `GITHUB_TOKEN` de solo lectura, herramientas verificadas por sha256, gitleaks y bandit bloqueantes, pip-audit semanal. Las imágenes que usa el propio CI aún van por etiqueta (OPE-4). Evidencia: `backend/Dockerfile`; `docker-compose.prod.yml:48-55`; `.github/workflows/ci.yml:17-18, 199-248`; `backend/tests/test_image_pinning.py`.
- **Un CI que ensaya buena parte de producción.** Migraciones de ida y vuelta (incluido el `reverse_sql` de los triggers), imagen de producción con `DEBUG=0` y healthchecks de web, worker y beat, restauración de un `pg_dump` real, `caddy validate`. Lo que aún no ensaya (el compose de producción y el comando real de gunicorn) está en OPE-4. Evidencia: `.github/workflows/ci.yml:82-95, 154-187, 260-317, 356-434`.
- **Migraciones de datos e integridad en la base donde se pensaron.** Las migraciones de datos usan `apps.get_model`, son idempotentes y no pisan ediciones manuales; el paso al enlace genérico se hizo en tres migraciones. Hay `CheckConstraint` para la fuente de un registro, unicidad parcial del ISBN y `UniqueConstraint` en todas las tablas puente. El vector de búsqueda lo mantiene un trigger, que cubre también `update()` y `bulk_update`. Evidencia: `backend/apps/content/migrations/0003-0005, 0007, 0009, 0010, 0011`; `backend/apps/media/models.py:397-404`; `backend/apps/reviews/models.py:91-102`; `backend/tests/test_search.py:61-75`.
- **Mejora progresiva y movimiento reducido, pieza por pieza.** Menú y lupa son `<details>` nativos; los lomos del estante son enlaces; el reproductor no contacta con terceros hasta el clic; el botón de imprimir nace oculto. `prefers-reduced-motion` se respeta en CSS y cada guion lo consulta en el momento de animar; el relevo se pausa fuera de la vista, con la pestaña oculta o con el puntero encima. Medido en navegador: 0 errores de consola y 0 violaciones de CSP en 21 páginas, foco visible y Escape que devuelve el foco, sin desbordamiento horizontal a 320 px. Evidencia: `backend/templates/base.html:88-111`; `backend/templates/media/partials/_player.html:14-29`; `backend/static/css/site.css:271-274`; `backend/static/js/integrantes.js:16-17, 78-85`; `backend/static/js/buscador.js:21-30`.
- **Pruebas de propiedad que calculan en vez de copiar.** La escala tipográfica es la única fuente de tamaños; el contraste AA se recalcula desde los tokens; los comentarios `{# #}` multilínea se detectan en el fuente y en el HTML; las librerías vendorizadas se comprueban por sha256; los medios (también el almacén privado) se aíslan en cada prueba; la base es PostgreSQL real con un solo `mock.patch` en toda la suite. Evidencia: `backend/tests/test_css_sistema.py:92-125`; `backend/tests/test_contraste_paleta.py`; `backend/tests/test_template_hygiene.py:35-75`; `backend/tests/test_vendored_assets.py:38-55`; `backend/conftest.py:8-66`. Es el modelo para sustituir las pruebas de texto (PRU-2).
- **Páginas de error que no dependen de lo que falla.** `500.html` no extiende la base ni usa contexto, así que se dibuja con la base de datos caída; una prueba lo exige con `django_assert_num_queries(0)`. Evidencia: `backend/templates/500.html`; `backend/tests/test_paginas_error.py`.
- **Código sin restos y URLs por nombre.** Solo una función de producción supera complejidad 10 (`MediaAsset.ensure_derivatives`, 13); no hay TODO/FIXME ni código comentado; de las 287 clases de `site.css`, solo 5 carecen de referencia literal, y todas se componen en la plantilla o las pone htmx. Todas las apps usan espacios de nombres y `{% url %}`/`reverse()`; el canonical descarta la query string salvo la paginación. Evidencia: `ruff --select C901`; `backend/apps/content/context_processors.py:82-90`.

## 3. Patrones sistémicos

Los 113 hallazgos no son 113 problemas independientes: casi todos son casos de ocho patrones. Corregir los hallazgos sin cambiar la forma de trabajar que los produce solo aplaza el siguiente.

### 3.1 Reglas de dominio sin una fuente única

**Qué es.** Las reglas centrales del sitio (qué es público, quién puede hacer qué, cómo se publica, en qué orden firman las coautorías, qué está destacado) no viven en un lugar del modelo que todos consulten. Cada vista, sitemap, feed, plantilla y comando las reescribe. No hay ningún Manager ni QuerySet propio en el proyecto, los roles son listas escritas a mano y nombres de grupo comparados como texto, y «publicar» está implementado dos veces.

**Por qué aparece aquí.** Un agente resuelve la tarea que tiene delante copiando el filtro más cercano. Si no existe un `.publicados()` que copiar, copia `status=...PUBLISHED` y se olvida de la relación. Los arreglos posteriores se hicieron caso por caso (una propiedad en un modelo, una condición en una plantilla, un filtro en Python) y ninguno se convirtió en regla.

**Hallazgos.** AGE-1, WEB-1, ARQ-6, PRU-1 (visibilidad); AGE-2, DOM-2, PRU-4 (roles y permisos); ARQ-2, DOM-1, AGE-4 (publicar); DAT-1 (firma); DAT-5, ARQ-5 (destacados y campos sin efecto); ARQ-4, ARQ-8 (falta una capa común).

**Qué cambiar.** Cada regla en un solo sitio del modelo, con un nombre que se pueda copiar: `Modelo.objects.publicados()` y accesores para las relaciones (`registro.evento_publico`), una matriz de roles declarada y llevada a producción por migración, una API `firmas` para la coautoría. Y una prueba de contrato por regla: para cada modelo publicable, un objeto oculto no aparece en ninguna superficie.

### 3.2 El mismo dato copiado en varias capas y lenguajes

**Qué es.** Valores que deben coincidir están escritos a mano en dos a seis sitios: cuántas integrantes se ven (Python, CSS, JS, `sizes`), los cortes de pantalla, las rutas con token (Python y dos veces en el Caddyfile), los proveedores de vídeo (embeds y CSP), la navegación (barra, sub-fila y mapa del pie), la lista blanca de HTML (nh3 y TinyMCE), los registros de cada tipo de contenido (sitemap, búsqueda, limpieza de archivos, datos de desarrollo) y la fuente tipográfica en las herramientas.

**Por qué aparece aquí.** Cada sesión toca la capa que necesita y copia el valor de la otra. Las pruebas que se añadieron fijan cada copia por separado (`assert A_LA_VISTA == 5`, `"repeat(5, minmax(0, 1fr))" in css`), así que sostienen la duplicación en vez de detectarla.

**Hallazgos.** FRO-1, WEB-3, FRO-9, ARQ-3, SEG-4, WEB-9, ARQ-1, TAR-5, PRU-3, MAN-2, FRO-6, OPE-7, OPE-8, HER-7.

**Qué cambiar.** Cada valor se decide una vez y viaja: el servidor lo emite como atributo `data-` y el JS y el CSS lo leen; la regex de redacción se construye con `reverse()`; `frame-src` se deriva de la tabla de proveedores. Donde no se pueda derivar, una prueba de relación entre fuente y copia, no dos pruebas de valor. Para los registros, metapruebas que recorran `apps.get_models()` y obliguen a decidir cada modelo nuevo.

### 3.3 Comentarios y documentos que narran la historia y ya no dicen la verdad

**Qué es.** Un tercio de `site.css` son comentarios, y muchos docstrings cuentan qué se hizo en cada sesión («antes…», «el dueño eligió…», D23, S-05, «ticket 4.3») en lugar del contrato vigente. Varios afirman ya lo contrario de lo que hace el código: que la exportación de desarrollo solo lleva lo público, que `acks_late` reencola una tarea muerta, que hay una comprobación de firma de los archivos subidos, que la tirada «enseña las flechas», que «media es la base».

**Por qué aparece aquí.** El agente siguiente lee los comentarios como especificación y los obedece: un comentario podrido es una instrucción equivocada. Cada pasada añade historia y nadie la poda, porque ninguna herramienta lo detecta.

**Hallazgos.** AGE-3, ARQ-7, SEG-2, TAR-1, OPE-8, HER-7, PRU-7, FRO-4.

**Qué cambiar.** Una regla escrita: el comentario dice qué hace el código hoy y qué restricción lo explica; la historia va al mensaje del commit. Cada garantía de seguridad o de privacidad se convierte en una prueba con nombre descriptivo. Un paso de CI rechaza identificadores de decisión nuevos en el código.

### 3.4 Pruebas que fijan la implementación y dejan sin cubrir el comportamiento

**Qué es.** La suite es grande (985 pruebas, 95 % de cobertura) pero mide sobre todo texto: 148 de 757 funciones leen `site.css`, los guiones o las plantillas y buscan cadenas literales; hay seis analizadores de CSS caseros con semánticas distintas; ninguna prueba ejecuta JavaScript. A la vez, lo que importa queda sin probar: cinco de las nueve transiciones editoriales, los estados ocultos distintos del borrador, los permisos por HTTP, las migraciones de datos y el cableado de las tareas programadas.

**Por qué aparece aquí.** Cada decisión de diseño trajo su archivo de pruebas, y la forma más rápida de «probar» un ajuste visual sin navegador es buscar el texto que se acaba de escribir. Cuando el diseño cambia, el agente copia el literal nuevo: la prueba registra el cambio en vez de detectar regresiones.

**Hallazgos.** PRU-2, PRU-6, PRU-1, PRU-4, PRU-5, PRU-3, PRU-7, PRU-8, PRU-9, PRU-10, FRO-8, WEB-7, COM-9.

**Qué cambiar.** Tres niveles: conservar las invariantes calculadas (contraste, escala, higiene), borrar las instantáneas de valores y añadir un navegador al CI (Playwright ya está en `tools/ux/`) para el comportamiento visual y el JS. Pruebas de contrato para las reglas de dominio. Y una regla para cada prueba nueva: comprueba lo que ve o hace la persona, no el código que se acaba de escribir.

### 3.5 Fallar en silencio, o informar éxito sin comprobarlo

**Qué es.** Ante un error, varias piezas siguen como si nada. `strip_metadata` vuelve sin quitar el GPS si Pillow no lee el archivo; `backup.sh` convierte un fallo de `tar` en «(media vacío)» y avisa éxito; el comando de derivados cuenta como verificados los que fallaron; los fallos reales se registran como WARNING, invisibles para Sentry; el buscador convierte errores de la base en «sin resultados»; la caché de color guarda para siempre el resultado de una lectura fallida.

**Por qué aparece aquí.** Envolver en `try/except Exception: return` hace que la tarea «funcione» y la suite pase. Sin nadie que revise, nadie pregunta qué ocurre en la rama del error.

**Hallazgos.** RES-1, RES-2, TAR-2, RES-9, RES-10, RES-6, TAR-7, TAR-8, HER-6, FRO-2.

**Qué cambiar.** Distinguir lo esperado (WARNING sin traza) de lo inesperado (`logger.exception`). Los controles de privacidad fallan cerrados. Un proceso solo declara éxito cuando lo verificó. Y hace falta una alarma que alguien reciba: Sentry en producción, un latido de beat, el ping del respaldo.

### 3.6 Lo que solo existe en producción no se ensaya antes de producción

**Qué es.** La configuración se bifurca por `DEBUG` en siete puntos y la suite corre siempre del lado de desarrollo. El CI nunca carga `docker-compose.prod.yml` ni el comando real de gunicorn. El despliegue arranca el código nuevo antes de migrar y deja los pasos de release a la memoria del operador. La retención de restic no borra nada y no existe la restauración desde ella. Los logs del worker pierden el formato y la redacción, y no hay timeouts hacia la base ni hacia Redis.

**Por qué aparece aquí.** Los agentes trabajan contra el stack de desarrollo, donde nada de esto se ve. Lo que no falla en local ni en la suite no aparece en ninguna sesión.

**Hallazgos.** OPE-1, OPE-2, OPE-3, OPE-4, OPE-5, OPE-6, OPE-7, RES-4, RES-5, RES-7, REN-2, REN-4, REN-8, TAR-6.

**Qué cambiar.** El release como servicio del compose (migrar antes de arrancar), el CI levantando el compose de producción, la restauración de restic probada de punta a punta, un settings de pruebas explícito, timeouts y comprobación de conexiones, y las variables de entorno leídas con un único módulo que rechace valores ambiguos.

### 3.7 Contenido no publicado y datos personales que salen por caminos laterales

**Qué es.** Las puertas principales están bien cerradas, pero hay salidas secundarias: la exportación de desarrollo llevaría borradores al repositorio público; un registro publicado enseña su evento no publicado; despublicar no retira el audio ni el PDF que sirve Caddy; Sentry recibiría cuerpos de formulario, variables locales y tokens; una imagen sin limpiar publica su GPS; el panel deja escribir a mano el consentimiento del boletín.

**Por qué aparece aquí.** Cada protección se diseñó para el camino que la sesión tenía delante: la ficha, la URL, el formulario. Los caminos que no son HTML (archivos, logs, serializaciones, relaciones) quedaron fuera.

**Hallazgos.** HER-1, AGE-1, DOM-4, RES-1, RES-3, TAR-4, SEG-1, SEG-5, DOM-5, TAR-3, HER-2.

**Qué cambiar.** Listas blancas por campo y por fila en todo lo que sale del sistema; redacción por defecto en Sentry (sin variables locales ni cuerpos); los archivos de piezas publicables servidos con comprobación de estado; y, antes de activar un canal nuevo (Sentry, el envío del boletín, un importador), preguntarse qué datos viajan por él.

### 3.8 Una identidad pública que no está fijada

**Qué es.** Las URL, los identificadores de los feeds y el origen del sitio dependen de cosas que cambian: el slug se edita en el panel sin aviso ni redirección; el GUID de cada ítem de los feeds es su URL absoluta; las URL absolutas se arman con el Host de cada petición; la ficha de una persona cambia de ruta según su membresía; y las páginas legales que enlaza el pie de todo el sitio son filas editables.

**Por qué aparece aquí.** Dentro del sitio todo se resuelve por nombre de ruta (bien hecho), así que un cambio de URL no rompe ninguna prueba. Lo que se rompe está fuera: enlaces en prensa, dossiers enviados, buscadores, aplicaciones de pódcast.

**Hallazgos.** COM-1, COM-5, COM-6, COM-8, COM-9, COM-12, WEB-2, WEB-7.

**Qué cambiar.** Decidirlo antes de anunciar el RSS o enviar el pódcast a los directorios: GUID estables, slug de solo lectura en lo público, un `SITE_URL` fijo, redirección al renombrar una ruta y una prueba con la lista congelada de prefijos públicos.

## 4. Hallazgos

Cómo leer cada ficha:

- **Severidad**: la final, después de la verificación (alta, media o baja).
- **Esfuerzo**: S, un cambio acotado que cabe en un PR pequeño; M, uno o varios PR medianos; L, un cambio grande que conviene hacer por etapas.
- **Confianza**: qué tan seguro es el diagnóstico.
- **Verificación**: «confirmado» si el hallazgo se sostuvo tal cual; «parcial» si se sostuvo con correcciones. Las correcciones se resumen en **Matiz de la verificación**, y el texto de la ficha ya usa las cifras corregidas.
- **Decisión registrada**: relación con una entrada de `docs/deferidos-y-decisiones.md` y si conviene reabrirla.

Las fichas van agrupadas por área (secciones 4.1 a 4.15). La tabla las ordena por severidad.

| ID | Hallazgo | Severidad | Esfuerzo | Área |
| --- | --- | --- | --- | --- |
| DAT-1 | El orden de firma de las coautorías (`position`) no se aplica en ninguna página | alta | S | Modelo de datos |
| WEB-1 | Fichas de obra, editorial, autor y colaborador sin regla de visibilidad ni contenido coherente | alta | M | Capa HTTP |
| OPE-1 | El despliegue arranca el código nuevo antes de migrar y deja el release a la memoria del operador | alta | M | Despliegue y operación |
| PRU-1 | Cinco de las nueve transiciones nunca se ejecutan en las pruebas; lo oculto solo se prueba con borradores | alta | M | Pruebas |
| AGE-1 | «Solo lo publicado» se reescribe a mano en 54 consultas; `Recording.event` quedó sin proteger | alta | M | Huellas de agentes |
| AGE-2 | Permisos de los roles congelados en la línea base; corregirlos no llegaría a producción | alta | S | Huellas de agentes |
| REN-1 | El orden de la búsqueda se calcula sobre el vector reanalizado en inglés | alta | S | Rendimiento |
| RES-1 | La limpieza de metadatos falla abierta y en silencio: el GPS se publica en el original | alta | M | Resiliencia |
| RES-2 | El respaldo informa éxito aunque los medios no se hayan respaldado | alta | S | Resiliencia |
| HER-1 | `datos_de_desarrollo exportar` llevaría borradores al repositorio público, sin guarda de entorno | alta | S | Herramientas de desarrollo |
| ARQ-1 | Agregar un tipo de contenido exige unos 13 registros manuales, y ninguna prueba avisa si falta uno | media | M | Arquitectura |
| ARQ-2 | «Publicar» está implementado dos veces; tipos editoriales y acciones se enumeran a mano | media | S | Arquitectura |
| ARQ-3 | Rutas, proveedores, grupos y colores copiados en otro módulo sin nada que los ate | media | S | Arquitectura |
| ARQ-4 | Falta una capa de «sitio»: `content` se volvió el núcleo implícito | media | L | Arquitectura |
| ARQ-5 | Contratos implícitos incoherentes: URL, imagen social y campos del panel sin efecto | media | M | Arquitectura |
| ARQ-6 | La lógica no tiene un lugar fijo | media | M | Arquitectura |
| ARQ-7 | El README y varios comentarios que hacen de contrato ya no son ciertos | media | S | Arquitectura |
| DAT-2 | Borrar una imagen, una persona o una obra arrastra contenido publicado sin que el panel lo muestre | media | M | Modelo de datos |
| DAT-3 | Búsqueda: índice en SQL crudo y plegado de acentos duplicado con otra semántica | media | M | Modelo de datos |
| DAT-4 | Los archivos se borran antes de que la transacción confirme el cambio | media | S | Modelo de datos |
| WEB-2 | El pie de todas las páginas y el consentimiento dependen de tres slugs editables | media | S | Capa HTTP |
| WEB-3 | Las vistas cargan con la composición visual | media | M | Capa HTTP |
| FRO-1 | Las medidas de maquetación están copiadas en Python, CSS, JS y atributos `sizes` | media | M | Plantillas, CSS y JS |
| FRO-2 | La mejora progresiva falla mal: el CSS da por hecho que el JS se montó | media | S | Plantillas, CSS y JS |
| FRO-3 | El poema destacado de la portada pierde sus saltos de verso | media | S | Plantillas, CSS y JS |
| FRO-4 | `site.css` se gobierna por orden de aparición y especificidad, con la cabecera como punto caliente | media | L | Plantillas, CSS y JS |
| FRO-5 | Parciales con contratos implícitos | media | M | Plantillas, CSS y JS |
| FRO-6 | Marcado y recetas copiados entre plantillas, con errores que ya divergen | media | M | Plantillas, CSS y JS |
| FRO-7 | El atributo `hidden` lo anula cualquier `display` y se parchea componente por componente | media | S | Plantillas, CSS y JS |
| FRO-8 | Selectores muertos sin detección general | media | M | Plantillas, CSS y JS |
| FRO-9 | La navegación tiene cuatro fuentes de verdad; el menú del teléfono no usa la de la barra | media | S | Plantillas, CSS y JS |
| SEG-1 | El `\|safe` del cuerpo supone que todo se escribe con `save()` | media | S | Seguridad |
| SEG-2 | Comentarios de seguridad que afirman garantías que el código no tiene | media | S | Seguridad |
| TAR-1 | Acks, límites de tiempo y reintentos de Celery no hacen lo que dicen comentarios y pruebas | media | S | Tareas y archivos |
| TAR-2 | Procesado de imágenes síncrono en `save()`, con cuatro disparadores y errores tragados | media | M | Tareas y archivos |
| TAR-3 | El ciclo de vida del suscriptor vive en las vistas y la purga mide desde la creación | media | M | Tareas y archivos |
| TAR-4 | Los secretos del boletín viajan como argumentos de tarea y el worker queda fuera de la redacción | media | S | Tareas y archivos |
| TAR-5 | La limpieza de archivos depende de registros manuales y de nombres calculados con las constantes de hoy | media | M | Tareas y archivos |
| TAR-6 | La caché del color del lomo no caduca ni tiene versión | media | S | Tareas y archivos |
| OPE-2 | Un único `DEBUG` decide estáticos, caché, correo y logs; la suite corre siempre del lado de desarrollo | media | M | Despliegue y operación |
| OPE-3 | La recuperación ante desastre no está probada de punta a punta | media | M | Despliegue y operación |
| OPE-4 | Lo que prueba el CI no es lo que se despliega | media | M | Despliegue y operación |
| OPE-5 | Los límites de petición pensados para el formulario público rigen en todo el sitio, panel incluido | media | S | Despliegue y operación |
| OPE-6 | Variables de entorno leídas a mano: «true» desactiva controles de seguridad | media | S | Despliegue y operación |
| OPE-7 | Redis tiene dos reglas de configuración; el CI ya corre con la caché en un host inexistente | media | S | Despliegue y operación |
| OPE-8 | Hechos operativos duplicados que ya divergen del código | media | S | Despliegue y operación |
| PRU-2 | Casi una de cada cuatro pruebas lee el texto de CSS, JS o plantillas en vez de probar lo que se ve | media | L | Pruebas |
| PRU-3 | Tareas programadas, limpieza de archivos y listas de rutas cableadas por texto, sin metapruebas | media | S | Pruebas |
| PRU-4 | Los permisos por rol se prueban con métodos del admin, nunca por HTTP | media | M | Pruebas |
| PRU-5 | Migraciones de datos sin pruebas, y un fixture atado a sus nombres de archivo | media | M | Pruebas |
| PRU-6 | Seis analizadores de CSS caseros, cada uno con una semántica distinta | media | M | Pruebas |
| PRU-7 | La suite está organizada por decisiones y lotes, con duplicados y comentarios caducos | media | L | Pruebas |
| MAN-1 | Castellano e inglés mezclados sin regla, con claves gemelas y vocabularios paralelos | media | M | Mantenibilidad |
| AGE-3 | Comentarios y docstrings como bitácora de sesiones, con afirmaciones ya falsas | media | M | Huellas de agentes |
| AGE-4 | Dos (o más) formas de hacer lo mismo, según la sesión que lo escribió | media | M | Huellas de agentes |
| REN-2 | Caddy marca como inmutable durante un año todo `/static/`, también TinyMCE, que va sin hash | media | S | Rendimiento |
| RES-3 | La redacción de PII y tokens cubre la URL y nada más | media | S | Resiliencia |
| RES-4 | Worker y beat pierden el JSON y la redacción; gunicorn escribe texto plano; no hay rotación | media | S | Resiliencia |
| RES-5 | Redis hace de caché y de broker con `noeviction`, claves sin caducidad y degradación parcial | media | S | Resiliencia |
| RES-6 | `/readyz/` incompleto y mudo, healthchecks que nadie consume y ningún aviso por defecto | media | M | Resiliencia |
| RES-7 | No hay plazos de extremo a extremo: gthread no corta peticiones y la base no tiene timeouts | media | S | Resiliencia |
| RES-8 | Imágenes decodificadas sin tope de píxeles, también en la portada pública | media | M | Resiliencia |
| DOM-1 | La máquina de estados tiene puertas laterales | media | M | Dominio editorial |
| DOM-2 | Publicar y descargar envíos depende del nombre del grupo, no de los permisos de Django | media | S | Dominio editorial |
| DOM-3 | No hay vista previa: para ver cómo queda un borrador hay que publicarlo | media | M | Dominio editorial |
| DOM-4 | Despublicar no retira los archivos: Caddy sigue sirviendo el audio y los PDF | media | M | Dominio editorial |
| DOM-5 | El panel deja reescribir a mano el consentimiento del boletín y el estado de los envíos | media | S | Dominio editorial |
| HER-2 | Herramientas de desarrollo en apps de producción, protegidas con un `--force` que el error anuncia | media | M | Herramientas de desarrollo |
| HER-3 | Cuatro caminos para poblar desarrollo que no convergen y repiten datos contradictorios | media | M | Herramientas de desarrollo |
| HER-4 | Lo vendorizado no tiene radar ni receta de actualización | media | M | Herramientas de desarrollo |
| COM-1 | Los GUID de los dos feeds son el enlace absoluto y cambian con el slug y el dominio | media | S | Permanencia de URL |
| COM-2 | Contraste insuficiente en dos sellos de la portada | media | M | Accesibilidad |
| COM-3 | Registros sin alternativa textual garantizada | media | M | Accesibilidad |
| COM-4 | «Las voces»: relevo automático sin pausa que reordena el DOM bajo el lector de pantalla | media | S | Accesibilidad |
| COM-5 | El slug de lo publicado se cambia desde el panel sin aviso, historial ni redirección | media | S | Permanencia de URL |
| COM-6 | El sitio no tiene un origen fijo: las URL absolutas salen del Host de cada petición | media | M | Permanencia de URL |
| ARQ-8 | El grafo de dependencias no tiene capas | baja | L | Arquitectura |
| DAT-5 | Campos que el panel ofrece y nadie lee; «destacado» modelado de tres maneras | baja | S | Modelo de datos |
| WEB-4 | Las parciales de fila dependen de precargas que cada vista recuerda o no | baja | M | Capa HTTP |
| WEB-5 | La limitación de tasa de la búsqueda se salta con peticiones HEAD | baja | S | Capa HTTP |
| WEB-6 | Un `next` arbitrario en el alta del boletín produce un 500 | baja | S | Capa HTTP |
| WEB-7 | La URL canónica y la paginación se calculan por separado y no coinciden | baja | S | Capa HTTP |
| WEB-8 | Semántica HTTP y endpoints auxiliares sin una convención común | baja | S | Capa HTTP |
| WEB-9 | Formularios públicos: límites, vocabularios y campos copiados entre capas | baja | S | Capa HTTP |
| FRO-10 | Guiones con ayudantes copiados, dos dialectos y montaje único | baja | S | Plantillas, CSS y JS |
| SEG-3 | Antiabuso: axes bloquea solo por IP y las confirmaciones no tienen tope por destinatario | baja | S | Seguridad |
| SEG-4 | La misma lista permitida, copiada en nh3, TinyMCE, la CSP y los embeds | baja | S | Seguridad |
| SEG-5 | Defensas que una variable de entorno apaga sin que el guard de producción lo detecte | baja | S | Seguridad |
| TAR-7 | El correo transaccional no se valida al arrancar ni deja rastro | baja | S | Tareas y archivos |
| TAR-8 | La degradación ante Redis cubre errores pero no cuelgues | baja | S | Tareas y archivos |
| PRU-8 | Aserciones que pasarían aunque el defecto estuviera presente | baja | S | Pruebas |
| PRU-9 | Fábricas de datos de prueba a medio centralizar | baja | M | Pruebas |
| PRU-10 | Higiene: una prueba modifica un archivo real del repositorio | baja | S | Pruebas |
| MAN-2 | Helpers y mecanismos copiados entre apps que ya divergen | baja | M | Mantenibilidad |
| REN-3 | El `srcset` consulta el almacenamiento en cada render y su copia menor es de 480 px | baja | M | Rendimiento |
| REN-4 | El worker de Celery abre un proceso por CPU del anfitrión | baja | S | Rendimiento |
| REN-5 | El perfil del sitio se lee en cada petición, dos veces en cuatro vistas | baja | S | Rendimiento |
| REN-6 | Consultas que traen colecciones enteras para usar una parte | baja | S | Rendimiento |
| REN-7 | El 42 % de la hoja de estilos que bloquea el render son comentarios | baja | S | Rendimiento |
| REN-8 | Conexiones persistentes a la base sin comprobación de salud | baja | S | Rendimiento |
| RES-9 | Los fallos reales se registran como WARNING | baja | S | Resiliencia |
| RES-10 | Comandos de mantenimiento con fallos parciales mudos o en cascada | baja | S | Resiliencia |
| DOM-6 | El «rastro inmutable» se borra junto con la pieza y sus notas admiten otra autoría | baja | M | Dominio editorial |
| HER-5 | La copia de desarrollo pisa por pk filas de las migraciones y sus fechas caducan | baja | M | Herramientas de desarrollo |
| HER-6 | Las herramientas de `tools/ux/` dan por buenos resultados que no lo son | baja | S | Herramientas de desarrollo |
| HER-7 | Decisiones copiadas fuera de su fuente quedaron obsoletas | baja | S | Herramientas de desarrollo |
| HER-8 | Las guardas de higiene del repositorio están inactivas o despistan | baja | S | Herramientas de desarrollo |
| COM-7 | Menú del teléfono: el foco sale del panel abierto y cae en contenido tapado | baja | S | Accesibilidad |
| COM-8 | La URL de una persona depende de si es integrante | baja | S | Permanencia de URL |
| COM-9 | Las pruebas fijan que el enclosure siga al Host; nada fija GUID, slugs ni redirecciones | baja | S | Permanencia de URL |
| COM-10 | El buscador vuelca la lista entera en la región viva; la tirada anuncia dos veces | baja | S | Accesibilidad |
| COM-11 | Alta del boletín: sin `autocomplete="email"`, consentimiento sin asociar, errores fuera de vista | baja | S | Accesibilidad |
| COM-12 | No hay política para renombrar rutas públicas | baja | S | Permanencia de URL |

### 4.1 Arquitectura y límites entre módulos (ARQ)

#### ARQ-1 · Agregar un tipo de contenido exige tocar unos 13 registros manuales repartidos, y ninguna prueba avisa si falta uno

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Un modelo no declara en su propia app que aparece en el sitio: se enumera a mano en registros centrales, casi todos dentro de `content`. Para un tipo público nuevo hay que hacer el trabajo normal de Django (modelo, migración, admin, urls, vistas, plantillas) y, además, tocar: `filecleanup.register()` por cada FileField; una clase Sitemap y su entrada en `SITEMAPS`; las rutas del índice (`StaticViewSitemap._views`); `NAV_PRINCIPAL`, `SUBNAV_COLECTIVO` y el mapa del pie, que es una lista aparte; la búsqueda en dos módulos (otra parte de la UNION y otra rama en `_resultado_por_nombre`); y `MODELOS` en los datos de desarrollo. Los registros que fallan en silencio son los del sitemap, la búsqueda y la limpieza de archivos; lo que falte en la navegación se ve en pantalla. Ninguna prueba recorre los modelos para exigir que estén todos (`grep -rn get_models backend/tests` → 0).

**Evidencia.**

- `backend/apps/content/sitemaps.py:20-34, 181-195` — `_views` con 13 nombres de ruta a mano; `SITEMAPS` con 13 secciones de modelos de seis apps.
- `backend/apps/content/sitemaps.py:140-148` — las fichas de colaborador no están en el sitemap, y no hay ninguna lista de excluidos que lo registre como decisión.
- `backend/apps/content/views.py:363-393` — `GRUPOS_DE_BUSQUEDA` (6) y `_resultado_por_nombre`, cuya última rama envía cualquier tipo desconocido a la ficha de evento (391-393).
- `backend/apps/content/services.py:65-116` — la UNION con los literales `'persona'`, `'registro'`, `'publicacion'` y `'actividad'`, que deben coincidir con las ramas de la vista.
- `backend/apps/media/apps.py:9-16`, `backend/apps/showcase/apps.py:18-20`, `backend/apps/submissions/apps.py:9-16` — los cinco FileField, registrados a mano. Comprobado en el shell: hoy no falta ninguno.
- `backend/apps/content/context_processors.py:10-49` y `backend/templates/partials/_mapa.html:13-57` — la navegación, en dos estructuras distintas.

**Por qué importa a futuro.** Un agente añade «Talleres» con el PDF del programa. Las páginas funcionan y la suite pasa. Si no llamó a `filecleanup.register(Taller, "programa")`, al borrar un taller el PDF sigue en `media/`, en los respaldos y accesible por su URL. Si lo añadió a la UNION con el tipo `'taller'` pero olvidó la rama de la vista, la búsqueda enlaza a `/agenda/<slug-del-taller>/`, que da 404, sin ningún error.

**Recomendación.** No hace falta un registro central nuevo; bastan metapruebas que recorran `apps.get_models()` de `apps.*`:

1. Todo FileField tiene receptores `post_delete` y `pre_save` de filecleanup (se comprueba por su `dispatch_uid`) o está en una lista explícita de exclusiones.
2. Todo modelo con `get_absolute_url` o ficha pública tiene sección en `SITEMAPS` o está en `EXCLUIDOS_DEL_SITEMAP`. Eso obliga a decidir sobre colaboradores y etiquetas, que hoy faltan sin explicación.
3. Todo modelo está en `MODELOS` o en una lista `NO_VIAJAN`.

Además, que la búsqueda tome sus tipos de una sola tupla compartida por `services.py` y `views.py`, y que un tipo desconocido lance un error explícito. Opcional: registrar todos los FileField en un único `ready()`. Generar el mapa del pie desde la misma estructura que la barra cuando se toque la navegación (FRO-9).

**Matiz de la verificación.** De los «13 puntos», siete son trabajo normal de Django cuya omisión salta a la vista; fallan en silencio unos cuatro. Que `MODELOS` sea opt-in es una salvaguarda deliberada de privacidad que falla del lado seguro. Las consecuencias de privacidad solo aplican a un FileField nuevo con datos personales: un PDF público huérfano solo deja basura en el disco. El registro central que se propuso al principio es desproporcionado para unos ocho tipos públicos; por eso la severidad bajó de alta a media.

#### ARQ-2 · «Publicar» está implementado dos veces, y los tipos editoriales y sus acciones se enumeran a mano

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** La vía autoritativa es `workflow.perform_transition`: valida, bloquea la fila, fija `published_at` y deja bitácora. La tarea `publish_due_items` reimplementa la transición «publish» sobre una tupla fija `(Article, Poem)`: cambia el estado, guarda con `update_fields` y crea la `EditorialTransition` con una nota fija y sin actor. No usa el servicio porque «publish» desde SCHEDULED exige el rol editor y la tarea no tiene usuario. El admin, por su parte, repite las nueve transiciones como nueve métodos `do_*` y una lista `actions`, y lee los roles por posición (`TRANSITIONS[...][2]`). Hoy las dos implementaciones coinciden, pero nada las obliga, y ya hubo que mantenerlas en paralelo (commit `a1c77b3`).

**Evidencia.**

- `backend/apps/content/tasks.py:12-47` — `for model in (Article, Poem)` (22) y la transición a mano (29-46).
- `backend/apps/content/workflow.py:19-29, 49-90` — la tabla de transiciones; la guarda de «schedule» menciona la tarea solo en un comentario.
- `backend/apps/content/admin.py:125-135, 138, 163, 214-248` — la lista `actions` y los nueve `do_*` casi idénticos.
- `backend/tests/test_admin_acciones_por_rol.py:59-61` — mitigación: falla si una transición no tiene su acción.
- `backend/tests/test_admin.py:74-87` — repite a mano los nueve nombres.
- `backend/tests/test_workflow.py:73-92` — las pruebas de la tarea no comparan con lo que deja `perform_transition` ni recorren las subclases de `EditorialItem`.
- `backend/apps/content/models.py:64-99` — `EditorialItem` es abstracto y no lleva registro de subclases.

**Por qué importa a futuro.** Cuando se construya el aviso al boletín o una invalidación «al publicar», el agente lo pondrá en `perform_transition` y las piezas programadas, que publica la tarea, no lo dispararán, con la suite en verde. Si se crea una tercera subclase de `EditorialItem` (p. ej. `Traduccion`), el editor podrá programarla, pero la tarea no la recorre y quedará «Programada» para siempre.

**Recomendación.** Que la tarea llame a `perform_transition(item, "publish", user=None, sistema=True)`, con un actor de sistema que salte el chequeo de rol y conserve la guarda de estado, el bloqueo y la bitácora; otra opción es extraer un `_aplicar_transicion(bloqueada, destino, actor, nota)` que usen ambos. Recorrer las subclases de `EditorialItem` en vez de la tupla. Convertir `TRANSITIONS` en un NamedTuple para no leer roles por posición; generar las acciones del admin en un bucle es opcional. Fijar como convención que los efectos asíncronos se encolan con `delay_on_commit`. Prueba: para cada subclase, la publicación programada deja la misma bitácora y los mismos efectos que la manual.

**Matiz de la verificación.** La parte del admin es higiene: una prueba ya la ata a la tabla, y las descripciones por acción son Django idiomático. En el camino de la tarea `published_at` nunca es nulo (lo garantiza el filtro `published_at__lte`), así que hoy esa fecha no diverge. Ver también DOM-1 y AGE-4.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-23 (decisión relacionada). qa-23 revisó `publish_due_items` solo por el horario de verano (es segura porque compara en UTC) y descartó probarla por eso. El diferido sigue valiendo para el DST, pero no cubre la duplicación de la transición; no hace falta reabrirlo, basta con tratar este hallazgo aparte.

#### ARQ-3 · Conocimiento duplicado entre capas sin nada que lo ate: rutas, proveedores, tipos y colores copiados en otro módulo

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Varias reglas viven en dos sitios y solo una convención las mantiene iguales; las pruebas ejercitan la copia, no la fuente:

1. La redacción de tokens en logs y Sentry usa una regex que copia las rutas de `community/urls.py` (`/novedades/confirmar|baja/`). La ruta con token vive en cuatro sitios: `urls.py`, `redaction.py` y dos veces en el Caddyfile. Todas las pruebas de redacción usan rutas literales, no `reverse()`.
2. `GRUPOS_DE_ALIADOS` repite `Partner.Kind`: un tipo nuevo se cuenta en la cabecera de `/aliados/` pero no aparece en ningún grupo.
3. El `frame-src` de la CSP repite los proveedores de `embeds.py`.
4. `CELERY_BEAT_SCHEDULE` nombra las tareas como texto y ninguna prueba comprueba que existan.
5. `Publication.lomo` calcula el contraste contra la tinta `#121823` escrita en Python, una copia de `--ink`.

**Evidencia.**

- `backend/config/redaction.py:27-29` frente a `backend/apps/community/urls.py:8-10`.
- `infra/caddy/Caddyfile:27, 92` — las dos copias del borde; ningún paso del CI las verifica.
- `backend/tests/test_log_redaccion_extra.py:25-26, 85-88` y `backend/tests/test_pii_retention.py:95-100` — rutas escritas a mano.
- `backend/apps/showcase/views.py:70-90`, `backend/apps/showcase/models.py:307-316` y `backend/templates/showcase/partner_index.html:10, 16` — la cabecera cuenta `partners|length` y el cuerpo solo recorre los grupos.
- `backend/config/csp.py:42, 108` y `backend/apps/media/templatetags/embeds.py:9-24`.

**Por qué importa a futuro.** Al construir la baja en un clic del boletín, un agente añade `novedades/baja-directa/<str:token>/`. Ni la regex de Python ni las del Caddyfile casan con «baja-directa», y el token de baja, que es permanente, queda escrito en el log JSON y en las transacciones de Sentry; la suite sigue en verde porque prueba rutas antiguas. Si se renombra `publish_due_items`, beat agenda cada minuto una tarea inexistente y la publicación programada se detiene sin ningún error visible.

**Recomendación.**

- Construir la regex de redacción de forma perezosa con `reverse('community:confirm', args=['X'])` y `reverse('community:unsubscribe', ...)`, probarla con `reverse()` y cubrir el Caddyfile con una prueba de CI. Lo de fondo es sacar el token de la ruta.
- Una tabla única de proveedores de embed (regex, plantilla del iframe, origen para la CSP) que lean `embeds.py` y `csp.py`.
- Derivar los grupos de aliados de `Partner.Kind`, con un grupo «Otros» para lo desconocido.
- Una prueba de que cada tarea de `CELERY_BEAT_SCHEDULE` está registrada tras el autodiscover (PRU-3).
- La tinta en una sola constante, o una prueba que la compare con `--ink`.

**Matiz de la verificación.** Se retiraron dos ejemplos: los tipos de propuesta frente a `ArticleType` (nada mapea uno al otro; queda como higiene en WEB-9 y MAN-1) y el tope 36 frente a 28 del manifiesto, que es intencional. El fallo de los proveedores sería visible en el navegador. La severidad media se sostiene por la redacción, los aliados y el beat; los proveedores y la tinta son de severidad baja.

#### ARQ-4 · Falta una capa de «sitio»: lo transversal cae en la app que se estaba tocando, y content se volvió el núcleo implícito

**Severidad:** media · **Esfuerzo:** L · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** No hay un hogar para las vistas, plantillas y modelos transversales, así que cada pieza quedó donde se escribió. `content` aloja la portada (que importa modelos de seis apps), la búsqueda de seis tipos, la navegación global y la URL canónica, los sitemaps de todo el sitio, `/healthz`, `/readyz`, `/robots.txt` y `/favicon.ico`, los ayudantes del pie de ficha (`pie.py`) y parciales comunes que usan cinco apps. `showcase` aloja `SiteProfile`, que mezcla la identidad global (cargada en cada página) con la configuración de la portada. Los roles se siembran en `people` y se comprueban en `content`, y la purga de datos personales de `community` y de axes vive en `submissions`. Sin contar los comandos de gestión, `content` importa seis de las otras siete apps. `content/views.py` (537 líneas, 40 commits) es el segundo archivo de código más reescrito, y siete de sus últimos ocho commits son de la portada.

**Evidencia.**

- `backend/apps/content/views.py:16-21, 144-214, 396-471, 474-537` — imports de seis apps, portada, búsqueda y sondas.
- `backend/config/urls.py:7-10, 14-22` — toma de `content` las vistas de infraestructura, el feed y los sitemaps.
- `backend/apps/content/pie.py:10-61` — lo importan `agenda/views.py:5`, `people/views.py:6`, `media/views.py:6` y `showcase/views.py:5`.
- `backend/apps/showcase/models.py:9-146` y `backend/apps/showcase/context_processors.py:6-26` — `SiteProfile` con `featured_recording`, `featured_poem` y `hero_image`, cargado en cada página.
- `backend/apps/submissions/management/commands/purge_stale_data.py:20-21, 39-50, 79-98` — purga suscriptores y registros de axes.
- `backend/apps/people/management/commands/setup_groups.py:58-60` frente a `backend/apps/content/permissions.py:9-13` — los nombres de los grupos, repetidos como literales.

**Por qué importa a futuro.** Un agente rediseña la portada y, para enseñar otra imagen, cambia el `select_related` de `_published()`: ese ayudante lo usan también el archivo de textos, las secciones, las etiquetas y la ficha de colaborador, así que cinco vistas cambian sin que nadie las revise. La próxima pieza transversal (aviso de cookies, créditos, envío del boletín) caerá en la app que el agente tenga abierta.

**Recomendación.** Por etapas:

1. Llevar `healthz`, `readyz`, `robots` y `favicon` a `config/views.py`, que ya es la capa de infraestructura, y las parciales comunes a `templates/partials/`. Son unas horas.
2. Crear una app de armazón (`apps.sitio`) con `pie.py`, la portada como `portada.py` (un constructor por bloque y una vista delgada), la búsqueda, los context processors y los sitemaps.
3. Opcional: mover `SiteProfile` con `SeparateDatabaseAndState`.

Llevar los roles a un módulo único (AGE-2) y la retención a funciones `purgar_*` de cada app, orquestadas por un comando del sitio.

**Matiz de la verificación.** `config/` ya es una capa transversal para la infraestructura; falta un hogar para el contenido transversal. «Mover un ayudante rompe cuatro apps» exagera: sería un ImportError inmediato y fácil de arreglar. Con un PR por lote en serie, los conflictos de fusión son improbables; el riesgo real son los ayudantes compartidos del archivo caliente y lo difícil que es encontrar las cosas. Las semillas tienen guarda de `DEBUG`/`--force` (HER-2). En el panel, `reviews` se rotula «Obras reseñadas», así que la confusión de nombres solo existe en el código.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, «Extracción SiteProfile → app siteconfig» (diferido conocido, «hacer aparte si el proyecto crece»). El problema es más ancho que `SiteProfile` y la condición «si el proyecto crece» ya parece cumplida. Conviene reabrirlo como una app del sitio, no como el traslado de dos modelos.

#### ARQ-5 · Contratos implícitos incoherentes entre entidades: URL, imagen social y campos del panel sin efecto

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Los protocolos que los consumidores dan por supuestos se cumplen a medias:

1. Work, Publisher, BookAuthor, Section y Tag no tienen `get_absolute_url`. Sus URL se componen por nombre de ruta en 17 sitios (11 en plantillas y 6 en Python) y el panel no ofrece «Ver en el sitio». Donde el método existe, al menos 10 sitios lo esquivan.
2. La regla «integrante → `/integrante/`, colaborador → `/colaborador/`» está en el modelo, otra vez en la búsqueda y una tercera vez como redirección.
3. Seis plantillas copian el bloque `og:image` con su respaldo, y ya derivan: artículo, evento y publicación dejan `twitter:card` en `summary` aunque caigan a la imagen del perfil, mientras poema y registro la suben a `summary_large_image`. `Article.og_image` se edita en el panel y no lo lee nadie; `Poem.og_image` sí se usa.
4. El `featured` de Article, Poem, Event y PressMention está en las columnas y filtros del panel sin ningún efecto (DAT-5), y el context processor sigue entregando `nav_sections`, que ninguna plantilla usa.
5. Event, Publication, PressMention y Partner no tienen `created_at` ni `updated_at`, y Recording solo `created_at`: sus sitemaps no pueden dar `lastmod`.

**Evidencia.**

- `backend/apps/reviews/models.py:4-105` y `backend/apps/content/models.py:15-40` — los cinco modelos sin `get_absolute_url`.
- `backend/templates/content/article_detail.html:46, 61, 62, 73`; `backend/apps/content/sitemaps.py:68, 161, 168, 175`; `backend/apps/content/views.py:248`; `backend/apps/showcase/views.py:32` — URL compuestas por nombre.
- `backend/apps/content/sitemaps.py:57, 93, 104, 148`; `backend/apps/content/feeds.py:49` — esquivan el método de Article, Collection, Page y Contributor.
- `backend/apps/content/views.py:275-279, 378-384` y `backend/apps/people/models.py:71-75` — la regla integrante/colaborador, tres veces.
- `backend/templates/content/article_detail.html:11, 14, 28-29` y `backend/apps/content/models.py:127-129` — la ficha usa `cover_image`; `og_image` no se lee.
- `base.html:26`, `article_detail.html:14`, `event_detail.html:12`, `publication_detail.html:12`, `poem_detail.html:14`, `recording_detail.html:11` — el `twitter:card` copiado.
- `backend/apps/content/admin.py:254-255, 272-273` y `backend/apps/agenda/models.py:6-48`.

**Por qué importa a futuro.** Una editora elige en el panel la imagen para compartir una reseña por WhatsApp con una gestora, y la ficha sigue publicando la portada o la del perfil, en una tarjeta pequeña. Si marca un evento como destacado, no pasa nada. El siguiente agente que ajuste la lógica social en una sola plantilla ampliará la deriva entre las seis.

**Recomendación.** Hacer obligatorio `get_absolute_url` en todo modelo con página y usarlo siempre: `{{ obj.get_absolute_url }}` en plantillas, `location` por defecto en los sitemaps y, en la búsqueda, una función de people del tipo `Contributor.url_de(slug, es_integrante)`. Un método `imagen_social()` por modelo (en Article, `og_image` y, si falta, `cover_image`) y una sola etiqueta `{% metadatos_sociales obj %}` para `og:image`, `twitter:card` y la imagen del JSON-LD. Quitar con migración, o conectar, los `featured` muertos, `nav_sections` y `Work.language`. Una base abstracta con `created_at` y `updated_at` para los modelos que no los tienen.

**Matiz de la verificación.** `PressMention.featured` quedó sin lector a propósito al retirar la cita de prensa de la portada (commit `7ee4e14`); hay una razón, pero el panel lo sigue ofreciendo. Componer URL con `{% url %}` es idiomático en Django y cambiar su forma es poco probable: lo más serio son los campos sin efecto y el bloque social, que ya derivó. `nav_sections` es un queryset perezoso y no cuesta consultas.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4, «Article no tiene get_absolute_url» (cerrado el 2026-09-02; decisión relacionada). Aquel cierre añadió el método solo a Article, Page y Collection. Era correcto, pero se aplicó caso por caso: conviene ampliarlo como contrato de toda entidad con página.

#### ARQ-6 · La lógica no tiene un lugar fijo: servicios, classmethods, helpers en vistas, presentación en modelos y reglas en apps.py

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Cada app decide a su manera dónde va la lógica. Hay dos `services.py` para ocho apps; cuatro classmethods que devuelven querysets en tres modelos (`Event.upcoming` y `past`, `Contributor.members`, `Call.open_now`), que no se pueden encadenar desde una relación (por eso `people/views.py` reescribe `member.events.filter(published=True)`); cuatro `_published()` en vistas y unos 28 filtros de visibilidad en línea. La presentación vive en modelos (`Publication.lomo` calcula luminancia y contraste; `MediaAsset.color_de_borde`) y en vistas (cada pliego de la portada es un dict de 13 claves armado en `content/views.py`). Las transiciones del suscriptor viven en las vistas de community. El procesamiento de imágenes se dispara desde tres puntos, con una dependencia de orden que solo explica un comentario. El olvido ya tiene una instancia latente: un registro publicado enseña su evento sin mirar `event.published` (AGE-1).

**Evidencia.**

- `backend/apps/agenda/services.py:1-5, 15-38` — su docstring dice que lo usa la portada, que dejó de hacerlo en el commit `30799d0`.
- `backend/apps/agenda/models.py:60-76` y `backend/apps/people/views.py:20-36` — classmethods y filtros repetidos sobre las relaciones.
- `backend/apps/content/views.py:37, 42-58, 84-141` — dos `_published`, el pliego de 13 claves y un filtro de plantilla importado en la vista.
- `backend/apps/media/views.py:28-29` — el pie del registro enseña su evento sin comprobar si está publicado.
- `backend/apps/showcase/apps.py:22-39`, `backend/apps/media/models.py:58-63` y `backend/apps/showcase/models.py:107-114, 229-249` — los tres disparadores de imágenes y la tinta escrita en el modelo.
- `backend/apps/community/views.py:70-82, 115-122, 149-151` — estados y tokens del suscriptor en las vistas.

**Por qué importa a futuro.** Para mostrar las próximas lecturas de una integrante, el agente no puede reutilizar `Event.upcoming()` sobre `member.events` y escribe otro filtro, con su propio olvido de `published`. Si cambia la paleta, `Publication.lomo` sigue midiendo contra una tinta que ya no existe.

**Recomendación.** Una regla corta en CONTRIBUTING.md, aplicada cada vez que se toque una zona:

- Las consultas reutilizables son métodos de QuerySet en `models.py` (`Event.objects.proximos()`, que también sirve como `member.events.proximos()`).
- Los cambios de estado van en `services.py` o `workflow.py`: mover el alta, la confirmación y la baja del boletín a `community/services.py` (TAR-3), y la purga a funciones que llamen el comando y la tarea.
- La lectura agregada de la portada y del dossier, en presentadores (dataclasses); los cálculos visuales, en templatetags o presentadores, no en modelos.
- Las señales, en `signals.py`, conectadas desde `ready()`.
- Para las imágenes, un único `procesar_imagen(asset)` encolado con `transaction.on_commit` (TAR-2).

**Matiz de la verificación.** Solo el docstring de `agenda/services.py` está desfasado; el de `content/services.py` es exacto. Son cuatro classmethods (no tres) y unos 28 filtros en línea (no 20). Conectar receptores en `ready()` es el patrón que documenta Django, y una prueba de comportamiento cubre el receptor de la portada (`backend/tests/test_portada_obra.py:158-171`), así que excluir `apps.py` de la cobertura no lo deja sin verificar; lo discutible son los tres disparadores. `people/views.py:36` no copia `Event.past()` (lista también las futuras): lo que falta es un QuerySet de visibilidad encadenable.

#### ARQ-7 · La documentación de la arquitectura y varios comentarios que hacen de contrato ya no son ciertos

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Lo primero que lee un agente describe otra aplicación. El README se presenta como «Revista literaria»; su «Estructura» lista seis apps (sin agenda ni showcase), atribuye Comment a community (se borró en la migración `0002_delete_comment`) y Dossier a content (es una vista de showcase), y apunta a `infra/nginx/` (hoy es Caddy). Otras afirmaciones falsas, comprobadas contra el código: `settings.py` dice que «media es la base», pero media depende de agenda, people, content y showcase; `agenda/services.py` dice que lo importan la portada y el dossier; `datos_de_desarrollo` y el README prometen «Viaja solo el contenido público»; el `help_text` de `PressMention.quote` dice «para portada y dossier», y la portada ya no cita prensa; Recording anuncia el feed de podcast «más adelante», y ya existe en `feed/registros/`. Hay además al menos 73 referencias a códigos de decisión o de hallazgo en el Python, 28 en plantillas y 40 en `site.css`.

**Evidencia.**

- `README.md:1-4, 20-35, 87-94` — identidad antigua, estructura obsoleta y la promesa de la exportación.
- `backend/apps/community/models.py:11` — la única clase es `NewsletterSubscriber`.
- `backend/config/settings.py:59` frente a `backend/apps/media/models.py:368, 377`, `backend/apps/media/views.py:5-6` y `backend/apps/media/feeds.py:50`.
- `backend/apps/media/models.py:319-323` y `backend/config/urls.py:10, 21` — el feed de podcast ya se sirve.
- `backend/apps/agenda/services.py:1-4, 15-20` y `backend/apps/showcase/models.py:287`.

**Por qué importa a futuro.** Un agente usa el README como mapa y busca los comentarios en community o el dossier en content. Lo grave es otro caso: el dueño restaura en desarrollo una copia de producción, pide «actualiza los datos de desarrollo», y el agente sigue el README, ejecuta `datos_de_desarrollo exportar` y sube al repositorio público los borradores y sus archivos (HER-1).

**Recomendación.** Primero, corregir la exportación (filtro por fila y una prueba; HER-1); eso va antes que la limpieza de comentarios. Después, corregir las afirmaciones y reescribir la «Estructura» del README a partir de `INSTALLED_APPS`, con una prueba que compare la lista del README con las apps instaladas. Adoptar la regla «el comentario dice qué hace el código hoy y por qué; la historia va al mensaje de commit» y aplicarla al tocar cada archivo, empezando por las docstrings de módulo (AGE-3).

**Matiz de la verificación.** Son siete afirmaciones falsas, no nueve: se retiraron dos. El comentario de `setup_groups` es cierto sobre su lista (si el editor debe gestionar agenda y showcase es una pregunta funcional; ver AGE-2) y `content/permissions.py` también rige para poemas. Las cifras de referencias son una cota inferior: la regex no cuenta «PR #NNN». La severidad subió de baja a media solo por la exportación; el resto, por sí solo, sería baja.

#### ARQ-8 · El grafo de dependencias no tiene capas: 7 de 8 apps forman un solo componente cíclico, y la app «base» depende de las de arriba

**Severidad:** baja · **Esfuerzo:** L · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `settings.py` ordena las apps «por dependencias: media es la base», pero media depende de agenda y de people en sus modelos (`Recording.event`, `Recording.participants`), de content en sus vistas y de showcase en su feed. Contando imports de Python, referencias a modelos y `reverse` entre espacios de nombres, siete apps forman un único componente fuertemente conexo; community solo depende de content. En las migraciones hay dos componentes, {media, people, agenda} y {content, reviews, showcase}. Hay nueve imports perezosos entre apps, en cuatro funciones, que no evitan ningún ciclo: solo esconden la dependencia. `Contributor.get_absolute_url`, en people, invierte una URL de content, una dependencia que un grep de imports no ve.

**Evidencia.**

- `backend/config/settings.py:59` — «media es la base».
- `backend/apps/media/models.py:367-378, 410`; `backend/apps/media/views.py:5-6`; `backend/apps/media/feeds.py:50`.
- `backend/apps/reviews/models.py:75-85` y `backend/apps/showcase/models.py:46-54, 191-193, 225` — `Work.publicacion`, `Publication.publisher` y `SiteProfile.featured_poem`.
- `backend/apps/media/migrations/0003_recording_event.py:9-12` y `backend/apps/agenda/migrations/0001_initial.py:11-14` — media depende de agenda, que depende de media.
- `backend/apps/content/services.py:75-77` y `backend/apps/content/feeds.py:23` — imports perezosos sin ciclo que evitar.

**Por qué importa a futuro.** Un agente que se fíe del comentario pondrá código compartido en media «porque es la base», o añadirá otro import perezoso para un ciclo que no existe, y el grafo real seguirá oculto. El coste es de comprensión: si alguien cierra un ciclo real de imports, el sitio no arranca, pero `manage.py check` y el CI lo detectan al momento.

**Recomendación.** Lo proporcionado: corregir el comentario de `settings.py`; mover `pie.py` y `permissions.is_editor` a un módulo neutro (con la app de sitio de ARQ-4, o un `apps/core`); subir al encabezado los imports perezosos innecesarios; y, como mucho, un contrato de import-linter en el CI que congele las aristas actuales para que no crezcan.

**Matiz de la verificación.** Son nueve imports perezosos, no seis, y community depende de content. Los ciclos de migraciones entre apps son habituales en Django y solo complican un squash, que aquí no hace falta. Un ImportError es ruidoso, no silencioso. Se descartaron como medidas para esta deuda el traslado de Recording con `SeparateDatabaseAndState` y la inversión del OneToOne entre Work y Publication. Severidad: de media a baja.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, «Extracción SiteProfile → app siteconfig», y §4, «Portada de podcast cuadrada (itunes:image)» (decisión relacionada). La arista media → showcase es el feed leyendo `SiteProfile`, y la extracción diferida la quitaría, pero no rompe los ciclos de modelos. El diferido sigue siendo razonable.

### 4.2 Modelo de datos, migraciones e integridad (DAT)

#### DAT-1 · El orden de firma de las coautorías (`position`) no se aplica en ninguna página

**Severidad:** alta · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** ArticleContributor y PoemContributor guardan `position` como «orden de firma (coautoría)» y ordenan por ese campo. Pero el código lee las firmas a través del M2M `authors`, cuyo gestor ordena por `Contributor.Meta.ordering = ["display_name"]`. Django no aplica el orden del modelo intermedio ni a `article.authors.all()` ni a `prefetch_related("authors")`: el SQL termina en `ORDER BY "people_contributor"."display_name" ASC`. Así, la firma sale en orden alfabético en la ficha, las tarjetas, las metas `article:author`, el JSON-LD, la tirada de la portada, el pie «Más de» y el RSS. No hay ni un uso de `articlecontributor__position` ni de `poemcontributor__position`. Reproducido en desarrollo: `/articulo/zz-largo-contra-la-lectura-apurada/` firma «Antonia Vergara, Matías Olivares, Rocío Carrasco, Tomás Figueroa», cuando las posiciones dicen Rocío, Matías, Antonia y Tomás; `/poema/zz-largo-inventario-del-patio/` invierte a sus dos firmantes. Ninguna prueba lo detecta porque los nombres de prueba ya están en orden alfabético.

**Evidencia.**

- `backend/apps/content/models.py:186-201` y `284-297` — los dos puentes, con `position` y `Meta.ordering = ["position"]`.
- `backend/apps/people/models.py:53-54` — `ordering = ["display_name"]`, el que de verdad aplica el M2M.
- `backend/apps/content/views.py:42-57, 104-117, 224-226, 251, 313` — precargas de `authors` sin orden y lecturas con `authors.all()`.
- `backend/apps/content/feeds.py:39, 54-56` — el autor del RSS.
- Plantillas: `content/article_detail.html:13, 25, 50`; `content/poem_detail.html:13, 35`; `content/home.html:97`; `content/partials/_article_card.html:19`; `content/partials/_poem_card.html:23`.
- Más precargas: `backend/apps/people/views.py:23, 30` y `backend/apps/showcase/views.py:54`.

En total son 12 lecturas (8 en plantillas y 4 en Python) y 8 precargas: unas 20 ubicaciones.

**Por qué importa a futuro.** El colectivo publica un texto a cuatro manos cuya primera firma no es la primera del alfabeto: la página, el RSS y los datos estructurados que leen los buscadores atribuyen el orden equivocado. La editora cambia la posición en el panel y no pasa nada. Toda vista nueva que liste firmas repetirá el error, porque el camino natural (`authors.all`) es el incorrecto.

**Recomendación.** Una sola API para la firma ordenada, por ejemplo una propiedad `firmas` en `EditorialItem` que lea el puente. En las vistas, precargar el puente y no el M2M: `Prefetch("articlecontributor_set", queryset=ArticleContributor.objects.select_related("contributor__photo").order_by("position", "pk"))`. El desempate por `pk` importa, porque el inline crea todas las filas con `position=0`. No usar `Contributor.objects.order_by("articlecontributor__position")` dentro de `Prefetch("authors")`: añade su propio join al puente, sin filtrar por el artículo, y puede duplicar o desordenar filas cuando una persona firma varios textos. Adaptar el filtro `firmas_sin` a la lista ordenada y reemplazar las 20 ubicaciones. Prueba con «Zoe» en posición 0 y «Ana» en 1 que compruebe ficha, tarjeta, pie «Más de», JSON-LD y RSS.

#### DAT-2 · Borrar una imagen, una persona o una obra arrastra contenido publicado sin que el panel lo muestre

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.**

- (a) Hay 15 claves foráneas hacia MediaAsset: 14 con SET_NULL (portadas, `og_image`, retratos, afiches, logos, la imagen de portada del sitio) y EventPhoto con CASCADE. La confirmación de borrado del admin solo enumera lo que cae en cascada. Verificado con NestedObjects: al borrar la tapa de una publicación solo lista «Recurso», mientras el Collector programa SET NULL sobre 14 columnas. Después filecleanup borra el archivo y sus derivados del disco: no hay vuelta atrás. Y como `get_deleted_objects` no pide permisos para los SET_NULL, ni para EventPhoto (un inline sin ModelAdmin), ni para las filas M2M autogeneradas, una editora sin permisos de showcase ni de agenda puede vaciar la portada, las tapas y los afiches borrando una imagen.
- (b) ArticleContributor y PoemContributor caen en cascada al borrar a la persona: sus textos y poemas publicados quedan sin firma. La confirmación lo anuncia como «ArticleContributor object (2)», porque los puentes no tienen `__str__`.
- (c) `ReviewedWork.work` también cae en cascada: borrar una obra desliga sus reseñas.
- (d) La GenericRelation borra la bitácora editorial junto con la pieza (DOM-6).

**Evidencia.**

- `MediaAsset._meta.get_fields(include_hidden=True)` (shell de solo lectura) — 15 relaciones inversas: 14 SET_NULL y `EventPhoto.asset` en CASCADE.
- `backend/apps/showcase/models.py:62-97, 196-198` — `og_image`, `hero_image`, `hero_image_phone` y `Publication.cover` con SET_NULL.
- `get_deleted_objects(..., admin.site)` con la editora (shell) — recursos 52 (una tapa) y 77 (la imagen social del sitio): solo «Recurso», con `perms=set()`.
- `backend/apps/agenda/admin.py:6-21` — EventPhoto solo existe como inline; `backend/apps/people/management/commands/setup_groups.py:10` — el editor no tiene showcase ni agenda.
- `backend/apps/content/models.py:186-201, 284-297, 204-218` — puentes en CASCADE y sin `__str__`; `ReviewedWork.work` en CASCADE (210).
- `backend/apps/media/filecleanup.py:42-50` — el archivo se borra en `post_delete`.

**Por qué importa a futuro.** La editora «limpia» la biblioteca de medios, que `seed_material_generico` llena de piezas provisionales, y borra «Foto de grupo provisional · Repitentes del Verso» (recurso 77). La confirmación solo dice «Recurso» y no exige ningún permiso adicional; al aceptar, el sitio pierde su imagen social por defecto, junto con cualquier tapa o afiche que la usara, y el archivo desaparece del disco. Al atender una petición de supresión, borrar el perfil de una persona deja sin firma su obra publicada.

**Recomendación.** `on_delete=PROTECT` en las autorías y en `ReviewedWork.work`, para obligar a reasignar antes de borrar, y también en las referencias públicas a MediaAsset. Como mínimo, sobrescribir `MediaAssetAdmin.get_deleted_objects` para listar los usos (recorriendo `Collector.field_updates`) y añadir una columna «Usado en». Dar un `__str__` legible a ArticleContributor, PoemContributor y ReviewedWork (EventPhoto ya lo tiene). Pasar Contributor a PROTECT obliga a diseñar el flujo de supresión de datos personales: desvincular o anonimizar las autorías antes de borrar.

**Matiz de la verificación.** El alcance es algo mayor de lo descrito: además de los SET_NULL, el CASCADE hacia EventPhoto y las filas M2M autogeneradas se borran sin pedir permisos. En (b) y (c), el panel sí muestra las filas puente que caen, con su recuento, aunque ilegibles: el «sin que el panel lo muestre» del título vale por completo solo para los SET_NULL. El punto (d) es el más débil (ver DOM-6).

#### DAT-3 · Búsqueda: el índice se define en SQL crudo y el plegado de acentos está duplicado con otra semántica

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El modelo declara `search_vector`, pero su contenido lo fija una función plpgsql escrita a mano en la migración 0011, que nombra las columnas tres veces (lista `UPDATE OF`, cuerpo de la función y reindexado). Django no la conoce, así que makemigrations no avisa al renombrar o borrar un campo. Los triggers dependen de `title`, `subtitle` y `body`, y Django borra columnas con `DROP COLUMN … CASCADE`: quitar `subtitle` elimina el trigger sin aviso, y renombrar `body` rompe todo guardado de artículos. Esas dos roturas las detectaría la suite, cuya base tiene los triggers; la tercera no: hacer buscable un campo nuevo (epígrafe, extracto) exige otra migración SQL, y nada avisa si falta.

Además, los acentos se pliegan dos veces con reglas distintas: el vector con `unaccent()` de PostgreSQL y el término con `_strip_accents` (NFKD de Python). Las letras sin descomposición Unicode (ø, ł, đ, æ, œ, ß) quedan distintas a cada lado: buscar «Wisława Szymborska» o «Czesław Miłosz» bien escritos no devuelve ningún texto, porque la consulta exige todos los términos. La búsqueda por nombre sí los encuentra, porque `__unaccent` pliega los dos lados.

**Evidencia.**

- `backend/apps/content/migrations/0011_unaccent_search.py:10-47` — la extensión, las funciones con `NEW.title`, `NEW.subtitle` y `NEW.body`, los triggers y el reindexado.
- `pg_depend` y `pg_trigger` (consulta de solo lectura) — los triggers dependen de esas columnas.
- `django/db/backends/base/schema.py:98` (Django instalado) — `sql_delete_column` con `CASCADE`.
- `backend/apps/content/models.py:102-107, 136, 177-183, 229-232, 252-253` — `search_vector` sin expresión; `Article.excerpt` y `Poem.epigraph` fuera del índice.
- `backend/apps/content/views.py:347-351, 424-425, 454-455` — `_strip_accents` y `SearchQuery(termino, config="spanish")`.
- SQL de verificación — la coincidencia da False con Søren, Wisława, Æsir, œuvre, Straße y Đorđe, y True con «reseña» y «Brontë».
- `backend/tests/test_search.py:61-91` — nada sobre `subtitle`, sobre qué columnas entran ni sobre letras sin descomposición.

**Por qué importa a futuro.** Hoy, un lector busca «Wisława Szymborska», la reseña existe y no aparece; con «Szymborska» sola, sí. A futuro, un agente quiere que el epígrafe de los poemas sea buscable, lo añade en la vista o en el modelo, makemigrations no genera nada y el campo sigue fuera del índice sin que ninguna prueba lo detecte.

**Recomendación.** Crear en una migración una configuración de búsqueda `es_sin_tildes` (`COPY = pg_catalog.spanish`, con `ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem`), usarla a ambos lados y quitar `_strip_accents` del FTS. Como `to_tsvector(regconfig, text)` es inmutable, el vector podría declararse en el modelo como `GeneratedField(expression=SearchVector("title", "subtitle", "body", config="es_sin_tildes"), db_persist=True)`; así makemigrations vería renombres y borrados y los triggers sobrarían. Conviene probarlo antes en una rama. Como mínimo: una prueba que compare las columnas del trigger con las del modelo y otra con «Wisława».

**Matiz de la verificación.** Es errónea la parte de que la extensión se usa desde cuatro apps sin declarar la dependencia: los cuatro lookups `__unaccent` están en `content/services.py`, la misma app que crea la extensión, y ninguna migración de otra app la usa. Cambiar el RunSQL por `UnaccentExtension()` es cosmético. Esas letras no tienen descomposición Unicode de ningún tipo (no es que les falte solo la canónica). El impacto es mayor que el ejemplo inicial de «Søren»: afecta a nombres frecuentes en un sitio de poesía.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «FTS por trigger de Postgres, no GeneratedField», y D3; §4, «epigraph en el trigger FTS de Poem». El hallazgo contradice la decisión: el motivo de fondo (unaccent no es IMMUTABLE) sigue en pie, pero se puede sortear con el envoltorio IMMUTABLE habitual o con la configuración de búsqueda propuesta, y D3 sumó un segundo plegado de acentos que hoy da resultados distintos. Conviene reabrirla. Como mínimo, una prueba que compare las columnas del trigger con el modelo y un único plegado de acentos.

#### DAT-4 · Los archivos se borran antes de que la transacción confirme el cambio

**Severidad:** media · **Esfuerzo:** S · **Confianza:** media · **Verificación:** confirmado

**Qué pasa.** filecleanup borra el archivo viejo en `pre_save`, antes del UPDATE y antes de que `FileField.pre_save` escriba el nuevo (orden verificado en el Django 5.2.18 instalado), y el de una fila borrada en `post_delete`, dentro de la transacción del Collector. Nada en el proyecto usa `transaction.on_commit`. Si el guardado falla después (disco lleno al escribir el archivo nuevo, una excepción en el resto de `MediaAsset.save()` o `SiteProfile.save()`, un OOM), la fila vuelve a apuntar al archivo viejo, que ya no existe. `strip_metadata` repite el patrón «destruir primero»: borra el original y guarda la copia limpia con el mismo nombre, fuera del try. La cobertura del borrado es completa (los cinco FileField están registrados): el problema es cuándo se borra.

**Evidencia.**

- `backend/apps/media/filecleanup.py:53-73` — `_al_reemplazar` borra el viejo y sus derivados en `pre_save`, sin `on_commit`.
- `backend/apps/media/filecleanup.py:21-27, 42-50, 76-91` — `_borrar` se traga cualquier excepción; `_al_borrar` en `post_delete`; el registro no usa `on_commit`.
- `django/db/models/base.py:988, 1008` y `django/db/models/fields/files.py:336-338` (Django instalado) — `pre_save.send` llega antes de `_save_table`, que es donde se escribe el archivo nuevo.
- `django/contrib/admin/options.py:1843, 2209` y `django/db/models/deletion.py:454, 507` — el changeform, el borrado y el Collector trabajan dentro de `transaction.atomic`.
- `backend/apps/media/models.py:58-63, 157-200` — `storage.delete(name)` (197) y `storage.save(name, ...)` (198) fuera del try.
- `backend/tests/test_file_lifecycle.py:99-154` — solo el camino feliz; ninguna prueba revierte una transacción.

**Por qué importa a futuro.** Con el disco del VPS lleno (por ejemplo por los 14 respaldos completos), un editor reemplaza el PDF del dossier o el audio de un registro: el vigente se borra, la escritura del nuevo falla con ENOSPC y la columna sigue apuntando a un archivo inexistente. El enlace del dossier y el enclosure del feed apuntan a nada, y solo se recupera desde el respaldo. Un futuro comando de importación que reemplace archivos dentro de `transaction.atomic()` y falle a mitad dejaría fichas rotas.

**Recomendación.** Diferir todo borrado a `transaction.on_commit(lambda: storage.delete(nombre))`. En el reemplazo, anotar el nombre viejo en `pre_save` (y saltarse el paso si `update_fields` no incluye el campo) y borrarlo en `post_save` con `on_commit`, como hace django-cleanup. Adoptar django-cleanup y dejar en filecleanup solo los derivados propios es una alternativa. En `strip_metadata`, escribir la copia limpia con un nombre temporal y sustituir con `os.replace`: nunca borrar antes de tener la copia. Prueba con `django_capture_on_commit_callbacks` y otra que fuerce una excepción después del guardado y compruebe que el original sigue en disco.

**Matiz de la verificación.** El núcleo se sostiene y el riesgo principal está en `pre_save`, que no necesita rollback: basta un ENOSPC. Son teóricos o inocuos el cambio de nombre en `strip_metadata` (con FileSystemStorage se reutiliza el mismo), los derivados huérfanos por concurrencia, que los manejadores no miren `raw` (loaddata crea instancias nuevas y `_al_reemplazar` sale antes de borrar) y el caso de `update_fields` (ningún camino actual de producción guarda así una instancia desactualizada).

#### DAT-5 · Campos que el panel ofrece y nadie lee; «destacado» modelado de tres maneras

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Cuatro de los seis booleanos `featured` (Article, Poem, Event y PressMention) solo aparecen en las columnas y filtros del admin: ninguna vista ni plantilla los lee. Lo mismo ocurre con `ReviewedWork.is_primary` (solo lo escriben las siembras, aunque el inline lo deja editar) y con `Work.language` (0 de 9 obras lo tienen en desarrollo). A la vez, «destacado» se resuelve de tres formas: un booleano en el ítem (Recording, con un tope de cinco que solo impone un slice, y Publication, por orden), una FK en SiteProfile (`featured_recording` como respaldo y `featured_poem`) y los booleanos sin uso. Estos cuatro no tienen `verbose_name` y aparecen en el formulario como «Featured», en inglés.

**Evidencia.**

- `backend/apps/content/models.py:133, 246` — `Article.featured` y `Poem.featured`.
- `backend/apps/agenda/models.py:43` y `backend/apps/agenda/admin.py:14-15` — `Event.featured`, solo en el admin.
- `backend/apps/showcase/models.py:212, 291` — `Publication.featured` se lee; `PressMention.featured` no.
- `backend/apps/content/models.py:204-211` — `is_primary`, que solo escriben `seed_textos_largos.py:328` y `seed_demo.py:850`.
- `backend/apps/content/views.py:78, 99-101, 150-166` — los únicos lectores de `featured`; `TOPE_TIRADA` solo como slice.
- `backend/apps/media/models.py:379-383, 422-424` — el `help_text` promete «hasta cinco» y `clean()` no lo valida: un sexto destacado se ignora sin aviso.

**Por qué importa a futuro.** Una editora marca un texto como destacado y no ocurre nada. Si se le pide a un agente «destacar textos en la portada», conectará `Article.featured` y aparecerán de golpe los textos marcados cuando la casilla no hacía nada (en desarrollo, 2 de 15), o creará un cuarto mecanismo.

**Recomendación.** Decidir con el dueño qué hacer con cada campo: quitarlo con una migración o conectarlo. Un solo mecanismo de destacado por tipo (booleano y `position`, con el tope validado en `clean()`), documentado en el modelo, y quitar el respaldo de SiteProfile si ya no hace falta. Mientras se decide, sacarlos de `list_display` y `list_filter`.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D19, D21 y D24 (decisión relacionada). Cada forma de destacar es razonable en su sección, pero ninguna decisión fijó un modelo común ni qué hacer con los cuatro `featured` sin lector. Conviene registrarlo.

### 4.3 Capa HTTP: vistas, URLs, formularios y consultas (WEB)

#### WEB-1 · Fichas de entidades secundarias sin regla de visibilidad ni contenido coherente con lo que enlaza a ellas

**Severidad:** alta · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Obra, editorial, autor de obra y colaborador externo no tienen estado propio, y su visibilidad no se deriva de nada: las vistas sirven cualquier fila y los sitemaps anuncian todas las obras, editoriales y autores. La única regla que existe vive en la búsqueda («una firma sin nada publicado no tiene qué enseñar en su página») y las fichas no la aplican. Comprobado en desarrollo: `/obra/antologia-del-margen/`, cuya única reseña está archivada, responde 200 («Reseñas de esta obra — Aún no hay publicaciones aquí») y aparece en `sitemap.xml`; lo mismo pasa con la editorial `laurel` y la autora `josefa-lillo`. Además, la ficha de una publicación del colectivo enlaza a su editorial, cuya ficha solo sabe de reseñas: `/editorial/ediciones-ceniza/` y `/editorial/la-polilla-editora/` salen vacías aunque tienen publicaciones del colectivo publicadas. Por código, un coautor externo de un poema aparece en la búsqueda y en las firmas del poema, pero su ficha solo lista textos y queda vacía.

**Evidencia.**

- `backend/apps/reviews/views.py:17-55` — `get_object_or_404` sin condición; `publisher.works.all()` y `author.works.all()` listan obras sin reseña publicada; solo `_reviews_of` (8-14) filtra por PUBLISHED.
- `backend/apps/content/sitemaps.py:151-178` — Work, Publisher y BookAuthor con `.all()`.
- `backend/apps/content/services.py:65-86` — la regla «integrante o con obra publicada», escrita solo dentro de `coincidencias_por_nombre`.
- `backend/apps/content/views.py:275-287, 313, 380-384` — `contributor_detail` sirve a cualquier colaborador y lista solo artículos.
- `backend/apps/showcase/views.py:27-34` y `backend/templates/reviews/publisher_detail.html:16-20` — la puerta «Editorial» lleva a una ficha sin las publicaciones del colectivo.
- `backend/templates/reviews/work_detail.html:18-24` — la visibilidad derivada resuelta a mano: `{% if work.publicacion and work.publicacion.published %}`.

**Por qué importa a futuro.** Al preparar una reseña, el editor crea desde el formulario del artículo la obra, su autora y su editorial. Desde ese momento, `/obra/x/`, `/autor/…/` y `/editorial/…/` responden 200 y figuran en el sitemap: el sitio anuncia a los buscadores qué libro va a reseñar aunque la reseña siga en borrador o se rechace, e indexa páginas vacías con el nombre del colectivo. Si la reseña se archiva, esas fichas siguen públicas sin plazo. Una gestora que pulsa «Editorial» en una publicación llega a una página que dice «Sin obras en el catálogo todavía».

**Recomendación.** Una visibilidad derivada en el QuerySet de cada entidad, usada a la vez por la vista, el sitemap y la búsqueda:

- `Work.objects.visibles()`: al menos un artículo publicado que la reseña (`Exists`) o una publicación del colectivo publicada.
- `Publisher.objects.visibles()`: obras visibles o publicaciones publicadas.
- `Contributor.objects.visibles()`: integrante o con obra publicada; es la expresión que hoy vive en `coincidencias_por_nombre`, extraída para no duplicarla.

Lo no visible responde 404. `publisher_detail` debe mostrar las publicaciones del colectivo con esa editorial, y `contributor_detail`, también los poemas. Hay que reescribir `test_bookauthor_detail_renders_with_its_works` (`backend/tests/test_reviews.py:51-59`), que fija el comportamiento actual.

**Matiz de la verificación.** Section no cuenta como entidad afectada (es taxonomía que mantiene el administrador): quedan cuatro tipos y tres sitemaps con el defecto. El caso del coautor externo de un poema no existe en los datos de desarrollo y se sostiene por el camino del código. Se separaron de este hallazgo, por ser problemas distintos, la fuga del registro hacia su evento (AGE-1) y los archivos servidos sin mirar el estado (DOM-4). También es real, y de severidad baja o media, que el rol autor tenga `reviews.change_work` sobre cualquier obra (`WorkAdmin` no filtra por dueño): edita páginas públicas sin pasar por el flujo editorial. Lo expuesto son metadatos de catálogo (título, autores, editorial, ISBN) y la intención de reseñar un libro; no se filtra texto ni datos personales. La severidad alta se mantuvo por mayoría del panel, por la repetición del patrón; uno de los tres verificadores la habría dejado en media.

#### WEB-2 · El pie de todas las páginas y el consentimiento de los formularios dependen de tres slugs editables

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `base.html` y `submit.html` enlazan con `{% url 'content:page_detail' 'privacidad' %}`, `'cookies'` y `'terminos'` a filas de Page creadas por migraciones de datos. Pero `PageAdmin` deja cambiar el slug, pasar la página a borrador o borrarla, y el grupo editor tiene esos permisos. Ninguna restricción, check ni prueba protege esos tres registros mientras el sitio funciona: las pruebas solo comprueban que existen tras migrar y que el pie trae los enlaces. La migración 0007 solo corre la primera vez y no vuelve a crear filas borradas.

**Evidencia.**

- `backend/templates/base.html:166-172` — consentimiento del boletín y pie legal, en todas las páginas.
- `backend/templates/submissions/submit.html:46-50` — el consentimiento del envío enlaza a `privacidad`.
- `backend/apps/content/admin.py:319-325` — `PageAdmin` sin `readonly_fields`, `has_delete_permission` ni `clean()`.
- `backend/apps/content/views.py:342-344` — `page_detail` exige PUBLISHED.
- `backend/apps/content/migrations/0007_legal_pages.py:55-68` — `PAGES` y `create_pages` con `get_or_create`.
- `backend/apps/people/management/commands/setup_groups.py:10, 76-81` — el editor tiene add, change, delete y view de Page.
- `backend/tests/test_newsletter.py:172-184` — solo el 200 y los enlaces del pie.

**Por qué importa a futuro.** Una editora pone «Política de privacidad» en borrador para reescribirla. Desde ese momento `/pagina/privacidad/` da 404, y los enlaces del pie y de los consentimientos del boletín (en todas las páginas) y de `/enviar/` remiten a una política que no existe: justo el documento que la Ley 21.719 exige poder consultar. Las altas y propuestas que entren mientras tanto se aceptan igual, y nada avisa.

**Recomendación.** Declarar las páginas de sistema en un solo lugar (`PAGINAS_LEGALES = ("privacidad", "cookies", "terminos")` en `content/models.py`, o un campo `clave` único y no editable que fije la migración) y protegerlas en el admin: slug y estado de solo lectura, sin borrado (`get_readonly_fields`, `has_delete_permission` y una validación en `clean()`). Registrar un check de `django.core.checks` que falle en `manage.py check --deploy` si alguna falta o no está publicada, y una prueba que intente despublicarlas desde el admin.

**Matiz de la verificación.** Renombrar el slug exige editarlo a propósito (el JS de prepopulate no reescribe el de una página ya guardada); lo probable es pasarla a borrador o borrarla. La identidad escrita en el código (cabecera del panel, remitente, respaldos `default:"Reseñas"`) se trata en FRO-6 y TAR-7, y los controles duplicados del destacado en DAT-5.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), «Texto legal de privacidad (Ley 21.719) es un BORRADOR», y §1 (técnicas), «serialized_rollback descartado» (decisión relacionada). El texto legal lo revisará un abogado desde el panel, la misma vía que hoy permite romper el pie: la decisión sigue siendo válida y refuerza la necesidad de proteger esos tres slugs.

#### WEB-3 · Las vistas cargan con la composición visual: textos, tipografía y medidas de pantalla en Python

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `home()` y `_registros_destacados()` no solo consultan: componen la página. Arman textos de interfaz (la firma entre comillas, el lugar con comas, el plural de «integrante», números con letras), deciden la tipografía (`TITULO_LARGO = 34` letras para bajar un paso el título) y fijan cuántos elementos caben (`ESTANTE = 8`, `A_LA_VISTA = 5`, `A_LA_VISTA_TELEFONO = 3`). Las pruebas importan esas constantes y buscan cadenas de `site.css`, así que cada ajuste de diseño toca a la vez vista, CSS y pruebas; el 5 y el 3 tienen además una tercera copia en `integrantes.js` (FRO-1). `home()` lleva 23 commits, 15 desde el 2026-10-07, casi todos de diseño. La presentación queda repartida sin criterio: «Lee/Leen» ya está en la plantilla y la firma, en la vista. A menor escala, los pies de ficha arman rótulos en Python y el ancla `#anio-AAAA` está escrita a mano en dos vistas y una plantilla, y `_resultado_por_nombre` trata cualquier tipo desconocido como actividad.

**Evidencia.**

- `backend/apps/content/views.py:65-81` — las constantes de maquetación, con su razón en prosa.
- `backend/apps/content/views.py:84-141, 144-214` — pliegos con firma, lugar y `largo`, cejilla con plural, puertas del cierre, numerales.
- `backend/apps/content/views.py:37, 130` — la vista importa el filtro de plantilla `primeros_versos`.
- `backend/templates/content/partials/_tirada.html:19, 36-40, 47-50` — la plantilla ya hace parte de la composición.
- `backend/static/css/site.css:1403, 1948-1949, 1966-1969` y `backend/static/js/integrantes.js:34` — las otras copias.
- `backend/tests/test_integrantes_portada.py:18, 81, 97, 103-108` y `backend/tests/test_estante.py:20, 61-62, 68-69` — importan las constantes y buscan literales de CSS y JS.
- `backend/apps/agenda/views.py:43-59` y `backend/apps/showcase/views.py:35-42` — el ancla `#anio-` a mano.

**Por qué importa a futuro.** Si piden que «Las voces» muestre seis, hay que cambiar Python, CSS, JS y los literales de las pruebas, y esos literales también fallan ante cualquier cambio inocuo del formato del CSS. Si un agente añade un tipo «obra» a `coincidencias_por_nombre` sin tocar `GRUPOS_DE_BUSQUEDA`, cualquier búsqueda que encuentre una obra da KeyError en `content/views.py:457` (un 500); si lo añade a los grupos pero no a `_resultado_por_nombre`, los resultados enlazan a una ficha de evento que no existe.

**Recomendación.** Dejar en la vista las consultas y pasar a la plantilla los datos y los indicadores visuales; los textos («Lee/Leen», comillas, plurales con `pluralize`), en la plantilla. Para los números que comparten capas, una sola fuente: la plantilla los emite como atributo `data-` o propiedad CSS y el CSS y el JS los leen (FRO-1). Un helper `url_de_anio(year)` en agenda. En la búsqueda, un diccionario `{tipo: (url_name, formateador)}` que lance un error explícito ante un tipo desconocido. Que las pruebas comprueben comportamiento (cuántos ejemplares hay en el HTML) y no el valor de la constante (PRU-2).

**Matiz de la verificación.** Es falso en gran parte que los comentarios con códigos de decisión hayan perdido su razón: los códigos D siguen documentados en `docs/deferidos-y-decisiones.md` y, en todos los comentarios revisados, la razón está escrita en prosa. Son etiquetas colgantes, no razones perdidas, y la cifra de 30 referencias no se reprodujo (salen 20 en los `views.py`). Las inclusion tags que consulten la base llevarían las consultas al renderizado; mejor que la vista siga consultando. Armar los rótulos del pie con `pie.py` es defendible. Para el 5 y el 3, `test_cinco_en_la_fila_y_tres_en_el_telefono` sí falla si una capa se desalinea. Lo de `_resultado_por_nombre`, por sí solo, sería baja. La parte de las pruebas se cuenta en PRU-2.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D19, D23 y D33, y §4, «La división con guion de los títulos» (decisión relacionada). Las reglas de composición son decisiones aprobadas: se discute dónde viven, no su contenido, y pasarlas a filtros o parciales no toca lo aprobado. §4 fija además otro umbral de título largo (90 letras) para el resto del sitio, que conviene unificar o justificar junto a `TITULO_LARGO = 34`.

#### WEB-4 · Las parciales de fila dependen de precargas que cada vista recuerda o no: N+1 y paginación que desaparece en silencio

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `_article_card.html` necesita `section`, `cover_image` y `authors` precargados, y `_poem_card.html` necesita `authors` y `recording`. Cada vista arma su queryset. `content._published()` lo hace bien, pero `member_detail`, `collection_detail` y `reviews._reviews_of` (que alimenta las fichas de obra, editorial y autor) no traen `cover_image`, y `collection_detail` tampoco `poem__recording`: hacen una consulta por fila. Además, `_article_list.html` incluye la paginación con `pagina=articles` y espera un Page; las fichas de obra, editorial y autor le pasan un QuerySet, así que `has_other_pages` se resuelve en silencio a vacío y la lista queda sin tope. Medido: `/coleccion/nuevas-voces/` hace 13 consultas, tres de ellas a `media_mediaasset` (una por texto con portada) y una a `media_recording`.

**Evidencia.**

- `backend/apps/people/views.py:20-25, 27-33, 42` — textos sin `cover_image`; poemas y registros sin tope.
- `backend/apps/content/views.py:319-331` — los enlaces de la colección sin esas relaciones.
- `backend/apps/content/views.py:42-57` — los querysets correctos, privados de `content/views.py`.
- `backend/apps/reviews/views.py:8-14, 30-55` — `_reviews_of` sin `cover_image` y sin paginar.
- `backend/apps/showcase/views.py:49-57` — `publication_detail` sí lo pide: la regla se cumple en un sitio y en otros no.
- `backend/templates/content/partials/_article_list.html:9` y `_pagination.html:7` — `{% if pagina.has_other_pages %}` no dibuja nada con un QuerySet.

**Por qué importa a futuro.** Cada ficha nueva que liste textos o poemas copiará el queryset más cercano y heredará el N+1, y quien cambie la fila (por ejemplo, para mostrar la sección de cada poema) tendrá que encontrar a mano los ocho querysets que la alimentan.

**Recomendación.** Un único queryset de origen por parcial, montado sobre el QuerySet de visibilidad (AGE-1): `Article.objects.publicados().para_fila()` (`select_related("section", "cover_image").prefetch_related("authors")`) y `Poem.objects.publicados().para_fila()` (`select_related("recording").prefetch_related("authors")`), usados también como `Prefetch("article", queryset=Article.objects.para_fila())` en colecciones y reseñas. Separar la paginación de `_article_list.html`, paginar las reseñas o hacer que la parcial falle de forma visible si no recibe un Page. Ampliar la prueba de miniaturas a las cinco vistas: sembrando imagen, sección, autoría y registro, 2 y 6 filas deben costar las mismas consultas.

**Matiz de la verificación.** Son cinco vistas afectadas, no tres; las plantillas que incluyen las parciales son 12 y los querysets que las alimentan, 8. Que la portada pase un QuerySet recortado a tres es intencional: ahí no hay error. Las listas de reseñas sin tope tienen hoy una o dos filas. El coste son unas pocas consultas por clave primaria en un sitio de poco tráfico, y la corrección es local: severidad de media a baja.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), D4, «guardia de queries sí, carga con umbral no» (decisión relacionada). D4 puso presupuestos de consultas solo en las vistas que mide; el hallazgo pide extenderlos o centralizar el queryset. La decisión sigue siendo buena.

#### WEB-5 · La limitación de tasa de la búsqueda se salta con peticiones HEAD

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `search` lleva `@ratelimit(key="ip", rate="60/m", method="GET", block=False)`. django-ratelimit solo cuenta los métodos indicados, pero Django ejecuta la vista completa también en HEAD (solo descarta el cuerpo). Comprobado con `django.test.Client`: tras 61 GET la respuesta sale limitada y hace 3 consultas, ninguna de búsqueda; cada HEAD a la misma URL sigue lanzando las 3 de búsqueda (texto completo de textos y de poemas, y la UNION por nombre), 6 en total.

**Evidencia.**

- `backend/apps/content/views.py:396, 422-423` — el decorador y la lectura de `request.limited`; no hay `@require_safe`.
- django_ratelimit 4.1.0 en el contenedor, `decorators.py:14-29` y `core.py:88-93, 169-170` — si el método no casa, ni cuenta ni limita.
- `backend/apps/community/views.py:49-50` y `backend/apps/submissions/views.py:17-19` — los límites de POST no se ven afectados.

**Por qué importa a futuro.** Un rastreador o un abuso con HEAD castiga justo el endpoint que el límite quería proteger, sin que el contador lo note.

**Recomendación.** `method=["GET", "HEAD"]` (o `ratelimit.ALL`) y `@require_safe`, para dejar explícitos los métodos admitidos. Prueba: 61 GET y después un HEAD, y con `CaptureQueriesContext` comprobar que no corre ninguna consulta de búsqueda.

**Matiz de la verificación.** No hay un límite global, y `GET /` (19 consultas, unos 65 ms) ya cuesta más que un HEAD a `/buscar/` (6 consultas, unos 40 ms): la evasión no cambia la exposición del sitio. Es falso que los logs no lo distingan: el log de acceso de Caddy registra el método. Que el ILIKE se encarezca al crecer el archivo está exagerado: textos y poemas usan texto completo con índice GIN. Severidad: de media a baja.

#### WEB-6 · Un `next` arbitrario en el alta del boletín produce un 500 público

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `_safe_next` devuelve en la misma variable una ruta (`request.POST["next"]`) o un nombre de URL (`"content:home"`), y cada rama de `subscribe` termina en `redirect(nxt)`. `redirect()` intenta primero `reverse(nxt)` y, si el texto no tiene «/» ni «.», relanza NoReverseMatch; a la vez, `url_has_allowed_host_and_scheme` da por válida una palabra suelta como URL relativa. Comprobado: un POST a `/novedades/` con un correo inválido y `next=agenda` devuelve 500, y `next=feed` redirige a `/feed/`.

**Evidencia.**

- `backend/apps/community/views.py:38-46, 58-82` — `_safe_next` y las cuatro salidas con `redirect(nxt)`.
- `django/shortcuts.py`, `resolve_url` (Django 5.2.18 en el contenedor).
- `backend/templates/base.html:159-161` — el único formulario envía `next={{ request.path }}`, que siempre empieza por «/».
- `backend/tests/test_newsletter.py:100-122` — no hay ningún caso con una palabra suelta.

**Por qué importa a futuro.** Los escáneres que rellenan formularios con valores de prueba provocan 500 en el formulario que está en el pie de todas las páginas, con un evento en Sentry si está configurado.

**Recomendación.** Que `_safe_next` devuelva siempre una URL: `nxt if nxt and nxt.startswith("/") and url_has_allowed_host_and_scheme(...) else reverse("content:home")`, y redirigir con `HttpResponseRedirect(nxt)`, que no interpreta el texto como nombre de vista. Pruebas con `next="agenda"`, `"//evil.com"`, `"feed"` y `""`.

**Matiz de la verificación.** Exige una petición manipulada con un token CSRF válido; sin él, la respuesta es 403. Con un correo válido, el suscriptor se guarda y la confirmación se encola antes del 500 (no hay `ATOMIC_REQUESTS`): el alta queda hecha y el visitante ve un error. Sentry agruparía los eventos en una sola incidencia, y el riesgo de reutilizar el helper es especulativo. Exigir `startswith("/")` elimina de paso el `Location: evil.com`, que hoy el navegador resuelve como ruta relativa (no es una redirección abierta). Severidad: de media a baja.

#### WEB-7 · La URL canónica y la paginación se calculan por separado y no coinciden

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El procesador `canonical` relee `request.GET["page"]` en todas las páginas, sin saber si la vista pagina ni qué página sirvió. Las vistas paginan con `get_page()`, que corrige en silencio cualquier valor raro y responde 200. Comprobado con curl: `/dossier/?page=7` y `/poema/<slug>/?page=3`, que no paginan, declaran canónica su propia URL con `?page=`; `/textos/?page=99999` y `?page=0` sirven la última página con canónica `?page=99999` o `?page=0`; `?page=01` y `?page=²` (porque `"²".isdigit()` es True) sirven la página 1 con otra canónica.

**Evidencia.**

- `backend/apps/content/context_processors.py:82-90` — `page.isdigit() and page != "1"` sobre el query string crudo.
- `backend/apps/content/views.py:61-62` — `_paginate` nunca da 404; `backend/apps/media/views.py:17` y `backend/apps/people/views.py:42` — dos copias en línea con el mismo 12.
- `backend/templates/content/partials/_pagination.html:13-32` — enlaces `?page=N` que reemplazan todo el query string.
- `backend/tests/test_seo.py:112-115` — exige la canónica `?page=2` en la portada, que no pagina: fija el defecto.

**Por qué importa a futuro.** Los enlaces antiguos y los rastreadores generan URL duplicadas que se declaran canónicas a sí mismas, justo lo que el procesador quería evitar. Quien añada un filtro (`?tipo=ensayo`) tendrá que acordarse de un procesador global que nadie relaciona con su vista.

**Recomendación.** Un único helper `paginar(request, qs, por_pagina=12)` que use `paginator.page()`, devuelva 404 (o redirija a la canónica) ante valores no enteros o fuera de rango y deje la página servida en `request` (`request.pagina_servida = page.number`). `canonical` añade `?page=N` solo si ese atributo existe y N > 1. Pruebas para `?page=0`, `?page=99999`, `?page=01` y para `?page=` en una página que no pagina; cambiar la de `test_seo.py`.

**Matiz de la verificación.** No son tres formas distintas de paginar, sino un helper sin reutilizar y dos copias en línea de la misma expresión. Que `?page=N` borre el query string es un riesgo a futuro: hoy ningún listado paginado usa otros parámetros.

#### WEB-8 · Semántica HTTP y endpoints auxiliares sin una convención común

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Varias decisiones de protocolo se toman caso a caso:

- `/buscar/` devuelve fragmento o página completa en la misma URL según `HX-Request`, sin `Vary: HX-Request`, y cualquier valor de la cabecera activa el fragmento.
- Al superar el límite de tasa, la búsqueda y las propuestas responden 200 y el boletín 302; nunca 429 ni `Retry-After`.
- `confirm` y `unsubscribe` tratan cualquier método que no sea POST como GET.
- `submission_file` da 500 si el adjunto no está en disco.
- El `except DatabaseError` de la búsqueda no usa savepoint: rompería la transacción si algún día se activa `ATOMIC_REQUESTS`.
- Los dos feeds se registran de dos formas (instancia compartida y fábrica por petición), con la trampa de hilos documentada solo en uno; el de podcast tiene título y descripción fijos y el de textos los lee del perfil; los `link` están escritos a mano. Las sondas, `robots` y `favicon` viven en `content/views.py`, con imports dentro de las funciones.

`grep -rn "require_http_methods\|require_safe\|require_GET\|vary_on\|cache_control" backend/apps backend/config` no encuentra nada: el único decorador de método es un `@require_POST`.

**Evidencia.**

- `backend/apps/content/views.py:419, 470` — `panel = bool(request.headers.get("HX-Request"))`; con curl, ninguna de las dos respuestas lleva `Vary`.
- `backend/templates/base.html:100-104` — `action` y `hx-get` apuntan a la misma URL con el mismo `name="q"`.
- `backend/apps/community/views.py:59-61, 108, 134-147` y `backend/apps/submissions/views.py:17-29, 48-57`.
- `backend/apps/content/views.py:441-464, 474-536` — el `except` sin `atomic` y las sondas.
- `backend/config/urls.py:17-21`, `backend/apps/media/feeds.py:43-47, 63-75` y `backend/apps/content/feeds.py:17-33` — los feeds.

**Por qué importa a futuro.** Fragmento y página completa comparten entrada en la caché HTTP: al volver atrás sin bfcache se puede ver el fragmento de 1,7 KB, sin cabecera ni estilos, y lo mismo pasaría con cualquier caché que se añada a la búsqueda. Un agente que copie `LatestArticlesFeed` y guarde la request en `self` para armar URL absolutas reintroduce la carrera entre hilos que ya se corrigió en el otro feed.

**Recomendación.** `@vary_on_headers("HX-Request")` en `search`, y decidir el fragmento por `request.headers.get("HX-Target") == "search-results"`. `@require_http_methods(["GET", "POST"])` en `confirm` y `unsubscribe`, y `@require_safe` en las vistas de lectura. Respuesta 429 con `Retry-After` en las variantes de página completa. Convertir `FileNotFoundError` en `Http404` en `submission_file`. Envolver el bloque de texto completo en `with transaction.atomic():`. Registrar los dos feeds de la misma forma y sin estado en `self` (con un `SITE_URL`, COM-6), con el título desde el perfil y `link` con `reverse_lazy`. Llevar sondas, `robots` y `favicon` a `config/views.py`. Para el `connect_timeout` de la base, ver RES-7.

**Matiz de la verificación.** Se descartaron dos puntos. Que no haya `Cache-Control` ni `Vary: Cookie` es el comportamiento estándar de Django y no tiene efecto sin una caché compartida. Pasar a 301 la redirección colaborador → integrante sería dañino, porque `is_member` es mutable: debe seguir en 302. La ausencia de métodos explícitos en `confirm` y `unsubscribe` es higiene, sin riesgo. Lo concreto hoy no es hx-boost (no se usa) sino que fragmento y página compartan URL.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-23 (que cita qa-10, el respaldo del buscador sin JavaScript), y §1 (UX), D2 y D16 (decisión relacionada). Servir fragmento o página en la misma URL es como se cubrió el buscador sin JavaScript, y sigue siendo razonable; faltan `Vary: HX-Request` y no tratar como fragmento toda petición que traiga esa cabecera.

#### WEB-9 · Formularios públicos: límites, vocabularios y campos copiados a mano entre capas

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Duplicaciones que nada mantiene sincronizadas:

- El tope de 10 MB aparece en cinco sitios: `MAX_FILE_MB`, el `help_text` literal «Máximo 10 MB», un comentario de settings, un comentario del Caddyfile y el `max_size 12MB` de Caddy. Los formatos admitidos se repiten en `ALLOWED_EXTENSIONS` y en el `help_text`.
- `SUBMISSION_TYPES` usa claves con tilde («reseña», «poesía», «crónica») que no coinciden con `ArticleType` («resena», «poesia»; los conjuntos además difieren), y `Submission.type` no tiene `choices`: el admin muestra el valor crudo.
- Hay dos honeypots distintos: el de propuestas es un `HiddenInput`, que los bots suelen devolver vacío; el del boletín es un campo de texto oculto con CSS.
- El formulario del boletín está escrito a mano en `base.html` y no usa `SubscribeForm`: los nombres de campo están duplicados.
- El correo del boletín no se normaliza, y `unique` distingue mayúsculas: `Ana@X.cl` y `ana@x.cl` son dos suscriptores (TAR-3).

**Evidencia.**

- `backend/apps/submissions/forms.py:7-8, 72-86, 98-100, 119-120` — constantes, claves con tilde, el `HiddenInput` y el `help_text` literal.
- `infra/caddy/Caddyfile:38-42` y `backend/config/settings.py:159-160` — las otras copias del tope.
- `backend/apps/submissions/models.py:52` y `backend/apps/submissions/admin.py:21` — `type` sin `choices` y fuera de `list_display`.
- `backend/templates/base.html:159-165` frente a `backend/apps/community/forms.py:10-11`.
- `backend/apps/community/views.py:70` y `backend/apps/community/models.py:26` — `get_or_create` con el correo tal cual y `EmailField(unique=True)`.
- `backend/tests/test_security_uploads.py:85-86` — el Caddyfile está fuera de la imagen: la prueba de coherencia tiene que correr en el CI, no en el contenedor.

**Por qué importa a futuro.** Si alguien sube el tope a 15 MB, el `help_text` seguirá diciendo 10 y Caddy cortará un adjunto de 13 MB con un 413 genérico antes de llegar al mensaje de Django. Una persona que se suscribe dos veces con distinta capitalización puede confirmar las dos filas y recibir cada boletín por duplicado.

**Recomendación.** Generar los textos de ayuda desde las constantes (`f"… Máximo {MAX_FILE_MB} MB."`, formatos desde `ALLOWED_EXTENSIONS`) y añadir una prueba de CI que lea `max_size` del Caddyfile y exija que supere `MAX_FILE_MB` con margen. `Submission.Type(TextChoices)` con claves sin tilde, `choices` en el campo, una migración de datos y, si se quiere garantía en la base, un CheckConstraint. Un `HoneypotMixin` común, siempre como campo de texto oculto con CSS. El formulario del pie, pintado desde `SubscribeForm` con una inclusion tag. Un `clean_email` que pase a minúsculas y, tras deduplicar, `UniqueConstraint(Lower("email"))`.

**Matiz de la verificación.** El pie no repite el `max_length`, solo los nombres de campo. El tope aparece en cinco sitios, no en cuatro. Añadir `choices` no hace que la base rechace nada. El desajuste con `ArticleType` exigiría un mapeo explícito de todas formas, así que el riesgo de «aceptar una propuesta como artículo» es especulativo. El honeypot débil lo amortigua el límite de 10 envíos por hora y por IP. Lo más concreto y barato es normalizar el correo.

### 4.4 Plantillas, CSS y JavaScript (FRO)

#### FRO-1 · Las mismas medidas de maquetación están copiadas en Python, CSS, JS y atributos sizes

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Cada «perilla» de la portada está escrita a mano en varios lenguajes, sin una fuente única, y las pruebas fijan las copias, no la relación entre ellas (`assert A_LA_VISTA == 5`, `"repeat(5, minmax(0, 1fr))" in SITE_CSS`, `"movil.matches ? 3 : 5" in INTEGRANTES_JS`):

- Integrantes visibles (5 y 3): la vista, tres reglas CSS, tres lugares de `integrantes.js` (incluido `ORDEN`, que solo tiene las claves 5 y 3) y el `sizes` del parcial.
- Tope de la tirada (5): `TOPE_TIRADA`, `NUMERALES` y 16 selectores CSS desenrollados hasta cuatro vecinos por lado. El `z-index: 30` del reparto en `registros.js` tiene que superar a mano el 10 del CSS.
- Obra de portada: `images.py` repite el asomo (96 y 112 px), el alto mínimo de 460 px y el corte de 719 px de la hoja.
- `sizes`: 720 px aparece 12 veces en 9 plantillas y 719 px, 3 veces, frente a 719/720 en el CSS. `_foto.html` replica la lógica del mosaico y ya se equivoca.
- Curvas: el JS copia `--ease` y la curva de la tirada.

Ya hay una divergencia: la fuente de titulares se recortó a los pesos 400-700 («lo que usa el sitio», según su NOTICE.txt) y dos reglas posteriores piden `font-weight: 800`, que se pinta a 700. El desenrollado de la pila se justifica en comentarios y pruebas con que «la CSP no admite estilos en línea», pero `style-src 'self'` bloquea los atributos `style`, `setAttribute('style')` y `cssText`, no `el.style.setProperty()`.

**Evidencia.**

- `backend/apps/content/views.py:67-68, 73, 78-79, 99, 192-195` — `A_LA_VISTA`, `A_LA_VISTA_TELEFONO`, `ESTANTE`, `TOPE_TIRADA` y `NUMERALES`.
- `backend/static/js/integrantes.js:15, 18, 34, 82-83` — `ORDEN = { 5: [...], 3: [...] }` y `V = Math.min(movil.matches ? 3 : 5, n)`; con otro V, `ORDEN[V]` es undefined y el intervalo lanza TypeError en cada tick.
- `backend/static/css/site.css:1455-1465, 1482-1489` — los 16 selectores; un sexto pliego quedaría en `--x:0` y `z-index:1`, debajo del de arriba.
- `backend/static/js/registros.js:5-6, 13, 46-49` y `backend/tests/test_tirada.py:50-56, 169-175` — la prueba prohíbe `.style` en el guion.
- `backend/apps/media/templatetags/images.py:9, 39-57` frente a `backend/static/css/site.css:1048-1051, 1060-1061`.
- `backend/templates/agenda/partials/_foto.html:14-20` — con una foto pide siempre 880 px; el CSS la pone a todo el ancho con 1 foto y a media con 2, 4 y 5.
- `backend/tests/test_integrantes_portada.py:103-108` — fija las copias, pero no cubre `ORDEN` ni el `sizes` de `_member_card_portada.html:11`.

**Por qué importa a futuro.** El dueño pide seis registros en la tirada. El agente sube `TOPE_TIRADA`, ve fallar `test_tirada.py` (crea 6 y espera 5), la ajusta, y nada le señala los 16 selectores: el sexto pliego queda tapado bajo el primero en el estado inicial. O pide cuatro voces en la fila: con el JS en `movil.matches ? 3 : 4`, `ORDEN[4]` es undefined y el relevo lanza un TypeError cada 1,8 s.

**Recomendación.** En este orden:

1. `integrantes.js`: generar el orden salteado para cualquier V, o leer el número de `data-a-la-vista` y `data-a-la-vista-telefono`, que pone la plantilla desde `A_LA_VISTA`; el CSS lee una propiedad declarada una sola vez.
2. Tirada: una prueba que cuente en `site.css` los niveles de la pila y los compare con `TOPE_TIRADA − 1`. Alternativa: calcular `--x`, `--y`, `--g` y `z-index` en `registros.js` con `setProperty()`, limitando la prohibición de la prueba a `cssText` y `setAttribute('style')` y corrigiendo los comentarios. Las posiciones están ajustadas a mano y el tope de 5 es una decisión razonada: lo proporcionado es la prueba.
3. Corregir el `sizes` de `_foto.html` para 1, 2, 4 y 5 fotos: es el único defecto vigente con efecto.
4. Cambiar `font-weight: 800` por 700.

El resto es higiene para cuando se toque la zona: un módulo de cortes con nombre (`TELEFONO = 719`) y una etiqueta `{% sizes 'tapa-estante' %}`, con una prueba de que cada corte existe en `site.css`; `--ease` leída con `getComputedStyle`; y pruebas de relación entre fuente y copias.

**Matiz de la verificación.** Era falso que con `TOPE_TIRADA = 6` pasaran todas las pruebas: falla `test_tirada.py`, aunque al ajustarla nada señala la pila. El sexto pliego no queda siempre invisible: queda tapado mientras el primero está al frente, que es el estado inicial. El desfase 719/720 solo afecta a una ventana de 720 px exactos y `sizes` es solo una pista. La diferencia entre TinyMCE y nh3 es inocua (el servidor manda), y el z-index 30 frente a 10 tiene margen. Severidad de alta a media: los fallos son visuales y el dueño revisa la portada en pantalla.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D19, D23 y D24-D25 (decisión relacionada). `ESTANTE` ya cambió una vez (de 6 a 8), lo que muestra el riesgo de tenerlo en varios lenguajes. Los valores siguen vigentes: el hallazgo trata de dónde viven.

#### FRO-2 · La mejora progresiva falla mal: el CSS da por hecho que el JS se montó bien

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El modo «con JavaScript» se activa antes de saber si el guion funcionó. En la portada, la cabecera se esconde con `@media (scripting: enabled)` y solo reaparece cuando `cabecera.js` pone `data-barra`: si el guion no llega o lanza una excepción, la portada queda sin barra en todo el desplazamiento (medido bloqueando el guion: a 2500 px, `data-barra` nulo y opacidad 0). En la tirada, `registros.js` añade `.con-js` y destapa la hoja de contactos antes de `marcar(0)`; si algo falla después, la pila queda en modo JS sin parte de sus manejadores (simulado en Chromium: los cinco pliegos superpuestos, en gris, y los contactos visibles sin efecto). Los montajes no comprueban que existan los nodos que necesitan, y en el estante cada lomo se empareja con su ficha solo por el orden de dos bucles distintos de la plantilla.

**Evidencia.**

- `backend/static/css/site.css:427-474` — el bloque `@media (scripting: enabled)`, con 22 reglas; la 465 esconde la cápsula y solo `:focus-within` la revierte.
- `backend/static/js/cabecera.js:4, 9, 34-45` — el comentario «Sin JavaScript queda la cabecera fija» solo vale si no hay scripting, no si el guion falla.
- `backend/static/js/registros.js:18-27, 57-72, 102` y `backend/templates/content/partials/_tirada.html:17, 58-60, 65`.
- `backend/static/js/estante.js:19-21, 28-31, 49, 58, 60` y `backend/templates/content/home.html:185-198, 207-214` — dos bucles emparejados por índice; `backend/tests/test_estante.py:37-51` no compara cada lomo con su ficha.
- `backend/templates/base.html:63, 158` — mitigación: sin cabecera queda el mapa del pie.

**Por qué importa a futuro.** Un agente retoca `cabecera.js` y deja un error de sintaxis. El CI no tiene ningún paso de JavaScript y queda en verde; quien usa ratón o dedo se queda sin barra en la página más visitada, con solo el mapa del pie y el botón del dossier. Un filtro añadido a uno solo de los bucles del estante hace que cada lomo abra la ficha de otro libro.

**Recomendación.**

1. Que la marca la ponga el propio guion al montarse y que el CSS dependa de ella: `cabecera.js` pone `html[data-barra=arriba]` al iniciar y la cápsula solo se esconde con esa marca. Para no parpadear en la primera pintura, esa primera línea va en el `<head>` sin `defer` (es `'self'`) o en un `<script nonce>`. Sin la marca, rige la cabecera clásica.
2. En `registros.js`, añadir `.con-js` y quitar `hidden` al final de `montar`, dentro de un try/catch que deshaga el estado si algo falla.
3. Al principio de cada `montar`, comprobar los nodos requeridos y salir sin tocar nada si falta alguno.
4. En el estante, enlazar lomo y ficha por id (`aria-controls` o `data-ficha`), no por posición.

Y en el CI, `node --check` y una prueba de humo en navegador (PRU-2).

**Matiz de la verificación.** El bloque tiene 22 reglas, no 24. La rama sin IntersectionObserver es inalcanzable en la práctica (todo navegador con `scripting` y `:has()` lo tiene): es código muerto que despista. `integrantes.js` no ilustra el patrón, porque falla antes de tocar nada. El caso de `estante.js` con `previo = -1` exige que la plantilla deje de marcar la primera ficha, cosa que `test_estante.py` fija, y su efecto es leve. Quitar `data-anuncio` lo detecta `test_tirada.py:160`; renombrar `.tirada-pista`, no. La portada sin cabecera queda degradada, no inutilizable (mapa del pie, botón del dossier, `:focus-within` para el teclado). Se mantiene en media porque es el molde que copiará el próximo componente y el CI no lo vigila.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D15 (cabecera al bajar: «sin JavaScript, la cabecera fija de siempre») y D34 (decisión relacionada). La promesa se cumple con `@media (scripting: enabled)`, que no sabe si el guion llegó o falló. La decisión sigue siendo razonable; el respaldo debería depender de una marca puesta por el guion.

#### FRO-3 · El poema destacado de la portada pierde sus saltos de verso

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Cuando no hay registros destacados, la portada muestra el poema elegido en el perfil con `{{ featured.object.body|truncatechars:280 }}` dentro de `.poem-body.poem-excerpt`. Desde que el filtro `versos` envuelve cada verso en `span.verso` (que es quien lleva `white-space: pre-wrap`), `.poem-body` ya no conserva los saltos. Esta plantilla no pasa por el filtro: el texto plano pierde saltos, sangrías y estrofas y se pinta como un párrafo corrido, cortado a media palabra a los 280 caracteres (medido con la hoja real a 951 px: 57 px de alto, dos líneas). La clase la comparten dos marcados distintos, y un cambio pensado para la ficha rompió la portada.

**Evidencia.**

- `backend/templates/content/home.html:84-101` — la rama `{% elif featured %}`; en la 95, el cuerpo sin filtro de versos.
- `backend/static/css/site.css:756, 762, 765, 767, 1307` — solo `.verso` lleva `pre-wrap`; el comentario de la 756, «pre-wrap preserva versos», quedó desfasado.
- `backend/templates/content/poem_detail.html:54` — la ficha usa `|versos` con la misma clase.
- `backend/apps/content/templatetags/versos.py:33-55, 88-123` — `versos` y `adelanto`.
- `backend/apps/content/views.py:99-103, 144-156` — la rama solo existe sin registros destacados.
- `backend/tests/test_home_ui.py:70-81` y `backend/tests/test_poems.py:142-151` — solo comprueban el título.

**Por qué importa a futuro.** Si el colectivo deja de destacar registros, o el sitio arranca en producción con un poema destacado y sin registros, la portada de un sitio de poesía enseña el poema como prosa corrida. En desarrollo hay cinco registros destacados, así que ni las mediciones de `tools/ux/` ni las revisiones ven esa rama.

**Recomendación.** Componer el extracto verso a verso con los filtros que ya existen, por ejemplo `{% for v in featured.object.body|adelanto:6 %}<span class="verso">{{ v }}</span>{% endfor %}`, o `|versos` sobre un recorte por líneas y no por letras. Separar las clases de ficha y de extracto, mover el comentario a `.verso` y añadir una prueba que cuente los `.verso` del extracto. Con `adelanto` se conservan los saltos, pero se pierden la sangría y las estrofas.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D19 (sin registros destacados vuelve el poema destacado), y §4, «El poema en prosa se compone como versos» (decisión relacionada). Lo que se rompe es el respaldo de D19, por el cambio del filtro `versos` descrito en §4. Las decisiones siguen siendo válidas: es una regresión que ninguna prueba vigilaba.

#### FRO-4 · site.css se gobierna por orden de aparición y especificidad, con la cabecera como punto caliente

**Severidad:** media · **Esfuerzo:** L · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** La hoja (1.970 líneas, 79 commits) resuelve los conflictos subiendo la especificidad o moviendo reglas, y lo deja escrito en comentarios («`.masthead` delante: la receta de `.btn`, más abajo en la hoja, le ganaría»; «`.home-block` se declara más abajo y le pisaba el relleno»). La cabecera concentra el problema: cuatro estados (clásica, cápsula, escondida en la portada, buscando) en dos anchos, expresados con 14 reglas que repiten el prefijo `:is(html[data-barra=pildora], html:not([data-barra]):has(.hero-nombre))`. Tres capas estilizan el mismo panel de búsqueda y la de `:has()` anula borde, radio y sombra de la cápsula; 8 selectores con `#search-results` llegan a especificidad (1,5,0). La portada se reconoce por `.hero-nombre`, una clase del h1 que ninguna regla estiliza y funciona solo como bandera de página. El archivo creció por acumulación: el Botón bajo el encabezado «Agenda, trayectoria y galería», el pie partido en dos zonas, la impresión a media hoja, «Las voces» al final; 47 `@media` con 8 anchos y 17 valores de `z-index` sin escala. Lo bueno: solo hay 6 `!important`, en 3 reglas.

**Evidencia.**

- `backend/static/css/site.css:439-461` — las 14 reglas con el prefijo de la cápsula y su variante de teléfono.
- `backend/static/css/site.css:331-333, 410-411, 453-454, 458, 503-514` — las capas del panel; 506-507 anulan ancho, relleno, fondo, borde, radio y sombra.
- `backend/static/css/site.css:223, 397-401, 810-811, 1572-1573` — comentarios que documentan parches de orden o de especificidad.
- `backend/static/css/site.css:769-786, 1657-1716, 1720-1740, 1909-1970` — la acumulación.
- `backend/static/css/site.css:291, 331, 404, 528, 542, 876, 1455-1465` — `z-index` 100, 70, 80, 200, 60, 120 y del 1 al 10.
- `backend/static/js/cabecera.js:9` y `backend/templates/content/home.html:26-31` — la bandera `.hero-nombre`; `backend/tests/test_home_ui.py:108-109` la fija en el h1.

**Por qué importa a futuro.** Un agente quiere cambiar el borde o el fondo del panel de búsqueda, edita `.busqueda .search` o su variante de cápsula y no cambia nada en ningún navegador con `:has()` (medido en `/poemas/`: borde 0, radio 0, sombra `none`, fondo transparente). Lo más probable es que añada otra regla aún más específica, y la pila crece. Copiar `.hero-nombre` a otra página la deja sin cabecera arriba, y nada lo detecta.

**Recomendación.**

1. Marcar la página en el marcado (`<body data-pagina="{% block pagina %}{% endblock %}">`) y usar `[data-pagina=portada]` en el CSS y en `cabecera.js`.
2. Ordenar la cascada con `@layer` (tokens, base, lienzo, componentes, estados, impresión) para que los estados de la cabecera ganen por capa y no por especificidad, y quitar los prefijos que solo existen para ganar a reglas posteriores.
3. Estilizar los resultados por clase y dejar `#search-results` solo como destino de htmx.
4. Fijar la política de navegadores: si no hace falta el panel sin `:has()` (Firefox anterior a 121), borrar esa capa.
5. Partir `site.css` en archivos por capa unidos con `@import` (ManifestStaticFilesStorage reescribe sus URL) o concatenados en collectstatic, con el `@media` de cada componente junto a él y la impresión al final.
6. Una escala de `z-index` en tokens (`--z-telon`, `--z-panel`, `--z-cabecera`, `--z-modal`, `--z-salto`).

**Matiz de la verificación.** `#search-results` aparece en 8 selectores, no en 9, y tras `@media print` quedan unas 230 líneas. No se encontró ninguna regla posterior que hoy pise una de impresión. La capa sin `:has()` es hoy peso muerto que despista.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D15, D16 (buscador en la barra, con el panel anterior para navegadores sin `:has()`) y D34 (decisión relacionada). La cabecera acumula estados aprobados; las decisiones siguen en pie y lo que hay que ordenar es el CSS.

#### FRO-5 · Parciales con contratos implícitos: heredan el contexto, suponen tipos y fijan el nivel de encabezado

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Solo 7 de los 67 `{% include %}` usan `only`; los demás heredan todo el contexto del padre. `_cabeza_de_seccion.html` documenta que eso ya causó un fallo (una sección heredó la cejilla del titular; se cazó en desarrollo) y por eso se incluye con `only`. `_index_head.html` tiene parámetros parecidos (cejilla, dek, cuenta) y se incluye sin `only` en 12 plantillas. `_article_list.html` pagina siempre como si recibiera un Page (WEB-4). Las tarjetas fijan `<h3>`, así que en al menos nueve páginas se salta de h1 a h3, y una prueba exige ese h3 con una razón que no se cumple.

**Evidencia.**

- `backend/templates/content/partials/_index_head.html:5-11, 14-17, 25-27` — parámetros documentados; toma `subnav_colectivo` del procesador de contexto, a propósito.
- Las 12 inclusiones sin `only`: `content/search.html:15`, `poem_index.html:9`, `collection_index.html:8`, `text_archive.html:9`, `showcase/partner_index.html:10`, `publication_index.html:9`, `press_index.html:9`, `agenda/gallery.html:10`, `agenda.html:9`, `trayectoria.html:10`, `media/recording_index.html:10`, `people/member_index.html:9`.
- `backend/templates/content/partials/_cabeza_de_seccion.html:9-10` — el fallo ya ocurrido.
- `backend/templates/content/partials/_article_card.html:15` y `_poem_card.html:15` — `<h3>` fijo. Saltos medidos en `/textos/`, `/poemas/`, cuatro secciones, `/coleccion/nuevas-voces/` y dos etiquetas.
- `backend/tests/test_ui_ux.py:58-71` — exige h3 «porque cuelga de secciones `<h2>`», pero en `/textos/` no hay ningún h2.

**Por qué importa a futuro.** Una vista nueva (un índice de talleres) pone `cejilla` en su contexto para otra cosa y su plantilla incluye `_index_head` sin pasarla: la cabecera pinta ese valor ajeno, como ya pasó con `_cabeza_de_seccion`. Bajo su h1, las tarjetas saltan un nivel y la prueba sigue exigiendo el h3.

**Recomendación.**

1. Incluir con `only` y parámetros explícitos, empezando por `_index_head` (pasando `subnav_colectivo`), `_article_card`, `_poem_card` y `_pie_de_entidad`. Escribir el contrato en la cabecera de cada parcial, como ya hacen `_foto` y `_cabeza_de_seccion`; el que no declara nada es `_article_card`. Una prueba que renderice cada parcial solo con sus parámetros declarados.
2. Pasar el nivel del encabezado como parámetro de las tarjetas (2 por defecto, 3 bajo una sección) y corregir la prueba de `test_ui_ux.py`.
3. Que `_article_list` reciba la página aparte, o que las vistas de reviews paginen (WEB-4).
4. Pintar el formulario del boletín desde `SubscribeForm` (WEB-9).

**Matiz de la verificación.** El `|safe` que se citaba está mitigado y se trata en SEG-1. El escenario de fuga exagera: `dek` no puede filtrarse (las 12 inclusiones lo pasan); solo `cejilla` (y, en `search.html`, cuenta, singular, plural y territorio), y solo en las páginas de la vista que añada la variable. La mayoría de las parciales sí documentan sus parámetros: lo que falta es imponerlos. De las cuatro llamadas a `_article_list` con un QuerySet, la de la portada está acotada a tres a propósito.

#### FRO-6 · Marcado y recetas copiados entre plantillas en vez de parciales o etiquetas, con errores que ya divergen

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Las plantillas repiten a mano piezas que cambian juntas:

- La unión de datos con « · » aparece 58 veces en 21 plantillas; unas 54 son construcciones condicionales con `{% if %}` (las otras 4, de bucle, están bien). En `publication_detail` y `publisher_detail` la línea empieza con un separador suelto cuando falta el primer dato: el mismo error que se corrigió solo en `work_detail` y `recording_detail`.
- El sufijo del título de la pestaña, con el respaldo «Reseñas» (el nombre viejo), está en 35 bloques `{% block title %}`; hay 6 respaldos más en rótulos RSS, `og:site_name`, `og:title`, el h1 oculto de la portada y el sello, y 3 en JSON-LD. El dossier usa «Colectivo» como respaldo y el 500 escribe «Reseñas» fijo.
- 13 cabeceras de índice escritas a mano en vez de usar `_index_head.html`; la URL absoluta de `og:image`, armada 16 veces en 6 plantillas; tres bloques «Participan», cuatro sobrecubiertas, cinco monogramas; `agenda.html` reimplementa `SiteProfile.correo_de_contacto` con `firstof`.
- En CSS, el patrón «toda la tarjeta es el enlace» (`::after` con `inset: 0`) tiene 5 implementaciones, y hay dos pares de clases con cuerpos idénticos.

**Evidencia.**

- `backend/templates/showcase/publication_detail.html:30-34` — sin año, la línea empieza con « · » (comprobado al renderizar); `year` admite nulos (`backend/apps/showcase/models.py:194`).
- `backend/templates/reviews/publisher_detail.html:10-13` — sin país, la línea empieza con « · Sitio web».
- `backend/templates/reviews/work_detail.html:10-16` — aquí está corregido, con un comentario que lo explica.
- `backend/templates/showcase/dossier.html:4, 23` y `backend/templates/500.html:2-15, 21`.
- `backend/apps/showcase/models.py:17, 120-126, 142-146` — `name` es obligatorio, con «Colectivo» por defecto, y `load()` garantiza la fila: el respaldo «Reseñas» casi nunca se alcanza.
- `backend/templates/base.html:7, 15, 16, 18, 23, 34` y `backend/templates/content/article_detail.html:11, 28-29, 46, 48`.
- `backend/templates/agenda/agenda.html:21`.

**Por qué importa a futuro.** La próxima corrección del separador se hará en una plantilla y no en las otras veinte, como ya pasó. Cambiar el formato del título de las pestañas exige editar 34 plantillas. Un enlace nuevo dentro de una tarjeta queda tapado por el `::after` si nadie recuerda elevarlo.

**Recomendación.**

1. Una etiqueta `{% unir ' · ' a b c %}` (un `simple_tag` con `format_html_join` que omite los vacíos) para las uniones condicionales.
2. En `base.html`, `<title>{% block titulo_pagina %}{% endblock %}{{ nombre_del_sitio }}</title>`, con `nombre_del_sitio` resuelto una vez en el procesador de contexto: un solo respaldo, el mismo que escriba el 500.
3. Una etiqueta `url_absoluta`, o un bloque `og_imagen` en la base, para las 16 URL.
4. Usar `_index_head.html` donde se pueda: sección, etiqueta y colección pueden migrar ya; las fichas con filas meta exigen ampliar el parcial.
5. Parciales `_participan`, `_tapa` y `_retrato_o_monograma`; la cejilla y el umbral de título largo como propiedades del modelo.
6. Una clase `.enlace-total` que incluya la regla de los enlaces secundarios, y borrar las clases duplicadas.

**Matiz de la verificación.** Los dos errores del separador no se ven hoy en desarrollo (no hay publicaciones sin año ni editoriales sin país con sitio web). El problema del título no es que «Reseñas» se vea, sino que haya tres respaldos distintos y un 500 con el nombre viejo. Solo 2 de las 5 recetas de enlace total elevan sus enlaces secundarios. Es falso que una ficha nueva perdería la sub-fila del colectivo: esa sub-fila solo existe en los seis índices del colectivo.

#### FRO-7 · El atributo hidden lo anula cualquier display del autor, y se parchea componente por componente

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** La hoja no tiene la regla global `[hidden]{display:none}`. Cuando un elemento que se muestra y oculta con `hidden` recibe un `display` (flex, grid, inline-flex), queda siempre visible, y se ha ido añadiendo un parche local por componente: `.estante-ficha[hidden]`, `.tirada-contactos[hidden]` y `.dossier-toolbar [hidden]`, este último con el comentario «`.btn` fija su `display`, y eso pesa más que el `hidden`». El cuarto componente, el relevo de «Las voces», funciona solo mientras `.integrante` no tenga un `display` propio: hoy esconde con `hidden` a las integrantes que esperan turno (7 en desarrollo), desde la plantilla y desde `integrantes.js`.

**Evidencia.**

- `backend/static/css/site.css:1219-1220` — `.estante-ficha{display:flex}` y su parche (commit `3f708c2`).
- `backend/static/css/site.css:1340, 1524` — `.tirada-contactos[hidden]` y `.tirada-contactos{display:flex}` (commit `3f80823`).
- `backend/static/css/site.css:779, 1571-1573` — `.btn{display:inline-flex}` y el parche del dossier (commit `e20bb4a`).
- `backend/static/css/site.css:1951, 1969` — `.integrante` sin `display`.
- `backend/templates/people/partials/_member_card_portada.html:8` y `backend/static/js/integrantes.js:35, 61-64`.

**Por qué importa a futuro.** Para alinear el nombre bajo el retrato, alguien añade `.integrante{display:flex; flex-direction:column}`. Desde 720 px, las siete integrantes escondidas aparecen de golpe en la fila de cinco y el relevo pierde sentido, sin que falle ninguna prueba. Un panel nuevo con `display:grid` que se oculta con `hidden` queda siempre visible hasta que alguien escribe el cuarto parche.

**Recomendación.** Añadir al principio de la hoja `[hidden]{display:none !important}`, la receta habitual de los resets modernos; no cambia el comportamiento actual, porque los tres parches ya hacen eso. Borrar los parches y fijar la regla con una prueba sobre la hoja parseada. Si algún día se usa `hidden="until-found"`, conviene la variante `:where(:not([hidden="until-found"]))`.

**Matiz de la verificación.** Las «15 escondidas» que se citaban salen del fixture de pruebas de 20 integrantes; con las 12 de desarrollo son 7.

#### FRO-8 · Selectores muertos sin detección general (8 hoy), con un precedente de fallo visible

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Cuando una plantilla cambia de estructura, las reglas que la estilaban dejan de aplicarse sin dar error. Ya pasó: en el commit `9877ce7`, tres reglas para `.article-card h2` (las parciales emitían h3) dejaron los títulos en magenta y a 18,7 px, y la prueba que se añadió vigila solo ese caso. Hoy hay 8 selectores imposibles en 5 reglas:

- `.lienzo > .sangre`, `.lienzo > .band` y `.lienzo > .band:last-child`, muertos desde que la portada envolvió sus bandas en `.portada-telon`.
- `.index-head > .btn` y `.index-head > p > .btn`: ninguna de las 25 cabeceras de índice lleva botón.
- `.band .monograma`: los monogramas de la portada están en una sección `.sangre`.
- `.home-block > .subhead:first-child` y `.band-in > .subhead:first-child`: los títulos de sección viven dentro de `header.seccion-cabeza`.

Además, una prueba exige una de esas reglas muertas: si se borra, `test_css_sistema.py:285` falla, y un agente podría «arreglarla» restaurándola.

**Evidencia.**

- Método: los 781 bloques de reglas de `site.css` (unos 907 selectores) se evaluaron con soupsieve contra 105 páginas renderizadas de desarrollo, quitando pseudo-clases de estado y las marcas que pone el JS. No casan 86: 78 dependen de datos (sin foto, sin cubierta, mensajes, errores) y 8 son imposibles.
- `backend/static/css/site.css:256-258` — el comentario de la 257 promete que «una banda que cierra la página llega hasta el pie», y eso ya no ocurre.
- `backend/templates/content/home.html:39-234` — `div.portada-telon` envuelve bandas y sangres; su último hijo es `section.home-cierre`.
- `backend/static/css/site.css:1083-1086, 587, 722-726, 1161-1167` — el telón repite `grid-column:full` pero no el `:last-child`; las demás reglas muertas.
- `backend/templates/content/partials/_cabeza_de_seccion.html:12-15` — el `h2.subhead` va dentro de `header.seccion-cabeza`.
- `backend/tests/test_ui_identity.py:194-220` — solo el caso de las tarjetas; `backend/tests/test_css_sistema.py:266-285` — exige la regla muerta.

**Por qué importa a futuro.** A un agente le piden quitar la franja de papel entre la última banda y el pie; ve `.lienzo > .band:last-child` y su comentario, supone que ya resuelve el caso y apila otra regla encima. Si un cambio en `_cabeza_de_seccion.html` quita el `header`, `.seccion-cabeza .subhead` deja de aplicarse y los títulos de sección recuperan 40 px de margen, sin que falle nada.

**Recomendación.** Borrar hoy las 5 reglas y apuntar la aserción de `test_css_sistema.py:285` a `.portada-telon > .sangre, .portada-telon > .band`. Después, una prueba (bs4 y soupsieve ya están en el entorno) que renderice páginas con datos que cubran los estados opcionales (sin foto, sin cubierta, sin póster, con mensajes, 404, formulario con errores, 1, 2, 4, 5 y 7 fotos, panel de búsqueda) y exija que cada selector case en alguna. Debe quitar las pseudo-clases de estado y llevar una lista explícita de las marcas que pone el JS (`con-js`, `aria-current`, `data-barra`, `es-frente`, `pliego--repartiendo`). Conviene presupuestar su mantenimiento: datos para cada estado y una lista de marcas que actualizar.

#### FRO-9 · La navegación tiene cuatro fuentes de verdad, y el menú del teléfono no usa la de la barra

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** La barra (`NAV_PRINCIPAL`) y la sub-fila del colectivo (`SUBNAV_COLECTIVO`) se definen en Python, pero el mapa del sitio son 15 enlaces escritos a mano en `_mapa.html`, y es lo único que ve el teléfono en «Menú», porque la barra se oculta por debajo de 900 px. Ya difieren: Prensa y Aliados son territorio «Colectivo» en la barra y en la sub-fila, pero «Prensa y gestión» en el mapa y en el `data-territorio` de sus índices; el orden de Agenda y Trayectoria cambia de una lista a otra, y también el de Registros y Publicaciones. El procesador `nav` entrega además `nav_sections`, que no usa ninguna plantilla.

**Evidencia.**

- `backend/templates/partials/_mapa.html:12-57` — 15 enlaces fijos con otra agrupación y otro orden.
- `backend/templates/base.html:88-92, 158` — la barra sale de `nav_principal`; el menú y el pie incluyen `_mapa.html`.
- `backend/apps/content/context_processors.py:10-49, 75` — `NAV_PRINCIPAL`, `SUBNAV_COLECTIVO` y `nav_sections`.
- `backend/static/css/site.css:379, 394-407` — por debajo de 900 px se oculta la barra y se muestra el mapa.
- `backend/templates/showcase/press_index.html:9` y `partner_index.html:10` — territorio «prensa».
- `backend/tests/test_indices.py:77, 95-112`, `backend/tests/test_ia.py:24-54` y `backend/tests/test_cabecera.py:76-101` — fijan cada lista por separado; ninguna prueba compara la barra o la sub-fila con el mapa.

**Por qué importa a futuro.** Piden una página «Talleres» dentro del colectivo. El agente la añade a la sub-fila y a la barra, actualiza la prueba de la sub-fila que falla y no toca `_mapa.html`, porque nada se lo pide. En el teléfono la página no aparece en «Menú» ni en el pie.

**Recomendación.** Una sola estructura en Python (grupos → enlaces con su territorio), entregada por el procesador de contexto, de la que salgan la barra, la sub-fila y el mapa del pie y del menú. Antes de unificar hay que decidir qué agrupación manda para Prensa y Aliados, porque cada una la fija una prueba distinta: no es solo una refactorización. Borrar `nav_sections`.

**Matiz de la verificación.** Las puertas del cierre de la portada no son una cuarta fuente de navegación: son salidas propias, con rótulos propios, como las del pie de entidad, y usan `reverse()`. Hay mitigaciones parciales: `test_indices.py` mantiene alineados los grupos del mapa con el `data-territorio`. Decir que el menú es «la única navegación en el móvil» exagera un poco: en los índices del colectivo la sub-fila también se ve. Como todas las URL se resuelven por nombre, el riesgo es de omisión o incoherencia, no de enlaces rotos.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D9 (barra de cinco enlaces y «Dossier»), y §4, «En el teléfono, Textos y el dossier a dos toques, dentro de Menú» (decisión relacionada). El registro da por hecho que en el teléfono se llega a esas páginas desde «Menú», pero ese menú es el mapa escrito a mano y un cambio en la barra no le llega. El diseño sigue siendo razonable; falta la fuente única.

#### FRO-10 · Guiones con ayudantes copiados, dos dialectos y montaje único

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** No hay módulos ni ayudantes compartidos, así que cada guion copia lo común. El gesto de deslizar (pointerdown, pointerup y pointercancel, umbral de 40 px, razón 1,5 y clic suprimido 400 ms) está duplicado entre `integrantes.js` y `registros.js`; la consulta de movimiento reducido está en 4 archivos y la comprobación de `Element.animate` en 3; `estante.js` y `registros.js` comparten la misma cadena de curva (una prueba exige que coincidan literalmente) y la curva de las fichas copia `--ease`. Conviven dos dialectos sin un linter que fije uno: ES5 con `var` (buscador, cabecera, embeds, dossier) y ES2015 o posterior (const y flechas; `async` y `?.` solo en `integrantes.js`). Cada guion se monta una sola vez al cargarse, sin idempotencia ni gancho para htmx.

**Evidencia.**

- `backend/static/js/integrantes.js:90-116, 119` y `backend/static/js/registros.js:9, 13, 67, 98-122, 132` — el mismo gesto y el montaje único.
- `backend/static/js/estante.js:11, 14, 16, 27, 80` — la misma curva y la copia de `--ease` (`backend/static/css/site.css:64`).
- `backend/static/js/cabecera.js:5-12` — IIFE en ES5; `dossier.js` usa `var` dentro de un listener, sin IIFE.
- `backend/tests/test_estante.py:205-211` — exige la copia literal de la curva en dos guiones.
- `backend/templates/content/home.html:6-11` — mitigación: cada guion se incluye una vez y las secciones no llegan por htmx.

**Por qué importa a futuro.** Un agente ajusta el umbral del gesto para tabletas en `registros.js` y no en `integrantes.js`, y «Las voces» y «La tirada» pasan a comportarse distinto sin que falle ninguna prueba. Si una sección de la portada llegara algún día por htmx, sus guiones no la montarían.

**Recomendación.** Un `static/js/comun.js`, o módulos ES con `<script type="module">` (compatibles con `script-src 'self'`), con `deslizar(elemento, alPasar)`, `quieto()`, `puedeAnimar()` y un `montarTodos(selector, montar)` idempotente (`dataset.montado`), registrado también con `htmx.onLoad`. Y una configuración de ESLint que fije un dialecto (PRU-2).

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D20, D23 y las ramas de «reducir movimiento» de D18, D20, D27 y D31 (decisión relacionada). Cada decisión añadió su gesto o su consulta en su propio guion; las decisiones están bien, falta un módulo común.

### 4.5 Seguridad como propiedad del código (SEG)

#### SEG-1 · El `|safe` del cuerpo supone que todo se escribe con `Model.save()`; loaddata, las migraciones de datos y `update()` se lo saltan

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Los dos únicos `|safe` del proyecto, el cuerpo de los artículos y el de las páginas, suponen que `clean_html` ya se aplicó al escribir. Esa garantía vive en `Article.save()`, `Page.save()` y el formulario del panel, no en la base ni en la salida. `loaddata` guarda con `save_base(raw=True)` sin llamar a `save()`, y es lo que usa `datos_de_desarrollo cargar`; las migraciones de datos usan modelos históricos, sin el `save()` propio (0007 y 0010 escriben `Page.body`); y cualquier `QuerySet.update`, `bulk_create` o `bulk_update` futuro también se lo salta. El propio docstring de `SanitizedBodyMixin` lo llama «una convención de la capa Python». El análisis estático del CI bloquea `mark_safe` en Python, pero nada vigila `|safe` en las plantillas. htmx corre con `allowEval` y `allowScriptTags` por defecto y sin `hx-disable` alrededor del HTML autoral; la CSP con nonce frena la ejecución de scripts, no la inyección de marcado (formularios, enlaces, atributos `hx-*`).

**Evidencia.**

- `backend/templates/content/article_detail.html:88-89` y `backend/templates/content/page_detail.html:9-10` — los dos `|safe`; no hay ningún `mark_safe` en Python.
- `backend/apps/content/models.py:177-183, 399-401` — el saneo y el tiempo de lectura, solo en `save()`.
- `backend/apps/content/admin.py:46-57` — el docstring de `SanitizedBodyMixin`.
- `backend/apps/content/migrations/0007_legal_pages.py:62-68` y `0010_privacy_ley_21719.py:43-52` — escriben cuerpos con modelos históricos.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:125-143` — `cargar` usa loaddata.
- `.github/workflows/ci.yml:241-248` — bandit solo analiza Python.
- `backend/templates/base.html:56, 159-160` — `htmx-config` sin `allowEval: false`; el pie lleva `{% csrf_token %}` en todas las páginas.

**Por qué importa a futuro.** Un agente escribe un importador desde WordPress, o una acción para «publicar un envío aceptado como texto», con `bulk_create` a partir de `Submission.body`, que es entrada pública. El cuerpo no pasa por nh3 y la ficha lo imprime con `|safe`. Un `<div hx-post="/admin/auth/user/add/" hx-include="[name=csrfmiddlewaretoken]" hx-trigger="load">` dentro del cuerpo se dispararía con la sesión del editor que abra la ficha, usando el token CSRF del formulario del pie. La CSP no lo impide: es una petición al mismo origen y no necesita eval.

**Recomendación.** Llevar la garantía a la salida o a la columna. Hay dos opciones equivalentes:

- Un filtro `{{ article.body|html_autoral }}` que llame a `clean_html` y marque el resultado como seguro (nh3 es rápido y se puede memoizar por hash). bandit señalará el `mark_safe` y habrá que justificar el `nosec`.
- Un campo `HTMLSaneadoField(models.TextField)` cuyo `get_prep_value` llame a `clean_html`. Django lo aplica en `save()`, `update()`, `bulk_create`, `bulk_update`, loaddata y migraciones. Su salvedad: también sanea los valores de búsqueda en consultas sobre `body`.

En cualquier caso: una prueba que recorra las plantillas y prohíba `|safe` salvo el filtro aprobado; `hx-disable` en los contenedores de HTML autoral; y una prueba que haga `Article.objects.filter(pk=…).update(body="<script>…")` y revise la ficha.

**Matiz de la verificación.** Hoy no hay exposición. Los tres caminos sin saneo (loaddata, 0007 y 0010) solo transportan contenido de confianza ya limpio (verificado en las 20 filas de la base y de `datos.json`), `cargar` exige `DEBUG` y una base vacía, y quien puede cambiar `datos.json` también puede cambiar las plantillas. `allowEval` ya lo neutraliza la CSP (no hay `'unsafe-eval'`), y `allowScriptTags` solo afecta a lo que htmx intercambia: el riesgo real de htmx son los atributos `hx-*`, que funcionan sin eval. `form-action 'self'` limita los formularios al mismo origen, aunque un POST al propio origen sigue siendo peligroso.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «FTS por trigger de Postgres, no GeneratedField», y §1 (producto), el texto legal de la migración 0010 (decisión relacionada). El registro ya reconoce que `update`, `bulk_update` y las importaciones se saltan `save()`, y por eso llevó el vector de búsqueda a la base; el saneo, en cambio, se quedó en `save()`. Es el mismo razonamiento aplicado a medias: el `|safe` necesita una garantía que no dependa de `save()`.

#### SEG-2 · Algunos comentarios de seguridad afirman garantías que el código no tiene

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** La justificación de seguridad vive en docstrings largos que citan identificadores («S-NN» aparece 54 veces en 29 archivos de código, plantillas e infraestructura). En un proyecto que mantienen agentes, que leen y obedecen los comentarios, una afirmación falsa funciona como una instrucción equivocada. Hay cinco comprobadas:

- `media/validators.py` anuncia una «comprobación de firma» que no existe para audio, vídeo ni PDF: el módulo solo valida extensiones.
- `datos_de_desarrollo` promete «solo el contenido público» y exporta borradores (HER-1).
- `csp.py` dice que el JSON-LD del artículo es «el único script inline propio»; hay otro en `base.html`, en todas las páginas, y otro en la ficha de evento.
- `redaction.py` habla de «los dos puntos de salida» y presenta el log de acceso de gunicorn como el residuo pendiente, cuando producción ya no lo emite y hay otras salidas (RES-3, TAR-4).
- El `help_text` de los registros promete SoundCloud y Bandcamp, que nada admite (SEG-4).

Hay además decisiones deliberadas sin una prueba que las fije, como el `csrf_exempt` de la baja en un clic.

**Evidencia.**

- `backend/apps/media/validators.py:11-14, 17-33` — solo `FileExtensionValidator`; un único commit (`d50159e`); un grep de magic, firma, signature y filetype en `apps/` y `config/` no encuentra nada.
- `infra/caddy/Caddyfile:49-58` — mitigación: `/media/` se sirve con `nosniff` y `Content-Security-Policy: default-src 'none'; sandbox`.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:6-11, 77-83, 125-127` — la promesa, el volcado sin filtro y la guarda solo en `cargar`.
- `backend/config/csp.py:4-5` frente a `backend/templates/base.html:29-39`, `content/article_detail.html:18` y `agenda/event_detail.html:16`.
- `backend/config/redaction.py:14-22, 50-52, 63-65` frente a `docker-compose.prod.yml:14-39` (sin `--access-logfile` desde el commit `868d55f`) y `infra/caddy/Caddyfile:18-30, 81-95`.
- `backend/config/settings.py:327-337` — Sentry sin `before_send_transaction` y con las variables locales por defecto.

**Por qué importa a futuro.** Un agente necesita aceptar `.mov` en los registros, lee que «la firma» protege el contenido y amplía la lista confiando en una verificación que no existe. Otro quita `@csrf_exempt` de `unsubscribe` para «endurecer» la vista; la suite sigue en verde, porque el cliente de pruebas no exige CSRF, y desde ese momento el botón de baja en un clic de Gmail y Outlook recibe un 403.

**Recomendación.** Convertir cada garantía en una prueba con nombre descriptivo y dejar en el código solo la regla, en una línea: qué se garantiza y dónde se prueba, sin la crónica. Corregir hoy las cinco afirmaciones. Para las decisiones deliberadas, una prueba que fije la intención para que nadie las «arregle»: por ejemplo, la baja en un clic con `Client(enforce_csrf_checks=True)`.

**Matiz de la verificación.** Son cinco afirmaciones comprobadas, no siete. El docstring de `unsubscribe` no es falso (el formulario lleva token y el docstring declara la exención y su motivo); el problema es que ninguna prueba la fija. El comentario sobre el almacenamiento privado es cierto con el valor por defecto: es una invariante sin imponer (SEG-5). El ejemplo del `.mov` no haría daño hoy, por las cabeceras de `/media/` y porque las extensiones peligrosas ya están fijadas en las pruebas. Hay más casos del mismo patrón, como el comentario caducado de `backend/tests/test_security_uploads.py:28-30`. Las referencias «S-NN» remiten a un informe externo que el árbol de trabajo marca como borrado: quedarán colgando.

#### SEG-3 · Huecos en el antiabuso: axes bloquea solo por IP y cualquier login correcto reinicia la cuenta; las confirmaciones no tienen tope por destinatario

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El login del panel es la única puerta autenticada y se protege con `AXES_LOCKOUT_PARAMETERS = ['ip_address']` y `AXES_RESET_ON_SUCCESS = True`. En axes 8.3.1, el reinicio borra los intentos que casan con los parámetros de bloqueo, es decir, con la IP: quien tenga una cuenta staff (un autor, por ejemplo) alterna cuatro contraseñas contra el superusuario con un login propio correcto y nunca llega al límite. No hay bloqueo por nombre de usuario, y ni Django ni Caddy limitan `/admin/login/`. En el boletín, el límite es de 5 altas por minuto por IP, pero no por destinatario: cada alta regenera el token y reenvía el correo.

**Evidencia.**

- `backend/config/settings.py:139-151` — umbral de 5, enfriamiento de 1 h, bloqueo por IP y reinicio al acertar.
- axes 8.3.1 en el contenedor, `axes/handlers/database.py:280-320, 352-372, 432-446` y `axes/helpers.py:260-304` — el reinicio filtra solo por IP.
- `django/contrib/admin/forms.py:20-27` — solo una cuenta staff llega a `login()` y puede provocar el reinicio.
- `backend/config/urls.py:13-15` e `infra/caddy/Caddyfile:35-96` — ningún límite sobre el panel.
- `backend/apps/community/views.py:49-82` — cada alta no confirmada regenera el token y envía otra vez.

**Por qué importa a futuro.** Una cuenta de autor comprometida programa ciclos de cuatro intentos contra el superusuario y uno propio correcto: miles de intentos por hora sin bloqueo. Si la contraseña es adivinable, quedan expuestos los suscriptores y los envíos. Por otro lado, alguien puede usar el formulario del pie para inundar de confirmaciones el buzón de un periodista y dañar la reputación del remitente.

**Recomendación.** `AXES_RESET_ON_SUCCESS = False` (o reiniciar solo la combinación usuario más IP) y `AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]`, con un umbral por usuario alto y un enfriamiento progresivo; un bloqueo solo por usuario permitiría a un tercero dejar fuera al dueño. Como defensa de fondo, valorar un segundo factor para el staff con django-otp. En el alta, no reenviar si `confirm_token_at` tiene menos de N minutos, manteniendo la misma respuesta.

**Matiz de la verificación.** «Cualquier cuenta» debe leerse «cualquier cuenta staff». La pieza de IPv6 (ratelimit agrupa por /64 y axes cuenta la dirección completa) es condicional: con la red Docker por defecto, es probable que ninguno de los dos vea la IPv6 real. `/readyz/` es público a propósito y no es mejor vector de saturación que cualquier página (ver RES-6). Severidad baja; sube a media si se multiplican las cuentas de autor.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), D1, resolución de IP unificada (decisión relacionada). D1 explica por qué axes cuenta por IP, pero no decidió bloquear solo por IP ni reiniciar con cualquier login correcto. Añadir el usuario a los parámetros de bloqueo no la contradice.

#### SEG-4 · La misma lista permitida está copiada en nh3, TinyMCE, la CSP y los embeds, y las copias ya no coinciden

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** La política de contenido está repartida en dos pares duplicados y dos literales sueltos: la lista de etiquetas y atributos de `sanitize.py` frente al `valid_elements` de `richtext_init.js`, que dice coincidir con nh3 pero omite `loading`; los proveedores de `embeds.py` frente al `frame-src` de `csp.py`; el `help_text` de `Recording.embed_url`, que promete SoundCloud y Bandcamp aunque ni `embeds.py` ni la CSP los admiten; y la relajación de estilos de la CSP, que depende de que el panel viva en `/admin/`, un literal repetido en `config/urls.py` y en robots. La divergencia con efecto: nh3 conserva `<img src="https://tercero/...">` (comprobado en el contenedor), que la CSP `img-src 'self' data:` bloquea.

**Evidencia.**

- `backend/apps/content/sanitize.py:6-44` — etiquetas, atributos (`img` con `loading`) y esquemas.
- `backend/static/admin/richtext_init.js:9-17` — `valid_elements` sin `loading`, con el comentario «Coincide con la lista blanca de nh3».
- `backend/config/csp.py:37, 42, 108` — `img-src`, `frame-src` con dos hosts literales y `startswith('/admin/')`.
- `backend/apps/media/templatetags/embeds.py:9-37` — solo YouTube y Vimeo.
- `backend/apps/media/models.py:342-346, 422-424` — la promesa del `help_text`; `clean()` no valida el proveedor.
- `backend/templates/media/partials/_player.html:2-3, 41-42` — una URL no reconocida cae a un enlace «Ver / escuchar ↗».

**Por qué importa a futuro.** Un agente sigue el `help_text` y añade SoundCloud a `embeds.py` sin tocar `csp.py`: al pulsar «Reproducir», el iframe aparece bloqueado. Una editora pega un texto de Google Docs con imágenes alojadas fuera: nh3 las conserva, la CSP las bloquea y salen rotas; la salida rápida, abrir `img-src` a `https:`, contradiría la promesa de `/cookies/` de no compartir datos con terceros. Y si se amplía nh3 (`class`, `id`) sin tocar TinyMCE, al reeditar una pieza TinyMCE elimina esos atributos y el guardado consolida la pérdida.

**Recomendación.** Un módulo único, por ejemplo `config/politica_contenido.py`, con `EMBED_PROVIDERS` (regex, constructor del `src`, host) y las listas de etiquetas y atributos. `csp.py` construye `frame-src` desde él, `embeds.py` lo usa, el `help_text` se genera a partir de él y `richtext_init.js` recibe `valid_elements` del servidor (con `json_script` o un atributo `data-` del widget). Para las imágenes, o se restringen al mismo origen en nh3 con `attribute_filter`, o se decide lo contrario de forma explícita. El prefijo del panel, desde `reverse('admin:index')`. Y pruebas de coherencia: `frame-src` contiene los hosts de `embeds.py`, y `valid_elements` coincide con nh3.

**Matiz de la verificación.** No son «cinco definiciones de la misma política». El `data:` de `img-src` no es una divergencia (lo usan el grano del CSS y las pieles de TinyMCE) y la falta de `loading` es inocua. Afirmar cadenas literales en una prueba de política de seguridad es correcto (derivarlas de las constantes sería tautológico): lo que falta es la prueba de coherencia entre copias. El fallo no sería silencioso: se ve en desarrollo y en producción.

#### SEG-5 · Hay defensas que una variable de entorno apaga sin que el guard de producción lo detecte

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `envguard` valida en positivo los secretos, los hosts y los orígenes, pero ignora los interruptores que apagan defensas: `RATELIMIT_ENABLE=0`, `AXES_ENABLED=0`, `DJANGO_CSP_REPORT_ONLY=1` y `DJANGO_HSTS_SECONDS=0`. El modo report-only, además, no declara `report-uri` ni `report-to`: «solo informa» sin informar a nadie. La separación del almacenamiento privado depende de `DJANGO_PRIVATE_MEDIA_ROOT`, sin ninguna comprobación de que quede fuera de `MEDIA_ROOT`, y ese almacenamiento genera URL `/media/…` (comprobado: `private_storage().url('submissions/…')` devuelve `/media/submissions/…`).

**Evidencia.**

- `backend/config/settings.py:38-47, 151, 156, 183-184, 263, 273-274` — el guard y los interruptores leídos del entorno.
- `backend/config/envguard.py:45-99` — no revisa ningún interruptor ni `PRIVATE_MEDIA_ROOT`.
- `backend/config/csp.py:33-48, 75-78` — sin `report-uri` ni `report-to`.
- `backend/apps/submissions/models.py:7-9, 55` — `FileSystemStorage` sin `base_url`.
- `backend/apps/submissions/admin.py:25-31` y `backend/apps/submissions/views.py:48-57` — mitigación: el panel no muestra la URL y descarga por una vista protegida.
- `docker-compose.prod.yml:138, 141` y `.env.prod.example:31-33` — Caddy monta solo el volumen público; la plantilla no menciona los interruptores de axes ni de ratelimit.

**Por qué importa a futuro.** Durante una prueba, el operador pone `RATELIMIT_ENABLE=0` o `DJANGO_CSP_REPORT_ONLY=1` en el `.env` del VPS y lo olvida: el sitio arranca sin aviso, los formularios quedan sin límite o la CSP deja de bloquear, y nadie se entera. O fija `DJANGO_PRIVATE_MEDIA_ROOT=/app/mediafiles` para unificar respaldos, y Caddy pasa a servir los manuscritos en `/media/submissions/AAAA/MM/<nombre original>`.

**Recomendación.** Con `DEBUG=0`, registrar un WARNING al arrancar, o rechazar el arranque salvo autorización explícita (`DJANGO_ALLOW_WEAKENED=nombre1,nombre2`), cuando axes, ratelimit, report-only o HSTS estén apagados. Comprobar que `PRIVATE_MEDIA_ROOT` no quede dentro de `MEDIA_ROOT`. Usar para el almacenamiento privado una subclase cuyo `url()` lance una excepción, como higiene frente a una plantilla futura. Añadir `report-to` si se mantiene el modo report-only.

**Matiz de la verificación.** Son cuatro interruptores sin red: `DJANGO_SECURE_SSL_REDIRECT=0` queda cubierto por la redirección automática de Caddy en el despliegue documentado. El riesgo del almacenamiento privado es su ubicación, no `url()`, que hoy nunca se muestra. Si alguien montara el volumen privado bajo `/srv/media` en el compose, la comprobación sobre `PRIVATE_MEDIA_ROOT` no lo vería: para eso sirve la prueba de separación o una prueba sobre el compose. Ambos casos exigen un acto deliberado del operador.

### 4.6 Tareas en segundo plano, correo, caché y ciclo de vida de archivos (TAR)

#### TAR-1 · Acks, límites de tiempo y reintentos de Celery no hacen lo que afirman sus comentarios y pruebas

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `settings.py` afirma que «con acks_late, una tarea que muere por time limit se reencola en vez de perderse» y que el límite blando «permite el reintento». En el Celery 5.6.3 instalado, `task_acks_on_failure_or_timeout` vale True por defecto, y `Request.on_failure` solo reencola un `TimeLimitExceeded` cuando esa opción es False: la tarea se confirma y se pierde. `SoftTimeLimitExceeded` hereda de `Exception`, no de `OSError` ni de `SMTPException`, así que no entra en `autoretry_for`. `retry_backoff=True` sin factor ni tope da esperas aleatorias de hasta 1, 2 y 4 s: los tres reintentos caben en unos 7 s, que no cubren una caída del proveedor de correo de varios minutos. Como `SMTPException` es subclase de `OSError`, se reintentan también los errores permanentes (destinatario rechazado, autenticación fallida). `acks_late=True` es global, y los límites de 30/60 s, pensados para el SMTP, rigen para todas las tareas. Las pruebas fijan los valores de configuración y repiten el comentario equivocado; como las tareas corren en modo eager, ninguna ejerce un timeout ni un reintento real.

**Evidencia.**

- `backend/config/settings.py:227-236` — límites globales, el comentario falso (233-234) y `CELERY_TASK_ACKS_LATE` global; en el contenedor, `acks_on_failure_or_timeout=True` y `reject_on_worker_lost=None`.
- `backend/config/settings.py:213-225, 288-290` — beat y los límites que heredan; `EMAIL_TIMEOUT=20`, que smtplib aplica a cada operación de socket y no a toda la sesión.
- `backend/apps/community/tasks.py:7-11, 38` — `autoretry_for=(smtplib.SMTPException, OSError)`, `retry_backoff=True`, `max_retries=3`, sin tope ni exclusiones.
- `backend/apps/content/tasks.py:6-11` — `acks_late` redundante y el comentario «si el worker muere, se re-encola».
- `backend/tests/test_resilience.py:71-79` y `backend/tests/test_workflow.py:131-138` — repiten la afirmación; `backend/tests/test_newsletter.py:144-152, 155-168` — solo atributos, y una llamada directa sin reintento real.
- `backend/apps/community/views.py:26, 70-82, 85-95` — respuesta de éxito y ningún campo que registre el fallo.

**Por qué importa a futuro.** El proveedor de correo no responde durante dos minutos. Una persona se suscribe y ve «te enviamos un correo»; la tarea se reintenta tres veces en unos 7 s, se agota y se confirma. El correo no llega, el suscriptor queda pendiente y nada lo registra en la base (solo Sentry, si está configurado). Cuando se construya el envío del boletín confiando en el comentario, un lote que supere los 30 s quedará a medias, sin reintento.

**Recomendación.** Por orden:

1. Corregir los cuatro comentarios y la prueba de `test_resilience.py`. Es barato y conviene hacerlo antes de agregar tareas.
2. Para el correo: `autoretry_for=(OSError, smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, SoftTimeLimitExceeded)`, `dont_autoretry_for` para los rechazos permanentes, `retry_backoff=30`, `retry_backoff_max=900` y unos 8 reintentos (cerca de una hora). Alternativa mínima: plazos coherentes (`EMAIL_TIMEOUT` de 10 s y límite blando de 60 s).
3. Guardar en el suscriptor la fecha del envío y el último error, para poder reenviar (TAR-7).
4. Cuando se construya el envío masivo: límites y `acks_late` por tarea, solo en las idempotentes; idempotencia explícita de los envíos; y, si de verdad se quiere reencolar tras un timeout, `CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT=False` y `CELERY_TASK_REJECT_ON_WORKER_LOST=True`.
5. Una prueba de comportamiento con un backend de correo que falle. En modo eager, `task.retry` vuelve a ejecutar la tarea de forma síncrona: para comprobar la cuenta atrás hay que simular `task.retry` o ejecutar fuera de eager.

**Matiz de la verificación.** Severidad de alta a media: hoy el daño es un correo de confirmación perdido que se recupera reenviando el formulario, y el envío masivo no existe. «acks_late reencola» es falso cuando el límite duro mata la tarea o muere el proceso hijo, pero cierto si muere el proceso principal (Redis reentrega el mensaje tras el `visibility_timeout`, por defecto 1 h). El reenvío duplicado exige esa ventana estrecha y hoy solo repetiría un correo de confirmación, inocuo. Que la pantalla responda con éxito es intencional (no revela quién está suscrito); lo que falta es registrar el estado del envío. El backoff corto de `content/tasks.py` es razonable para una tarea idempotente que corre cada minuto.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «CELERY_TASK_ALWAYS_EAGER en tests» (decisión relacionada). La decisión ya admitía que la suite no ejercita reintentos ni límites de tiempo, y por eso las afirmaciones falsas pasaron sin aviso: los contratos miran la configuración, no su efecto. El modo eager sigue siendo razonable; estas garantías piden una prueba con un worker real, como `test_concurrency.py`.

#### TAR-2 · El procesamiento de imágenes corre síncrono en save(), repartido en cuatro disparadores y tragándose los errores

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `MediaAsset.save()` decodifica el original completo en cada guardado, aunque solo cambie el texto alternativo, para ver si trae EXIF; si lo trae, lo reescribe limpio, y genera hasta tres copias para el `srcset`. Si la imagen es la portada, una señal `post_save` de showcase genera hasta 12 copias AVIF y WebP, antes de `strip_metadata` (lo reconoce un comentario), y `SiteProfile.save()` vuelve a pedirlas en cada guardado del perfil. Todo ocurre en el hilo de gunicorn y dentro de la transacción del admin. Hay cuatro disparadores: `MediaAsset.save`, la señal de showcase, `SiteProfile.save` y el comando de reparación. Los fallos se tragan: el módulo tiene cinco `except Exception` y ningún logger. El comando solo cubre el `srcset` (no limpia metadatos ni hace las copias de portada) y responde «Derivados verificados para N recursos» aunque haya fallado. AVIF y GIF quedan fuera de la lista de formatos que se limpian y conservan su EXIF sin error (RES-1).

**Evidencia.**

- `backend/apps/media/models.py:58-63` — `save()` llama, en síncrono, a `strip_metadata()` y `ensure_derivatives()`.
- `backend/apps/media/models.py:113-118, 141-144, 171-181, 231-236, 279-286` — los cinco `except Exception` (117, 143, 180, 235, 285); los imports (1-11) no incluyen logging.
- `backend/apps/media/models.py:171-178` — `img.load()` antes de mirar los metadatos; la lista de la 177 excluye AVIF y GIF.
- `backend/apps/showcase/apps.py:22-39` y `backend/apps/showcase/models.py:107-114` — la señal entre apps y el segundo disparador.
- `backend/apps/media/management/commands/generate_image_derivatives.py:15-20` — cuenta los recursos sin distinguir fallos.
- Medido en memoria, sin escribir: las 12 copias de portada de una imagen de 3000×2000 tardan 3,1 s en un equipo de 8 núcleos; en producción el contenedor web tiene `cpus: 1.5`.

**Por qué importa a futuro.** Un editor reemplaza el archivo de la imagen que ya es portada por una foto de móvil con GPS cuyo JPEG viene truncado. La señal, `strip_metadata` y `ensure_derivatives` fallan en `load()` y salen: el original queda servido por Caddy con las coordenadas, sin copias y sin una línea de log, y el comando responde «Derivados verificados». En la evolución del código, un agente añade un derivado nuevo solo en `save()` y no en el comando ni en el cargador de desarrollo, y nadie lo nota.

**Recomendación.** Un único servicio `procesar_imagen(asset_id)` que haga, en este orden, la limpieza de metadatos, el `srcset`, las copias de portada si corresponde y el color de borde. Encolarlo con `transaction.on_commit(lambda: procesar_imagen.delay(pk))` desde `save()`, solo cuando cambie el archivo y con su propio `soft_time_limit` (por ejemplo 120 s); el proceso ya es idempotente. Que showcase pida al servicio las copias de portada en vez de tener su propia señal, y quitar la llamada de `SiteProfile.save()`. Cambiar los `except Exception: return` por `logger.warning(..., exc_info=True)` y estrecharlos a `OSError`, `UnidentifiedImageError` y `DecompressionBombError`. Mirar `getexif()` antes de `load()` (Pillow lee la cabecera sin decodificar). Guardar el resultado de la limpieza (`metadata_stripped_at`) para auditarla y reintentarla. Que el comando use el mismo servicio, limpie también las imágenes antiguas e informe cuántas fallaron.

**Matiz de la verificación.** Con workers gthread, `--timeout 30` no limita la duración de una petición; el límite efectivo es el `write 60s` de Caddy, y lo medido (3-4 s por portada en un núcleo) queda lejos: sobra «el guardado se acercará al timeout». También es falso que cada guardado tarde varios segundos o que el trabajo se repita entre la señal y `SiteProfile.save`: las copias solo se codifican si faltan, y un guardado normal cuesta una decodificación (unos 30 ms a 4 MP). No todo fallo se traga: las escrituras fuera del try propagan el error, la transacción se revierte y la fila vuelve a un archivo que filecleanup ya borró (DAT-4); ese es el riesgo real de hacer E/S de archivos dentro de la transacción. El orden señal → limpieza no filtra GPS en las copias: los guardadores de Pillow no copian el EXIF.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D18, la obra en AVIF y WebP hasta 2560 px (decisión relacionada). La decisión de formatos sigue siendo buena; lo cuestionable es generar las copias dentro de un `save()` síncrono y tragándose los errores.

#### TAR-3 · El ciclo de vida del suscriptor vive en las vistas y la purga mide la antigüedad desde la creación

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Las transiciones de alta, confirmación y baja cambian campos sueltos desde tres vistas, sin métodos de modelo ni marca de tiempo del cambio de estado; el admin, que deja todo editable, es una cuarta vía (DOM-5). Consecuencias:

- (a) La purga borra las altas pendientes y las bajas según `created_at`. Quien se vuelve a suscribir pasa a pendiente con un token nuevo de 48 h, pero conserva su `created_at` antiguo.
- (b) Los envíos rechazados o retirados también se purgan por `created_at`, mientras la política de privacidad publicada promete eliminarlos «pasado un tiempo desde su resolución». `Submission` no tiene marca de resolución: un envío de hace siete meses rechazado hoy desaparece con su adjunto la semana siguiente. El comentario del comando («referencia conservadora, nunca borra antes de lo debido») va en el filtro de las bajas y dice lo contrario de lo que ocurre.
- (c) La baja no anula el `confirm_token` vigente, y la re-suscripción conserva el `confirmed_at` antiguo en una fila pendiente.
- (d) El correo es único pero distingue mayúsculas y no se normaliza: «`Ana@Correo.cl`» y «`ana@correo.cl`» son dos suscriptores.

**Evidencia.**

- `backend/apps/community/views.py:70-79, 99-122, 149-151` — alta, confirmación (busca por token sin mirar el estado) y baja (solo cambia `status`).
- `backend/apps/community/models.py:26-36` — sin `status_changed_at` ni `unsubscribed_at`; los tokens tienen índice pero no son únicos.
- `backend/apps/community/forms.py:10` — el correo se conserva tal cual; en la base, un índice único btree sobre varchar.
- `backend/apps/submissions/management/commands/purge_stale_data.py:39-50` — los tres filtros por `created_at__lt`; el comentario invertido en 42-43.
- `backend/apps/submissions/models.py:40-74` y `backend/apps/submissions/admin.py:19-26` — solo `created_at`; el estado se cambia a mano en el panel.
- `backend/apps/content/migrations/0010_privacy_ley_21719.py:23-30` — la promesa de la política publicada.

**Por qué importa a futuro.** Una convocatoria está abierta desde marzo. Un envío entra el 2026-03-01 y el equipo lo rechaza el martes 2026-10-27. El lunes 2026-11-02 a las 04:30, la purga semanal encuentra un rechazado con `created_at` anterior al corte de 180 días y borra el adjunto y la fila seis días después de la resolución: no queda nada con qué atender una reclamación. Cuando exista el envío del boletín, las filas duplicadas por mayúsculas harán que quien se dio de baja en una siga recibiendo en la otra.

**Recomendación.** Llevar las transiciones a métodos del modelo (`solicitar_confirmacion()`, `confirmar()`, `dar_de_baja()`) que fijen un `status_changed_at` y limpien lo que corresponde: la baja anula `confirm_token` y la re-suscripción limpia `confirmed_at`. Normalizar el correo (`strip().lower()`) y, tras deduplicar las filas existentes, migrar a `UniqueConstraint(Lower("email"), name="suscriptor_email_ci")`. Añadir `resolved_at` a `Submission`, fijado al pasar a rechazado o retirado (también desde el admin) y rellenado por migración, y purgar por esa fecha; las pendientes, por `confirm_token_at`, y las bajas, por `status_changed_at`. Corregir el comentario y añadir pruebas de re-suscripción cruzada con la purga y de resolución tardía. Opcional: unicidad parcial de `token` (con `token != ''`) y `CheckConstraint(~Q(status="confirmed") | Q(confirmed_at__isnull=False))`.

**Matiz de la verificación.** El comentario invertido es el del filtro de las bajas, y borrar antes a quien se dio de baja favorece la privacidad: ahí el daño es solo el comentario falso. El caso de la re-suscripción es estrecho (la purga tiene que caer dentro de las 48 h previas a confirmar) y se repara solo con un alta nueva. Confirmar después de la baja exige un POST de quien tiene el buzón. La duplicación por mayúsculas exige que la misma persona confirme las dos filas.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), D2, boletín latente con doble opt-in y purga periódica (decisión relacionada). D2 fijó el ciclo (captar, confirmar, purgar), pero no dónde vive ni desde qué fecha se cuenta. Sigue siendo razonable; necesita una marca de tiempo del último cambio de estado.

#### TAR-4 · Los secretos del boletín viajan como argumentos de tarea y el worker queda fuera de la redacción

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** La vista pasa a Celery el correo del suscriptor y las dos URL con token. La redacción de tokens está pensada para el proceso web: el filtro `RedactTokensFilter` cuelga del handler de Django, y `sentry_before_send` solo limpia `request.url`, `query_string` y `transaction`. En el worker, Celery secuestra el logger raíz (`worker_hijack_root_logger` vale True y no hay receptor de `setup_logging`): a partir de la segunda línea, el log sale en el formato de Celery, sin JSON y sin filtro (observado en `docker compose logs worker`). Sentry tiene `include_local_variables=True` por defecto (sentry-sdk 2.72) y, cuando la tarea falla, envía las variables locales de cada marco: `email`, `confirm_url` y `unsub_url`. El depurador del SDK solo tapa claves exactas como `password` o `token`. Los argumentos de `extra.celery-job` sí se sustituyen con `send_default_pii=False`; las variables locales no. La fuga tampoco es exclusiva del worker: en la web, el `logger.exception` de `_send_confirmation` ante un `BrokerError` lleva `sub` (cuyo repr es el correo) y las dos URL, pese al comentario «Sin la dirección en el mensaje».

**Evidencia.**

- `backend/apps/community/views.py:85-96` — la línea 90 pasa el correo y las URL; la rama `BrokerError` (95-96) registra con esas variables vivas.
- `backend/apps/community/tasks.py:7-38` — `email`, `confirm_url` y `unsub_url` son las variables del marco; autoretry y, al final, la excepción.
- `backend/config/redaction.py:39-52` — `before_send` no toca marcos ni `extra`.
- `backend/config/settings.py:294-315, 321-337` — el filtro cuelga del handler raíz; `sentry_sdk.init` sin `include_local_variables`, `event_scrubber` ni `data_collection`.
- `backend/config/celery.py:1-9` — sin receptor de `setup_logging`.
- En el contenedor: `celery/app/log.py:87-109` (sin receptores, vacía los handlers del raíz) y `sentry_sdk/scrubber.py:104-121, 159-163` (solo claves exactas).
- `.env.prod.example:83-88` — «Sentry: opcional pero recomendado».

**Por qué importa a futuro.** En producción, con `SENTRY_DSN` definido y la contraseña SMTP equivocada, alguien se suscribe y la tarea lanza `SMTPAuthenticationError`. Tras los reintentos, la integración de Celery envía el evento a Sentry con `ana@correo.cl` y las dos URL con token en las variables del marco. Quien acceda al proyecto de Sentry puede confirmar o dar de baja a esa persona, y la política publicada queda desmentida.

**Recomendación.**

1. Pasar a la tarea solo `subscriber_id` y construir las URL dentro, con un `SITE_URL` validado por envguard (COM-6); encolar con `send_confirmation_email.delay_on_commit(sub.pk)`. Así el broker, Sentry y los logs nunca ven los secretos.
2. Conectar `celery.signals.setup_logging` para aplicar `dictConfig(settings.LOGGING)`, o poner `CELERY_WORKER_HIJACK_ROOT_LOGGER = False`, pero solo después de que el formateador redacte de forma recursiva (RES-4).
3. En Sentry, `include_local_variables=False`, o un `before_send` que aplique `redact_path` a todas las cadenas del evento (marcos, `extra`, mensajes).
4. Una prueba que construya un evento con marcos y variables que contengan un token y compruebe que sale redactado.

**Matiz de la verificación.** Hoy ninguna línea del log del worker lleva tokens: los formatos de Celery no imprimen los argumentos, y Sentry ignora los loggers `celery.app.trace` y `celery.worker.job`. La parte de los logs es un riesgo latente. El mensaje completo de smtplib solo viaja si el fallo ocurre en `sendmail`; ante un fallo de conexión o de autenticación basta el marco de la tarea para la fuga. La rama `BrokerError` de la web casi no se alcanza, porque con Redis caído el límite de tasa falla cerrado antes.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), D2, y §2, «Correo SMTP / deliverability» (decisión relacionada). El correo de confirmación es el único envío real y sus tokens son la prueba del consentimiento, pero ninguna decisión cubre que viajen como argumentos de la tarea ni que el worker quede sin redacción. Basta con pasar el id del suscriptor.

#### TAR-5 · La limpieza de archivos depende de registrar cada FileField a mano y de nombres calculados con las constantes actuales

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Para que se limpie el disco, cada app tiene que llamar a `filecleanup.register(Modelo, "campo")` en su `ready()`, y nada lo impone: ninguna prueba recorre los FileField del proyecto para exigir el registro, y dos de los cinco registros (`Publication.pdf` y `SiteProfile.dossier_pdf`) no tienen ninguna prueba de limpieza. Los derivados se encuentran por convención de nombres, calculados con las constantes de hoy (`SRCSET_WIDTHS`, `PORTADA_WIDTHS`, `PORTADA_FORMATS`). Si se cambia un ancho o un formato, las copias antiguas desaparecen de `derivative_names()` y del `srcset` y quedan huérfanas para siempre, aunque el docstring del comando de derivados pida correrlo justo al ajustar los anchos: el comando solo crea, nunca borra, y tampoco rehace las copias de portada. No hay ningún barrido que compare el almacenamiento con la base.

**Evidencia.**

- `backend/apps/media/apps.py:9-16`, `backend/apps/submissions/apps.py:9-16` y `backend/apps/showcase/apps.py:18-20` — los registros a mano; agenda, people, reviews, content y community no tienen `ready()`.
- `backend/apps/media/filecleanup.py:30-39, 76-91` — `register()` conecta las señales con `dispatch_uid` del tipo `filecleanup:delete:{app.modelo}:{campo}`, que permitiría escribir la metaprueba.
- `backend/apps/media/models.py:18, 23-24, 65-87, 299-315` — las constantes y `derivative_names()`, que solo itera las vigentes; `_portada_name` incluye a propósito la extensión del original.
- `backend/apps/media/management/commands/generate_image_derivatives.py:1-20` — pide correrlo al cambiar los anchos, pero solo llama a `ensure_derivatives()`.
- `backend/tests/test_file_lifecycle.py:96-154` — cubre Submission, MediaAsset y Recording; `backend/conftest.py:19-29` recorre los FileField solo para aislar el almacén privado.
- `infra/backup/backup.sh:34-36, 52-57` — cada respaldo hace un tar completo de los medios; se guardan 14.

**Por qué importa a futuro.** Un agente añade `Event.flyer_pdf` en agenda, cuya app no tiene `ready()`, y no llama a `register()`. Los PDF reemplazados y borrados quedan en `/media/agenda/`, servidos por Caddy y copiados en cada respaldo; si el campo fuera un adjunto privado con datos personales, una petición de supresión no se cumpliría. Otro agente ajusta `SRCSET_WIDTHS` para mejorar la carga: las copias viejas no se borran nunca, y si después se borra una foto a pedido de la persona retratada, esas copias siguen accesibles en las URL que estuvieron publicadas en el `srcset`.

**Recomendación.** Registrar automáticamente en `MediaConfig.ready()` todos los FileField de `apps.get_models()`, con una lista explícita de excepciones; como mínimo, la metaprueba de ARQ-1 y PRU-3, que falla si un FileField no tiene receptores con `dispatch_uid` de filecleanup. Para los derivados, guardar los nombres generados en un campo JSON del recurso (lo preferible) o borrar por un patrón que incluya la extensión (`{stem}__*{suffix}` y `{stem}__portada-{ext}-*`). Un patrón `{stem}__*` a secas sería un error: `foto.jpg` y `foto.png` del mismo mes comparten raíz, y borrar una se llevaría las copias de la otra, justo lo que `_portada_name` evita. Opcional: un comando `media_huerfanos --dry-run/--borrar` como red de seguridad.

**Matiz de la verificación.** Las cifras del volumen de desarrollo (723 archivos, 453 huérfanos) son correctas pero no miden el patrón: son restos de la suite anteriores al aislamiento de `MEDIA_ROOT` (commit `b05d593`), con nombres de fixtures. Desde que existe el mecanismo no se ha producido ningún huérfano, y en producción no cabe esperar ese remanente; el huérfano del almacén privado es un `MARCADOR.txt` puesto a mano. La severidad se queda en media porque la frecuencia es baja: ningún FileField nuevo en tres meses.

#### TAR-6 · La caché del color del lomo no caduca ni tiene versión, y el desfase solo existe en producción

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `MediaAsset.color_de_borde()` guarda el color con `cache.set(clave, color, None)`, es decir, sin caducidad, bajo la clave `color-de-borde:{file.name}`. La clave no lleva versión del algoritmo, no se invalida al reemplazar ni al borrar el archivo y también guarda para siempre el `""` de una lectura fallida. Los nombres de archivo se reutilizan: filecleanup borra el viejo antes de que se guarde el nuevo, así que un reemplazo con el mismo nombre de subida en el mismo mes recibe exactamente el mismo nombre (la siembra lo documenta). En producción la caché es la base 2 de Redis, con `appendonly yes`, y sobrevive a reinicios y despliegues. En desarrollo es LocMem por proceso y en las pruebas se vacía antes de cada test: el desfase no se ve con `runserver` ni en la suite. Además, el compose afirma que Redis «No se usa como caché».

**Evidencia.**

- `backend/apps/media/models.py:265-297` — la clave solo con el nombre, `timeout=None` y el `""` cacheado ante cualquier excepción.
- `backend/config/settings.py:242-252` y `backend/config/cache.py:55-67` — LocMem con `DEBUG`, Redis si no; con Redis caído se vuelve a medir en cada visita.
- `docker-compose.yml:22-28` y `docker-compose.prod.yml:115-125` — el comentario (del 2026-07-27, un día antes de que la caché pasara a Redis), `appendonly` y `noeviction`.
- `backend/conftest.py:8-16` — `cache.clear()` antes y después de cada prueba.
- `backend/apps/media/filecleanup.py:53-73` y `backend/apps/media/management/commands/seed_material_generico.py:469-489` — el nombre se reutiliza al reemplazar.
- `backend/apps/showcase/models.py:229-249` y `backend/templates/content/home.html:190-196` — el lomo del estante lee el color en cada render. Medido: 8 mediciones con la caché fría y 0 en caliente.

**Por qué importa a futuro.** En producción, una editora sube «tapa.jpg» como tapa de una plaqueta y la portada guarda su azul sin caducidad. Al notar un error de imprenta, sube en el mismo recurso otra «tapa.jpg», corregida y en rojo: el archivo nuevo recibe el mismo nombre y el lomo sigue azul junto a una tapa roja, tras reinicios y despliegues, hasta que alguien vacíe Redis a mano. En local se ve bien. Lo mismo ocurre si un agente cambia el algoritmo de medición: las tapas existentes conservan el color viejo.

**Recomendación.** El color es un dato derivado del archivo, como `width` y `height`: guardarlo en una columna de MediaAsset (`border_color`) calculada junto a los derivados (TAR-2) y rellenada con `generate_image_derivatives`. Así la caché sobra. Si se prefiere mantenerla: clave con versión del algoritmo y huella del archivo (`f"color-de-borde:v2:{name}:{size}"`), caducidad finita (por ejemplo 30 días), sin cachear el fallo y con borrado en el `on_commit` del reemplazo. Corregir el comentario del compose.

**Matiz de la verificación.** El desfase aparece en cualquier stack con `DEBUG=0` y Redis persistente, no solo en producción. Compartir memoria y `noeviction` con el broker no es un riesgo real a esta escala (las claves pesan unos bytes; ver RES-5): lo que falla es el comentario. Un `KEY_PREFIX` sobra con una base dedicada; la versión en la clave sí da una palanca de invalidación.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D28 (color «medido una vez por archivo con Pillow y guardado en la caché»), y §1 (técnicas), «CACHES → Redis… Seguro con noeviction gracias a los TTLs» (decisión relacionada). D28 no previó reemplazos de archivo ni cambios del algoritmo, y su clave sin caducidad contradice la premisa de la decisión de CACHES (RES-5). La idea sigue siendo buena si la clave lleva versión, caduca y no guarda el resultado vacío.

#### TAR-7 · El correo transaccional no se valida al arrancar ni deja rastro, y su contenido vive en la tarea

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El guard de producción comprueba secretos, hosts y orígenes, pero nada del correo. Con los valores de la plantilla (`EMAIL_HOST=smtp.tuproveedor.cl`, `EMAIL_HOST_PASSWORD=secreto`, un `DEFAULT_FROM_EMAIL` de ejemplo) el sitio arranca normalmente, y cada confirmación falla después en el worker, tras tres reintentos de segundos, mientras el formulario responde «te enviamos un correo». Si falta la variable, el remitente por defecto es `no-reply@resenas.cl`. No se registra si un correo salió (`confirm_token_at` marca el alta, no el envío), así que no hay forma de reenviar ni de saber a quién no le llegó. El asunto y el cuerpo están escritos en Python dentro de la tarea, sin plantilla ni nombre del colectivo.

**Evidencia.**

- `backend/config/envguard.py:22-31, 45-99` — los marcadores de plantilla no incluyen «secreto»; ninguna comprobación del correo.
- `.env.prod.example:83-86, 92-97` — los valores de ejemplo del correo; `SENTRY_DSN` comentado.
- `backend/config/settings.py:278-291, 317-325` — `EMAIL_HOST` por defecto `localhost` y el remitente por defecto.
- `backend/apps/community/tasks.py:7-11, 21-38` — reintentos, y asunto y cuerpo literales.
- `backend/apps/community/models.py:26-36` y `backend/apps/community/admin.py:8` — ningún campo ni columna de envío, y ninguna acción de reenvío.

**Por qué importa a futuro.** El dueño copia la plantilla, rellena lo que el guard exige y deja el bloque SMTP tal cual. Un visitante se suscribe y lee «te enviamos un correo»; la tarea falla por DNS, se reintenta en segundos y termina en el log del worker. Sin `SENTRY_DSN`, nadie se entera, y durante semanas ninguna suscripción se confirma. Cuando se construya el boletín, el agente copiará a otra tarea el patrón de cuerpo escrito en Python.

**Recomendación.** En `check_production_env`, exigir un `DEFAULT_FROM_EMAIL` explícito cuyo dominio no sea de plantilla y rechazar `EMAIL_HOST` o `EMAIL_HOST_PASSWORD` con valores como «tuproveedor» o «secreto»; dejar esos valores vacíos en la plantilla, como los demás secretos (OPE-6). Un remitente por defecto inofensivo (`webmaster@localhost`). Guardar `confirmation_sent_at` cuando la tarea termina y mostrarlo en el admin, con una acción para reenviar. Asunto y cuerpo en `templates/community/email/confirmacion.txt`, renderizados con `render_to_string` y `site_profile.name`.

**Matiz de la verificación.** «Nada lo delata» se matiza: el fallo definitivo queda en el log del worker, y en Sentry si está configurado. Lo que falta es el rastro en la aplicación y la validación al arrancar. Que `resenas.cl` no sea un dominio del colectivo no se pudo verificar, y ese remitente solo entra si se borra la variable.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §2 (infraestructura), «Correo SMTP / deliverability» (diferido conocido). El SMTP real y la prueba de entrega dependían de la infraestructura; lo que añade este hallazgo (validar al arrancar, dejar rastro del envío) no depende de ella y se puede hacer ya.

#### TAR-8 · La degradación ante Redis cubre errores pero no cuelgues, y con Redis caído el buscador se apaga

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** media · **Verificación:** parcial

**Qué pasa.** `ResilientRedisCache` traduce los `RedisError` a la ruta de degradación, pero `CACHES` no fija timeouts: rigen los implícitos de redis-py 8.1.0 (5 s para conectar y 5 s por operación, sin reintentos). Ante un Redis que acepta conexiones y no responde (un contenedor pausado), cada operación espera unos 5 s: una búsqueda tarda unos 10 s y la portada, que hace una lectura y una escritura por cada tapa del estante, decenas de segundos; unas pocas visitas simultáneas ocupan los 12 hilos mientras dure el cuelgue. El productor de Celery es peor: kombu pasa `socket_timeout=None`. Además, `RATELIMIT_FAIL_OPEN = False` es global: con la caché caída, el buscador responde siempre «Demasiadas búsquedas seguidas», un mensaje que no describe lo que pasa. La prueba de resiliencia del buscador solo afirma el código 200.

**Evidencia.**

- `backend/config/settings.py:242-257` — `CACHES` sin `OPTIONS` y `RATELIMIT_FAIL_OPEN = False`, con un comentario que justifica el fail-closed.
- `backend/requirements.txt:72, 278` — kombu 5.6.2 y redis 8.1.0; en el shell, el pool de la caché usa 5 s y 5 s, y el canal de kombu tiene `socket_timeout=None`.
- `backend/config/cache.py:18-21, 36-74` — el docstring declara deliberado que, con Redis caído, los endpoints con límite respondan «espera un momento».
- `backend/apps/content/views.py:396, 422-423, 492-503` — el buscador limitado y `_broker_ok`, que sí usa timeouts de 3 s.
- `backend/templates/content/partials/_search_results.html:6-7` — el mensaje de «demasiadas búsquedas», también cuando la causa es Redis.
- `backend/tests/test_resilience.py:14-20, 52-56, 66-69` — Redis simulado en un puerto sin escucha; solo se afirma el 200.

**Por qué importa a futuro.** Un Redis atascado ralentiza la portada y el buscador hasta saturar los hilos. Y si alguien añade un `.delay()` fuera de una vista con límite de tasa (por ejemplo, al guardar algo en el admin), ese encolado puede bloquear un hilo sin límite, porque kombu no tiene timeout de socket.

**Recomendación.** `"OPTIONS": {"socket_timeout": 1, "socket_connect_timeout": 1}` en `CACHES` (la caché es prescindible) y `CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_timeout": 5, "socket_connect_timeout": 3}`. Para el buscador, decidir y dejarlo escrito: si debe funcionar con Redis caído, llamar a `django_ratelimit.core.get_usage(...)` y tratar el contador no disponible como «no limitado»; si no, un mensaje veraz («el servicio no está disponible»). Que la prueba afirme el comportamiento elegido, no solo el 200.

**Matiz de la verificación.** Se retiraron «redis-py espera indefinidamente» y «el sitio se congela hasta que alguien lo reinicia»: con redis 8.1.0 los timeouts efectivos son de 5 s y los hilos se liberan solos cuando Redis vuelve a responder. Que el buscador falle cerrado ya está documentado como decisión; quedan pendientes el mensaje y la prueba. El punto del productor de Celery es el más sólido, aunque hoy lo protege el límite de tasa de la única vista que encola.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «CACHES → Redis (db 2) en prod» (decisión relacionada). La caché se llevó a Redis para compartir los contadores de ratelimit, y por eso un Redis caído o colgado alcanza al buscador. La decisión sigue siendo necesaria, pero la caché necesita timeouts de socket, como ya los tiene `/readyz/`.

### 4.7 Configuración, despliegue, CI y operación (OPE)

#### OPE-1 · El despliegue arranca el código nuevo antes de migrar y deja los pasos de release a la memoria del operador

**Severidad:** alta · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** En producción ningún servicio migra al arrancar. web lleva `DJANGO_SKIP_MIGRATE=1`, y worker y beat ni siquiera pasan por `entrypoint.sh`, porque su `entrypoint:` es celery: el `DJANGO_SKIP_MIGRATE` de sus bloques es configuración muerta. El procedimiento documentado es `git pull` → `up -d --build` → `run ... migrate  # si hubo migraciones`; entre el segundo y el tercer paso, el código nuevo sirve contra el esquema viejo, y si el operador no sabe que hubo migraciones, el sitio se queda así. La cabecera de `docker-compose.prod.yml` sigue el mismo orden (primero `up`), aunque ahí pide `migrate` y `setup_groups` sin condición. El valor por defecto va en sentido contrario a la política: `entrypoint.sh` migra salvo que se le diga lo contrario, y el compose base, que se declara «prod-safe», no lo desactiva. `setup_groups` no figura en el redespliegue y, aunque corriera, ya no añade permisos a un grupo existente (AGE-2). No hay una imagen etiquetada a la que volver.

**Evidencia.**

- `docs/despliegue.md:40, 49-59` — el redespliegue hace `up` (53) antes del `migrate` condicional (54); `setup_groups` solo aparece en la instalación inicial (40).
- `docker-compose.prod.yml:3-7, 40-43, 67-70, 86-89` — la cabecera y los `DJANGO_SKIP_MIGRATE` de web, worker y beat.
- `docker-compose.yml:3-5, 35-50, 52-69` — web migra al arrancar; worker y beat con `entrypoint: ["celery", ...]` y `depends_on` en forma corta; ninguna `image:` etiquetada.
- `backend/entrypoint.sh:4-18` — migra y ejecuta `setup_groups` salvo `DJANGO_SKIP_MIGRATE=1`; `collectstatic` en cada arranque si se pide.
- `backend/apps/content/views.py:474-486` — `/healthz/` no toca la base y `/readyz/` solo hace `SELECT 1`: ningún healthcheck detecta columnas ausentes.
- `backend/apps/showcase/context_processors.py:6-17` y `backend/apps/showcase/models.py:120-126` — `SiteProfile.load()` se evalúa en todas las páginas; las migraciones `showcase/0008` y `0009` (del 20 y el 22 de octubre) añadieron campos a ese modelo.
- `backend/Dockerfile:7, 13, 19, 29, 37` — base fijada por digest y requisitos con hashes: reconstruir un commit es reproducible, salvo el `pip` sin versión.

**Por qué importa a futuro.** Un agente añade un campo a SiteProfile, como ya pasó dos veces este mes. El dueño ejecuta `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` y omite el `migrate`, porque la guía dice «si hubo migraciones». En cada petición HTML, el procesador de contexto lanza `ProgrammingError: column ... does not exist` y todo el sitio responde 500. `/healthz/` sigue en 200, así que ni el healthcheck ni `restart: unless-stopped` reaccionan, y sin `SENTRY_DSN` no llega ninguna alerta. beat sigue encolando cada minuto y el worker falla con el mismo error. Para volver atrás no hay imagen anterior: hay que reconstruir otro commit en el VPS.

**Recomendación.** Hacer del release un paso del propio compose: un servicio `release` de un solo uso, con la misma imagen, `command: sh -c "python manage.py migrate --noinput && python manage.py setup_groups && python manage.py collectstatic --noinput"`, `restart: "no"` y el volumen de estáticos, y en web, worker y beat `depends_on: {release: {condition: service_completed_successfully}}`. Así `up -d` migra una sola vez y antes de arrancar el código nuevo. Si no se quiere el servicio, la variante mínima es reordenar la guía (construir → `migrate` y `setup_groups` → `up -d`) y quitar el «si hubo migraciones».

Además:

- Invertir el valor por defecto del entrypoint: no migrar salvo con `DJANGO_MIGRATE_ON_START=1`, que solo fija el override de desarrollo. Quitar el `DJANGO_SKIP_MIGRATE` muerto de worker y beat.
- Etiquetar la imagen con el commit (`image: resenas-app:${APP_VERSION}`), conservar la anterior y documentar el rollback. Con un release, el web viejo sigue sirviendo mientras se migra: hacen falta migraciones expand/contract (primero añadir, después quitar).
- Llevar los permisos de cada modelo nuevo con una migración de datos (AGE-2).
- Que el smoke del CI arranque web con `DJANGO_SKIP_MIGRATE=1` y migre en un paso aparte, como en producción.

**Matiz de la verificación.** Son 39 migraciones, no 47, añadidas en 21 commits, y solo unas 20 de 235 fusiones a `main` (el 8,5 %) trajeron una: «casi todo despliegue llevaría una» solo vale si se despliega por semanas, aunque una cadencia irregular favorece olvidar el paso condicional. El escenario es más grave que el original: cualquier campo nuevo en SiteProfile rompe todas las páginas, no solo las del modelo tocado. Ejecutar `collectstatic` en cada arranque tiene un impacto bajo (nombres con hash, sin `--clear`). El rollback por reconstrucción es reproducible; lo que falta es una imagen etiquetada y un procedimiento. El fallo de `setup_groups` es latente y falla cerrado.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §2 (infraestructura), «CD real» (diferido conocido). El job de release se difirió a falta de un registro de imágenes, y mientras tanto el despliegue queda en manos del operador. Migrar antes de arrancar el código nuevo no depende de esa infraestructura y se puede corregir ya.

#### OPE-2 · Un único DEBUG decide almacenamiento de estáticos, caché, correo y logs, y la suite siempre corre del lado de desarrollo

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El almacenamiento de estáticos, la caché, el backend de correo, el formato de los logs, el guard de producción, las cabeceras de seguridad y el entorno de Sentry se eligen al importar settings según `DEBUG`: siete bifurcaciones. Las pruebas corren con `DJANGO_DEBUG=1` y con el mismo módulo de settings que producción, y otros dos ajustes dependen de que `"pytest" in sys.modules`. Por eso la suite nunca usa `ManifestStaticFilesStorage` con `manifest_strict`: un `{% static %}` que apunta a un archivo inexistente da, en desarrollo y en la suite, un 404 silencioso del recurso, y en producción un `ValueError` («Missing staticfiles manifest entry») que tumba la página entera. El job prod-runtime solo pide `/healthz/`, `/readyz/`, `/` y un estático, y con la base vacía la portada no activa las referencias condicionadas a datos. Al margen, `CELERY_TASK_ALWAYS_EAGER` se activa sin `CELERY_TASK_EAGER_PROPAGATES`, y la falta de `CONN_HEALTH_CHECKS` se trata en REN-8.

**Evidencia.**

- `backend/config/settings.py:15, 38-47, 186-199, 242-252, 267-276, 279-282, 307, 329` — las siete bifurcaciones en tiempo de importación.
- `backend/config/settings.py:121, 151, 225` — `CONN_MAX_AGE`, `AXES_ENABLED` y el modo eager, estos dos según pytest; ni `CONN_HEALTH_CHECKS` ni `CELERY_TASK_EAGER_PROPAGATES` aparecen en el repositorio.
- `backend/config/staticfiles.py:11-14` — hereda de `CompressedManifestStaticFilesStorage`; el `ValueError` se reprodujo con `url('js/dossier-v2.js', force=True)`.
- 14 referencias `{% static %}` distintas en `base.html`, `content/home.html` (tres dentro de `{% if %}` que dependen de datos), `showcase/dossier.html:9` y `500.html:23`, más el Media del editor del panel (`backend/apps/content/admin.py:33-37`).
- `.github/workflows/ci.yml:44, 101, 113-123, 154-187, 299-306` — la suite con `DEBUG=1`; las mitigaciones (`check --deploy`, `collectstatic` real, prod-runtime).
- `backend/pytest.ini:2` y `backend/pyproject.toml:20-28` — el mismo módulo de settings que producción; settings fuera de la cobertura.

**Por qué importa a futuro.** Un agente añade `{% if destacados %}<script src="{% static 'js/relevo.js' %}" defer></script>{% endif %}` a la portada, o renombra `js/dossier.js` y olvida `dossier.html`. La suite queda en verde, y prod-runtime también, porque con la base vacía la condición es falsa y `/dossier/` nunca se pide. En el VPS, en cuanto hay datos que activan la condición, la portada responde 500.

**Recomendación.** Lo más rentable, primero: una prueba que recorra las plantillas, los Media de los formularios y los `static()` literales y exija `django.contrib.staticfiles.finders.find(ruta)` para cada referencia. Después:

- Separar los ejes con una variable explícita (`DJANGO_ENV=dev|test|prod`) o con módulos `config/settings/{base,dev,test,prod}.py`.
- Un `DJANGO_SETTINGS_MODULE` de pruebas en `pytest.ini` que fije `AXES_ENABLED = False`, `CELERY_TASK_ALWAYS_EAGER = True` y `CELERY_TASK_EAGER_PROPAGATES = True` sin mirar `sys.modules`.
- Una prueba que ejecute `collectstatic` con el almacenamiento de producción en un directorio temporal y renderice una página de cada tipo.

**Matiz de la verificación.** Son siete bifurcaciones, no cuatro. Se retiró la afirmación sobre la serialización: en Celery 5.6.3, el modo eager serializa los argumentos con JSON, así que un modelo como argumento también hace fallar la suite. La excepción tragada en eager está mitigada hoy, porque la única tarea encolada se verifica por `mail.outbox`. Que la suite no use SMTP es inherente a Django. El CI con `DEBUG=0` sí ejercita las diez referencias de `base.html` y la lámina de la portada, pero no las tres condicionadas de `home.html`, `dossier.js` ni los Media del panel. Excluir settings de la cobertura es práctica habitual.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «CACHES → LocMem en dev/tests», «CELERY_TASK_ALWAYS_EAGER en tests» y «filterwarnings = error», y los bloques de CI build-prod y prod-runtime (decisión relacionada). Esas decisiones ponen la suite del lado de desarrollo a propósito, y solo dos jobs ejercen `DEBUG=0`. Siguen siendo razonables, pero dejan sin pruebas propias la rama de producción de settings.

#### OPE-3 · La recuperación ante desastre no está probada de punta a punta: la retención off-site no funciona, no hay restauración desde restic y restore.sh no es atómico

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Son cuatro problemas:

1. `restic forget --keep-last N` agrupa por defecto por host y rutas, y cada respaldo sube una ruta distinta (`/backups/<marca de tiempo>`). Cada snapshot forma su propio grupo, así que `--keep-last 30` nunca borra nada, `RESTIC_KEEP` no tiene efecto y la poda nunca llega a ejecutarse.
2. `restore.sh` solo lee `/backups` local: no hay un camino escrito para recuperar desde restic, que es justo el caso «perdí el servidor».
3. `restore.sh` ejecuta `pg_restore --clean` sin `--single-transaction` ni `--exit-on-error`, de modo que un fallo a medias deja la base mezclada, y borra los medios actuales (`rm -rf /volumes/media/*`) antes de comprobar que el tar se puede extraer.
4. El CI no ejecuta el camino feliz de `restore.sh`: reproduce a mano sus opciones contra una base nueva y solo comprueba que el script se niega sin confirmación. Tampoco construye la imagen real del contenedor de respaldo, que lleva restic y curl.

**Evidencia.**

- `infra/backup/backup.sh:22-23, 35-36, 43-47` — destino con marca de tiempo, `tar` con errores silenciados (RES-2) y `restic forget --prune --keep-last` sin `--group-by`.
- Documentación de restic sobre `forget`: los snapshots se agrupan por host y rutas, la política se aplica a cada grupo y `--prune` solo poda si se eliminó alguno.
- `infra/backup/restore.sh:21-27, 30-33, 35-44` — solo `/backups` local; `pg_restore` no atómico; `rm -rf` antes de `tar xzf`.
- `.github/workflows/ci.yml:386-390, 398-409, 425-434` — la única invocación de `restore.sh` (431) es la prueba de rechazo.
- `infra/backup/Dockerfile:4-8` — la imagen real, que ningún job construye.
- `docker-compose.yml:71-104` y `.env.prod.example:69-81` — restic «Muy recomendado», con `RESTIC_KEEP=30`.

**Por qué importa a futuro.** Se pierde el VPS. El dueño descubre que lo externo es un repositorio restic que ningún script restaura e improvisa `restic restore latest --target /` bajo presión, mientras el almacenamiento externo conserva todos los snapshots diarios desde el primer día y la factura crece. En el servidor vivo, restaurar un respaldo cuyo `media.tar.gz` quedó truncado borra los medios que había y la extracción falla a la mitad.

**Recomendación.**

- En `backup.sh`: `restic forget --group-by host,tags --tag resenas --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --prune`, o respaldar siempre desde una ruta fija. Mejor aún, respaldar los volúmenes directamente con restic, sin tar.gz, para que funcione la deduplicación. Y un `restic check` semanal.
- Un `restore.sh --desde-restic <snapshot|latest>` que haga `restic restore` a un directorio temporal y siga con el flujo local.
- En `restore.sh`: `pg_restore --single-transaction --exit-on-error`; `tar tzf` antes de tocar nada; extraer en `/volumes/media.nuevo` y sustituir solo al final; opciones `--solo-bd` y `--solo-medios`.
- En el CI: construir `infra/backup/Dockerfile`, ejecutar `restore.sh` con `RESTORE_CONFIRM` sobre una base con el esquema vivo, comprobar conteos y archivos restaurados, y hacer un ida y vuelta de restic contra un repositorio local.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §2 (infraestructura), «Respaldo off-site (restic)» (diferido conocido). La restauración desde restic estaba anotada como pendiente, pero el registro daba por buena la rama restic de `backup.sh`, y su retención no borra nada. No es solo esperar la infraestructura: hay fallos de código que se pueden corregir ya.

#### OPE-4 · Lo que el CI prueba no es lo que se despliega: la imagen se reconstruye en el VPS, el compose de producción nunca se carga y las comprobaciones están copiadas a mano

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** La imagen de producción se construye en el VPS desde el árbol de trabajo (`git pull` y `up -d --build`); el CI construye la suya tres veces, una por job, y la descarta. El CI nunca invoca `docker compose`: el job prod-runtime rehace a mano los `docker run`, copia como texto los healthchecks de web, worker y beat, y arranca gunicorn con el comando por defecto de la imagen (workers sync, tres procesos). El comando real de producción (gthread, `--threads`, `--timeout`, `--max-requests`, `--forwarded-allow-ips`) solo vive en `docker-compose.prod.yml`, que nadie ejecuta antes del VPS. Las imágenes del CI van por etiqueta mutable (`postgres:16`, `redis:7`, `caddy:2-alpine`, `alpine`), mientras el compose fija digest, y `test_image_pinning.py` no revisa los workflows: un PR de Dependabot que cambia el digest de caddy se valida contra otra imagen. Además, web, worker y beat tienen cada uno `build: ./backend` sin `image:`, y CONTRIBUTING manda reconstruir solo web tras cambiar dependencias. Por último, trivy es solo informativo, las actions van por etiqueta, pytest-xdist está instalado pero la suite corre en serie, y no hay `concurrency` ni `timeout-minutes`.

**Evidencia.**

- `.github/workflows/ci.yml:134, 140-143, 197, 207, 255-259, 266, 290-291, 308, 316-317, 362` — tres builds; gunicorn con el comando por defecto; los healthchecks copiados bajo un comentario que dice verificar los del compose; trivy con `continue-on-error`.
- `.github/workflows/ci.yml:26, 36, 273, 274, 330, 338, 369, 409, 413, 431` — diez imágenes por etiqueta mutable; además, ocho `uses:` por etiqueta.
- `docker-compose.prod.yml:4, 13-35, 56-103` — el redespliegue con `--build` en el servidor, el único lugar con el comando real de gunicorn y los healthchecks reales.
- `docker-compose.yml:37-38, 53-54, 64-65` y `CONTRIBUTING.md:50-54` — tres `build:` y la reconstrucción parcial.
- `backend/tests/test_image_pinning.py:24-25` — revisa los Dockerfile y los compose, no `.github/workflows`.
- `backend/requirements-dev.txt:408` — pytest-xdist instalado, sin uso en `ci.yml:101`.

**Por qué importa a futuro.** Un agente cambia `--threads` o añade una opción de gunicorn con una errata en `docker-compose.prod.yml`. El CI no carga ese archivo y queda en verde; en el VPS, `up -d --build` recrea web, gunicorn sale por la opción inválida, el contenedor entra en un bucle de reinicios y Caddy responde 502 hasta revertir. Otro caso: un agente cambia la ruta del archivo de agenda de beat y actualiza el healthcheck en el compose; el CI sigue comprobando su copia y pasa, y en producción beat queda en estado unhealthy.

**Recomendación.** Lo proporcionado para un solo VPS:

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q` como lint en el CI.
- Levantar prod-runtime con el compose real (`up -d --wait`, con un `ci/prod.env`) o, como mínimo, pasar el comando de gunicorn a `backend/gunicorn.conf.py`, que gunicorn lee por defecto, para que Dockerfile, compose y CI compartan configuración.
- Fijar por digest las imágenes del CI y extender `test_image_pinning.py` a `.github/workflows/*.yml`. Construir también `infra/backup/`.
- Corregir el comentario de `ci.yml:255-259`, una sola `image:` para web, worker y beat, `pytest -n auto` y, para trivy, `--exit-code 1` con un umbral decidido, o retirar el paso.

Publicar la imagen en un registro con la etiqueta del commit y desplegar esa misma es lo ideal, pero hoy es desproporcionado.

**Matiz de la verificación.** Las tres imágenes locales tienen el mismo contenido; sus identificadores difieren solo por la etiqueta de servicio del compose. El riesgo real es la reconstrucción parcial que indica CONTRIBUTING, no el redespliegue documentado, que reconstruye las tres. Son ocho `uses:`, no siete, y Dependabot ya los actualiza. Lo que difiere entre el CI y el VPS es sobre todo la configuración (compose y gunicorn), no el contenido de la imagen, que es reproducible salvo `pip`.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §2 (infraestructura), «CD real» (diferido conocido): su texto da por hecho que «el build-prod de CI ya construye y valida la imagen», pero el VPS reconstruye otra y el CI nunca carga el compose de producción. El pendiente sigue vigente; conviene corregir su premisa.

#### OPE-5 · Los límites de petición se pensaron para el formulario público y se aplican a todo el sitio, panel incluido; en desarrollo no existen

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Caddy aplica `request_body max_size 12MB` a todo el sitio, un valor razonado para el adjunto público de 10 MB. Pero el panel permite subir audio y vídeo en `Recording.file` (mp3, wav, flac, mp4, webm…), PDF de publicaciones y del dossier e imágenes, sin tope propio: el único control de tamaño de la aplicación está en el formulario de envíos. En producción, cualquier archivo de más de 12 MB recibe un 413 sin cuerpo; en desarrollo funciona, porque runserver atiende sin Caddy delante. En Django, `DATA_UPLOAD_MAX_NUMBER_FIELDS` vale 200, frente a 1000 por defecto: un evento con 35 fotos y sin participantes envía 203 parámetros y no se puede guardar (`TooManyFieldsSent`, un 400), y una colección con 43 piezas envía 202. Y pegar en TinyMCE una imagen como `data:` la pierde en silencio, porque nh3 borra ese `src` al guardar.

**Evidencia.**

- `infra/caddy/Caddyfile:4-16, 38-42` — `read_body 30s` y `read_header 10s` globales; `max_size 12MB` para todo el sitio y sin `handle_errors`, así que el 413 sale vacío.
- `backend/apps/media/models.py:26-30, 336-341` y `backend/apps/media/validators.py:20-33` — imagen y grabación sin tope; solo listas de extensiones.
- `backend/apps/showcase/models.py:55-61, 206-211` — los PDF solo validan la extensión.
- `backend/apps/submissions/forms.py:110-125` — el único control de tamaño de la aplicación (línea 119).
- `backend/config/settings.py:159-162` — `DATA_UPLOAD_MAX_MEMORY_SIZE` de 3 MB y `DATA_UPLOAD_MAX_NUMBER_FIELDS = 200`.
- `backend/apps/agenda/admin.py:6-21` y `backend/apps/content/admin.py:298-316` — medido: un evento nuevo envía 28 parámetros y 5 más por foto; una colección, 30 y 4 por pieza.

**Por qué importa a futuro.** Un editor sube la grabación de una lectura de 20 minutos (un mp3 a 128 kbps pesa unos 19,2 MB) para que entre en el pódcast. Caddy corta a los 12 MB con un 413 vacío y el editor ve una página de error del navegador; en local la misma subida funciona, así que nadie lo puede reproducir. Alguien documenta un recital con 35 fotos y el evento no se guarda.

**Recomendación.** Límites por ruta en Caddy (un bloque `handle /admin/*` con un `max_size` mayor, y 12 MB para el resto) y validadores de tamaño explícitos por campo (audio y vídeo, PDF, imagen) con mensajes claros, de modo que el límite real sea el de Django y el de Caddy quede algo por encima; una prueba que compare el `max_size` del Caddyfile con el mayor tope de los validadores. Devolver `DATA_UPLOAD_MAX_NUMBER_FIELDS` a 1000 (el tamaño del cuerpo ya lo acota Caddy) y probar desde el admin un evento con 40 fotos. En TinyMCE, `paste_data_images: false`.

Ojo con `read_body`: `read_header` solo acota las cabeceras, y el cuerpo lento lo acota `read_body`. Caddy reenvía el cuerpo a gunicorn en streaming, así que cada subida lenta retiene uno de los 12 hilos durante toda la ventana, y `/admin/` acepta POST anónimos (basta la cookie CSRF de un GET) que Django vuelca a `/tmp`. Hay que elegir los valores sabiendo ese costo, o sacar las subidas grandes del camino web (incrustar el reproductor o importar con un comando).

**Matiz de la verificación.** `read_body 30s` no se pensó para el adjunto, sino contra los clientes lentos; solo `max_size` menciona el adjunto. El umbral medido es de 35 fotos sin participantes; cada 5 participantes o casillas marcadas resta una foto. Lo de TinyMCE quedó verificado y no se arregla subiendo `DATA_UPLOAD_MAX_MEMORY_SIZE`. Se corrigió la recomendación inicial, que proponía subir `read_body` a 10 minutos con el argumento de que `read_header` ya protegía. Con el cliente todavía subiendo, el navegador puede mostrar «conexión restablecida» en vez del 413.

#### OPE-6 · Variables de entorno leídas a mano: «true» desactiva controles de seguridad y el guard valida algo distinto de lo que usa Django

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `settings.py` hace 38 lecturas con `os.environ.get` y repite a mano tres formas de interpretarlas. Los seis booleanos se comparan con `"1"`: cualquier otro valor (`true`, `True`, `yes`, `on`) da False sin aviso, y entre ellos hay controles activos por defecto (`RATELIMIT_ENABLE`, `AXES_ENABLED`, `EMAIL_USE_TLS`, `DJANGO_SECURE_SSL_REDIRECT`). Las listas se parten por comas sin quitar espacios. El guard de producción interpreta el entorno por su cuenta, quitando espacios, así que aprueba valores que Django luego entiende de otra manera. Verificado en el contenedor: con `RATELIMIT_ENABLE=true AXES_ENABLED=true EMAIL_USE_TLS=true`, los tres quedan en False; con `DJANGO_ALLOWED_HOSTS="revista.cl, www.revista.cl"`, el segundo host queda como `" www.revista.cl"` y el guard no informa nada. La plantilla de producción trae valores de ejemplo del correo que no contienen los marcadores que busca el guard (TAR-7), y `entrypoint.sh` repite la convención 1/0 con dos variables más.

**Evidencia.**

- `backend/config/settings.py:15, 151, 156, 263, 273, 287` — los seis booleanos con `== "1"`.
- `backend/config/settings.py:22-32` — `split(",")` sin quitar espacios.
- `backend/config/settings.py:121, 139, 161, 231, 232, 274, 284, 290, 331` — nueve conversiones con `int()` o `float()`; con `EMAIL_PORT=` vacío salta un ValueError en la 284.
- `backend/config/envguard.py:31, 45-99` — los marcadores de plantilla y la validación con espacios ya quitados; nada del correo.
- `.env.prod.example:9-10, 92-97` — promete secretos vacíos pero trae `EMAIL_HOST_PASSWORD=secreto`.
- `backend/entrypoint.sh:6, 13` — `DJANGO_SKIP_MIGRATE` y `DJANGO_COLLECTSTATIC`.

**Por qué importa a futuro.** El dueño añade www separando con «, »: www responde 400 por `DisallowedHost` y el arranque no avisa. Un agente escribe en el `.env` `AXES_ENABLED=true` y `EMAIL_USE_TLS=true` «para asegurarse»: el login del panel pierde el bloqueo por fuerza bruta y el correo por el puerto 587 sale sin STARTTLS, sin ningún aviso.

**Recomendación.** Un módulo `config/env.py` con `env_bool` (acepta 1, 0, true, false, yes, no, on y off sin distinguir mayúsculas, y lanza `ImproperlyConfigured` nombrando la variable ante cualquier otro valor), `env_int` y `env_list` (sin espacios ni vacíos), usado en las 38 lecturas; o django-environ, si se acepta la dependencia. Que envguard reciba los valores ya interpretados por settings, para validar exactamente lo que usa Django. Dejar vacíos en `.env.prod.example` los valores del correo y comprobarlos en el guard. Una prueba parametrizada de `env_bool`.

**Matiz de la verificación.** HSTS no es una decisión irreversible tomada en el código: `DJANGO_HSTS_SECONDS` es configurable (con 0 no se emite la cabecera), el CI solo fija el valor por defecto, y `preload` no tiene efecto hasta que alguien envía el dominio a hstspreload.org. Lo único rígido es no poder mantener HSTS sin `includeSubDomains`, y eso es higiene. El ValueError de `EMAIL_PORT` se identifica por el traceback. El espacio en `CSRF_TRUSTED_ORIGINS` casi no tiene efecto (los POST del mismo sitio se validan contra el Host): el fallo efectivo está en `ALLOWED_HOSTS`. Lo del correo es operación, no seguridad.

#### OPE-7 · Redis tiene dos reglas de configuración: el broker se puede cambiar por entorno y la caché no; el CI ya corre con la caché apuntando a un host inexistente

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `settings.py` afirma que la URL de Redis «se deriva de REDIS_PASSWORD (única fuente)», pero `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` se pueden fijar por entorno y `CACHES.LOCATION` no: siempre se construye con `REDIS_HOST`, `REDIS_PORT` y `REDIS_PASSWORD`. El guard deja de exigir `REDIS_PASSWORD` en cuanto existe `CELERY_BROKER_URL`, aunque la caché siga dependiendo de esa contraseña, y la plantilla de desarrollo fija el broker explícitamente. El job prod-runtime del CI lo demuestra: fija el broker hacia su propio contenedor de Redis pero no `REDIS_HOST`, y la caché queda en `redis://redis:6379/2`, un nombre que no existe en esa red. Como la caché tolerante solo registra un WARNING y `/readyz/` solo mira el broker, todo sale en verde. Además, broker, resultados y caché comparten una instancia con `maxmemory 256mb` y `noeviction` y un comentario que dice que «No se usa como caché» (RES-5).

**Evidencia.**

- `backend/config/settings.py:203-211, 238-257` — la «única fuente» que no lo es; la caché solo sale de `_REDIS_BASE`; `RATELIMIT_FAIL_OPEN = False`.
- `backend/config/envguard.py:66-79` y `backend/tests/test_envguard.py:73-77` — el guard y su prueba aceptan `REDIS_PASSWORD` vacío con un broker externo.
- `.env.example:18-22` — el broker fijado a mano en desarrollo.
- `.github/workflows/ci.yml:270-287, 299-302` — el entorno de prod-runtime; medido: con ese entorno, la caché queda en `redis://redis:6379/2`.
- `backend/config/cache.py:36-74` — medido: con el host inalcanzable, `is_ratelimited` da True desde la primera petición.
- `backend/apps/content/views.py:492-520` y `docker-compose.yml:22-26` — `/readyz/` sin la caché, y el comentario falso.

**Por qué importa a futuro.** Siguiendo al guard y a su prueba, alguien mueve Celery a un Redis gestionado (`CELERY_BROKER_URL=redis://user:pw@ext:6379/0`) y retira del compose el servicio redis. La caché sigue apuntando a `redis:6379`, django-ratelimit limita a todo el mundo, y el boletín, los envíos y el buscador responden «espera un momento», mientras `/readyz/` sigue en 200.

**Recomendación.** Una sola variable base (por ejemplo `REDIS_URL`, o la derivación actual) de la que salgan las tres URL, con la misma regla de sobrescritura para todas; si se quiere un broker separado, exigir también una `CACHE_URL` explícita. Que el guard compruebe las URL efectivas (credenciales presentes en las tres) y que `/readyz/` incluya la caché. Corregir el comentario del compose. Poner `CELERY_TASK_IGNORE_RESULT = True`, porque ninguna vista lee resultados. Si la caché crece, separarla en otra instancia con `allkeys-lru` (RES-5).

**Matiz de la verificación.** Los resultados de Celery no se acumulan (caducan al día, unas 1.440 claves pequeñas) y las claves de color pesan unos bytes: llenar 256 MB es improbable y esa parte es higiene. Que el CI salga en verde se debe sobre todo a que ningún paso usa la caché, no solo a que se traguen los errores. Con `docker-compose.prod.yml` tal cual, la configuración que el guard acepta ni siquiera arranca, porque el compose exige `REDIS_PASSWORD`: el escenario exige retirar el Redis local, que es lo que haría una migración a un Redis gestionado.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «CACHES → Redis (db 2) en prod, LocMem en dev/tests» (decisión relacionada). Como la suite usa LocMem, no se nota que en el CI la caché de producción apunte a un host inexistente. La decisión sigue siendo razonable, pero el broker y la caché deberían derivarse de la misma variable.

#### OPE-8 · Hechos operativos duplicados sin nada que los mantenga iguales: documentación, comentarios y versiones de herramientas que ya divergen del código

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Muchos datos de operación están escritos en dos o más sitios y ninguna prueba los ata. En tres meses y medio ya divergieron:

- Documentación: estáticos «por WhiteNoise» (los sirve Caddy); un procedimiento de restauración en producción que dice que «el migrate del arranque queda como no-op», cuando en producción nadie migra al arrancar; `infra/nginx/`, que no existe; y una recuperación total que pide copiar `BACKUP_DIR` sin mencionar restic.
- Comentarios: Redis «No se usa como caché»; beat «dispara publish_due_articles» (la tarea es `publish_due_items`); el Caddyfile dice que gunicorn corre con workers sync (son gthread); `redaction.py` presenta como residuo el log de acceso de gunicorn, ya retirado.
- Herramientas: pre-commit fija ruff v0.16.0 «igual que el lockfile», que tiene la 0.17.1; el comando de CONTRIBUTING para regenerar los lockfiles usa `python -m piptools`, que no está instalado en la imagen; `pip install --upgrade pip` va sin versión en el Dockerfile y en el CI; Python 3.12 aparece en el Dockerfile y dos veces en el CI sin nada que los iguale; y el `.dockerignore` de la raíz no lo usa ningún build.
- Hay unas 50 referencias a identificadores externos (S-xx, sec-n, «hallazgo») en config e infraestructura.
- De cara a Django 6, dos dependencias de internos: django-ratelimit 4.1.0, que sostiene la política de `config/cache.py`, y `config/staticfiles.py`, que usa internos de `ManifestFilesMixin`.

**Evidencia.**

- `README.md:34, 180-181, 183-187` — `infra/nginx/`, WhiteNoise y un redespliegue sin `setup_groups`.
- `docs/respaldos.md:62-82, 104-105` — el «migrate del arranque» y la recuperación sin restic.
- `infra/caddy/Caddyfile:4-8, 27, 60-74, 92` — «workers de tipo sync», la regex del token dos veces y los estáticos servidos por Caddy.
- `docker-compose.prod.yml:36-39, 127-128, 142-144` y `docker-compose.yml:24-25, 63` — sin `--access-logfile`; «estáticos vía WhiteNoise» frente al montaje en el proxy; la tarea mal nombrada.
- `.pre-commit-config.yaml:14-17` frente a `backend/requirements-dev.txt:424`, y `CONTRIBUTING.md:50-53, 67-68`.
- `backend/Dockerfile:7, 13` y `.github/workflows/ci.yml:55, 61, 239, 246` — Python y pip.
- `.dockerignore:1-13` — todos los builds usan como contexto `./backend` o `./infra/backup`.

**Por qué importa a futuro.** Un agente despliega una migración nueva. Esa noche se pierde el disco y el dueño sigue `docs/respaldos.md`: restaura el respaldo de la madrugada, anterior a la migración, y hace `docker compose up -d`. Como en producción el migrate del arranque está desactivado, el esquema queda por detrás del código; las vistas que leen la columna nueva dan 500 y `/readyz/` sigue en verde. En otro caso, alguien renombra `novedades/` a `boletin/`: ninguna prueba falla, y tanto el filtro de Django como los logs de Caddy vuelven a escribir los tokens de baja en claro.

**Recomendación.** Cada hecho en una sola fuente, y el resto atado con pruebas baratas:

- El hook de ruff como `repo: local` con `entry: ruff`, para que use la versión del lockfile, o el ecosistema de pre-commit en Dependabot.
- pip-tools fijado en `requirements-dev.in`, o documentar `uv pip compile`; `pip==26.2.1` fijado en el Dockerfile y en el CI.
- Un `.python-version` que lea setup-python (`python-version-file`), con una prueba que compare su versión menor con el `FROM` del Dockerfile.
- Una prueba que lea el Caddyfile y compruebe que la regex de redacción cubre las rutas de `community/urls.py`.

Corregir los textos enumerados, empezando por el procedimiento de restauración de `docs/respaldos.md`, cambiar cada identificador externo por su razón técnica en una frase y borrar el `.dockerignore` de la raíz. Antes de subir de versión a Django 6, decidir cómo sustituir django-ratelimit.

**Matiz de la verificación.** `README.md:121` está en la sección de desarrollo y ahí es cierta: lo engañoso de verdad es `docs/respaldos.md:81-82`, que forma parte de un procedimiento de producción. `respaldos.md:104-105` vale si `BACKUP_DIR` es un montaje externo; lo que falta es documentar la restauración con restic. «Única fuente» y «sync» fueron inexactos desde que se escribieron. Las 50 referencias son coincidencias en 34 líneas, los documentos a los que remiten siguen en HEAD (su borrado solo está preparado) y casi todos esos comentarios ya explican la razón técnica: es baja. No está demostrado que pre-commit haga fallar el CI, porque no está instalado. django-ratelimit tiene una prueba de comportamiento que lo protege y el proyecto se mantiene en Django 5.2 LTS.

### 4.8 Calidad y estrategia de la suite de pruebas (PRU)

#### PRU-1 · Flujo editorial y visibilidad: cinco de las nueve transiciones no se ejecutan nunca y lo oculto solo se prueba con borradores

**Severidad:** alta · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `workflow.TRANSITIONS` define nueve transiciones y las pruebas ejecutan cuatro (submit, accept, publish y schedule). request_changes, reject, unpublish, archive y restore no se ejecutan en ninguna prueba: `test_admin` solo comprueba que las acciones existan con `callable()`. Los estados ARCHIVED y REJECTED no aparecen en ninguna prueba de piezas. Todas las pruebas de «no se ve» usan DRAFT (el valor por defecto de las fábricas) o `published=False`: ninguna comprueba que una pieza en revisión, aprobada, programada o archivada quede fuera de las vistas públicas, aunque el filtro está copiado unas 28 veces en 8 módulos públicos (AGE-1). En el sitemap hay siete secciones con filtro y solo la de artículos tiene una prueba de exclusión; las demás solo se prueban con «no lanza». El feed de podcast no tiene ninguna prueba con un audio no publicado. La cobertura no lo detecta: la línea del filtro se ejecuta aunque nadie compruebe lo que devuelve. Tampoco hay ninguna regla escrita, ni prueba, sobre la visibilidad de Work, Publisher y BookAuthor (WEB-1).

**Evidencia.**

- `backend/apps/content/workflow.py:19-29, 76-78` — la tabla de nueve transiciones; `published_at` se asigna al publicar si está vacío y nunca se borra.
- `backend/tests/test_workflow.py:15-138` — `perform_transition` solo se llama con submit, publish, accept y schedule.
- `backend/tests/test_admin.py:74-88` — `test_all_transition_actions_registered` solo afirma `callable(...)`.
- `backend/tests/test_admin_acciones_por_rol.py:21-30, 60-110` — prueba qué acciones ofrece cada rol y solo ejecuta «accept», que se rechaza para la autora.
- `backend/apps/content/sitemaps.py:74-134, 164-178` y `backend/tests/test_discovery.py:35-41, 58-70` — solo el borrador de artículo se prueba fuera del sitemap.
- `backend/apps/media/feeds.py:77-80` y `backend/tests/test_recordings.py:165-181` — el feed de podcast solo se prueba con registros publicados.
- `grep -rnE 'ARCHIVED|REJECTED' backend/tests/` no encuentra nada fuera de Submission.

**Por qué importa a futuro.** Con unas 28 copias del filtro, el refactor probable es centralizarlo en un manager (AGE-1). Si se hace con `exclude(status=DRAFT)` o con `published_at__lte=now()`, lo archivado y lo despublicado (que conservan `published_at`) y lo aprobado con fecha vuelven a la portada, la búsqueda, el RSS y el sitemap, con toda la suite en verde. Y lo que ya llegó a un feed o a un buscador no se puede retirar.

**Recomendación.**

1. Una prueba parametrizada sobre `TRANSITIONS`: para cada transición, origen válido → destino, un rol permitido y uno denegado, y la entrada en la bitácora. Son unas 20 líneas que siguen solas a la tabla.
2. Una matriz de visibilidad parametrizada para Article y Poem: cada estado no público (DRAFT, IN_REVIEW, CHANGES_REQUESTED, APPROVED, SCHEDULED con fecha futura, ARCHIVED, REJECTED) contra cada superficie (portada, índices, ficha con 404, búsqueda, RSS, sitemap, ficha de integrante, colección, reseñas de obra o editorial), con un control publicado en la misma prueba.
3. Lo mismo con `published=False` para eventos, registros (incluido el feed de podcast), publicaciones y páginas.
4. Decidir y fijar con una prueba la regla de visibilidad de Work, Publisher y BookAuthor.

Esta matriz es un requisito previo de AGE-1: primero se escribe y después se centraliza el filtro.

**Matiz de la verificación.** Las cinco transiciones sin prueba pasan por el mismo `perform_transition` genérico que sí está probado: lo que falta es una prueba de especificación de la tabla y de las envolturas del admin, no cubrir código nuevo. La matriz de estados solo hace falta en Article y Poem, porque `PublishStatus` es binario. Las fichas de eventos, publicaciones y registros sí tienen pruebas de 404 con `published=False`, así que si cayera un filtro del sitemap solo se filtrarían URL. El hueco con exposición real es el feed de podcast: sin su filtro, expondría el título, la descripción y el archivo de un audio no publicado. El recuento de copias del filtro varía según qué se cuente (28 en 8 módulos públicos; el grep da 30 líneas al incluir la tarea y las siembras). Un verificador habría bajado la severidad a media; el panel la mantuvo en alta por mayoría.

#### PRU-2 · Casi una de cada cuatro pruebas lee el texto de site.css, de los guiones o de las plantillas en vez de probar lo que se ve

**Severidad:** media · **Esfuerzo:** L · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** 148 de las 757 funciones de prueba (236 de los 985 casos recolectados, el 24 %) abren `site.css`, los `.js` o las plantillas y buscan cadenas en el texto. Unas 100 son instantáneas de valores literales: `"padding-block:11px"`, `"--asomo:112px"`, `"translate:calc(66px+var(--x))var(--y)"`, `"const DESLIZA = 800;"`, `"ir(actual + (dx < 0 ? 1 : -1))"`. Lo literal no garantiza el requisito ni es necesario para cumplirlo: `test_los_enlaces_de_la_barra_se_pulsan_en_44_px` exige `"padding-block:11px"`, pero los 44 px dependen también del tamaño de letra y de la interlínea; bajar uno de esos dos valores deja la prueba en verde con otro alto, y poner 12 px, que cumple el requisito, la pone en rojo. Ninguna prueba ejecuta JavaScript: ni el CI ni pre-commit corren node, ESLint o Playwright; `embeds.js` no tiene ninguna prueba y los otros seis guiones solo tienen búsquedas de texto. Hay también unas cinco «lápidas», pruebas que prohíben para siempre nombres de diseños retirados (`cinta`, `tirada-flecha`, `hero-stats`…), alguna atada a la redacción de un comentario: `"cinta" not in SITE_CSS.replace("reemplazó a la cinta", "")`. Cada decisión de diseño nueva añadió otro archivo de este tipo.

**Evidencia.**

- `backend/tests/test_css_sistema.py:51-56, 771-775, 822-864, 1107-1112, 1163-1179` — `_regla` devuelve la primera coincidencia; aserciones literales de píxeles, grados y curvas.
- `backend/tests/test_estante.py:108-121, 188-221` y `backend/tests/test_tirada.py:168-187, 244` — reglas copiadas con sus espacios, constantes y expresiones de JS, una lápida.
- `backend/tests/test_integrantes_portada.py:103-159` y `backend/tests/test_cabecera_capsula.py:48-66` — bloques comparados con su sangría y selectores exactos.
- `.github/workflows/ci.yml:101` y `.pre-commit-config.yaml:4-28` — ningún paso de JavaScript.
- `backend/static/js/embeds.js:1-35` — sin prueba; la garantía de privacidad (ningún iframe de entrada) sí está cubierta en el servidor por `backend/tests/test_embed_consent.py:49-97`.

De las 148 funciones, unas 60 de `test_css_sistema` afirman declaraciones de un selector concreto y unas 39 de nueve archivos de funcionalidad también son literales; unas 49 son invariantes de la hoja completa o listas de excepciones, y esas conviene conservarlas.

**Por qué importa a futuro.** El próximo ajuste visual pone en rojo decenas de pruebas sin que cambie nada en pantalla (unir los siete bloques `@media (min-width:900px)`, reformatear la hoja, renombrar una variable de un guion), y el agente las «arregla» copiando el valor nuevo. Al revés, una regresión real no pone nada en rojo: un enlace que vuelve a medir 23 px por otra causa, o un guion que lanza una excepción al montarse.

**Recomendación.** Tres niveles:

1. Conservar y ampliar las invariantes de hoja completa (mínimo de 12 px, solo tokens de escala, transiciones con tokens, contraste calculado, listas de excepciones) y las comprobaciones cruzadas entre CSS y plantillas, sobre la hoja parseada (PRU-6).
2. Borrar las instantáneas de valores concretos y las lápidas a medida que se toque cada zona, y sustituirlas por mediciones en navegador. Lo prioritario y barato: `node --check` de los ocho guiones en el CI y en pre-commit (y un ESLint mínimo después), y un job con el playwright-core 1.64 que ya trae `tools/ux/`: de 10 a 15 comprobaciones a 951 y 375 px que fallen ante cualquier error de página (enlaces de la barra de 44 px o más, sin desbordamiento horizontal, el iframe aparece solo tras pulsar, el estante cambia de libro con el teclado, la tirada responde).
3. Una regla escrita: una prueba nueva solo lee `.css` o `.js` para afirmar una invariante.

**Matiz de la verificación.** Severidad de alta a media: es deuda que encarece el cambio y deja el JS sin ejecutar, y lo peor que puede pasar es un componente de la portada roto a la vista. La cifra de que 53 de los 79 commits que tocan `site.css` editan también una prueba que la lee no prueba que las pruebas se reescriban con el código: solo entre 22 y 30 de esos commits reescriben o borran aserciones existentes; los demás añaden pruebas nuevas, que es lo normal. Un formateador que solo toque espacios rompe las búsquedas en bruto y los cortes por texto, no las aserciones hechas con `_regla`, que normalizan espacios. Se retiraron dos evidencias: un fallo de `registros.js` que vino de la caché del navegador (ninguna prueba lo habría visto) y la UNION de la búsqueda frente al techo de consultas, que es una optimización legítima.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, #33 (accesibilidad y rendimiento automatizados: pa11y o axe, Lighthouse, k6), y §1 (UX), D31 y D34 (decisión relacionada). Sin navegador en el CI, las garantías visuales se escribieron como búsquedas de texto, y algunas decisiones lo piden así (D34). El diferido explica las pruebas estructurales, no las instantáneas de valores; `tools/ux/` ya mide en navegador y podría acoger parte de ellas. Conviene reabrir #33 al menos para la prueba de humo.

#### PRU-3 · Tareas programadas, limpieza de archivos y listas de rutas cableadas por texto, sin meta-pruebas

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Varias garantías dependen de que alguien se acuerde de registrar algo, y ninguna prueba lo deriva del código:

- (a) `CELERY_BEAT_SCHEDULE` nombra las tareas con su ruta en texto (`apps.content.tasks.publish_due_items`, `apps.submissions.tasks.purge_stale_pii`) y ninguna prueba resuelve esos nombres contra las tareas registradas: las pruebas llaman a las funciones directamente.
- (b) La limpieza de archivos se registra a mano, y nada recorre los FileField del proyecto para exigirla (TAR-5).
- (c) No hay una clasificación de las rutas públicas: la revisión del HTML renderizado usa una lista de 15 rutas escrita a mano, sin ninguna ficha y sin `submit_thanks`.
- (d) `test_envguard` copia a mano los entornos con `DEBUG=0` de `ci.yml` y no incluye el del paso `check --deploy`.

**Evidencia.**

- `backend/config/settings.py:213-222` — los nombres de las tareas, como texto.
- `backend/config/celery.py:7-9` — `autodiscover_tasks()` es perezoso: en el contenedor, `app.tasks` no tiene ninguna tarea de `apps.*` hasta llamar a `app.loader.import_default_modules()`.
- `backend/apps/content/tasks.py:6-47` — el nombre sale de la ruta del módulo, y moverla a `workflow.py` es un cambio plausible (ARQ-2).
- `.github/workflows/ci.yml:310-317` — prod-runtime solo comprueba el ping del worker y la fecha del archivo de agenda de beat.
- `backend/apps/media/filecleanup.py:76-91`, `backend/conftest.py:19-29` y `backend/tests/test_file_lifecycle.py:99-154` — los `dispatch_uid`, el único recorrido de FileField (para el almacén privado) y las pruebas, sin Publication ni SiteProfile.
- `backend/tests/test_template_hygiene.py:35-48, 51-75` — el fuente se revisa entero; el HTML renderizado, con 15 rutas a mano.

**Por qué importa a futuro.** Un agente traslada `publish_due_items` a `workflow.py` para reutilizar `perform_transition`. beat sigue enviando cada minuto `apps.content.tasks.publish_due_items`, el worker lo descarta como tarea no registrada y, sin `SENTRY_DSN`, nadie se entera: los artículos programados no salen nunca. Si el movido es `purge_stale_pii`, los datos personales se quedan en la base y en los respaldos más allá del plazo que promete la política. Las pruebas de las tareas siguen en verde porque importan la función.

**Recomendación.** Tres metapruebas baratas:

1. Para cada entrada de `settings.CELERY_BEAT_SCHEDULE`, afirmar `entry["task"] in app.tasks`, forzando antes el descubrimiento (`app.loader.import_default_modules()` o `autodiscover_tasks(force=True)`); si no, el resultado depende del orden de importación.
2. Para cada FileField de `apps.get_models()`, exigir un receptor `post_delete` con `dispatch_uid` `filecleanup:delete:<modelo>:<campo>` y validadores de subida, con una lista explícita de excepciones.
3. Una prueba de clasificación: toda ruta pública con nombre (de `get_resolver()`) está en una categoría (índice, ficha, utilidad o excluida), y una ruta nueva sin clasificar hace fallar la prueba.

Para la copia de los entornos del CI, añadir el que falta o quitarla: leer el YAML exigiría PyYAML, que no está instalado.

**Matiz de la verificación.** Las listas de rutas de las pruebas tienen propósitos distintos y deliberados (la barra se fija a propósito como decisión de diseño, el presupuesto de consultas cubre las vistas calientes): sacarlas de `get_resolver()` no tendría sentido; lo útil es la prueba de clasificación. De las 24 rutas sin argumentos, 7 no son HTML y una solo acepta POST; la revisión renderizada cubre 15 de las 16 páginas HTML restantes, y la revisión del fuente cubre todas las plantillas, así que el riesgo de restos de plantilla está casi neutralizado.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-23, «test de DST + higiene de beat» (decisión relacionada). qa-23 dio por cubierta la higiene de beat con ignorar en git su archivo de agenda, sin contemplar que el schedule nombra las tareas por texto. Prescindir de freezegun sigue siendo razonable, y esta metaprueba no depende de esa decisión.

#### PRU-4 · Los permisos por rol se prueban llamando a métodos del admin, nunca por HTTP, y el usuario con rol se fabrica de tres maneras

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Las pruebas de rol llaman a `has_change_permission`, `get_actions` o `get_queryset` del ModelAdmin con RequestFactory. Ninguna entra al panel por HTTP como autor o como editor: ni el listado, ni la ficha, ni el POST de una acción, ni un POST de la ficha con `status` en el cuerpo. El usuario con rol se fabrica de tres formas. El fixture `groups` ejecuta `setup_groups`, porque, según su docstring, los grupos vacíos «no se dan en ningún despliegue»; pero dos ayudantes `_usuario` locales crean el grupo vacío con `get_or_create`, y así la «editora» de `test_la_editora_conserva_las_nueve` no tiene ningún permiso de modelo. Ninguna prueba fija la matriz de permisos: nada impide dar al autor permiso de ver los envíos o los suscriptores, que guardan datos personales. El único `force_login` con rol es el de la descarga de adjuntos. Y hay un hueco que hoy fallaría: las acciones `do_*` no declaran `allowed_permissions`, y `perform_transition` no mira los permisos de modelo (DOM-2).

**Evidencia.**

- `backend/tests/test_admin.py:12-24` — los métodos del admin se llaman directamente.
- `backend/tests/test_admin_acciones_por_rol.py:37-40, 59-61` y `backend/tests/test_admin_hardening.py:25-34, 72-79` — dos copias de `_usuario`; en la segunda, el grupo vacío es deliberado.
- `backend/conftest.py:67-93` — los fixtures `groups`, `editor` y `autor`.
- `backend/apps/people/management/commands/setup_groups.py:9-29` — `EDITOR_APPS` y `AUTHOR_PERMS`, sin ninguna prueba que los fije.
- `backend/tests/test_views.py:90-111` — los únicos `force_login(autor)` y `force_login(editor)` (líneas 105 y 108).
- `backend/apps/content/admin.py:125-135, 140-164, 179-191, 202-248` y `backend/apps/content/workflow.py:32-37, 49-57` — acciones sin `allowed_permissions`; la transición solo mira el grupo y el dueño.
- `backend/apps/submissions/admin.py:19-35` — sin `has_*_permission` propios: con `view_submission`, un autor vería nombre, correo y texto de cada envío.

**Por qué importa a futuro.** Tras un incidente, el dueño quita `content.change_article` al grupo editor para dejarlo en solo lectura, confiando en el comentario del admin. Una editora entra al listado (le basta `view_article`), marca un artículo aprobado, elige «Publicar» y envía el POST: el artículo queda publicado y la bitácora lo registra. No falla ninguna prueba: no hay pruebas HTTP del panel con roles, y la prueba de acciones afirma precisamente que una editora sin permisos de modelo conserva las nueve.

**Recomendación.** Usar solo los fixtures `groups`, `autor` y `editor`: borrar los `_usuario`, o hacer que deleguen en `setup_groups` y quiten permisos de forma explícita donde la prueba lo necesite. Añadir unas siete pruebas HTTP con `client.force_login`:

- El listado de artículos de un autor solo muestra los suyos.
- El POST de la ficha de un artículo publicado da 403. (Con GET, el autor la ve en solo lectura y recibe 200, porque tiene `view_article`.)
- Un POST de la ficha con `status=published` no cambia el estado, y un POST con `action=do_publish` no publica.
- `/admin/submissions/submission/` y `/admin/community/newslettersubscriber/` dan 403 al autor.
- Una editora sin `change_article` que envía `action=do_publish` no publica. Hoy fallaría: hay que añadir `allowed_permissions=("change",)` a las acciones o comprobar `has_change_permission` en `_run`, y entonces `test_la_editora_conserva_las_nueve` pasará a usar el fixture.

Para la matriz, afirmar invariantes y no una igualdad exacta, que sería un detector de cambios: el grupo autor no tiene ningún permiso de submissions, community ni auth, ni ningún `delete_*`.

#### PRU-5 · Migraciones de datos sin pruebas, y un fixture atado a sus nombres de archivo

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Hay cinco migraciones RunPython: content 0004 (copia `article_id` al enlace genérico de transiciones y notas), content 0007 y 0010 (siembran y actualizan las páginas legales), community 0003 y showcase 0004. Ninguna prueba ejecuta la ida y la vuelta de 0004, de community 0003 ni de showcase 0004 sobre datos: no hay MigrationExecutor ni django-test-migrations. El CI solo hace `migrate`, `migrate content 0008` y `migrate` otra vez, sobre una base que solo tiene lo que siembran las propias migraciones: detecta migraciones que lanzan, no datos mal transformados, y nunca revierte hasta 0004. La ida de 0007 y 0010 sí se ejecuta al crear la base de pruebas, y `test_newsletter.py` afirma su resultado. El fixture `legal_pages` importa `apps.content.migrations.0007_legal_pages` y `0010_privacy_ley_21719` por su nombre de archivo y las ejecuta con el registro de modelos actual, no con el histórico.

**Evidencia.**

- `backend/apps/content/migrations/0004_editorial_generic_data.py:5-22, 32-34` — ida y vuelta sin ninguna prueba con filas.
- `backend/conftest.py:96-110` — `importlib.import_module(...)` y la llamada con los modelos actuales y `schema_editor=None`.
- `.github/workflows/ci.yml:86-95, 385-395` — la reversión solo llega a content 0008; el job de respaldo solo exige que haya alguna página.
- `backend/tests/test_newsletter.py:172-192` — afirma el resultado de la ida de 0007 y 0010.
- `backend/apps/community/migrations/0003_newslettersubscriber_confirm_token_and_more.py:14-23, 48` — nunca se ejecuta con filas; la vuelta es un `pass`.
- `backend/apps/showcase/migrations/0004_ensure_siteprofile_singleton.py:4-12` y `backend/pytest.ini:6` — la base de pruebas se construye ejecutando todas las migraciones hacia adelante.

**Por qué importa a futuro.** Un agente repite el patrón de 0003 a 0005 para mover datos entre modelos: una migración añade el campo nuevo, otra lo rellena y la última borra el viejo. La copia filtra mal (omite las filas con NULL, por ejemplo). En el CI no hay filas, la copia afecta a cero y todo pasa; en el VPS, el tercer paso elimina la columna original y las filas no copiadas pierden el dato, que solo se recupera desde un respaldo. Si escribe una prueba al estilo de `legal_pages`, esta corre con los modelos actuales y no prueba nada.

**Recomendación.** Adoptar django-test-migrations, o un helper con MigrationExecutor, y exigir una prueba por cada RunPython nuevo: migrar a la anterior, crear filas con los modelos históricos, migrar hacia adelante y afirmar el resultado, y también la vuelta si existe. Para las páginas legales, sacar el contenido a una función de la app (por ejemplo `apps/content/legal.py`) que usen tanto la migración como el fixture.

**Matiz de la verificación.** No es cierto que ninguna prueba ejecute la ida sobre datos: la de 0007 y 0010 sí. Aplastar las migraciones solo rompería el fixture al borrar los archivos reemplazados, y lo haría de forma ruidosa (ModuleNotFoundError); con 39 migraciones no es urgente. La severidad media se justifica por las futuras migraciones de datos en varios pasos, no por las cinco actuales.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «serialized_rollback descartado», y el bloque de CI «test» (decisión relacionada). El fixture atado a los nombres de archivo fue la solución elegida a conciencia, y la reversibilidad que comprueba el CI es de esquema, no de datos. Sigue siendo razonable, pero deja sin probar lo que esos RunPython hacen con filas reales.

#### PRU-6 · Seis analizadores de CSS caseros, cada uno con una semántica distinta

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Cada archivo trae su propio analizador de CSS hecho con expresiones regulares: `_reglas` en `test_css_sistema`, `test_cabecera_capsula` y `test_contraste_paleta`; `_bloque` en dos versiones (una corta desde la cabecera, la otra desde la primera llave); y, dentro de `test_css_sistema`, `_bloque`, `_pantalla` e `_impresion` repiten tres veces el mismo recorrido de llaves. Unos quitan comentarios y espacios; otros (`test_estante`, `test_tirada`, `test_portada`, `test_integrantes_portada`, `test_ui_ux`, `test_security_csp`) buscan en el texto crudo: unas 46 aserciones literales sobre la hoja cruda, 30 de ellas con espacios exactos, como `".estante{display:grid; grid-template-columns:auto minmax(0, 1fr);"`. `_regla` toma «la PRIMERA regla con ese selector» porque supone que es la de pantalla, una convención que nada impone. 21 anclas dependen de la sangría (`"@media (min-width:900px){\n  .pub-grid"`). Cuatro pruebas recortan `css[css.index("@media …"):]` hasta el final del archivo, así que una regla puede salir de su `@media` y la aserción sigue pasando. `test_portada` se ancla en un comentario, `test_integrantes_portada` borra un comentario antes de afirmar y `test_nav_css` toma el primero de los siete bloques `@media (min-width:900px)` de la hoja.

**Evidencia.**

- `backend/tests/test_css_sistema.py:15-25, 51-56, 323-332, 604-617, 710-718` — `_css`, `_reglas`, `_regla` y las tres copias del recorrido de llaves.
- `backend/tests/test_cabecera_capsula.py:17, 22-38, 71-78` y `backend/tests/test_contraste_paleta.py:142-145` — otros dos `_reglas`, con comentarios o sin normalizar.
- `backend/tests/test_nav_css.py:24-29, 55-59` frente a `backend/static/css/site.css:375, 990, 1111, 1134, 1172, 1269, 1698` — el primero de siete bloques.
- `backend/tests/test_estante.py:214-221`, `backend/tests/test_tirada.py:236-243`, `backend/tests/test_portada.py:183-184, 194-195` y `backend/tests/test_integrantes_portada.py:103-108, 158` — cortes hasta el final del archivo, anclas en la sangría y en comentarios.
- `backend/tests/test_buscador_en_la_barra.py:47-55` — otro analizador, que incluye las cabeceras `@`.

**Por qué importa a futuro.** Al reordenar la sección de integrantes, un agente deja `.integrantes-retratos > li:nth-child(n+4){display:none}` después del cierre del `@media (max-width:719px)`. En escritorio desaparecen los retratos 4 y 5, y `test_cinco_en_la_fila_y_tres_en_el_telefono` sigue en verde (simulado en memoria). Al revés, formatear la hoja con un espacio antes de «{» no cambia nada en pantalla y rompe decenas de aserciones sobre el texto crudo, mientras las basadas en `_reglas` pasan: cada archivo interpreta la hoja a su manera.

**Recomendación.** Para las pruebas de hoja que se conserven (las invariantes de PRU-2), un único helper en `tests/css.py` o en conftest, basado en un analizador real (tinycss2, en Python puro), que devuelva cada regla con su contexto de `@media`, `@supports` o `@container`. Buscar por contexto y selector, nunca por posición ni sobre el texto crudo, y no anclar en comentarios. Borrar las copias locales.

**Matiz de la verificación.** Las cifras se precisan: el grep de anclas con salto y sangría da 31 líneas, de las que 21 son de CSS (las otras son cuerpos de poema), y las aserciones literales sobre la hoja cruda son unas 46. En las pruebas que cortan hasta el final, el ancla fija la primera regla del bloque; son las demás reglas afirmadas las que pueden salir del `@media` sin que la prueba falle.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, #33 (decisión relacionada). Los analizadores caseros son otra consecuencia de no tener navegador en el CI, pero el diferido no los justifica: se puede adoptar un único helper con un analizador real sin resolver #33.

#### PRU-7 · La suite está organizada por decisiones y lotes: un mismo comportamiento en muchos archivos, pruebas duplicadas y comentarios que ya no dicen la verdad

**Severidad:** media · **Esfuerzo:** L · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Los 83 archivos `test_*.py` siguen la historia del trabajo, no la estructura del código: `test_tirada` es D19, `test_estante` es D24, `test_cabecera_capsula` es «la opción C del tablero» y `test_ia` es «Lote H». La portada, que es una sola vista, tiene siete archivos dedicados y pruebas en diecinueve, y los docstrings remiten de un archivo a otro («el aspecto está en test_css_sistema.py», «la hoja, en test_titular.py»). Hay duplicados escritos en sesiones distintas: la regla del comentario `{# #}` de una sola línea (en `test_template_hygiene` y `test_security_csp`, con implementaciones distintas), el saneo al guardar (`test_models` y `test_sanitize_hardening`), el orden de los bloques de la portada (`test_home_ui` y `test_portada`) y el honeypot del boletín (`test_ia`, `test_newsletter` y `test_newsletter_consent`). Entre 45 y 49 de los 69 docstrings de módulo, y 64 de los 346 docstrings de prueba, citan códigos que solo explican documentos externos (D19, «ticket 2.3», S-05, «hallazgo #12», «paso 13», «Lote H», «el tablero»), y las numeraciones chocan: «S-20» designa la composición de permisos por rol en `conftest.py:74` y la redacción de tokens en `test_pii_retention.py:7`. Hay comentarios caducos, y los nombres mezclan inglés y castellano.

**Evidencia.**

- `backend/tests/test_portada_obra.py:1-7` — un docstring que reparte la vista entre archivos.
- `backend/tests/test_template_hygiene.py:35-48` frente a `backend/tests/test_security_csp.py:157-169` — la misma regla, dos implementaciones.
- `backend/tests/test_models.py:29-33` frente a `backend/tests/test_sanitize_hardening.py:95-104`.
- `backend/tests/test_home_ui.py:84-91` frente a `backend/tests/test_portada.py:65-79`.
- `backend/tests/test_newsletter_consent.py:149-159`, `test_ia.py:91-93` y `test_newsletter.py:81-85` — el honeypot, tres veces y en dos idiomas.
- `backend/conftest.py:67-75` frente a `backend/tests/test_pii_retention.py:1-9` — el choque de «S-20».
- `backend/tests/test_security_uploads.py:27-35` — dice que construir un URLField rompe la suite por un aviso que ya se resolvió; y el docstring de `test_portada` sigue describiendo «12 voces».

**Por qué importa a futuro.** El próximo agente que cambie la portada no sabe qué archivos tocar y crea uno nuevo, como se hizo 26 veces en octubre en toda la suite. Las pruebas duplicadas divergen: si alguien relaja el honeypot en un archivo, los otros dos siguen exigiendo el comportamiento anterior. Y cuando se confirme el borrado de los documentos externos, «S-20» en `conftest.py:74` no explicará nada.

**Recomendación.** Reorganizar por módulo y comportamiento, por ejemplo `tests/content/test_portada.py`, `tests/content/test_flujo_editorial.py`, `tests/content/test_visibilidad.py`, `tests/community/test_boletin.py` y `tests/ui/test_hoja_invariantes.py`. Fusionar los duplicados. Reescribir los docstrings como la regla vigente («la barra lleva cinco enlaces»), sin historia ni códigos. Hacerlo por app, en PR pequeños, comparando `pytest --co -q` antes y después para no perder pruebas. Un detalle técnico: `backend/tests` no tiene `__init__.py` y `pytest.ini` no fija `--import-mode`, así que repartir en subcarpetas con nombres repetidos da «import file mismatch»; hay que añadir `__init__.py` en cada subcarpeta (conservando `import tests.factories`) o usar `--import-mode=importlib`.

**Matiz de la verificación.** Son 83 archivos `test_*.py`, no 95, y la portada tiene siete archivos dedicados, no «diez o más»; de los 26 archivos creados en octubre, unos 8 son de la portada. El riesgo de que «nadie se atreva a borrar una prueba» está exagerado: solo 5 de los 64 docstrings con códigos se quedan casi vacíos al quitarlos, y los demás enuncian la regla con palabras. El coste real es ruido, historia que se pudre y choques de numeración.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D22 a D24 y D31 a D34, cuyas filas remiten cada una a su archivo de pruebas (decisión relacionada). Atar cada decisión a un archivo alentó organizar la suite por decisión. El registro sigue siendo útil; reorganizar por componente solo obliga a actualizar esas referencias.

#### PRU-8 · Aserciones que pasarían aunque el defecto estuviera presente

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Hay pruebas cuyo nombre promete algo que la aserción no comprueba:

1. `test_el_envio_de_propuestas_no_da_500_con_redis_caido` hace un GET al formulario, pero el límite de envío solo actúa en POST: nunca toca Redis.
2. `test_consulta_desmesurada_se_trunca` y `test_la_consulta_se_recorta_a_la_longitud_maxima` solo afirman el código 200; la segunda siembra «Umbral» y no comprueba que aparezca.
3. El presupuesto de consultas de la portada (24, «medido 16») se mide con publicaciones sin tapa ni editorial: quitar el `select_related("cover", "publisher")` del estante no cambia el número de esa prueba.
4. `test_subscribe_same_email_stays_unique_under_concurrency` prueba el `get_or_create` de Django (el UNIQUE del correo), no la vista de alta.

**Evidencia.**

- `backend/tests/test_resilience.py:42-49, 59-63` y `backend/apps/submissions/views.py:17-41` — GET contra un límite que solo mira POST.
- `backend/tests/test_search_hardening.py:30-43` y `backend/apps/content/views.py:360, 396-460` — el recorte y el `except DatabaseError` que garantiza el 200.
- `backend/tests/test_performance.py:25-51` y `backend/apps/content/views.py:73, 161-167` — el presupuesto de la portada y el `select_related` del estante.
- `backend/tests/test_concurrency.py:86-101` — los hilos llaman al ORM, no a la vista.

**Por qué importa a futuro.** En el próximo rediseño de la portada se pierde el `select_related` del estante: con los datos de desarrollo (10 publicaciones con tapa y 4 con editorial), la portada pasa de 19 a unas 31 consultas y el presupuesto sigue en verde. Si alguien quita el recorte de la consulta de búsqueda, las dos pruebas siguen dando 200: una consulta de 5.000 caracteres solo se encarece, y el `except` garantiza la respuesta aunque falle.

**Recomendación.** (1) Hacer POST y fijar el comportamiento elegido: el envío se rechaza con el aviso y no se guarda. (2) Comprobar que la búsqueda larga encuentra el artículo con una consulta que case, y que la consulta emitida mide como máximo `SEARCH_MAX_QUERY`. (3) Sembrar la portada con tapas, editoriales y autoras y llevarla al patrón de escalado (N frente a M filas, mismas consultas) que ya usan otras vistas. (4) Lanzar los hilos contra `client.post` de la vista; hoy dos altas simultáneas generan dos tokens y dos correos, con impacto bajo. Regla general: toda prueba de «no aparece» lleva un control positivo en la misma respuesta.

**Matiz de la verificación.** Se retiraron dos casos: la agrupación por año de la trayectoria sí está fijada en `test_filas.py:203-236` (la prueba de `test_agenda` solo es redundante) y el dossier sí tiene control positivo (si dejara de listar publicaciones, fallaría `test_dossier_aggregates_everything`). Es falso que solo tres vistas tengan prueba de escalado: hay al menos ocho (textos, agenda, trayectoria, galería, dossier, ficha de publicación, ficha de evento y buscador); el único hueco real es la portada. Hay 14 pruebas que solo afirman el código de estado (5 son presupuestos y están bien).

#### PRU-9 · Fábricas a medio centralizar: duplicadas archivo por archivo y capaces de crear estados que el dominio no produce

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `factories.py` dice estar centralizado «para eliminar la duplicación de helpers», pero la duplicación volvió. Hay 17 llamadas a `Image.new` en 13 archivos y 10 ayudantes locales para crear una imagen (4 casi idénticos a `make_image`); 9 `_sopa` distintos; `Contributor.objects.create` aparece 47 veces en 20 archivos, sin fábrica, y `Recording.objects.create` 16 veces aunque existe `make_recording`; y hay ocho maneras de crear una pieza publicada. Conviven dos mecanismos: fixtures `make_article` y `make_poem` en conftest y funciones en `factories.py`. `make_article(status=PUBLISHED)` deja `published_at` vacío (24 llamadas en 9 archivos), mientras `perform_transition` siempre la rellena; con el orden por `-published_at`, PostgreSQL pone los nulos primero. Y el slug por recuento (`articulo-{count}`) colisiona si una prueba borra y vuelve a crear.

**Evidencia.**

- `backend/tests/factories.py:1-5, 40-46, 49-59, 69-74` — la promesa, `make_image`, `make_recording` y `publish()`, que sí rellena la fecha.
- `backend/conftest.py:113-129, 132-148` — `make_article` y `make_poem`, sin fecha por defecto.
- `backend/apps/content/workflow.py:76-78` y `backend/apps/content/models.py:87-89, 139` — la transición rellena la fecha; el campo admite nulos.
- `backend/apps/content/admin.py:59-63, 193-200` — un editor puede vaciar la fecha en el panel.
- `backend/tests/test_home_ui.py:18-19` y `backend/tests/test_indices.py:36-37` — `_pub`, idéntico en dos archivos.

**Por qué importa a futuro.** Un campo obligatorio nuevo en Contributor obliga a tocar 47 llamadas repartidas por la suite; el agente arregla las que fallan y deja variantes incoherentes. Una prueba futura de «lo más reciente primero» que mezcle una pieza publicada sin fecha con otra fechada fijará, sin querer, un orden que en producción solo se daría si un editor vacía la fecha.

**Recomendación.** Elegir un solo mecanismo, fixtures o funciones, y llevar allí `make_contributor` y `make_member`, el uso de `make_recording`, un `make_image(tamaño, formato, crédito)`, `make_published_article` y `make_published_poem` que rellenen `published_at`, y un `sopa(client, url)` que además afirme el 200. Que `make_article(status=PUBLISHED)` rellene la fecha por defecto, y usar `itertools.count` para los slugs. Opcional: factory_boy con `Sequence` y `SubFactory`.

**Matiz de la verificación.** Ninguna de las 24 llamadas sin fecha afirma hoy un orden, y una la rellena justo después. Como un editor puede vaciar la fecha desde el panel, el estado no es imposible (ver DOM-1). Severidad de media a baja.

#### PRU-10 · Higiene: una prueba modifica un archivo real del repositorio y otras se equivocan sobre el alcance de marcas e imports

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `test_la_version_cambia_al_editar_la_hoja` cambia con `os.utime` la fecha de modificación del `site.css` real del repositorio (montado en el contenedor) y la restaura en el `finally`; la prueba vecina hace lo mismo bien, sobre `tmp_path`. En `test_security_csp`, `pytestmark = pytest.mark.django_db` está en la línea 132, después de la sección «Middleware (unitario, sin BD)», pero una marca de módulo se aplica a todo el archivo (al recolectar, las 15 pruebas salen marcadas). `test_estante` repite el `cache.clear()` que ya hace el fixture automático.

**Evidencia.**

- `backend/tests/test_version_estaticos.py:48-61, 64-77` — el `os.utime` sobre el archivo real y la prueba vecina sobre `tmp_path`.
- `backend/config/context_processors.py:26-34` — la función lee `settings.BASE_DIR` en cada llamada: reapuntarlo funciona.
- `backend/tests/test_security_csp.py:20, 27-121, 132` — el encabezado «sin BD» y la marca de módulo tardía.
- `backend/tests/test_estante.py:15, 145` y `backend/conftest.py:8-16` — el `cache.clear()` repetido.

**Por qué importa a futuro.** Dos sesiones de pytest sobre el mismo `backend/` montado pueden dejar `site.css` con la fecha desplazada o volver intermitente esa prueba. Quien añada una prueba en la sección «sin BD» creerá que no toca la base, y un acceso accidental no se detectaría.

**Recomendación.** Reapuntar `settings.BASE_DIR` a una copia en `tmp_path`, como ya hace la prueba vecina. Marcar solo las pruebas que usan la base, o corregir el encabezado. Borrar el `cache.clear()` redundante. Extraer el `from conftest import …` de `test_media_aislado.py` a un `tests/_soporte.py` es opcional.

**Matiz de la verificación.** Se retiró que la fecha quede en el futuro (es 120 s posterior al archivo propio más reciente) y que un timeout del CI deje algo alterado (el checkout es efímero y el `finally` cubre Ctrl-C). Con xdist ninguna otra prueba ve nada que importe. La afirmación de que `--import-mode=importlib` rompería `test_media_aislado` es falsa en este proyecto, porque `pytest.ini` pone `pythonpath = .`. Mover la marca al principio del archivo no cambia el comportamiento.

### 4.9 Mantenibilidad y salud del código Python (MAN)

#### MAN-1 · Castellano e inglés mezclados sin regla, con claves gemelas de significado distinto y vocabularios paralelos

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** No hay una regla de idioma. Los modelos y campos están en inglés, con añadidos recientes en castellano (`Work.publicacion`, el `related_name` `obra_resenada`); una misma clase mezcla métodos (`ensure_derivatives`, `ensure_portada_derivatives`, `portada_srcset`, `color_de_borde`); y hay propiedades en castellano junto a campos en inglés (`Recording.duracion` junto a `duration_minutes`). La mezcla ya produce trampas: `stats()` devuelve `festivals` (festivales más ferias) y `festivales` (solo festivales), y el contexto de la portada pasa `integrantes` (un número que ninguna plantilla lee) junto a `members` e `integrantes_vista` (listas). Hay vocabularios paralelos: los tipos de propuesta («reseña», «poesía», «crónica», con tilde) frente a `ArticleType` («resena», «poesia», sin «crónica»), y `Submission.type` no tiene `choices` en el modelo; en la base ya hay valores con tilde. Tres modelos llaman `type` al campo y cinco, `kind`. Ninguna función tiene anotaciones de tipo, y los contratos entre servicios y plantillas son diccionarios con claves implícitas; como no hay `string_if_invalid`, una clave equivocada en una plantilla sale vacía sin aviso.

**Evidencia.**

- `backend/apps/agenda/services.py:15-38` — `'festivals'` (34) y `'festivales'` (35); el docstring (18-21) atribuye a la portada un uso que no tiene desde el commit `30799d0`.
- `backend/templates/agenda/trayectoria.html:16` y `backend/templates/showcase/dossier.html:62-63` — los dos consumidores, cada uno con una clave.
- `backend/tests/test_agenda.py:96-109` — comentarios con el reparto obsoleto y la prueba que fija las claves.
- `backend/apps/content/views.py:159-173, 186-213` — `integrantes` (203) es un entero que solo usa la propia vista.
- `backend/apps/media/models.py:101, 147, 202, 265, 361-366, 414-420` — la mezcla de idiomas dentro de MediaAsset y Recording.
- `backend/apps/submissions/forms.py:72-86`, `backend/apps/content/models.py:43-50, 177-180` y `backend/apps/submissions/models.py:52` — los dos vocabularios; en la base, `Submission.type` tiene «ensayo», «otro» y «reseña».

En cifras: unos 72 de 244 nombres de función están en castellano y unos 5 son mixtos (cerca del 30 %); 0 de 336 funciones tienen anotaciones, y `ruff --select ANN` da 765 avisos en `apps` y `config`.

**Por qué importa a futuro.** A un agente le piden «vuelve a poner las cifras en la portada, con festivales y ferias». Lee el docstring de `stats()` y escribe `{{ stats.festivals }}` con el rótulo «festivales»: con un festival y una feria, la portada anuncia «2 festivales» ante programadores y jurados, y ninguna prueba falla. Al «convertir un envío en artículo», `Article.objects.create(type=submission.type)` guarda «reseña» sin error (no hay `full_clean` ni CheckConstraint) y los filtros por `ArticleType.RESENA` no lo encuentran.

**Recomendación.**

1. Escribir la regla de idioma en CONTRIBUTING.md o en un CLAUDE.md (por ejemplo, identificadores en inglés y textos visibles en castellano; lo que importa es que haya una sola) y aplicarla al código nuevo.
2. Renombrar ya las trampas: `festivals` → `festivales_y_ferias`, corrigiendo el docstring de `stats()` y los comentarios de `test_agenda.py`; quitar del contexto la clave `integrantes`, que nadie lee.
3. El tipo de envío como TextChoices en el modelo, con una migración de datos («reseña» → «resena»). Alinearlo con `ArticleType` es en parte una decisión de producto, porque `ArticleType` tiene «critica» y «nota», que el formulario no ofrece.
4. Activar `string_if_invalid` (o un objeto que lance) en la configuración de pruebas, que sí atrapa una clave equivocada en una plantilla. TypedDict o dataclasses (`Puerta`, `Pliego`, `Cifras`, `Coincidencia`) para documentar los contratos, y ruff ANN en `services.py`, `pie.py`, `workflow.py` y `permissions.py`.

**Matiz de la verificación.** Las cifras se corrigieron al alza: los nombres en castellano rondan el 30 % (no 45 de 244) y ruff ANN da 765 avisos (no 562). Que los enumerados estén unos anidados y otros a nivel de módulo, y que convivan `type` y `kind`, es higiene: un nombre equivocado ahí da un FieldError ruidoso. Las anotaciones sin un comprobador de tipos en el CI no protegen las plantillas, que Django resuelve en ejecución.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D21 y D28, y §4, «Rótulos del panel a medias en inglés» (cerrado; decisión relacionada). Esas entradas solo tratan los rótulos del panel, y se contradicen entre sí: §4 da el panel por «entero en español» y D21 admite modelos aún en inglés. Sobre el idioma de los identificadores no hay ninguna decisión: conviene registrar una regla.

#### MAN-2 · Helpers y mecanismos copiados entre apps que ya empiezan a divergir (incluida la normalización de acentos)

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Lo común se copia en vez de compartirse. Hay tres `_published()` en tres módulos de vistas; la paginación de 12 escrita como un helper y dos copias en línea (WEB-7); seis `reverse()` de fichas que duplican un `get_absolute_url` existente, cinco sobre filas de la UNION de la búsqueda y tres hacia modelos que no tienen el método; la regla integrante o colaborador repetida en la búsqueda (ARQ-5); el honeypot implementado de dos maneras (WEB-9); el límite de tasa con `block=False` y la comprobación manual de `request.limited` repetida en tres vistas; la guarda de desarrollo copiada en cuatro comandos (HER-2); y `purge_stale_data` borra los adjuntos a mano aunque filecleanup ya lo hace (RES-10). La normalización de acentos existe en Python (NFKD en la búsqueda, NFD en `seccion_aporta`) y en la búsqueda de texto completo no coincide con el `unaccent` de PostgreSQL contra el que se compara (DAT-3).

**Evidencia.**

- `backend/apps/content/views.py:42-62, 345-351, 379-393, 396, 422-423, 444, 455` — `_published`, `_paginate`, `_strip_accents`, la regla de la búsqueda y el límite con comprobación manual.
- `backend/apps/media/views.py:11-17`, `backend/apps/showcase/views.py:10-11, 32` y `backend/apps/people/views.py:42` — las otras copias.
- `backend/apps/content/sitemaps.py:56-57, 67-68, 93, 104, 147-148` y `backend/apps/content/feeds.py:48-49` — `reverse` a mano en vez de `get_absolute_url`.
- `backend/apps/content/models.py:15, 30, 150, 165-167` y `backend/apps/reviews/models.py:4, 21, 37` — modelos con página y sin `get_absolute_url`; el segundo plegado de acentos.

**Por qué importa a futuro.** Un agente crea una vista pública nueva y copia `@ratelimit(key="ip", rate="5/m", method="POST", block=False)` sin el `if getattr(request, "limited", False)`: la vista queda sin límite y ninguna prueba falla, porque las pruebas de abuso solo cubren las vistas existentes. Un ensayo publicado que cita a «Søren Kierkegaard» no aparece al buscar «Søren».

**Recomendación.**

1. `get_absolute_url` en todos los modelos con página, usado en sitemaps, feeds y búsqueda; para las filas de la UNION, una sola función `url_de(tipo, slug, integrante)`.
2. Un decorador propio `limitar(rate)` que envuelva ratelimit y resuelva en un solo sitio la respuesta de «demasiados intentos».
3. Un mixin `HoneypotForm`, y un helper o clase base para la guarda de los comandos de desarrollo (HER-2).
4. Quitar el borrado manual de `purge_stale_data`, sacando el recuento de adjuntos de otra parte.
5. En la búsqueda de texto completo, quitar los acentos del término en la base (`SearchQuery` acepta una expresión como `Func(Value(termino), function="unaccent")`), o adoptar la configuración de DAT-3.

**Matiz de la verificación.** La divergencia de acentos solo afecta a la búsqueda de texto completo de textos y poemas: los `__unaccent__icontains` pliegan los dos lados, así que buscar «Søren» sí encuentra a una persona llamada así. Entre NFKD y NFD no hay divergencia práctica. El grep da 14 `reverse` de fichas fuera de los modelos, no 11. Cambiar la ruta de las integrantes no obliga a tocar varios sitios mientras tenga nombre; solo si cambian el nombre, los argumentos o la regla. Los tres `_published()` son ayudantes privados para modelos distintos: que se llamen igual no es una deriva. La guarda de `datos_de_desarrollo` exige `DEBUG` y no admite `--force`.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), D3, y §4, «Article no tiene get_absolute_url» (decisión relacionada). D3 añadió un plegado de acentos en Python junto al de la base, y el cierre de `get_absolute_url` se quedó en tres modelos: las dos cosas explican parte de las copias. Siguen siendo válidas, pero piden un ayudante compartido.

### 4.10 Huellas de código generado por agentes de IA (AGE)

#### AGE-1 · La regla «solo lo publicado» se reescribe a mano en 54 consultas, con cinco representaciones y parches por relación; Recording.event quedó sin proteger

**Severidad:** alta · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** No hay ningún Manager ni QuerySet propio. La visibilidad pública se repite en cada vista, servicio, sitemap y feed, con cuatro vocabularios según la sesión que creó cada modelo: `status=EditorialStatus.PUBLISHED` (Article y Poem, con ocho estados), `status=PublishStatus.PUBLISHED` (Collection y Page, con dos estados y el mismo valor), `published=True` (Recording, Event, Publication y PressMention) y `active=True` (Partner; Contributor combina `is_member` y `active`). Los valores por defecto se contradicen: PressMention y Partner nacen públicos y el resto, ocultos. Las relaciones que apuntan a objetos publicables se taparon una a una y de formas distintas: con una propiedad de modelo (`Poem.published_recording`, tras una fuga anterior), con una condición en la plantilla (`work.publicacion.published`) y con un filtro en Python (`event_detail`). `Recording.event` no se protegió: un registro publicado de un evento no publicado enseña el título y el enlace del evento (que da 404) en su ficha, en su pie y en el índice; el tipo y el año en la carátula; y, en la tirada de la portada, la sala, la ciudad, la fecha y la primera foto del evento como imagen del pliego. Está probado el caso inverso (`test_ficha_de_evento.py:68`), no este. Además, `Recording.published_at` es un campo manual que ningún código escribe.

**Evidencia.**

- `backend/apps/content/views.py:91-98, 113-141` — la tirada precarga las fotos del evento y usa su sala, su ciudad y su fecha sin mirar `evento.published`.
- `backend/apps/media/views.py:11-12, 28-29`, `backend/templates/media/recording_detail.html:22`, `backend/templates/media/recording_index.html:31`, `backend/templates/media/partials/_caratula.html:10` y `backend/templates/content/partials/_tirada.html:22-23, 29-30, 38-39` — las salidas sin condición.
- `backend/apps/agenda/views.py:33-42` — la ficha del evento sí exige `published` y filtra los registros en Python.
- `backend/apps/content/models.py:53-61, 270-281, 300-302, 319-322, 382-384` — los dos enumerados, la propiedad `published_recording` y la fecha manual de Collection.
- `backend/templates/reviews/work_detail.html:20` — la regla, en la plantilla.
- `backend/apps/media/models.py:384-385` — `published` y `published_at` de Recording; solo los lee el feed.

En cifras: 54 apariciones en código de aplicación, en 13 módulos (`grep -rnE "EditorialStatus.PUBLISHED|published=True|PublishStatus.PUBLISHED" backend/apps backend/config --include=*.py | grep -v migrations | grep -v /management/`); ningún manager ni QuerySet propio; cinco classmethods que hacen de QuerySet; y una relación sin proteger, con cinco salidas.

**Por qué importa a futuro.** Una editora deja sin publicar un recital (porque se canceló, o porque fue una sesión privada) que tiene un registro publicado y destacado. La portada imprime en el pliego la sala, la ciudad, la fecha y la primera foto del evento, y la ficha y el índice del registro muestran su título con un enlace que da 404; todo, indexable. Por otro lado, el próximo listado que escriba un agente (los eventos de una integrante, los poemas de una colección en otra página) repetirá el filtro de memoria o lo olvidará: el patrón ya produjo una fuga y, como se arregló de tres maneras, no hay un lugar canónico que copiar.

**Recomendación.**

1. Un QuerySet por familia con un método común: `EditorialQuerySet.publicados()` en EditorialItem y `PublicableQuerySet.publicados()` para los booleanos (en Partner, sobre `active`), montados como manager (`objects = ….as_manager()`) para que funcionen también desde las relaciones (`member.events.publicados()`). Convertir `upcoming`, `past`, `members` y `open_now` en métodos de esos QuerySets.
2. Para cada FK hacia algo publicable, una propiedad del modelo al estilo de `published_recording` (`Recording.evento_publico`, `Work.publicacion_publica`), usada en las cinco salidas de `Recording.event`; en la tirada, precargar las fotos solo de eventos publicados.
3. Una prueba «canario» parametrizada: para cada modelo publicable, un objeto oculto con un texto marcador, enlazado desde objetos publicados por todas sus relaciones, no aparece en la portada, los índices, las fichas, el buscador, los feeds ni el sitemap (PRU-1).
4. Una prueba que falle si aparece `published=True` o `status=…PUBLISHED` fuera de los QuerySets.
5. A medio plazo, una base abstracta común (estado y fecha de publicación, que `save()` rellena al publicar) y una sola política de valores por defecto.

El orden importa: primero la matriz de pruebas de PRU-1 y después centralizar el filtro.

**Matiz de la verificación.** «54 consultas» es el recuento literal del grep; descontando dos escrituras, una comparación en Python y el cuerpo de los propios classmethods, son unos 49 filtros de lectura. Los vocabularios son cuatro, no cinco, porque los dos enumerados comparten el valor `'published'`. La fuga es latente: en la base de desarrollo no hay ningún registro publicado con su evento oculto. La portada enseña sala y ciudad, no una dirección. Las obras, editoriales y colaboradores sin regla de visibilidad se tratan en WEB-1.

#### AGE-2 · Los permisos de los roles quedaron congelados en la línea base: el editor no gestiona agenda ni colectivo, el autor no puede escribir poemas, y la corrección no llegaría a producción

**Severidad:** alta · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `setup_groups` reparte los permisos con listas escritas a mano en el commit inicial (`764bb90`, 2026-07-09), cuando el sitio era una revista de reseñas. `EDITOR_APPS` enumera seis de las ocho apps: faltan agenda y showcase, creadas el 2026-07-27. `AUTHOR_PERMS` solo cubre artículos y catálogo: Poem llegó después y nadie lo añadió. Verificado en la base de desarrollo: el grupo editor tiene 104 permisos, todos de community, content, media, people, reviews y submissions, y el autor no tiene ninguno sobre Poem, PoemContributor ni CollectionPoem. Como `has_change_permission` exige primero el permiso de modelo, una autora no puede ver ni crear poemas, aunque `permissions.py`, `workflow.py` y el admin están escritos para que sea dueña de los suyos. Además, `setup_groups` es «siembra, no sincronización»: si un grupo ya tiene permisos, no se toca. Corregir las listas no cambia los grupos que ya existen, salvo con `--reset`, que descarta los ajustes manuales. Las pruebas no lo ven: `test_admin_acciones_por_rol` crea el grupo «autor» vacío y llama a `PoemAdmin.get_actions` sin comprobar que el autor pueda entrar a esa pantalla, y `test_poems` prueba `perform_transition`, que no mira los permisos de modelo.

**Evidencia.**

- `backend/apps/people/management/commands/setup_groups.py:9-10, 12-29` — `EDITOR_APPS` y `AUTHOR_PERMS`, idénticas a las del commit inicial (`git log -S"EDITOR_APPS"` y `git log -S"AUTHOR_PERMS"`).
- `backend/apps/people/management/commands/setup_groups.py:46-61, 99-108` — la siembra: `if nuevo or not group.permissions.exists()`; si no, «conservados».
- `docker-compose.prod.yml:7, 43` y `backend/entrypoint.sh:4-11` — en producción corre como paso explícito y sin `--reset`; en desarrollo, en cada arranque.
- `backend/apps/content/admin.py:183-188, 202-211` y `backend/apps/content/permissions.py:5-13` — el permiso de modelo va primero; «el autor solo puede editar su pieza (artículo o poema)»; los nombres de grupo, como literales.
- `backend/apps/content/workflow.py:19-21` — «submit» admite al dueño en cualquier pieza, poemas incluidos.
- `backend/tests/test_admin_acciones_por_rol.py:37-40, 64-68`, `backend/tests/test_poems.py:26-32` y `backend/conftest.py:67-79` — grupos vacíos, transiciones sin panel y un fixture que siempre siembra sobre una base vacía.

Quedan fuera del rol editor 9 modelos (Event, EventPhoto, Milestone, SiteProfile, SiteSocialLink, Publication, WhereToBuy, PressMention y Partner), y del rol autor, los 3 modelos de poemas.

**Por qué importa a futuro.** El colectivo da de alta a una editora sin superusuario. En el panel no ve «Agenda y trayectoria» ni «Colectivo»: no puede anunciar un recital ni cambiar el poema destacado. Una autora entra y no ve «Poemas», el contenido principal del sitio. Un agente lo «arregla» añadiendo agenda, showcase y los permisos de poema a las listas; las pruebas pasan; y en producción `setup_groups` imprime «ya configurado; se conservan sus permisos» y no cambia nada.

**Recomendación.**

1. Una matriz de roles declarada en un solo módulo (por ejemplo `apps/people/roles.py`, con constantes `ROL_ADMIN`, `ROL_EDITOR` y `ROL_AUTOR` que importen `setup_groups`, `permissions` y `workflow`), donde cada modelo del proyecto aparezca incluido o excluido de forma explícita. Derivar el editor de las apps propias y añadir al autor los permisos de poema (y, si el flujo lo pide, los de los puentes de autoría, la obra reseñada y las notas editoriales). Una prueba que recorra `apps.get_models()` y falle si un modelo no está en la matriz.
2. Llevar los cambios a producción con una migración de datos que solo añada los permisos nuevos, o con una sincronización aditiva que nunca restaure los retirados; las exclusiones del operador, guardadas aparte.
3. Pruebas que entren al panel con los grupos reales: `client.get("/admin/agenda/event/")` da 200 al editor, y `client.get("/admin/content/poem/add/")`, 200 al autor (PRU-4).
4. Preguntar al dueño si el editor debe gestionar showcase, que incluye el perfil del sitio: puede ser deliberado que no, pero no está escrito.

**Matiz de la verificación.** El fallo es cerrado: nadie obtiene más acceso del debido. Lo que se rompe es la usabilidad de los roles, y el dueño puede repararla a mano desde el admin. En producción, `setup_groups` corre como paso explícito del despliegue, no en cada arranque, con el mismo efecto. Que el autocompletado del dueño de una pieza dé 403 al editor (le falta `auth.view_user`) es coherente con los permisos medidos, pero no se ejecutó.

#### AGE-3 · Comentarios y docstrings como bitácora de sesiones: un tercio de la hoja de estilos es historia, cita decisiones de documentos que se están borrando y ya contiene afirmaciones falsas

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El código guarda la historia de cada cambio («Antes…», «Medía…», «el dueño eligió…», D18, «ticket 4.3», S-05, «paso 18 del backlog»), y esos comentarios no se mantienen. Afirmaciones falsas comprobadas:

1. Las flechas de la tirada se quitaron en D29 (commit `22a5b90`), y tres comentarios las siguen describiendo, mientras otro de la misma hoja dice «no hay flechas».
2. `csp.py` dice que el único script inline es el JSON-LD del artículo (hay tres) y que los estilos permiten `'unsafe-inline'` (hoy solo bajo `/admin/`).
3. Dos de los 26 contrastes escritos en `site.css` son falsos (3,40:1 es en realidad 3,47; 2,98:1 es 2,84) y otro está mal redondeado (3,89 es 3,88), después de un PR titulado «los ratios del CSS vuelven a ser ciertos». Un comentario dice que una saturación es «igual que --paper» (73 % frente a 65,2 %).
4. `--alto-cabecera` mide «64 desde 720 px», pero el cambio ocurre a 900.
5. `stats()` dice servir a la portada, `settings.py` dice que «media es la base» y el README presenta una «revista literaria de reseñas» (ARQ-7).

Las referencias apuntan además a documentos que no viajan con el código. Antes de esta auditoría se retiraron de `docs/` once documentos de auditorías y planes anteriores, entre ellos `docs/backlog-ux-ui.md` y `docs/plan-ejecucion-ux.md`; el borrado está preparado pero sin commit. Las pruebas, el README, CONTRIBUTING y `tools/ux/` los siguen citando, así que esas referencias hay que reapuntarlas o quitarlas antes de confirmar el borrado. Los identificadores D se resuelven en `docs/deferidos-y-decisiones.md`, que se conserva.

**Evidencia.**

- `backend/templates/content/home.html:7-8`, `backend/templates/content/partials/_tirada.html:7-9`, `backend/static/css/site.css:1315` frente a `1470-1472`, y `backend/static/js/registros.js:3-6` — las flechas que ya no existen.
- `backend/config/csp.py:3-8` frente a `23-30` y `108`; comprobado con curl: `/` sirve `style-src 'self'` y `/admin/login/`, `'self' 'unsafe-inline'`.
- `backend/templates/base.html:30`, `content/article_detail.html:18` y `agenda/event_detail.html:16` — los tres JSON-LD.
- `backend/static/css/site.css:35-36, 41-42, 44-45, 1133` — los contrastes y la saturación; `38-40` frente a `372-376` — el corte de la cabecera.
- Mitigación: `backend/tests/test_tirada.py:150-153, 244` y `backend/tests/test_security_csp.py:34-35, 68-85` frenan dos de esos comentarios.

En cifras: en `site.css`, unas 704 de 1.971 líneas son comentario, y entre 56 y 72 de sus 250 comentarios llevan marcas de historia o de decisión (unas 290 líneas, un 15 % de la hoja). En código, plantillas, CSS y JS hay 76 «Dnn», 21 «ticket», 30 «S-nn», 24 «hallazgo», 26 «dueño» y 10 «tablero».

**Por qué importa a futuro.** El próximo agente lee los comentarios como especificación. Si tiene que fijar un elemento bajo la cabecera en tabletas, lee «64 desde 720 px» y escribe `@media (min-width:720px){top:64px}`: entre 720 y 899 px la cabecera mide 56 y el elemento queda 8 px despegado, sin prueba que lo vea. Otro añade al panel un FileField para las bases de una convocatoria, lee en `validators.py` que hay una «comprobación de firma» y da el contenido por verificado (SEG-2).

**Recomendación.**

1. Una regla corta: el comentario dice qué hace el código y qué restricción vigente lo explica (CSP, accesibilidad, rendimiento), nunca qué hacía antes ni quién lo pidió. La historia va en el mensaje del commit y del PR.
2. Una pasada que quite los «Antes…», «Medía…» y «el dueño…» y los identificadores de decisión. Las decisiones ya tienen un registro único, `docs/deferidos-y-decisiones.md`, que basta enlazar una vez donde haga falta.
3. Corregir las afirmaciones citadas y borrar de `site.css` los contrastes escritos a mano, que ya calcula `test_contraste_paleta`.
4. Un paso del CI que falle si aparece un identificador de decisión nuevo fuera de las migraciones.

**Matiz de la verificación.** El título infla el alcance: un tercio de la hoja son comentarios, y una cuarta parte de ellos narra historia. Que los guiones expliquen que no tocan estilos por la CSP no es falso: `style-src 'self'` sí bloquea los atributos `style`, y los guiones no tocan el CSSOM; como mucho es impreciso (FRO-1). Las referencias «Dnn» no quedarán huérfanas, porque remiten a `docs/deferidos-y-decisiones.md`, que sigue versionado; sí quedarán huérfanas las «S-nn», «ticket», «hallazgo», «paso» y los enlaces explícitos, unas 190 referencias. Los dos riesgos citados primero (restaurar las flechas, relajar `style-src`) ya los frenan pruebas; el riesgo real está en los comentarios que ninguna prueba vigila: la firma de `validators.py`, la purga invertida (TAR-3), la ayuda de Recording (SEG-4), el corte de 720 frente a 900 y la cabecera del guion de preparación del entorno. El docstring de `csp.py` quedó falso a los dos días de escribirse y lleva tres meses así.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D29, la tirada sin flechas (decisión relacionada). D29 quitó las flechas y los comentarios siguen describiéndolas. Además, el encabezado del registro y la nota de §1 remiten a documentos de `docs/` que el árbol de trabajo marca como borrados: la decisión sigue en pie, y lo que ha envejecido son los comentarios y esas referencias del propio registro, que conviene actualizar.

#### AGE-4 · Dos (o más) formas de hacer lo mismo, según la sesión que lo escribió

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Varias operaciones tienen implementaciones paralelas:

1. Publicar: `perform_transition` y `publish_due_items` cambian el estado y escriben la bitácora cada una por su cuenta (ARQ-2).
2. El honeypot: en la vista del boletín y como propiedad del formulario de envíos, con widgets distintos (WEB-9).
3. Quitar tildes: NFKD con filtro de combinantes en la búsqueda, NFD en `Article.seccion_aporta` y NFKD con descarte de lo no ASCII en las semillas (MAN-2).
4. La paginación: un helper y dos copias en línea (WEB-7).
5. El mismo dato con dos nombres: la salida de `cronologia()` es `timeline`/`block` en la trayectoria y `cronologia`/`bloque` en el dossier; y en la plantilla del dossier el perfil es a la vez `profile` y `site_profile`, dos consultas a la misma fila (REN-5).
6. Los datos de prueba: fixtures en conftest, funciones en `factories.py`, 210 `objects.create` en línea y 10 ayudantes de imagen (PRU-9).
7. Los datos de desarrollo: cuatro comandos y un guion que los orquesta (HER-3).
8. Los rótulos del panel: Recording y SiteProfile se tradujeron (D21), pero 189 de 236 campos siguen con su `verbose_name` en inglés por defecto, y la prueba que se llama «los campos de la ficha se leen en español» comprueba seis.

**Evidencia.**

- `backend/apps/content/workflow.py:49-90` frente a `backend/apps/content/tasks.py:12-47` — dos implementaciones de publicar, probadas por separado.
- `backend/apps/community/views.py:66` frente a `backend/apps/submissions/forms.py:85, 127-130` — dos honeypots.
- `backend/apps/content/views.py:61-62, 347-351` y `backend/apps/content/models.py:165-167` — paginación y plegados de acentos.
- `backend/apps/agenda/views.py:22-30` frente a `backend/apps/showcase/views.py:108-118` — la misma estructura con dos nombres y el perfil cargado dos veces.
- `backend/conftest.py:113-148` frente a `backend/tests/factories.py:20-74` — dos mecanismos de fábricas.

Los cuatro comandos de datos suman 1.902 líneas, el 23 % del Python de aplicación. Los rótulos se contaron recorriendo `_meta.concrete_fields` en el shell.

**Por qué importa a futuro.** Se pide que, al publicar un texto, se avise a los suscriptores o se actualice la fecha de «última publicación». El agente lo pone en `perform_transition` y los textos programados, que publica la tarea, quedan fuera; como cada camino tiene sus pruebas, la suite sigue en verde. Un campo obligatorio nuevo en MediaAsset rompe a la vez todos los ayudantes de imagen y los `create` en línea. Y la editora sigue viendo «Title», «Starts at» y «Venue name» en la ficha de una actividad, con la prueba de rótulos en verde.

**Recomendación.** (1) Que la tarea llame a `perform_transition` con un actor de sistema (ARQ-2). (2) Un mixin de honeypot. (3) Un único `sin_tildes()` en un módulo de utilidades. (4) El mismo helper de paginación en todas las vistas. (5) Un solo nombre por estructura, y quitar `profile` del contexto del dossier. (6) Las fábricas concentradas en un solo mecanismo (PRU-9). (7) `datos_de_desarrollo` como mecanismo único y las semillas archivadas (HER-3). (8) Completar los `verbose_name` y hacer que la prueba de rótulos recorra todos los campos.

**Matiz de la verificación.** En la plantilla del dossier hay 22 usos de `profile`, no 25. Los ayudantes de imagen locales son 10 (no «al menos 9»); tres tienen motivo para diferir, pero cabrían como parámetros, y los MediaAsset creados en línea fuera de ellos son unos 11, no «decenas». La paginación no diverge: es higiene. En publicar, los dos caminos tienen hoy el mismo efecto observable; el riesgo es a futuro, aunque es el más serio del lote. El guion que «orquesta» las siembras llama a dos de los cuatro comandos. Lo de los rótulos es, más que dos formas de hacer lo mismo, una traducción a medias.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-23 (decisión relacionada). En su punto 1 es el mismo caso que ARQ-2: qa-23 evaluó la tarea solo por el horario, no por duplicar la transición.

### 4.11 Rendimiento y eficiencia (REN)

#### REN-1 · El orden de la búsqueda se calcula sobre el vector re-analizado en inglés

**Severidad:** alta · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `SearchRank("search_vector", query)` recibe una cadena, y Django la envuelve en `SearchVector("search_vector")`. El SQL resultante es `ts_rank(to_tsvector(COALESCE(search_vector::text, '')), plainto_tsquery('spanish', …))`: convierte en texto el tsvector guardado («'atent':44 'atras':29 …») y lo vuelve a analizar con la configuración por defecto de la base, que es `pg_catalog.english`. Al pasarlo a texto se pierden además la frecuencia y las posiciones. El filtro `@@` sí usa el vector correcto, así que el conjunto de resultados está bien; el orden no. Medido en desarrollo: con «detalle», «silencio» y «verso», todas las coincidencias tienen rango 0 y el orden queda indefinido; con «poemas» y «lectura», todas reciben el mismo rango (0,0608), de modo que la relevancia tampoco decide. Reanalizar el vector de cada coincidencia cuesta unos 10 ms frente a 0,1 ms con `F("search_vector")`, unas cien veces más.

**Evidencia.**

- `backend/apps/content/views.py:426-439` — `.annotate(rank=SearchRank("search_vector", query))` en textos (430) y poemas (436), con `.order_by("-rank")[:tope]`; el SQL generado en el shell lo confirma. `grep -rn "SearchRank(" backend/apps` da exactamente 2.
- `backend/apps/content/views.py:356-357, 420` — `SEARCH_RESULTS = 10` y `SEARCH_RESULTS_PANEL = 5`: el panel ya recorta hoy con «poemas», que tiene 7 coincidencias.
- `backend/apps/content/migrations/0011_unaccent_search.py:10-48` — los triggers guardan `to_tsvector('pg_catalog.spanish', unaccent(...))`, que el rango descarta.
- `backend/tests/test_search_hardening.py:72-93` — solo afirma cuántos resultados hay; `grep -rn rank backend/tests` no encuentra nada: ninguna prueba fija el orden.

El defecto está desde el commit inicial en los textos y se copió a los poemas.

**Por qué importa a futuro.** Hoy, en el panel del buscador, al buscar «poemas» aparecen 5 de los 7 textos que coinciden, elegidos por un rango que vale lo mismo para todos; con «verso», el orden lo decide el plan de PostgreSQL. Cuando un término común pase de diez coincidencias en la página completa, el recorte puede dejar fuera justo los textos más pertinentes, sin ningún error visible. Y quien intente afinar la relevancia (más peso al título, `cover_density`) no verá ningún efecto y buscará el fallo en otra parte.

**Recomendación.** `SearchRank(F("search_vector"), query)` en los dos querysets. Una prueba de comportamiento: dos textos publicados, uno con el término en el título y repetido y otro con una sola mención; el primero debe salir arriba. Como mejora opcional, premiar el título con una migración que reescriba las funciones de los triggers con `setweight(...título..., 'A') || setweight(...cuerpo..., 'D')` y reindexe.

**Matiz de la verificación.** Es sobre todo un defecto funcional de la búsqueda, no de eficiencia: el sobrecoste es despreciable con este tráfico. El docstring de la búsqueda no miente: el LIMIT sí resolvió el problema que describe, y cualquier `ORDER BY rank` calcula el rango de todas las coincidencias (con `F()` es barato). El recorte no esconde «justo los más pertinentes», sino una selección arbitraria que puede dejarlos fuera. No conviene añadir una prueba que busque `to_tsvector(COALESCE(` en el SQL: ataría la prueba a la implementación. Un verificador habría bajado la severidad a media; el panel la mantuvo en alta por mayoría.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), D3 y «FTS por trigger de Postgres» (decisión relacionada). Las decisiones construyen y guardan el vector en español y sin acentos, y la consulta lo descarta. Siguen siendo correctas: el fallo está en la consulta.

#### REN-2 · Caddy marca como inmutable durante un año todo /static/, también TinyMCE, que va sin hash

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El bloque `/static/*` del Caddyfile pone `Cache-Control: public, max-age=31536000, immutable` a todo, con el supuesto, escrito en su comentario, de que todos los nombres llevan hash. No lo llevan los 14 archivos de `vendor/tinymce/`, que el almacenamiento deja sin hash a propósito (su cargador pide archivos por rutas relativas, y el CI comprueba que sigan así); esa ruta tampoco lleva versión. WhiteNoise, que antes servía los estáticos, solo marca inmutable lo que lleva hash (al resto le da 60 s con `DEBUG=0`): al pasar los estáticos a Caddy se perdió esa distinción. De paso, el almacenamiento escribe un `.gz` por archivo que Caddy no usa (su `file_server` no tiene `precompressed`), y `encode zstd gzip` vuelve a comprimir en cada respuesta.

**Evidencia.**

- `infra/caddy/Caddyfile:36, 60-74` — la cabecera inmutable para todo `/static/*`, sin `precompressed`.
- `backend/config/staticfiles.py:14-38` — `unhashed_prefixes = ("vendor/tinymce/",)`.
- `backend/apps/content/admin.py:34-38` y `backend/static/admin/richtext_init.js:4-19` — `tinymce.min.js` sin hash junto a `richtext_init.js` con hash; sin `cache_suffix`.
- `.github/workflows/ci.yml:154-187, 324-351` — el CI comprueba el manifiesto de TinyMCE y las cabeceras de `/media/`, nada de las de `/static/`.
- `backend/static/vendor/VERSIONS.md:8-18, 25, 32-35` — el procedimiento de actualización no menciona la caché.
- whitenoise 6.12.0 en el contenedor, `middleware.py:44-49, 164-180` — `immutable_file_test` solo acepta nombres versionados.

**Por qué importa a futuro.** Se actualiza TinyMCE por un parche de seguridad siguiendo VERSIONS.md y, en el mismo cambio, `richtext_init.js` (con hash, que llega nuevo) activa un plugin más. Las editoras que usaron el panel durante el último año tienen en caché, marcados como inmutables, el núcleo, el tema, la piel y los plugins viejos, y el navegador no los revalida ni al recargar: el plugin nuevo se carga contra el núcleo viejo y el editor falla solo en sus navegadores (en una ventana privada funciona). Si no hay plugins nuevos, siguen sin el parche hasta que caduque la caché.

**Recomendación.** Lo más robusto es poner la versión en la ruta (`vendor/tinymce-7.9.3/`), definida en una constante que usen `unhashed_prefixes` y `RichTextWidget.Media`, para que cada actualización cambie la URL, y añadir ese paso a VERSIONS.md. Alternativa: que Caddy marque inmutable solo lo que lleva hash (un matcher `path_regexp` con `[.][0-9a-f]{12}[.]`) y dé `Cache-Control: no-cache` (Caddy ya envía ETag y Last-Modified) o un max-age corto al resto. Corregir el comentario del Caddyfile y el de `docker-compose.prod.yml:128`, y añadir un paso de CI que pida un archivo de TinyMCE a través de Caddy y falle si llega como inmutable. Añadir `precompressed gzip` al `file_server` es opcional.

**Matiz de la verificación.** El alcance real son los 14 archivos de TinyMCE, que solo carga el panel: las copias sin hash de los demás estáticos existen, pero ninguna referencia llega a ellas. Los `.gz` sin uso son higiene con este tráfico, no un problema de rendimiento, y la cifra de 264 sobre 545 salía de un artefacto local antiguo. El impacto de seguridad está acotado, porque TinyMCE solo corre en el panel y el servidor vuelve a sanear al guardar. TinyMCE no se ha tocado desde que se vendorizó: el riesgo se activará en la próxima actualización.

#### REN-3 · El srcset pregunta al almacenamiento en cada render y su copia menor (480 px) sirve miniaturas de 48-96 px

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `MediaAsset.srcset()` hace un `storage.exists()` por cada ancho en cada render, y `portada_srcset()`, uno por ancho y formato (hasta 12). Medido: 72 llamadas por render de la portada (32 imágenes), 38 en una ficha de evento y 34 en la galería. Hoy cuestan alrededor de 1 ms, porque el almacenamiento es el disco local. Con `SRCSET_WIDTHS = (480, 960, 1440)`, las ranuras pequeñas reciben la copia de 480 px. El peor caso es el dossier: 25 miniaturas sin carga diferida (retratos de 96 px, tapas de 120 y logos de 160) descargan 448 KB a 480 px, frente a unos 179 KB estimados con una copia de 240. El póster del vídeo propio usa el archivo original.

**Evidencia.**

- `backend/apps/media/models.py:18, 147-155, 299-315` — los anchos y los `exists()` por ancho y formato, sin memoizar.
- `backend/apps/media/models.py:231-236, 243-251` — `ensure_derivatives` no genera copias si no puede leer el archivo o si el formato no es JPEG, PNG ni WebP.
- `backend/apps/media/templatetags/images.py:18-36, 71-78, 121-126` — las etiquetas piden el `srcset` en cada render.
- `backend/templates/content/partials/_firmas_lectura.html:10` y `_article_card.html:21` — `sizes` de 48 a 96 px.
- `backend/templates/showcase/dossier.html:76, 127, 161` — miniaturas con `lazy=False`.
- `backend/templates/media/partials/_player.html:33` — el original como póster.

**Por qué importa a futuro.** Los listados y, sobre todo, el dossier que reciben los gestores en el teléfono descargan más bytes de imagen de los necesarios. Y si algún día los medios pasan a un almacenamiento de objetos (S3 o compatible), cada `exists()` se convertirá en una petición HTTP: unas 72 por render de la portada, segundos por página.

**Recomendación.** Añadir un ancho pequeño (por ejemplo 240) a `SRCSET_WIDTHS` y regenerar las copias con `generate_image_derivatives`. Registrar los derivados generados (un JSONField con anchos y formatos que escriban `ensure_derivatives` y `ensure_portada_derivatives`) y armar el `srcset` desde ese dato, sin tocar el almacenamiento. No basta con confiar en que existen todos los anchos menores: para GIF, BMP, TIFF o archivos ilegibles no se generan copias y el `srcset` apuntaría a 404. Usar un derivado como póster del vídeo.

**Matiz de la verificación.** En desarrollo no hay imagen de portada elegida, así que las 72 llamadas salen todas de `srcset()`; con imagen se sumarían hasta unas 27. El escenario de S3 es hipotético y su síntoma se vería al momento. «Con DPR 2 bastaría una copia de 192» no vale para las miniaturas recortadas (`object-fit: cover` sobre fotos apaisadas necesita de 290 a 430 px): en `/textos/`, una copia de 240 ahorraría 2,6 veces, no 3,9. Severidad de media a baja.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D18 (decisión relacionada). El `srcset` de hasta 12 entradas sale de las copias de D18. La decisión de formatos sigue siendo buena, pero no obliga a consultar el almacenamiento en cada render ni a prescindir de un ancho pequeño.

#### REN-4 · El worker de Celery abre un proceso por CPU del anfitrión, sin relación con su carga ni con su límite de memoria

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `celery -A config worker -l info` no fija `--concurrency`, así que Celery usa el número de CPU del anfitrión e ignora el `cpus: 1.0` del contenedor. En este equipo hay un proceso principal y ocho hijos, y el contenedor de desarrollo ocupa 386 MiB. La carga real es una tarea por minuto, algún correo y una purga semanal. No hay `max_tasks_per_child`, y el healthcheck lanza cada 60 s otro proceso Python dentro del mismo límite de memoria.

**Evidencia.**

- `docker-compose.yml:52-61` — el worker sin `--concurrency` ni `--max-tasks-per-child`.
- `docker-compose.prod.yml:67-84` — `mem_limit` de 512 MiB, 1 CPU y el healthcheck con `celery inspect ping`.
- `backend/config/settings.py:203-236` y `backend/config/celery.py:1-9` — sin ajustes de concurrencia.
- celery `worker/worker.py:20, 109-113` y billiard `context.py:50-75` en el contenedor — la concurrencia por defecto es `os.cpu_count()`.

**Por qué importa a futuro.** En un VPS con muchas vCPU (10 o 12 o más), el worker supera en reposo su límite de memoria: el kernel mata procesos y un correo de confirmación en curso se confirma como fallido y se pierde (TAR-1), sin aviso en el sitio.

**Recomendación.** `--concurrency ${CELERY_CONCURRENCY:-2}` y `--max-tasks-per-child 200` en el compose (u opcionalmente `--max-memory-per-child`), documentados junto a `WORKER_MEM_LIMIT` en la plantilla de producción.

**Matiz de la verificación.** El RSS de cada hijo sobreestima el coste, porque comparten páginas de memoria con el principal: el coste marginal real es de unos 35-40 MiB por hijo. Con 2 a 4 vCPU, lo esperable con estos límites, no hay problema; con 8, el reposo queda en torno al 75 % del límite. Que los hijos crezcan «tras semanas de tareas» es especulativo, porque las tareas no cargan volúmenes grandes. Severidad de media a baja.

#### REN-5 · El perfil del sitio se lee en cada petición, dos veces en cuatro vistas, y no hay ninguna caché de lectura

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El procesador de contexto `site_profile` ejecuta `SiteProfile.load()`, un `get_or_create`, en cada render, incluso en el fragmento htmx del buscador, que no lo usa. La base pide `og_image` en otra consulta y las redes en una tercera. Las vistas que necesitan el perfil lo vuelven a cargar: la portada, la trayectoria (que llama a `stats()` sin pasarle el perfil), el dossier y el feed de textos, que lo lee dos veces. En las páginas sencillas, tres de las cuatro consultas son de este «cromo» común. No se cachean páginas, fragmentos ni el perfil, y la base hace único cada HTML (el nonce de la CSP y el token CSRF del pie), así que cachear páginas completas no es posible sin rediseñarla.

**Evidencia.**

- `backend/apps/showcase/context_processors.py:17-26` y `backend/apps/showcase/models.py:119-126` — `load()` en cada render, sin `select_related`.
- `backend/templates/base.html:25-26, 30, 35-36, 160` — `og_image`, el nonce del JSON-LD y el token del pie.
- `backend/apps/agenda/views.py:30` y `backend/apps/agenda/services.py:15-22` — `stats()` sin perfil vuelve a cargarlo.
- `backend/apps/showcase/views.py:109-115`, `backend/apps/content/views.py:147` y `backend/apps/content/feeds.py:22-33` — las lecturas duplicadas.
- `backend/apps/content/context_processors.py:75` — `nav_sections`, que nadie usa.

**Por qué importa a futuro.** Cada vista nueva que necesite el perfil lo volverá a pedir (la firma `stats(perfil=None)` lo invita), y cada relación nueva del perfil que se pinte en la base añadirá una consulta a todas las páginas. Cuando se quiera abaratar la portada, la vía obvia, `cache_page`, no funcionará por el nonce y el token CSRF.

**Recomendación.** Cargar el perfil una vez por petición: que el procesador lo deje en `request` y lo exponga con `SimpleLazyObject` (así el fragmento htmx deja de pagarlo), con `select_related("og_image")` y `prefetch_related("social_links")`, y un ayudante `perfil_de(request)` para vistas y feeds. Otra opción es cachearlo con una caducidad corta e invalidarlo al guardar el perfil o sus redes. Si hace falta cachear, que sea por fragmentos (`{% cache %}` del estante o de la tirada) o por datos, no por página. Quitar `nav_sections`.

**Matiz de la verificación.** Sí existe una caché de lectura, la del color de borde (TAR-6); lo exacto es que no se cachean páginas, fragmentos ni el perfil. La consulta de `og_image` solo ocurre si el perfil tiene imagen social. El sitemap también paga el perfil.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4, «Páginas 404 y 500 con la identidad del sitio» (cerrado; decisión relacionada). El registro ya documenta que el procesador consulta la base en cada render, y por eso `500.html` no hereda de la base. Cachear el perfil es compatible con esa decisión, que debe mantenerse: un 500 no puede depender ni de la base ni de la caché.

#### REN-6 · Consultas que traen colecciones enteras para usar una parte: fotos de eventos, sitemap y feeds

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** La galería precarga todas las fotos, con su recurso, de todos los álbumes, para enseñar tres por álbum y su número. La tirada de la portada precarga todas las fotos de los eventos de los registros destacados para usar, como mucho, la primera: hoy son 24 fotos de 4 eventos, y no se usa ninguna, porque los cinco destacados tienen póster. El sitemap trae las filas completas de textos y poemas, con el cuerpo HTML y el vector de búsqueda (unos 100 KB de columnas para 20 piezas), para escribir 12 KB de XML. Ni el sitemap ni los feeds se cachean, y no hay GET condicional: el feed envía `Last-Modified`, pero responde 200 a un `If-Modified-Since` posterior porque falta `ConditionalGetMiddleware`.

**Evidencia.**

- `backend/apps/agenda/views.py:70-77` y `backend/templates/agenda/gallery.html:14, 27, 30` — se precarga todo y se usan tres fotos y el total.
- `backend/apps/content/views.py:91-98, 115, 129` — todas las fotos de cada evento para usar `fotos[0]`.
- `backend/apps/content/sitemaps.py:50-51, 75-76, 160-178` — filas completas, sin `only()`.
- `backend/config/settings.py:72-85` e `infra/caddy/Caddyfile:36, 71` — sin `ConditionalGetMiddleware` ni caché en el borde para feeds y sitemap.

**Por qué importa a futuro.** Cuando el colectivo suba un álbum por recital, cada visita a la galería instanciará cientos de objetos para enseñar unas decenas, y la portada seguirá cargando fotos que no usa. Los lectores de RSS piden el feed cada pocos minutos y siempre reciben la respuesta completa.

**Recomendación.** En la galería, `Prefetch("photos", queryset=EventPhoto.objects.select_related("asset")[:3])` más `annotate(n_fotos=Count("photos"))` (con el recorte, `photos|length` daría 3, de ahí el `Count`); en la tirada, `[:1]`; y paginar la galería. `.only("slug", "updated_at")` en los sitemaps. `cache_page` de una hora en el sitemap y los feeds, y `ConditionalGetMiddleware` (o `@condition`) para responder 304.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D19, la imagen del pliego es el póster o la primera foto del evento (decisión relacionada). La regla solo necesita una foto por evento; precargarlas todas es una implementación cara de una decisión que sigue siendo razonable.

#### REN-7 · El 42 % de la hoja de estilos que bloquea el render son comentarios

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `site.css` es la única hoja de estilos y bloquea la primera pintura de cada página. El almacenamiento la hashea y la comprime, pero no la minifica, así que viajan sus 250 bloques de comentario. Sin ellos pasa de 136.531 a 79.601 bytes (el 42 % de los bytes son comentarios); comprimida, de 39.878 a 16.462 bytes, un 59 % menos. La hoja lleva 79 commits: cada despliegue que la toca obliga a todos los visitantes a descargarla de nuevo.

**Evidencia.**

- `backend/static/css/site.css:179-186` — uno de los 250 bloques de comentario.
- `backend/templates/base.html:51` — la hoja, en el `<head>`.
- `backend/config/staticfiles.py:14-38` — `post_process` hashea y comprime, sin minificar.
- `backend/config/context_processors.py:8-27` y `backend/config/settings.py:188-199` — en producción manda el hash del manifiesto.

**Por qué importa a futuro.** En un teléfono con red móvil son unos 23 KB comprimidos de más en el camino crítico, en la primera visita y después de cada cambio de estilos, y cada comentario de diseño nuevo engorda ese camino.

**Recomendación.** Quitar comentarios y espacios en `VendoredStaticFilesStorage.post_process` antes del hash (por ejemplo con rcssmin), conservándolos en la fuente. Comprobar que los `url()` relativos de las fuentes se siguen reescribiendo y que las precargas de `base.html` apuntan a la misma URL.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4 (rediseño), «LCP y CLS medidos en desarrollo… Repetir en la vista previa de producción» (decisión relacionada). Esa medición pendiente es la manera de cuantificar el efecto de minificar.

#### REN-8 · Conexiones persistentes a la base sin comprobación de salud

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** En producción, `CONN_MAX_AGE` vale 60 s y no se define `CONN_HEALTH_CHECKS`. Con tres workers de cuatro hilos, cada hilo reutiliza su conexión sin comprobarla. Si PostgreSQL se reinicia o se recrea sin reiniciar web, la primera petición de cada hilo cuya conexión se abrió en los 60 s anteriores falla con `OperationalError` y responde 500; Django solo descarta la conexión después del error.

**Evidencia.**

- `backend/config/settings.py:113-123` — `CONN_MAX_AGE` de 60 por defecto y sin `CONN_HEALTH_CHECKS`.
- `docker-compose.prod.yml:19-25` — tres workers y cuatro hilos.
- `docker-compose.override.yml:11-16` — en desarrollo vale 0, así que no se reproduce en local.
- `docker-compose.yml:46-50` — `depends_on` sin `restart: true`: recrear db no reinicia web.

**Por qué importa a futuro.** Tras fusionar un PR de Dependabot que actualiza el digest de postgres y ejecutar `up -d`, se recrea solo la base, y un visitante que llega justo después recibe un 500 («server closed the connection unexpectedly») que nadie puede reproducir. Con poco tráfico serán pocas peticiones, a veces ninguna.

**Recomendación.** `"CONN_HEALTH_CHECKS": True` en `DATABASES["default"]`. Cuesta un `SELECT 1` por cada petición que reutiliza una conexión, algo despreciable con este tráfico.

### 4.12 Manejo de errores, resiliencia y observabilidad (RES)

#### RES-1 · El control de privacidad de las imágenes falla abierto y en silencio: el GPS se publica en el original

**Severidad:** alta · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `media/models.py` tiene cinco `except Exception` sin registro y ningún logger. `strip_metadata`, que quita la ubicación y los datos de cámara del original público, vuelve sin hacer nada en dos casos: si Pillow no puede cargar el archivo, o si el formato no está en su lista (JPEG, MPO, WEBP, TIFF, PNG). El ImageField del panel acepta archivos de ambos casos. Verificado en el contenedor: (a) un JPEG con GPS truncado al 90 % pasa la validación del formulario, `img.load()` lanza OSError, la función vuelve y el GPS queda intacto; (b) `.avif` está entre las extensiones aceptadas (Pillow 13 lo soporta), y un AVIF con GPS da `fmt == "AVIF"` y no se limpia. Hay una tercera vía: un JPEG con la ubicación solo en XMP no se detecta como «con metadatos» y no se reescribe. Caddy sirve el original tal cual desde `/media/`. El mismo patrón deja sin rastro los demás fallos del procesado: los derivados se omiten en silencio, el color de borde devuelve `""` y lo guarda sin caducidad, y el comando de derivados cuenta como verificados los recursos que fallaron.

**Evidencia.**

- `backend/apps/media/models.py:157-200` — `strip_metadata`: vuelve si el formato no está en la lista (176-178) y ante cualquier excepción (180-181), sin registro.
- `backend/apps/media/models.py:113-118, 141-144, 231-236, 243-251, 265-286` — los demás `except` silenciosos: copias de portada, derivados (incluido el `return` por formato no soportado) y color de borde.
- `backend/apps/media/models.py:26-30` — ImageField sin validador propio: rige `validate_image_file_extension`, que con este Pillow admite `.avif`.
- `backend/apps/media/management/commands/generate_image_derivatives.py:15-20` — informa «Derivados verificados» aunque haya fallado.
- `backend/apps/media/filecleanup.py:14-27` — aquí sí hay logger con traza: conviven dos criterios.
- `backend/tests/test_security_uploads.py:72-82` — ninguna prueba cubre metadatos por formato ni archivos truncados (`test_file_lifecycle.py` sí prueba que un JPEG normal con GPS sale limpio).
- `infra/caddy/Caddyfile:49-58` — `/media/` se sirve directamente desde el volumen.

`grep -n "except Exception" backend/apps/media/models.py` da cinco, y el módulo no menciona ningún logger. Las tres vías de fuga se reprodujeron en memoria.

**Por qué importa a futuro.** Una integrante sube desde el panel `recital.avif`, una foto tomada en su casa con la ubicación activada. El formulario la acepta, `strip_metadata` ve AVIF y vuelve, `ensure_derivatives` también, y ningún log registra nada. La página publica el original, y cualquiera que lo descargue lee las coordenadas (en la prueba, S 33°26'10", W 70°39'5"). El próximo agente que toque el procesado no tiene ninguna señal de que el control dejó de aplicarse.

**Recomendación.** Que el control falle cerrado:

1. Una lista permitida coherente: `FileExtensionValidator(["jpg", "jpeg", "png", "webp"])` en `MediaAsset.file`, o un validador que exija que el formato real sea JPEG, PNG o WebP.
2. Reescribir siempre el original al subirlo, no solo cuando se detecta EXIF: así desaparecen EXIF, XMP e IPTC.
3. Si no se puede reescribir sin metadatos, rechazar la subida con un mensaje del tipo «vuelve a exportar la imagen».
4. `logger = logging.getLogger(__name__)` y registros con el pk y el nombre del archivo: WARNING para un formato no soportado y `logger.exception` para lo inesperado.
5. No cachear el resultado de un fallo (o hacerlo con una caducidad corta), y que el comando cuente los fallos y salga con un código distinto de 0.
6. Pruebas: un JPEG truncado con GPS, un AVIF con GPS y un JPEG con la ubicación solo en XMP quedan sin ubicación o se rechazan.

**Matiz de la verificación.** Un JPEG truncado al 90 % no «se ve bien»: se pinta con una franja gris abajo y sin derivados, así que es más probable que alguien lo note y lo reemplace (y el reemplazo borra el original con GPS). El AVIF sí se ve perfecto. Las aplicaciones de mensajería suelen quitar el EXIF, de modo que las vías creíbles son un AVIF exportado con metadatos y un JPEG con la ubicación en XMP. El `except DatabaseError` de la búsqueda, citado al principio junto a estos, sí registra con traza: se trata en RES-9.

#### RES-2 · El respaldo informa éxito aunque los medios no se hayan respaldado: los fallos de tar se tragan como «(media vacío)»

**Severidad:** alta · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** En `backup.sh`, cada `tar czf … 2>/dev/null || echo "  (media vacío)"` descarta el error y convierte cualquier fallo (disco lleno, error de lectura, montaje ausente) en un mensaje que dice «vacío». Con `set -eu`, el `||` anula el aborto. Un directorio vacío nunca entra en esa rama, porque GNU tar sale con 0 y crea un archivo válido: el mensaje solo aparece cuando algo falló. El script sigue como si nada: sube a restic el tar truncado, rota los respaldos antiguos (borra el más viejo, que estaba completo) y envía el ping de éxito. El trap de fallo, que es justo la alerta que se diseñó, nunca se dispara en este caso. Además, el directorio del respaldo se crea antes del `pg_dump` y, si la corrida falla, queda a medias; la rotación cuenta esos directorios incompletos y desplaza respaldos buenos, y `restore.sh latest` elige el más reciente aunque sea uno fallido.

**Evidencia.**

- `infra/backup/backup.sh:35-36` — `tar czf … 2>/dev/null || echo "  (media vacío)"`, para los medios públicos y los privados.
- `infra/backup/backup.sh:5, 16-27` — `set -eu`, el trap de fallo y el `mkdir` del destino antes del dump.
- `infra/backup/backup.sh:52-63` — la rotación no distingue respaldos completos; el mensaje de éxito y el ping no dependen de nada.
- `infra/backup/restore.sh:21-27, 30-33, 35-44` — `latest` es el directorio más reciente; borra los medios antes de extraer (OPE-3).
- `docker-compose.yml:75-103` y `.env.prod.example:70-71` — los volúmenes montados en `/volumes`, `BACKUP_DIR` de ejemplo en `/var/backups/resenas` y 14 copias.
- `.github/workflows/ci.yml:402-409, 425-434` — `backup.sh` solo se prueba con directorios válidos.
- Reproducido con GNU tar 1.35 bajo `sh -eu`: el directorio vacío da código 0 y un archivo de 111 bytes; el inexistente toma la rama «(media vacío)», deja un archivo de 20 bytes y el script sigue.

**Por qué importa a futuro.** `BACKUP_DIR` está en el disco del VPS y guarda 14 copias completas de los medios, que crecen con el audio y el vídeo. Un día el dump cabe pero el tar de los medios falla por falta de espacio: el script imprime «(media vacío)», sube el archivo truncado, purga la copia completa más antigua y el monitor recibe un OK. Mientras los medios sigan creciendo, cada corrida puede volver a truncarse, y nadie lo sabrá hasta intentar restaurar. Si entonces se ejecuta `restore.sh latest`, el script borra los medios actuales y extrae el archivo truncado.

**Recomendación.** Quitar `2>/dev/null || echo …` y dejar que `set -e` aborte: el trap ya avisa al monitor de fallos. Si se quiere avisar de un volumen vacío, comprobarlo aparte antes de archivar (`[ -z "$(ls -A /volumes/media)" ]`), y tratar aparte el código 1 de GNU tar («file changed as we read it») para no generar falsas alarmas. Verificar cada artefacto antes de declarar éxito (`gzip -t` y `pg_restore --list db.dump > /dev/null`). Escribir en `$DEST.partial`, mover a `$DEST` y crear un archivo `OK` solo al final, y rotar y elegir `latest` solo entre directorios con `OK`. En `restore.sh`, verificar los archivos antes de borrar nada y restaurar con `pg_restore --single-transaction --exit-on-error` (OPE-3). Añadir al job del CI un caso negativo, con un volumen ilegible o un destino pequeño, que exija una salida distinta de 0.

**Matiz de la verificación.** Un volumen con nombre que falte lo crea Docker vacío, y entonces tar sale con 0: ni esta rama ni la corrección lo detectarían; haría falta un umbral mínimo de archivos o de tamaño. Con el disco lleno, `pg_dump` escribe primero: si no cabe ni el dump, falla él y la alerta sí salta; el caso enmascarado exige que quepa el dump y no el tar de medios, algo plausible con 14 copias completas. Como la rotación diaria libera espacio, lo esperable son copias incompletas intermitentes y no detectadas, más que «ninguna copia íntegra». Y si un archivo cambia durante la copia, GNU tar sale con 1 e imprime el mismo «(media vacío)» aunque el archivo esté bien.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §2 (infraestructura), «Alerta de fallo de respaldo (dead-man's-switch)» (diferido conocido). Estaba pendiente probar que un fallo dispara la alerta, y hoy no la dispararía con los medios. No depende solo de la infraestructura: hay que corregir el script antes de definir `BACKUP_PING_URL`.

#### RES-3 · La redacción de PII y tokens cubre la URL y nada más: Sentry recibe cuerpos POST, variables locales y cabeceras; Caddy registra el token en el Referer

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `sentry_sdk.init` usa los valores por defecto del SDK 2.72 salvo `send_default_pii=False`, y `sentry_before_send` solo redacta `request.url`, `query_string` y `transaction`. Verificado en el SDK instalado: aun con `send_default_pii=False`, el SDK (1) adjunta el cuerpo del POST hasta 10 KB; (2) envía las variables locales de cada marco (`include_local_variables=True`); (3) solo enmascara claves exactas de una lista (password, token, csrf…), no `email`, `author_name`, `body` ni `confirm_url`; y (4) no trata el Referer como cabecera sensible. Así, el `logger.exception` de `_send_confirmation` produce un evento con el cuerpo (`email`) y las variables `sub` (cuyo repr es el correo), `confirm_url` y `unsub_url`, con los dos tokens en claro (TAR-4), y un 500 en una propuesta sin adjunto manda el nombre, el correo y el texto. Además, `before_send` falla abierto: ante una excepción, devuelve el evento sin redactar. Fuera de Sentry, el sitio responde con `Referrer-Policy: same-origin`, así que los estáticos, el POST de los formularios de confirmación y de baja y el buscador htmx (`HX-Current-URL`) llevan la URL con el token, y el filtro del Caddyfile solo reescribe `request>uri`, no las cabeceras.

**Evidencia.**

- `backend/config/settings.py:327-337` — `sentry_sdk.init` sin `include_local_variables`, `max_request_body_size`, `event_scrubber` ni `data_collection`.
- `backend/config/redaction.py:28, 39-52, 55-65` — la regex, `before_send` (con `except: pass`) y `before_breadcrumb`.
- `backend/apps/community/views.py:85-96` y `backend/apps/community/models.py:43-44` — las URL con token como variables y el `__str__` que devuelve el correo.
- `backend/apps/community/tasks.py:7-38` y `backend/apps/submissions/forms.py:90` — las variables de la tarea y los campos personales del envío.
- `infra/caddy/Caddyfile:22-30, 87-95` — los dos filtros solo reescriben la URI.
- `backend/templates/base.html:11-13, 49-61, 102, 161`, `backend/templates/community/newsletter_confirm.html:21` y `newsletter_unsubscribe.html:15` — estáticos, buscador y formularios que envían el Referer.
- sentry_sdk 2.72.0 en el contenedor (`integrations/_wsgi_common.py`, `consts.py`, `scrubber.py`, `client.py`) — los valores por defecto citados.

**Por qué importa a futuro.** El dueño activa `SENTRY_DSN`, como recomienda la plantilla. Redis cae una hora y cada alta en el boletín dispara el registro de error de `_send_confirmation`: el evento lleva el correo y los dos enlaces con token, y quien lea el proyecto de Sentry puede confirmar o dar de baja suscripciones ajenas. La prueba existente arma a mano un evento con solo dos campos y no lo detecta.

**Recomendación.** Antes de definir `SENTRY_DSN`:

- En `sentry_sdk.init`: `include_local_variables=False`, `max_request_body_size="never"` y `EventScrubber(denylist=DEFAULT_DENYLIST + ["email", "author_email", "author_name", "body", "title", "confirm_url", "unsub_url", "next", "sub"], recursive=True)`.
- En `before_send`, quitar de `request.headers` el Referer y `Hx-Current-Url`, y `request.data`; ante una excepción, devolver None en lugar del evento crudo.
- Servir las páginas de confirmación y de baja con `Referrer-Policy: no-referrer` y no meter en `next` la ruta con token; añadir `request>headers>Referer` y `request>headers>Hx-Current-Url` al filtro de Caddy.
- Una prueba con un transporte de prueba del SDK que provoque errores en el alta y en un envío y compruebe que en el evento serializado no aparecen ni el correo ni los tokens.

Lo de fondo es sacar el token de la ruta: que el enlace lo canjee y redirija a una URL sin secreto.

**Matiz de la verificación.** Severidad de alta a media: Sentry es opcional y no consta que esté activo, el destinatario es la cuenta del dueño y el daño de un token se limita a confirmar o dar de baja una suscripción. El cuerpo solo se adjunta si mide 10 KB o menos, así que un envío con adjunto lo pierde por tamaño. En las vistas de confirmación y baja, la variable `token` sí la enmascara la lista; la fuga va por el repr de `request` y por `sub`. La integración de Celery ya sustituye los argumentos de la tarea en `extra`. Lo del Referer en Caddy queda dentro del VPS: rompe la redacción declarada, pero quien lee esos logs ya tiene la base. Que `before_send` falle abierto es higiene, porque solo hace operaciones simples sobre un diccionario.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-21, «test de captura de Sentry». El hallazgo contradice la decisión: qa-21 descartó probar Sentry por ser un opt-in «estándar y bien entendido» y, si se retomaba, iba a afirmar solo `send_default_pii=False`; pero aun con ese valor el SDK envía cuerpos, variables locales y cabeceras. Conviene reabrirla, cubriendo `before_send` y las variables locales.

#### RES-4 · Logs: worker y beat pierden el formato JSON y la redacción, gunicorn escribe texto plano y no hay rotación

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Celery tiene `worker_hijack_root_logger=True` y el proyecto no conecta la señal `setup_logging`: en worker y beat, Celery vacía los handlers del logger raíz y pone los suyos, así que el JsonFormatter y el RedactTokensFilter de `LOGGING` no rigen allí (reproducido: tras `setup_logging_subsystem()`, el raíz queda sin filtro ni formateador JSON). Las líneas de reintento de Celery ya escriben la dirección del suscriptor dentro de la excepción SMTP (`Retry in 2s: SMTPRecipientsRefused({'persona@ejemplo.cl': …})`), en contra de la intención declarada en la vista. Gunicorn no recibe configuración de log y escribe sus errores (incluidos los avisos de procesos muertos) en texto plano junto al JSON de Django, aunque la plantilla promete que «los logs salen en JSON con DEBUG=0». Ningún servicio del compose define `logging:` con `max-size` o `max-file`: con el driver json-file por defecto, los logs crecen sin límite en el disco del VPS, el mismo de PostgreSQL, los medios y los respaldos, salvo que el daemon de Docker tenga opciones de rotación, que no están en el repositorio. Y hay una trampa para quien lo corrija: el JsonFormatter solo redacta los extras de tipo cadena, y Celery adjunta a cada línea «Task … received» y a cada fallo un extra `data` con los argumentos de la tarea.

**Evidencia.**

- `backend/config/celery.py:1-9` — sin receptor de `setup_logging`.
- `backend/config/settings.py:293-315` — el handler raíz con formato JSON y filtro de redacción, que Celery reemplaza.
- `docker-compose.yml:52-69` y `docker-compose.prod.yml:14-39` — worker y beat con `-l info`; gunicorn sin configuración de log.
- `.env.prod.example:83-89` — la promesa del JSON (85).
- `backend/config/logformat.py:43-48` — solo redacta extras de tipo cadena; reproducido: un `data` con los argumentos sale con el token en claro.
- `backend/apps/community/views.py:85-96` — la intención de dejar la dirección fuera del log (95).
- `grep -n "logging:\|max-size" docker-compose*.yml` no encuentra nada.

**Por qué importa a futuro.** Un agente sigue la recomendación obvia y pone `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` para tener JSON en el worker. Desde ese despliegue, cada «Task … send_confirmation_email received» sale en JSON con el correo y los enlaces de confirmación y de baja (este, permanente) sin redactar, y quien lea `docker logs` puede dar de baja a cualquier suscriptor. Mientras tanto, sin `max-size`, el log de acceso de Caddy y los de worker y beat siguen creciendo en el disco de la base y de los respaldos.

**Recomendación.** En este orden:

1. Que el JsonFormatter redacte de forma recursiva (diccionarios, listas, tuplas) o descarte el extra `data` de Celery, con su prueba.
2. Después, conectar `celery.signals.setup_logging` a `dictConfig(settings.LOGGING)`, o poner `CELERY_WORKER_HIJACK_ROOT_LOGGER = False` junto con `CELERY_WORKER_REDIRECT_STDOUTS = False`.
3. Pasar a gunicorn `--log-config-dict` con el mismo formateador.
4. Un ancla `x-logging: &logging {driver: json-file, options: {max-size: "10m", max-file: "5"}}` aplicada a todos los servicios.
5. Pruebas: tras `app.log.setup_logging_subsystem()`, el handler raíz conserva el filtro de redacción.

**Matiz de la verificación.** La exposición actual es menor de lo que sugiere el texto: el formato de Celery no imprime los extras, así que hoy las URL con token no aparecen en el log del worker. El correo sí aparece en las líneas de reintento, pero eso no se debe a perder el filtro (que solo redacta rutas con token): es un problema aparte de datos personales en el log. Aplicada tal cual, la recomendación obvia crearía una fuga peor que la actual; por eso la redacción recursiva va primero. La rotación depende de una configuración del VPS que no está en el repositorio, y «en meses» depende del tráfico. Lo de Sentry se dedujo de valores por defecto verificados, sin ejecutarlo contra Sentry.

#### RES-5 · Redis hace de caché y de broker a la vez con noeviction, claves sin caducidad y un envoltorio de degradación parcial

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El compose dice «noeviction: … No se usa como caché», pero en producción settings usa la base 2 del mismo Redis como caché. `noeviction` se aplica a toda la instancia: si se llena, Redis rechaza también las escrituras del broker. La única clave de la aplicación (`color-de-borde:*`) se guarda sin caducidad y cachea también los fallos (TAR-6). Celery guarda en la base 1 resultados que nadie lee. Y ResilientRedisCache envuelve solo cinco métodos de RedisCache (`add`, `get`, `set`, `delete` e `incr`): `get_many`, `set_many`, `delete_many`, `has_key`, `touch` y `clear` siguen propagando `RedisError`.

**Evidencia.**

- `docker-compose.yml:22-26` y `docker-compose.prod.yml:115-125` — el comentario, `maxmemory 256mb` y `noeviction` para toda la instancia.
- `backend/config/settings.py:203-211, 238-257` — broker en la base 0, resultados en la 1 y caché en la 2.
- `backend/apps/media/models.py:265-286` — la clave sin caducidad, que también guarda el `""` de un fallo.
- `backend/config/cache.py:36-74` — los cinco métodos envueltos.
- `backend/apps/showcase/models.py:229-237` y `backend/tests/test_resilience.py:14-62` — el lomo del estante lee la caché, y ninguna prueba de resiliencia cubre la portada.

**Por qué importa a futuro.** Un agente optimiza la portada leyendo los ocho colores con `cache.get_many()`. Las pruebas pasan, porque usan LocMem y la prueba de resiliencia no cubre la portada, y en la siguiente caída de Redis la portada responde 500 en vez de pintar los lomos en un color neutro. El comentario falso tiene además un riesgo inverso: quien vea la caché en Redis y lea «No se usa como caché» puede cambiar la política a `allkeys-lru`, que expulsaría mensajes del broker.

**Recomendación.** Separar la caché en otro servicio Redis con `allkeys-lru` y su propio `maxmemory`, dejando `noeviction` solo al broker. Como mínimo, prohibir `timeout=None` (la caducidad por defecto de Django ya es de 300 s) y dar caducidad y versión a la clave del color (TAR-6). `CELERY_TASK_IGNORE_RESULT = True`. Envolver de forma genérica todos los métodos públicos de RedisCache, con una prueba que los compare con los de la clase original. Corregir el comentario del compose.

**Matiz de la verificación.** Los resultados de Celery caducan al día (unas 582 claves de unos 300 bytes en desarrollo; en producción, menos de medio megabyte): son desperdicio, no un riesgo. El escenario de un `cache_page` o un `get_or_set` sin caducidad era falso: Django aplica 300 s por defecto y `cache_page` exige una caducidad; solo un `None` explícito crea claves permanentes. Que la caché llene 256 MB es improbable. El camino más plausible hacia un Redis lleno es el propio broker: con el worker atascado durante semanas sin aviso (RES-6), beat encola un mensaje por minuto sin caducidad; entonces `noeviction` rechaza también las escrituras de la caché, el envoltorio las degrada y el límite de tasa, que falla cerrado, deja limitados para todos el buscador, el boletín y los envíos. Los métodos sin envolver que tocan Redis son seis.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), «CACHES → Redis (db 2) en prod… Seguro con noeviction gracias a los TTLs», y §1 (UX), D28. El hallazgo contradice la decisión: compartir un Redis con `noeviction` se justificó porque todas las claves caducaban, y D28 introdujo una que no caduca. Solo sigue siendo razonable si toda clave caduca o si la caché se separa del broker.

#### RES-6 · Salud y alertas: /readyz/ incompleto y mudo, healthchecks que nadie consume y ningún aviso de error por defecto

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `_db_ok` y `_broker_ok` hacen `except Exception: return False` sin registrar la causa. `/readyz/` comprueba la base y el PING del broker, pero no el worker ni beat, que son las piezas que fallan en silencio (el correo, la publicación programada, la purga semanal). Tampoco comprueba las migraciones pendientes (OPE-1) ni el espacio en disco. Los healthchecks del compose solo marcan «unhealthy»: `restart: unless-stopped` no reinicia contenedores enfermos, y nada los vigila. No hay `ADMINS` ni otro canal de aviso, y Sentry es opcional; aun así, `500.html` promete «Ya quedó registrado y lo estamos mirando». Además, `/readyz/` es público y abre una conexión nueva a Redis en cada petición.

**Evidencia.**

- `backend/apps/content/views.py:474-520` — `healthz` trivial; `_db_ok` y `_broker_ok` sin registro; `readyz` solo con la base y el broker, con `redis.from_url` por petición.
- `backend/config/urls.py:14-15` e `infra/caddy/Caddyfile:76-77` — las sondas, públicas y sin restricción.
- `docker-compose.prod.yml:55-65, 76-84, 95-103` — healthchecks de web, worker y beat, con `restart: unless-stopped`; nada actúa sobre el estado unhealthy.
- `docker-compose.prod.yml:26-29, 71, 147-148` y `docker-compose.yml:52-69` — los plazos de apagado, el límite de memoria del worker y dependencias sin condición de salud.
- `backend/templates/500.html:30-33` — la promesa.
- `backend/config/settings.py:211-222, 317-337` — entradas de beat sin caducidad; Sentry solo con `SENTRY_DSN`; ningún archivo define `ADMINS`.
- `infra/backup/backup.sh:13-20, 61-63` — el único aviso de «hombre muerto» del sistema, y solo cubre los respaldos.

**Por qué importa a futuro.** Tras un corte de red o un reinicio de Redis, el worker sigue vivo pero deja de consumir, o beat deja de despachar. Docker lo marca unhealthy y no hace nada; `/readyz/` sigue respondiendo 200, porque solo prueba la base y el PING. El poema programado para el viernes se queda en «Programado», invisible en el sitio, y los correos de confirmación se acumulan en la cola. Sin Sentry, sin `ADMINS` y sin monitor externo, nadie se entera hasta que una integrante pregunta por qué no apareció su texto.

**Recomendación.**

- Registrar la causa en cada comprobación (`logger.warning("readyz: base no disponible: %s", exc)`).
- Un latido de punta a punta: que `publish_due_items`, que corre cada minuto, guarde una marca de tiempo y que `/readyz/` falle si tiene más de cinco minutos; así se prueban beat, broker y worker a la vez. Otra opción es que la tarea haga ping a una URL tipo healthchecks.io, como el respaldo. Y una comprobación de negocio barata: «no hay piezas programadas vencidas hace más de cinco minutos».
- `checks["migraciones"]` (un `MigrationExecutor(connection).migration_plan(...)` vacío) y `checks["disco"]` (`shutil.disk_usage` sobre los medios públicos y privados).
- Un monitor externo apuntado a `/readyz/`.
- Exigir Sentry en producción, o advertirlo en envguard, o ajustar el texto de la página 500.
- Dejar escrito que Compose no se recupera solo de un estado unhealthy (si se quiere, un contenedor tipo autoheal), y fijar `stop_grace_period` por encima de los plazos de gunicorn y Celery.

**Matiz de la verificación.** El ejemplo de «el worker muere por falta de memoria» está casi mitigado: si muere el proceso principal, el contenedor termina y se reinicia, y si muere un hijo, se reemplaza. El fallo silencioso real es el cuelgue (un proceso vivo que no consume, un beat que no despacha) o un bucle de reinicios. «Ya quedó registrado» es cierto (el 500 queda en el log JSON); lo falso, sin Sentry, es «lo estamos mirando». Que `/readyz/` sea público tiene poco impacto: hace un `SELECT 1` y un PING y solo revela dos booleanos. Comprobar migraciones y disco son mejoras, no defectos de la sonda.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, #27 (restringir `/readyz` al monitor, pendiente de la capa de monitoreo), §2, «Alerta de fallo de respaldo», y el bloque de CI prod-runtime (diferido conocido). La capa de monitoreo estaba diferida, y por eso nadie consume la sonda ni los healthchecks. Pero el diferido solo trataba de restringir el endpoint, no de lo que comprueba ni de registrar la causa: el hallazgo amplía ese pendiente.

#### RES-7 · No hay plazos de extremo a extremo: gthread no corta peticiones colgadas y la base no tiene timeouts

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Con `--threads`, gunicorn usa workers gthread, cuyo bucle principal sigue avisando que está vivo aunque todos los hilos estén ocupados (verificado en gunicorn 26.2): `--timeout 30` no mata peticiones colgadas, y era el único plazo que tenía la aplicación. PostgreSQL corre con `statement_timeout=0` y `lock_timeout=0` (verificado con SHOW), `DATABASES` no tiene `OPTIONS` y rige el `connect_timeout` por defecto de psycopg, de 130 s. La caché no fija timeouts y rigen los 5 s de redis-py, multiplicados por las operaciones de la portada (TAR-8). El `reverse_proxy` de Caddy no tiene `response_header_timeout`: el cliente se corta a los 60 s, pero el hilo de gunicorn sigue ocupado. El comentario del Caddyfile aún dice que gunicorn corre con workers sync.

**Evidencia.**

- `docker-compose.prod.yml:4-7, 19-27, 43, 55-65` — tres workers de cuatro hilos, `--timeout 30` y el healthcheck de web.
- gunicorn 26.2.0 en el contenedor, `workers/gthread.py:306-319, 400-427` y `config.py:117` — `notify()` en cada vuelta sin mirar el pool; con hilos, la clase es gthread.
- `backend/config/settings.py:113-123, 242-252` — `DATABASES` sin `OPTIONS` y `CACHES` sin timeouts.
- psycopg, `conninfo.py:23, 123-146`, y Django, `db/backends/base/base.py:249, 591-616` — el `connect_timeout` por defecto y cómo se descubre una conexión muerta.
- redis-py y Django en el contenedor — 5 s por operación sin reintentos; medido: una lectura contra una dirección sin ruta tarda 5,02 s.
- `infra/caddy/Caddyfile:4-16, 77` — timeouts del servidor, el comentario de «workers de tipo sync» y el proxy sin transporte configurado.

`grep -rn "statement_timeout\|connect_timeout\|socket_timeout\|CONN_HEALTH_CHECKS" backend` solo encuentra la sonda `readyz`.

**Por qué importa a futuro.** El proceso de Redis se congela sin rechazar conexiones (un disco que no responde, un contenedor pausado). Cada lectura y escritura del color de borde espera 5 s y la portada tarda unos 80 s; una docena de visitas ocupa los 12 hilos, Caddy corta a los clientes a los 60 s, gunicorn no mata nada y web pasa a unhealthy sin que nadie lo reinicie. El sitio vuelve solo cuando Redis responde. Otra variante: un agente introduce una consulta lenta sin índice, y sin `statement_timeout` cada petición que la dispara retiene un hilo mientras dura.

**Recomendación.** En `DATABASES`, `"CONN_HEALTH_CHECKS": True` (REN-8) y `"OPTIONS": {"connect_timeout": 5, "options": "-c statement_timeout=15000"}`, configurables por entorno. El `lock_timeout` conviene fijarlo en la sesión de `migrate` (el remedio estándar para que un cambio de esquema no espere detrás de una transacción larga, como el `pg_dump` del respaldo) y no en toda la aplicación, donde convertiría esperas de milisegundos en errores. En `CACHES`, timeouts de 0,5 a 1 s, porque la caché es prescindible. Dejar escrito junto al ajuste de hilos que, con gthread, `--timeout` no es un plazo por petición, y corregir el comentario del Caddyfile.

**Matiz de la verificación.** Es falso que `/healthz/` siga en «ok» con todos los hilos bloqueados: pasa por el mismo pool, el healthcheck falla y el contenedor queda unhealthy; lo cierto es que nadie actúa sobre ese estado. La «ráfaga de 500» tras reiniciar PostgreSQL está exagerada: solo reutilizan una conexión muerta los hilos que la abrieron en los 60 s anteriores, unos pocos, y en la búsqueda el `except` los convierte en «sin resultados». Con tablas tan pequeñas, un cambio de esquema bloquea milisegundos. `response_header_timeout` en Caddy solo da al cliente un error antes: no libera el hilo. Con Redis detenido (y no colgado), el fallo es inmediato: la portada respondió en 0,3 s.

#### RES-8 · Las imágenes se decodifican a tamaño completo sin tope de píxeles, también en la portada pública cuando falla la caché

**Severidad:** media · **Esfuerzo:** M · **Confianza:** media · **Verificación:** parcial

**Qué pasa.** Las tres rutas que abren imágenes decodifican el original completo en el hilo de la petición: el guardado del recurso (limpieza y derivados), las copias de portada (en RGBA, seis anchos por dos formatos, con un redimensionado por formato) y `_medir_color_de_borde`, que corre en la portada pública por cada tapa que no está en caché. `img.draft()` solo reduce JPEG: un PNG o un WebP se decodifica entero. No hay validación de dimensiones: Pillow solo avisa por encima de 89 MP, y Caddy limita bytes, no píxeles. Medido en el contenedor: un PNG plano de 48 MP, de 160 KB, llega a 569 MB de pico y tarda entre 1 y 1,3 s en la ruta del color de borde; un JPEG de 48 MP, de 750 KB, llega a 387 MB en la ruta de los derivados. El contenedor web tiene 768 MB por defecto, para tres procesos de cuatro hilos.

**Evidencia.**

- `backend/apps/media/models.py:58-63, 171-181, 231-236, 252-263` — limpieza y derivados con `load()` completo dentro de `save()`.
- `backend/apps/media/models.py:113-145` — copias de portada: `load()`, `exif_transpose` y conversión, con dos redimensionados por ancho desde la imagen completa.
- `backend/apps/media/models.py:265-297` — el color de borde: si falta en la caché, mide; `draft()` solo reduce JPEG.
- `backend/apps/showcase/models.py:107-114, 229-237` y `backend/templates/content/home.html:190-196` — el lomo de cada publicación del estante pide el color.
- `backend/apps/content/views.py:73, 163-167` — hasta ocho publicaciones en el estante.
- `docker-compose.prod.yml:19-25, 48, 117` — tres workers de cuatro hilos y 768 MB por defecto.

**Por qué importa a futuro.** Una integrante sube como tapa de una publicación destacada un PNG plano de 8000×6000 px, que pasa el tope de 12 MB de Caddy. En la primera visita a la portada, la medición del color de esa tapa pide unos 570 MB en un solo hilo; con los otros procesos vivos, el contenedor supera el límite y el kernel mata ese proceso antes de guardar el color en la caché. Cada visita siguiente, bots incluidos, repite la medición: la portada da 502 de forma intermitente hasta que alguien cambie la tapa. Con Redis caído pasa lo mismo con todas las tapas grandes que no sean JPEG. En el panel, reemplazar la imagen de portada por una muy grande puede matar el proceso a mitad del guardado y, por DAT-4, dejar la fila apuntando a un archivo ya borrado.

**Recomendación.** Lo barato primero: bajar `Image.MAX_IMAGE_PIXELS` (por ejemplo a 40 MP) en `MediaConfig.ready()`, para que Pillow falle con `DecompressionBombError`, y validar las dimensiones en el formulario leyendo solo la cabecera (`Image.open(f).size`, sin `load()`). Calcular el color de borde una sola vez al guardar el recurso y guardarlo en una columna (TAR-6), o al menos aplicar `reduce()` o `thumbnail()` antes de convertir. Encadenar las copias, cada ancho a partir del anterior y con un solo redimensionado por ancho para ambos formatos. Mover los derivados y las copias de portada a una tarea con `transaction.on_commit` (TAR-2) es opcional.

**Matiz de la verificación.** Con un Redis lleno (`noeviction`), los colores ya guardados se siguen leyendo: la medición en cada visita solo ocurre con Redis caído o cuando, como en el escenario, el proceso muere antes de guardar el color. Las tapas JPEG pasan por `draft()` y cuestan poco (unos 29 MB): el riesgo público es de las tapas PNG, WebP o AVIF grandes, y hoy las ocho tapas son JPEG de 1,4 MP. Una tapa de tamaño libro a 300 ppp (de 4 a 9 MP) no provoca el problema: hacen falta unos 25-30 MP o más en PNG o WebP. El fallo es transitorio, porque gunicorn vuelve a levantar el proceso. Severidad de alta a media.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D28 (color medido «una vez por archivo» y guardado en la caché) y D18 (las copias de la obra) (decisión relacionada). La medición de D28 se pensó para hacerse una sola vez, pero, si falta en la caché, corre en la petición pública y decodifica el original sin tope. Sigue siendo razonable si la medición pasa al guardado o a una tarea, con un límite de píxeles.

#### RES-9 · Los fallos reales se registran como WARNING: invisibles para Sentry, ruidosos en el log y, en el buscador, ocultan errores de programación

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** En todo el código de aplicación hay una sola llamada de nivel ERROR (`community/views.py:96`); los demás fallos usan `logger.warning(..., exc_info=True)`, y la integración de logging de Sentry solo crea eventos desde ERROR (los WARNING llegan como migas, no como eventos). Tres casos:

1. El buscador captura cualquier `DatabaseError`. La razón que da el comentario, un término que el motor de texto completo rechace, nunca aplicó: `SearchQuery` usa `plainto_tsquery`, que acepta cualquier texto, y el byte NUL ya se quita antes. Lo que atrapa son errores de la UNION por nombre o una conexión muerta, y los convierte en «sin resultados».
2. ResilientRedisCache registra un WARNING con la traza completa en cada operación fallida: con Redis caído, la portada genera 16 trazas por visita y ningún evento, y los usuarios leen «Demasiados intentos…» en el alta y en los envíos.
3. Si falla el borrado del manuscrito privado de un envío, la fila se borra igual y el archivo queda huérfano, con solo un WARNING.

**Evidencia.**

- `backend/apps/content/views.py:414-416, 425, 441-464` — el NUL ya se quita (416); el `try` envuelve la búsqueda por texto y la UNION (455).
- El SQL que genera `SearchQuery` en el shell — usa `plainto_tsquery` incluso con `& | ! :* (`.
- Commits `98457c2` y `cf37da1` — el `except` entró cuando ya se usaba `plainto_tsquery`, y después se metió la UNION dentro del mismo `try` sin tocar el comentario.
- `backend/config/cache.py:18-21, 36-74` y `backend/config/logformat.py:40-42` — cinco WARNING con traza, y el formateador las incluye completas.
- Medido con la caché apuntando a un puerto sin escucha: `GET /` responde 200 en 0,3 s con 16 WARNING, y el buscador muestra «Demasiadas búsquedas seguidas…» con 2.

**Por qué importa a futuro.** Una consulta cancelada por un futuro `statement_timeout` (RES-7), o un error dependiente de datos en una parte de la UNION, hacen que la búsqueda de personas y actividades devuelva vacío sin un solo evento en Sentry. Con Redis caído, el log se llena de trazas sin que la web genere ningún aviso.

**Recomendación.** WARNING para lo esperado y manejado, sin traza; `logger.exception` o ERROR para lo inesperado. En el buscador, capturar solo `OperationalError` (o limitar el `try` al bloque de texto completo) y registrar como ERROR. En la caché, un ERROR una vez por intervalo y el resto sin traza, exponiendo la marca del último fallo para que `/readyz/` la use y para mostrar «el servicio no está disponible» en vez de «demasiados intentos». En filecleanup, ERROR con el modelo, el pk y el nombre del archivo, y un comando de barrido de huérfanos privados.

**Matiz de la verificación.** «Invisibles para Sentry» solo vale si `SENTRY_DSN` está definido. «Un fin de semana con Redis caído sin que nadie reciba aviso» exagera: la caché comparte servidor con el broker, y worker y beat registran ERROR al perder la conexión, el healthcheck del worker falla y `/readyz/` da 503; lo cierto es que la web no avisa por sí misma. Tampoco se sostiene que la UNION pueda romperse «solo con ciertos datos»: los tipos se resuelven al analizar la consulta y `test_search.py` lo detectaría; lo que oculta el `except` son errores de datos futuros y, sobre todo, conexiones muertas o cancelaciones. Fallar cerrado ante Redis caído es una decisión documentada y sensata; solo confunde el texto del mensaje. Severidad de media a baja.

#### RES-10 · Comandos de mantenimiento con fallos parciales mudos o en cascada

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `purge_stale_data` borra los adjuntos en un bucle y después las filas, sin aislar los pasos: un fallo al borrar un archivo aborta también la purga de suscriptores y de registros de axes, y la tarea semanal no reintenta, así que los datos personales se retienen otra semana. El bucle además es redundante: la señal `post_delete` de filecleanup ya borra el adjunto y registra el fallo. `generate_image_derivatives` aborta en el primer recurso que lanza una excepción, sin decir cuál, y cuenta como verificados los que fallaron en silencio. `setup_groups` omite sin avisar los permisos de `AUTHOR_PERMS` que no existen. Y `datos_de_desarrollo exportar` borra la carpeta versionada antes de saber si podrá leer todos los archivos.

**Evidencia.**

- `backend/apps/submissions/management/commands/purge_stale_data.py:61-71` — el bucle de `file.delete()` y los borrados en serie, sin `try`.
- `backend/apps/media/filecleanup.py:21-27, 42-50` y `backend/apps/submissions/apps.py:16` — la señal que ya borra el adjunto y tolera el fallo.
- `backend/apps/submissions/tasks.py:5-12` y `backend/config/settings.py:213-222` — la tarea semanal, sin reintentos.
- `backend/apps/media/management/commands/generate_image_derivatives.py:15-20` — sin `try` por recurso.
- `backend/apps/people/management/commands/setup_groups.py:63-70` y `backend/tests/test_admin_hardening.py:119-122` — `if perm:` descarta en silencio, y la prueba solo exige que haya algún permiso.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:105-123` — `rmtree` antes de leer los archivos.

**Por qué importa a futuro.** Un adjunto del almacén privado queda con permisos que el worker no puede borrar. El lunes a las 04:30, la purga lanza `PermissionError` dentro del bucle y no se purga nada: ni los envíos, ni los suscriptores pendientes o dados de baja, ni los registros de axes. El fallo se repite cada semana hasta que alguien corrija los permisos, y el sitio incumple su propia política de retención con el error escondido en el log del worker.

**Recomendación.** En la purga, quitar el bucle explícito y dejar el borrado de los archivos a la señal, sacando el recuento de adjuntos de otra parte; aislar cada grupo con su `try` y `logger.exception`, salir con un código distinto de 0 si alguno falló y dar a la tarea `autoretry_for=(OperationalError,)`. En el comando de derivados, un `try` por recurso con el pk en el mensaje y un recuento de fallos. En `setup_groups`, una prueba que exija que se resuelvan todos los `AUTHOR_PERMS`, o un aviso al sembrar. En `exportar`, escribir en una carpeta temporal y sustituir al final.

**Matiz de la verificación.** Son siete comandos en `management/commands`, no ocho. En la purga no hace falta `on_commit`, porque `QuerySet.delete` ya es atómico. El fallo no deja «una línea» en el log: deja una traza en ERROR, y Sentry con Celery ya está cableado, aunque sea opcional. El caso de renombrar un modelo en `setup_groups` no lo provoca el descarte en producción, donde el grupo existente se conserva tal cual: solo afecta a siembras nuevas. Lo de `exportar` es higiene, porque la carpeta está versionada y se recupera con git.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), D2, la purga semanal de los lunes a las 04:30 (decisión relacionada). D2 confía la minimización de datos a esa purga, y un fallo con un solo adjunto aborta también la de suscriptores y de axes, sin reintento. La decisión es correcta; la purga necesita pasos aislados y aviso de fallo.

### 4.13 Dominio editorial: flujo de estados, visibilidad, permisos y admin (DOM)

#### DOM-1 · La máquina de estados tiene puertas laterales: la fecha editable, la tarea programada y save()

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `status` es de solo lectura en el panel, pero la editora puede cambiar `published_at` en cualquier estado. Puede dejar una pieza «Programada» sin fecha, justo lo que la guarda de «schedule» dice impedir: nunca se publicará sola. La tabla de transiciones tiene huecos: no hay forma de desprogramar (desde SCHEDULED solo existe «publish») y REJECTED es un callejón sin salida. Además, «publish» desde SCHEDULED conserva la fecha futura: la pieza es pública desde ya, porque ninguna vista mira `published_at <= now`, pero lleva fecha futura en el RSS, encabeza los listados y `ultima_publicacion()` anuncia «Actualizado el» con una fecha que no ha llegado. Hay más caminos que esquivan la máquina: `publish_due_items` reimplementa el cambio y fija la lista `(Article, Poem)`, igual que `ultima_publicacion` (ARQ-2), y nada en `EditorialItem.save()` impide fijar `status` a mano. En Recording y Collection, nada rellena `published_at` al publicar: un registro sin fecha sale el primero en el podcast (PostgreSQL pone los nulos primero en un orden descendente), sin `pubDate`, y queda fuera de «última publicación».

**Evidencia.**

- `backend/apps/content/admin.py:193-200` — `status` de solo lectura para todos; `published_at`, solo para quien no es editor. En el shell, el formulario de la editora incluye `published_at` como no obligatorio.
- `backend/apps/content/workflow.py:19-29, 67-72, 76-78` — SCHEDULED solo como origen de «publish», REJECTED sin salida, la exigencia de fecha futura solo al programar y la fecha que solo se fija si está vacía.
- `backend/apps/content/tasks.py:22-46` y `backend/apps/content/services.py:11-30` — las listas fijas de modelos; la «última publicación» se pinta en `content/home.html:230` y `showcase/dossier.html:50`.
- `backend/apps/media/feeds.py:77-92` y `backend/apps/media/models.py:384-385` — orden descendente por `published_at`, sin `pubDate` si falta, y una fecha que nada rellena.
- `backend/apps/content/models.py:87-89, 139, 256, 319-322, 331` y `backend/apps/content/views.py:42-57, 290-292` — fechas que admiten nulos, orden sin `nulls_last` y vistas que solo filtran por estado.
- `backend/tests/test_workflow.py:73-129` — nada sobre publicar ya una pieza programada a futuro ni sobre vaciar su fecha.
- `backend/apps/submissions/models.py:18-19` y `backend/apps/agenda/models.py:25-26` — tampoco hay restricciones de rango en las fechas de convocatorias y eventos.

**Por qué importa a futuro.** Una editora programa un poema para el lunes 3 de noviembre y el viernes pulsa «Publicar» para adelantarlo: sale al instante, encabeza `/poemas/` y la portada, el RSS lo anuncia con fecha del lunes y el cierre de la portada dice «Actualizado el 3 de noviembre de 2026». Si en vez de eso vacía la fecha para «cancelar» la programación, el formulario lo acepta (verificado) y la pieza queda «Programada» sin fecha para siempre, sin ninguna transición que la devuelva a «Aprobada».

**Recomendación.**

1. Validar en el modelo: `clean()` y un `CheckConstraint(condition=~Q(status__in=["published", "scheduled", "archived"]) | Q(published_at__isnull=False), name="%(app_label)s_%(class)s_fecha_si_publicado")` en Article y Poem. Desde Django 4.1 el ModelForm valida las restricciones, así que el panel mostrará un error y no un 500. Antes, una migración que corrija las filas que la violen. Es preferible a dejar `published_at` de solo lectura, que impediría corregir o retrofechar piezas legítimas.
2. Programar con la acción «schedule» mediante una página intermedia que pida la fecha.
3. Añadir «unschedule» (SCHEDULED → APPROVED) y, si se quiere, «reopen» (REJECTED → DRAFT).
4. En «publish», si `published_at` es futura, fijarla a ahora.
5. Que `publish_due_items` pase por `perform_transition` con un actor de sistema (ARQ-2), y obtener las subclases con `[m for m in apps.get_models() if issubclass(m, EditorialItem)]`, también en `ultima_publicacion` (que debe seguir sumando Recording, que no es una pieza editorial).
6. Rellenar `published_at` en el `save()` de Recording y Collection cuando pasan a publicados sin fecha, y ordenar con `F("published_at").desc(nulls_last=True)`.
7. Restricciones de rango para `closes_at > opens_at` y `ends_at >= starts_at`.

Opcional: que `EditorialItem.save()` rechace los cambios de `status` que no vengan de `perform_transition`.

**Matiz de la verificación.** «Puede cambiar la fecha sin que quede rastro» exagera: el admin registra un LogEntry con el usuario, la hora y el campo cambiado; lo que falta es el valor anterior y una entrada en la bitácora editorial. Los casos con fechas nulas son latentes en desarrollo: no hay registros ni colecciones publicados sin fecha ni piezas publicadas con fecha futura.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, qa-23 (decisión relacionada). La publicación programada depende solo de `published_at`, y la editora puede vaciarla o cambiarla: una pieza programada sin fecha no se publica nunca. El análisis de qa-23 sigue valiendo para el horario de verano, pero no protege la fecha.

#### DOM-2 · Publicar y descargar envíos depende del nombre del grupo, no de los permisos de Django

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El panel solo compone con los permisos de Django en `has_change_permission` y `has_delete_permission`. Las nueve acciones de transición no declaran `allowed_permissions`, y `perform_transition` decide con `is_editor()`, que mira `groups.filter(name__in=["admin", "editor"])`. `submission_file`, que entrega adjuntos con datos personales, también usa solo `is_editor`. Consecuencias: retirar `change_article` y `change_poem` no impide publicar, despublicar ni archivar desde el listado (basta con poder verlo); retirar `view_submission` no impide descargar los adjuntos recorriendo los pk; y quien tenga todos los permisos de modelo pero esté fuera de esos grupos es tratado como autor. Los nombres «admin» y «editor» son literales repetidos sin una constante compartida: renombrar el grupo en el panel quita los poderes sin ningún aviso. Hay más casos del patrón: `SiteProfileAdmin.has_add_permission` sustituye el permiso en vez de componerlo, y el inline de notas editoriales deja editable su autor (DOM-6).

**Evidencia.**

- `backend/apps/content/permissions.py:9-13` — `is_editor` por nombre de grupo.
- `backend/apps/content/workflow.py:32-37, 57-58` — la guarda de la transición: grupo o dueño, nunca `has_perm`.
- `backend/apps/content/admin.py:140-164, 214-248` — `get_actions` filtra solo por grupo y las acciones no tienen `allowed_permissions`; simulado: sin los permisos de cambio y borrado, las nueve siguen disponibles.
- `backend/apps/content/admin.py:179-191` — la composición correcta, con un comentario que promete que revocar el permiso basta.
- `backend/apps/submissions/views.py:48-57` y `backend/apps/submissions/admin.py:28-35` — simulado: con `view_submission` negado, la descarga responde 200 con el archivo; el enlace usa el pk entero.
- `backend/apps/people/management/commands/setup_groups.py:46-60` — los nombres de grupo, como literales.
- `backend/tests/test_admin_hardening.py:72-79` — «revocar surte efecto» solo afirma el cambio y el borrado, no las transiciones ni la descarga.

**Por qué importa a futuro.** Para proteger los datos de los envíos, el dueño quita `submissions.view_submission`, `content.change_article` y `content.change_poem` al grupo editor. Las editoras ya no ven el listado de envíos ni editan piezas, pero en el listado de artículos siguen viendo las nueve acciones y la transición las deja pasar, y `GET /envios/<pk>/archivo/` con pk 1, 2, 3… les entrega los manuscritos.

**Recomendación.** Declarar permisos propios en `EditorialItem.Meta.permissions` (por ejemplo `publish_%(class)s` y `review_%(class)s`) y que `_allowed` use `user.has_perm(...)` en lugar del nombre del grupo; declarar `allowed_permissions` en las acciones, con sus `has_publish_permission` y `has_review_permission`. En `submission_file`, exigir `request.user.has_perm("submissions.view_submission")`. Llevar los nombres de grupo a una constante única (AGE-2) o sacarlos de las decisiones de autorización. En los métodos del admin que se redefinen, componer siempre con `super()`. Una prueba que retire cada permiso al grupo editor y compruebe que la vista correspondiente responde 403 o 404 (PRU-4).

**Matiz de la verificación.** En Django los permisos son aditivos: no se le puede retirar a una editora un permiso que le da su grupo. En la práctica, o se retira al grupo entero, y entonces todas las editoras siguen pudiendo publicar y descargar, o se la saca del grupo con permisos sueltos, y entonces `is_editor` la trata como autora; eso refuerza el hallazgo. Renombrar grupos exige `auth.change_group`, que solo tiene el admin: la probabilidad es baja, aunque el fallo sería silencioso. El caso de SiteProfileAdmin hoy no tiene efecto, porque la fila única ya existe.

#### DOM-3 · No hay vista previa: para ver cómo queda un borrador hay que publicarlo

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Todas las fichas filtran por publicado sin distinguir al personal, y el panel ofrece «Ver en el sitio» también en los borradores: la editora, y también el superusuario, llega a un 404. Una prueba documenta la intención contraria («el editor necesita el enlace para comprobar cómo quedará») a la vez que fija el 404 con un cliente anónimo. En los poemas, la composición del verso (sangría francesa, estrofas, saltos) solo se ve en la ficha, y la única forma de revisarla es publicar.

**Evidencia.**

- `backend/apps/content/views.py:229-241, 301-307, 319-320, 342-343` — artículo, poema, colección y página filtran por publicado dentro de `get_object_or_404`.
- `backend/apps/media/views.py:11-12, 21-22`, `backend/apps/agenda/views.py:33-39` y `backend/apps/showcase/views.py:10-11, 22-25` — registro, evento y publicación, igual.
- `backend/tests/test_get_absolute_url.py:73-87` — el docstring con la intención y el 404 con cliente anónimo.
- `backend/apps/content/admin.py:66-72, 251-282` — en el shell, «Ver en el sitio» está activo en siete modelos y también para los borradores.
- `backend/static/css/site.css:756-765` y `backend/templates/content/poem_detail.html:54` — la composición del verso, solo en la ficha.
- `backend/apps/content/tasks.py:12-47` — la tarea publica sola cada pieza programada vencida.

En siete tipos de ficha, `grep -rni "preview\|vista previa" backend/apps backend/templates` no encuentra nada.

**Por qué importa a futuro.** El equipo se acostumbra a «publicar para mirar y despublicar». En ese minuto, la pieza entra en el sitemap y, si es un artículo, en el RSS (un registro, en el feed de podcast), y los lectores de feeds no la retiran al despublicar. Con la publicación programada, una pieza mal compuesta sale sola a la hora fijada sin que nadie la haya visto renderizada, sobre todo a ancho de teléfono.

**Recomendación.** Una vista previa solo para el personal. En las fichas, si `request.user.is_staff` y la persona puede ver la pieza en el panel (`has_view_permission` más el `get_queryset` del ModelAdmin), servir el borrador con una franja «Vista previa: no publicado», `<meta name="robots" content="noindex">` y `Cache-Control: private, no-store`. Alternativa: una ruta `/vista-previa/<ct>/<pk>/` y un `get_view_on_site_url` que apunte a ella mientras la pieza no esté publicada. Pruebas: mantener la del 404 para anónimos y añadir la del 200 para la editora y para la dueña de la pieza.

**Matiz de la verificación.** El RSS de 20 entradas solo incluye artículos: un poema publicado «para mirar» entra en el sitemap, no en un feed. En artículos y poemas, «publicar para mirar» exige aceptar y publicar, y repetirlo para volver; el hábito es más probable en los modelos con una simple casilla (registros, eventos, publicaciones, colecciones y páginas).

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4, «Article no tiene get_absolute_url» (cerrado; decisión relacionada). Ese cierre devolvió «Ver en el sitio» pensando en las piezas publicadas, y en un borrador lleva a un 404 porque no hay vista previa. La decisión sigue siendo correcta; falta completar el caso de lo no publicado.

#### DOM-4 · Despublicar no retira los archivos: Caddy sigue sirviendo el audio y los PDF

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `Recording.file` y `Publication.pdf` viven en `MEDIA_ROOT` con su nombre original, y Caddy los sirve directamente desde el volumen, sin pasar por Django. El estado `published` solo oculta la ficha: el archivo de un registro o de un libro sin publicar responde a quien tenga, o adivine, la URL. El feed de podcast ya repartió además la URL absoluta del enclosure a cada cliente. El propio código reconoce que despublicar debe poder deshacerse (`Poem.published_recording`), pero eso solo se cumple en el HTML. Borrar el registro o reemplazar su archivo sí lo borra del disco (filecleanup); despublicar, no.

**Evidencia.**

- `infra/caddy/Caddyfile:44-58` y `docker-compose.prod.yml:141` — `/media/` se sirve desde el volumen, montado en el proxy; el comentario reconoce que esas respuestas «NO pasan por Django».
- `backend/apps/media/models.py:336-341, 384` y `backend/apps/showcase/models.py:206-213` — nombres originales y un booleano de publicación.
- `backend/apps/media/feeds.py:77-80, 95-98` — el enclosure como URL absoluta.
- `backend/apps/content/models.py:270-281` — la reversibilidad, solo en el HTML.
- `backend/apps/submissions/models.py:7-9, 55` — el precedente del almacén privado.
- `backend/apps/media/filecleanup.py:42-91` — mitigación parcial: el borrado y el reemplazo sí retiran el archivo.

**Por qué importa a futuro.** Un participante retira su permiso y la editora desmarca «publicado» en su registro. La ficha pasa a 404 y el ítem sale del feed, pero la URL absoluta del archivo, ya repartida en el enclosure y en el reproductor, sigue respondiendo 200 desde Caddy a las aplicaciones de pódcast y a cualquier enlace compartido. Reproducido en desarrollo: `/registro/test-testcito/` da 404 y `/media/recordings/2026/08/5-audio.mp3`, 200. Lo mismo pasa con un PDF que un buscador ya indexó.

**Recomendación.** Servir esos dos campos por Django con comprobación de estado: una vista como `/archivo/registro/<slug>/` que dé 404 si no está publicado y delegue la entrega en Caddy (X-Accel-Redirect o `handle_response`) o use `FileResponse`. Alternativa: mover el archivo al almacén privado al despublicar y devolverlo al publicar. Como mínimo, nombres aleatorios en `upload_to` (uuid4) y renombrar al despublicar, y avisar en el panel de que despublicar no retira el archivo. Prueba: con el registro despublicado, la URL de su archivo deja de responder 200.

**Matiz de la verificación.** Un archivo que nunca se publicó solo queda expuesto si alguien adivina su nombre, porque Caddy no lista directorios; es plausible cuando el nombre coincide con el slug.

#### DOM-5 · El panel deja reescribir a mano estados que tienen flujo propio: el consentimiento del boletín y los envíos

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Fuera de las piezas editoriales, los modelos con estado no tienen guarda en el admin. El de suscriptores deja editar `status`, `confirmed_at`, `token` y `confirm_token`, y añadir suscriptores a mano: una editora puede dar de alta una dirección como «Confirmado» con una fecha inventada, saltándose el doble opt-in que las vistas hacen cumplir, y ve el token de baja de cada persona. El de envíos deja pasar `status` de cualquier valor a cualquier otro y editar el título, el cuerpo y el correo que escribió quien envió. Y ese estado está acoplado a la purga semanal, irreversible, que mide la antigüedad por `created_at` (TAR-3).

**Evidencia.**

- `backend/apps/community/admin.py:6-10` — en el shell: todos los campos editables, ninguno de solo lectura, alta permitida y solo la acción de borrar.
- `backend/apps/community/models.py:11-35` y `backend/apps/community/views.py:70-79, 99-122` — el doble opt-in que solo imponen las vistas.
- `backend/apps/submissions/admin.py:19-26` y `backend/apps/submissions/models.py:43-58` — cinco estados en un campo libre, sin transiciones.
- `backend/apps/people/management/commands/setup_groups.py:10, 76-81` — el editor tiene todos los permisos sobre suscriptores, envíos y convocatorias.
- `backend/apps/submissions/management/commands/purge_stale_data.py:39-50, 61-68` — la purga depende del estado.

**Por qué importa a futuro.** Una editora usa «Añadir suscriptor» para cargar a mano las direcciones de una lista en papel de un recital, con estado «Confirmado» y la fecha de hoy. Cuando se construya el envío del boletín filtrando por los confirmados, esas personas recibirán correo sin haber pasado por el doble opt-in, y `confirmed_at` no probará nada ante un reclamo por la Ley 21.719. En los envíos, alguien cambia por error a «Rechazado» uno recibido hace 200 días, y el lunes siguiente la purga lo borra con su adjunto.

**Recomendación.** En el admin de suscriptores: `readonly_fields` para `status`, `confirm_token_at` y `confirmed_at`, `exclude` de los dos tokens y `has_add_permission = False`, con una sola acción, «dar de baja», que deje constancia. En el de envíos: solo lectura para `author_name`, `author_email`, `title` y `body`; cambios de estado mediante acciones que fijen la fecha de resolución (TAR-3) y dejen registro con el valor anterior; y `reviewer` asignado automáticamente a quien revisa.

**Matiz de la verificación.** Hay que retirar «sin rastro» y «sin saber quién ni cuándo»: cada cambio hecho en el panel deja un LogEntry con el usuario, la hora y los campos cambiados, visible en «Historial». Lo que falta son los valores anterior y nuevo y una guarda de transiciones. Que la editora vea el token de baja tiene poco impacto, porque ya puede editar el estado. Devolver a «Confirmado» a alguien que se dio de baja anula su baja explícita y evita su purga.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), D2, el boletín con doble opt-in (decisión relacionada). D2 hace del doble opt-in la base del consentimiento, y el panel permite vaciar esa garantía. La decisión sigue siendo correcta; esos campos deberían ser de solo lectura.

#### DOM-6 · El «rastro inmutable» se borra junto con la pieza y sus notas se pueden atribuir a otra persona

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `EditorialTransition` se declara «rastro inmutable», pero solo lo es en la interfaz: ni el modelo ni la base lo protegen. La GenericRelation de `EditorialItem` hace que borrar un artículo o un poema (con la acción de borrado de la editora) borre en cascada su historial y sus notas. `actor` usa SET_NULL y no guarda el nombre: las transiciones de una cuenta borrada quedan con el actor vacío, igual que las automáticas de Celery. En las notas editoriales, `author` es un desplegable editable con todas las cuentas y no se rellena solo (el mismo patrón que ya se corrigió en `MediaAsset.uploaded_by`), y las notas se pueden editar y borrar desde el inline. La nota de una transición nunca se rellena desde el panel: solo la tarea programada escribe en ella, así que «Pedir cambios» llega a la autora sin ningún motivo.

**Evidencia.**

- `backend/apps/content/models.py:404-434` — el docstring «Rastro inmutable», sin `save()` ni `delete()` propios y con el actor en SET_NULL (416-423).
- `backend/apps/content/models.py:93-96` — las GenericRelation; el Collector programa el borrado de las transiciones con la pieza.
- `backend/apps/content/admin.py:100-114` — en el formulario de la editora, el autor de la nota es un desplegable con todas las cuentas, no obligatorio, y la nota se puede borrar.
- `backend/apps/content/admin.py:202-212` — `_run` llama a la transición sin nota.
- `backend/apps/content/tasks.py:40-45` — la transición automática, sin actor; en desarrollo, 3 de 15 transiciones tienen el actor vacío.
- `backend/apps/media/admin.py:10-18` — el contraste: `uploaded_by` de solo lectura y asignado al guardar.

**Por qué importa a futuro.** Una pieza polémica se borra «para limpiar» y con ella desaparece quién la aceptó y cuándo se publicó; queda solo el LogEntry genérico del borrado. Cuando haya que reconstruir una disputa de autoría o un error de publicación, el historial no estará, o no habrá forma de fiarse de quién escribió cada nota.

**Recomendación.** Guardar en cada transición una copia del título de la pieza y del nombre del actor, y sustituir la GenericRelation por una consulta, o impedir el borrado duro de piezas publicadas (usar «Archivar») y registrar una transición de borrado desde `delete_model` y `delete_queryset`. Que `EditorialTransition.save()` rechace las actualizaciones y `delete()` lance una excepción (idealmente, también un trigger `BEFORE UPDATE OR DELETE` en PostgreSQL). Un actor de sistema explícito para Celery. En el admin, un `save_formset` que ponga `author = request.user` en las notas nuevas, con el autor de solo lectura y sin poder editar ni borrar notas ajenas. Si se mantiene el diseño, que el docstring diga «no editable desde el panel».

**Matiz de la verificación.** Severidad de media a baja: el borrado no es silencioso, porque la confirmación lista «transiciones editoriales: 2» y el LogEntry conserva quién borró y qué. La cascada viene de la clave foránea original: es diseño heredado, no una regresión. La atribución falsa de notas solo la puede hacer el grupo editor, porque los autores no ven el inline. No hay notas en desarrollo y borrar cuentas es raro: el defecto más concreto es que las notas quedan sin autor por defecto.

### 4.14 Herramientas de desarrollo, datos de demostración y salud del repositorio (HER)

#### HER-1 · «datos_de_desarrollo exportar» manda al repositorio público borradores y subidas de prueba, y no tiene guarda de entorno

**Severidad:** alta · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** El docstring y el README prometen que «viaja solo el contenido público: lo que se ve en el sitio» y que los registros de prueba no viajan. El código hace otra cosa: `exportar` serializa todas las filas de los 28 modelos de `MODELOS` (`objects.order_by("pk")`) y solo excluye los registros cuyo slug empieza por `test-`; no mira `status`, `published` ni `active`. Tampoco comprueba `settings.DEBUG`, cosa que `cargar` sí hace. La lista blanca va por modelo y no por campo: cualquier campo nuevo de un modelo de la lista viaja solo (un teléfono, notas internas, un FileField). Los archivos se leen con `default_storage`, no con el almacén de cada campo. La copia versionada ya trae un texto archivado, uno en revisión y un poema en borrador, todos de demostración, y cuatro subidas manuales de prueba. La prueba que lleva el nombre de la garantía solo comprueba qué modelos aparecen, no qué filas. Y la prueba que exige que la copia cargue sobre el esquema actual obliga a reexportar la base de desarrollo, sin curar, cada vez que un cambio de modelo la rompe.

**Evidencia.**

- `backend/apps/content/management/commands/datos_de_desarrollo.py:6-11` — la promesa.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:29-59, 77-83` — `MODELOS`, con 28 entradas; el volcado sin filtro por fila y sin guarda.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:105-123, 125-127, 143` — los archivos de todas las filas, el `rmtree`, la lectura con `default_storage`; la guarda de `DEBUG` solo en `cargar`, que usa loaddata.
- `README.md:87-91` — «Solo viaja contenido público» y la invitación a reexportar.
- `backend/tests/test_datos_de_desarrollo.py:38-44, 47-56, 66-71` — compara modelos, busca correos y obliga a reexportar; nada mira el estado.
- `backend/datos_de_desarrollo/datos.json:2265, 2293, 2815` — `archived`, `in_review` y `draft`: 3 de los 23 textos y poemas; `734-735, 1308, 1322` y el recurso 10 — las subidas de prueba.
- `backend/apps/content/management/commands/seed_demo.py` — las tres filas no públicas son demostraciones del flujo editorial: hoy no se ha filtrado contenido real.

**Por qué importa a futuro.** El sitio entra en producción con poemas inéditos en borrador y reseñas en revisión. Para reproducir un fallo, alguien restaura un respaldo en su equipo con `restore.sh latest`, que trae la base y los medios. Semanas después, un cambio de modelo rompe la prueba de carga de la copia, y el agente, confiado en «Viaja solo el contenido público», ejecuta `exportar`. `datos.json` pasa a contener todos los artículos y poemas de producción en cualquier estado, y `media/`, los originales de cada imagen, audio y PDF que nombran. Ninguna prueba falla, el PR se fusiona sin revisión y los inéditos quedan en el historial de un repositorio público, que no se limpia sin reescribirlo. Para concursos y editoriales, un poema así deja de ser inédito.

**Recomendación.**

1. Filtrar por fila: en los modelos con estado, `published` o `active`, exportar solo lo público, más una lista explícita de slugs de demostración del flujo editorial (`DEMOS_NO_PUBLICADAS`). Exportar solo los recursos y archivos que referencien filas exportadas, tras decidirlo con el dueño (hoy la biblioteca de medios viaja entera a propósito y tiene 12 recursos sin referencia).
2. Una prueba que falle si `datos.json` tiene filas no públicas fuera de esa lista.
3. Una guarda que no dependa de `DEBUG`: que `exportar` se niegue si la base no parece de desarrollo, por ejemplo si algún suscriptor o envío no es de `@example.com`, o si falta una fila centinela que crean `cargar` y las siembras.
4. Una lista blanca por campo (`CAMPOS = {"people.Contributor": [...]}`) que falle si un modelo de la lista tiene campos sin clasificar, para que cada campo nuevo obligue a decidir.
5. Leer cada archivo con el almacén de su campo y negarse si no es el público.
6. Corregir el docstring y el README, y regenerar `datos.json`.

**Matiz de la verificación.** La guarda de `DEBUG` no cierra el escenario principal: una copia de producción restaurada en local corre con `DEBUG=1`, y en producción `exportar` no alcanza el repositorio, porque la imagen no lo monta; lo útil es el filtro por fila y la centinela. Leer con `default_storage` es un riesgo latente: hoy los cuatro FileField exportados usan el almacén público y el único privado no viaja; si eso cambiara, el comando fallaría cerrado, aunque después del `rmtree` (recuperable con git). Hoy el daño es nulo: las tres filas vienen de las siembras y las subidas de prueba no llevan EXIF. Que la carga con loaddata se salte el saneo es otro problema, de severidad baja (SEG-1). El README promete menos que el docstring, y lo que promete se cumple. Uno de los tres verificadores habría bajado la severidad a media; el panel la mantuvo en alta por mayoría, por tratarse de un riesgo futuro e irreversible.

#### HER-2 · Las herramientas de desarrollo viven en apps de producción, van en la imagen y se protegen con guardas copiadas y un --force que el propio error anuncia

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Cuatro comandos de desarrollo viven en `apps/content` y `apps/media`: `seed_demo`, `seed_textos_largos`, `seed_material_generico` y `datos_de_desarrollo`. Suman 1.902 líneas y 639 de las 3.128 sentencias que mide la cobertura (cerca del 20 %), más `seed_assets/` y `textos_largos/`. El `.dockerignore` del backend excluye las pruebas y los datos de desarrollo, pero no estos comandos, y la etapa de producción del Dockerfile hace `COPY . .`: en producción están disponibles (`manage.py help` los lista). Cada comando copia a mano su guarda (`if not settings.DEBUG and not options["force"]`): hay tres copias, una variante sin `--force` y `exportar` sin ninguna. El mensaje de error enseña cómo saltársela («Con DEBUG=0 exige --force explícito»), y `--force` es la vía normal de las pruebas, porque pytest-django corre con `DEBUG=False`. Esto haría `--force` en producción: `seed_demo` crea dos cuentas de staff (una en el grupo editor) con correo de un dominio ajeno, un suscriptor con un token fijo y un envío falso, y publica citas inventadas atribuidas a medios reales (El Mercurio de Valparaíso, Radio Universidad) y a un fondo público real como aliado; `seed_material_generico` pondría marcadores «provisional · reemplazar» en cada imagen vacía del contenido real, completaría las galerías reales con marcadores hasta seis fotos (su comentario dice lo contrario) y sustituiría el manifiesto si tiene menos de 40 palabras.

**Evidencia.**

- `backend/.dockerignore:26-35` y `backend/Dockerfile:27-34` — los comandos entran en la imagen de producción.
- `backend/apps/content/management/commands/seed_demo.py:58-74, 82-83, 222-231, 244-251, 565-603, 666-670` — la guarda y su mensaje, las cuentas de staff, el suscriptor y el envío falsos, las menciones de medios reales y el aliado.
- `backend/apps/content/management/commands/seed_textos_largos.py:241-249` — la segunda copia de la guarda.
- `backend/apps/media/management/commands/seed_material_generico.py:343-348, 363-387, 429-436, 458-461, 494-503` — la tercera copia, la mezcla de marcadores con fotos reales y el cambio del manifiesto.
- `backend/apps/content/management/commands/datos_de_desarrollo.py:77-127` — `exportar` sin guarda y `cargar` solo con `DEBUG`.
- `backend/tests/test_seed_demo_guard.py:19-31` — «Con --force sí corre (entornos de staging)».
- `backend/tests/test_seed_material_generico.py:91-95` — no ejercita el cupo por defecto de seis fotos.

**Por qué importa a futuro.** A un agente con acceso al VPS le piden «carga datos de ejemplo para que el dueño vea la portada». Ejecuta `seed_demo` en el contenedor de producción, recibe el error que sugiere `--force` y lo repite con `--force`. La portada pública pasa a mostrar menciones de prensa inventadas de medios reales y a un fondo estatal como aliado, ante pares y gestores, y las fichas reales quedan con rótulos «reemplazar». Limpiarlo obliga a separar a mano lo que es demostración de lo que es real. El próximo comando de siembra copiará el patrón, o se olvidará de la guarda.

**Recomendación.**

1. Una app `apps.desarrollo` con los cuatro comandos, `seed_assets/` y `textos_largos/`, instalada solo con `DEBUG` o con `DJANGO_HERRAMIENTAS_DE_DESARROLLO=1` (comprobando `importlib.util.find_spec`) y excluida en `backend/.dockerignore`.
2. Una clase base `ComandoDeDesarrollo(BaseCommand)` con una sola guarda y sin `--force`, que exija `DEBUG` y la ausencia de una marca explícita de producción (por ejemplo `DJANGO_ENTORNO: "produccion"` en el entorno de `docker-compose.prod.yml`). Las pruebas fijarían `settings.DEBUG = True`, como ya hace la de `datos_de_desarrollo`.
3. Cambiar los medios, fondos y editoriales reales de la demostración por nombres ficticios evidentes.

**Matiz de la verificación.** Las 639 sentencias no se pudieron recalcular; las 1.902 líneas sí. Que `exportar` no tenga guarda no es un hueco en producción (solo lee la base y escribe en una carpeta que no existe en la imagen): es una incoherencia, y su riesgo real está en HER-1. Las cuentas de staff de `seed_demo` reciben una contraseña aleatoria que se imprime una sola vez: el daño de un `--force` sería de reputación y de contaminación del contenido, no un acceso para terceros. Ningún arranque ni compose invoca estos comandos.

#### HER-3 · Cuatro caminos para poblar desarrollo que no convergen y repiten datos contradictorios

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Para montar una máquina nueva se documentan tres caminos a la vez: `seed_demo` (CONTRIBUTING.md y README.md), `datos_de_desarrollo cargar` («en lugar de seed_demo, no además») y `tools/ux/preparar-entorno.sh`, «un solo guion» que corre `seed_demo`, aplica la identidad con un bloque de Python embebido, crea integrantes de relleno y corre `seed_material_generico`. A ellos se suma `seed_textos_largos`. Cada camino da una base distinta: la copia trae siete publicaciones `demo-*`, tres registros `demo-*`, la obra y la reseña `zz-demo-` (al menos 12 filas que ningún código genera) y los textos `zz-largo-`, que el guion no siembra. La identidad del sitio está en cuatro sitios con valores opuestos: para `seed_demo` es «Reseñas», fundado en 2019, en «Santiago, Chile», con `hola@resenas.cl`; para el guion y para `datos.json`, «Repitentes del Verso», 2023, «Chile»; y `seed_material_generico` añade su propio manifiesto. El reparto entre cada `relleno-N` y su nombre está duplicado en el guion y en `seed_textos_largos`. La convención de «marcador» se aplica de dos formas (igualdad con el crédito o búsqueda de una subcadena), con un caso incoherente: el crédito de `seed_demo` cuenta como marcador para colocar imágenes y como foto real para el cupo de la galería. Y `seed_demo` reescribe con `.update(**extra)` lo editado en las integrantes cada vez que corre.

**Evidencia.**

- `CONTRIBUTING.md:12-22` y `README.md:56-85, 165-176` — los tres caminos documentados.
- `backend/apps/content/management/commands/seed_demo.py:160-188, 279-291, 610-622` — el `update` de las integrantes, la identidad antigua y el crédito de sus fotos.
- `tools/ux/preparar-entorno.sh:67-136` — la identidad real, la lista de relleno y la llamada a `seed_material_generico`; no ejecuta `seed_textos_largos`.
- `backend/apps/content/management/commands/seed_textos_largos.py:55-69, 258-266` — el reparto repetido; `_firma` crea en silencio `zz-largo-<slug>` si no encuentra el slug.
- `backend/apps/media/management/commands/seed_material_generico.py:29-30, 39-42, 373, 469-503` — el crédito, los marcadores y las dos comparaciones.
- `backend/datos_de_desarrollo/datos.json` — la identidad real y las filas que solo existen ahí (`grep -rln "demo-cartografia-del-eco\|zz-demo"` solo la encuentra a ella).

**Por qué importa a futuro.** Un agente en un equipo nuevo sigue CONTRIBUTING, corre `seed_demo` y ve un sitio «Reseñas» de 2019 en Santiago, sin las siete publicaciones de demostración ni los textos largos de la copia. «Corrige» plantillas o datos, o mide la portada contra las referencias de `tools/ux/final/` con otra base y atribuye a su cambio diferencias que solo son de datos. Si alguien antepone un nombre en la lista de relleno, los textos largos salen firmados por otras personas, sin ningún aviso. Y cada cambio de modelo hay que replicarlo en tres siembras, en el guion y en la copia.

**Recomendación.** Elegir una fuente de verdad. Lo más barato es que `datos.json` sea el estado canónico: el guion llamaría a `datos_de_desarrollo cargar` en lugar de `seed_demo` y del bloque embebido; la identidad real pasaría a un solo módulo (por ejemplo `apps/desarrollo/identidad.py`) que usen todos; `seed_demo` quedaría como fixture de pruebas o se retiraría; y las piezas que hoy solo existen en la copia se generarían desde código o quedarían documentadas como «solo en la copia». Unificar los ayudantes de imagen de las siembras y la convención de marcador en una función `es_marcador(asset)`. Dejar un solo camino en el README y en CONTRIBUTING.

**Matiz de la verificación.** Las líneas de identidad de `seed_demo` son del 2026-07-27, no del 29. Las filas sin generador son al menos 12, no 11 (falta la obra `zz-demo-cuadernos-del-ruido` y sus dependientes). El reparto no está duplicado «en bash y en Python»: son dos programas Python, uno embebido en un guion bash. `seed_demo` no pisa una identidad ya aplicada: solo actúa si el nombre está vacío o es «Colectivo».

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4, «Configurar la identidad del sitio en producción» (decisión relacionada). El registro documenta el guion de preparación y `seed_material_generico` como el camino de desarrollo, que es uno más de los que no convergen. El pendiente de producción sigue vigente, pero el registro debería remitir a un único camino.

#### HER-4 · Lo vendorizado no tiene radar ni receta: el hash cubre 1 de los 14 archivos de TinyMCE y la actualización es un texto

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `VERSIONS.md` reconoce que Dependabot, pip-audit y trivy no ven htmx ni TinyMCE y se presenta como el sustituto de ese radar, pero en la práctica es un procedimiento manual. La prueba solo calcula el sha256 del archivo principal de cada librería: los otros once archivos de código o estilo de TinyMCE (tema, modelo, iconos, los tres plugins y las pieles) pueden cambiar o quedarse en otra versión sin que nada lo note, y solo se comprueba que existan cuatro rutas. El origen de TinyMCE es la URL de su repositorio, sin artefacto ni hash, y qué archivos se copian solo figura como una cifra en prosa. Nada liga `plugins: "lists link autolink"` de `richtext_init.js` con los plugins vendorizados. Y el paso 2 del procedimiento dice «Sustituye el archivo», en singular.

**Evidencia.**

- `backend/static/vendor/VERSIONS.md:8-18, 22-25, 32-35, 43-46` — el procedimiento, la fila de TinyMCE (fecha «2025», origen sin artefacto) y la cifra de 14 archivos.
- `backend/tests/test_vendored_assets.py:21-27, 38-45, 48-55, 58-64, 67-77` — sha256 solo de `htmx.min.js` y `tinymce.min.js`; existencia de cuatro rutas.
- `find backend/static/vendor -type f` — 14 archivos en `tinymce/` (12 de código o estilo y 2 de licencia), además de `htmx.min.js` y `VERSIONS.md`.
- `backend/static/vendor/tinymce/tinymce.min.js:1-3` — «TinyMCE version 7.9.3 (2026-05-19)»; la versión coincide con el registro, la fecha no.
- `backend/static/admin/richtext_init.js:9` — los plugins pedidos, sin prueba que los cruce con los archivos.
- `.github/dependabot.yml:1-75` y `.github/workflows/ci.yml:9-10, 70-80, 189-207` — ninguna entrada para npm ni para `static/vendor`.

**Por qué importa a futuro.** Sale un aviso de seguridad de TinyMCE 7.x, el editor con el que publican las cuentas del panel, y nadie se entera, porque el CI semanal no mira el JavaScript. Cuando alguien actualice siguiendo `VERSIONS.md` al pie de la letra, reemplazará solo `tinymce.min.js`, actualizará la fila y la suite pasará en verde con el tema, el modelo, los plugins y las pieles en 7.9.3. Ver también REN-2: aun con todos los archivos al día, la caché inmutable de Caddy puede servir los viejos.

**Recomendación.**

1. Un manifiesto legible por máquina (`backend/static/vendor/manifest.json`) con la librería, la versión, el paquete npm, el `dist.integrity` y el sha256 de cada archivo; la prueba compara el árbol completo y falla si sobra o falta algo. `VERSIONS.md` queda como prosa.
2. Un guion `tools/vendor/actualizar.py <lib> <versión>` que baje el paquete de npm (TinyMCE también se publica allí), verifique `dist.integrity`, extraiga solo los archivos del manifiesto y lo reescriba.
3. Una prueba que lea `plugins:` de `richtext_init.js` y exija que exista `plugins/<p>/plugin.min.js`.
4. Un radar: un `package.json` en `backend/static/vendor` con las versiones exactas (no se instala) y una entrada npm para ese directorio en `dependabot.yml`.

**Matiz de la verificación.** El alcance estaba mal sumado: son 14 archivos en `tinymce/` (12 de código o estilo y 2 de licencia), más htmx y `VERSIONS.md`; el título es correcto. «Donde ninguna prueba mira» es falso: `test_security_csp.py:186-189` comprueba que el panel carga TinyMCE, y si falta un plugin TinyMCE avisa en el propio editor y sigue sin él. Ni la expresión regular sobre la tabla ni la versión fijada son defectos ocultos (fallan de forma visible), y que el historial tenga una sola entrada se explica porque TinyMCE no ha cambiado. TinyMCE solo corre en el panel y hay una CSP con `'self'` y nonce, así que un fallo típico de inyección tendría aquí un impacto bajo: lo que justifica la corrección es la falta de radar.

#### HER-5 · La copia de desarrollo es una foto fija: pisa por pk las filas de las migraciones de datos y sus fechas caducan

**Severidad:** baja · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `exportar` serializa con la clave primaria y `cargar` usa loaddata, que actualiza la fila que tenga el mismo pk. La guarda de «base sin contenido» solo mira cuatro modelos, y las páginas que crea la migración 0007 se sobrescriben por pk: en una base nueva, 0007 crea privacidad (1), cookies (2) y términos (3), y la copia trae quienes-somos (1), bases (2), privacidad (3), cookies (4) y términos (5). Hoy esas actualizaciones encadenadas no chocan con la restricción única por azar del orden. Las fechas son absolutas: al exportar (2026-10-22), los cuatro eventos ya habían pasado, y la única convocatoria abierta cierra el 2026-12-01. También se exporta el vector de búsqueda, un dato derivado (52 KB de los 215 KB del archivo) que el trigger recalcula al insertar.

**Evidencia.**

- `backend/apps/content/management/commands/datos_de_desarrollo.py:30-62, 84, 125-146` — `MODELOS` incluye Page y SiteProfile; serializa con pk; la guarda mira cuatro modelos; loaddata.
- `backend/apps/content/migrations/0007_legal_pages.py:55-68` — crea las tres páginas legales, en ese orden.
- `backend/apps/content/migrations/0009_search_vector_triggers.py:3-14` — el trigger que recalcula el vector.
- `backend/datos_de_desarrollo/datos.json:3068-3116, 3128-3203, 3840-3851` — páginas con otros pk, eventos pasados y convocatorias que caducan.
- `backend/tests/test_datos_de_desarrollo.py:66-71` — la carga se comprueba contando publicaciones.
- `backend/apps/agenda/views.py:18` y `backend/apps/content/views.py:168` — sin eventos futuros, la agenda cae a «recientes» y la portada pierde el bloque del próximo evento.

**Por qué importa a futuro.** Una migración de datos futura que cree una página nueva (por ejemplo «accesibilidad») la creará con pk 4 en una base nueva. Si nadie reexporta la copia, `cargar` la convierte en «cookies» sin ningún error y la prueba sigue en verde: en ese equipo, la página nueva da 404. Quien cargue hoy la copia no ve el próximo evento en la portada y, desde el 1 de diciembre, tampoco una convocatoria abierta: puede creer roto lo que solo está vacío, y las mediciones de la portada, la agenda y los envíos cambiarán por la fecha y no por el diseño.

**Recomendación.**

1. No exportar las filas que crean las migraciones, o exportarlas con claves naturales (`natural_key` por slug y `use_natural_primary_keys=True`) para que loaddata las busque por slug.
2. Una prueba de que los slugs y los cuerpos de las páginas que deja `migrate` siguen ahí después de `cargar`.
3. Guardar `exportado_en` en el JSON y, en `cargar`, desplazar las fechas de eventos, convocatorias y publicaciones en `ahora − exportado_en`.
4. Quitar el vector de búsqueda del JSON.

**Matiz de la verificación.** La migración 0010 no añadió una página: solo reescribe el cuerpo de privacidad; el único antecedente de una migración que crea páginas es 0007. Que la copia pise el perfil del sitio por pk es deliberado: así viaja la identidad. Los bloques de «próximos» no desaparecerán en diciembre: ya hoy no hay eventos futuros, y la agenda cae a «recientes»; lo que caduca el 1 de diciembre es la convocatoria. El caso de la página pisada exige una migración nueva que cree páginas y no volver a exportar, y todo queda en desarrollo. Severidad de media a baja.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (producto), «Texto legal de privacidad es un BORRADOR», y §4, «Configurar la identidad del sitio en producción» (decisión relacionada). Las filas que `cargar` pisa por pk son justo las páginas legales y el perfil del sitio, un contenido que el registro considera provisional: una copia vieja podría devolver un texto legal anterior al revisado. Ninguna decisión lo prevé.

#### HER-6 · Las herramientas de verificación de tools/ux dan por buenos resultados que no lo son

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.**

- (a) `capture.js` guarda el código HTTP pero no lo comprueba: una página 404 o 500 imprime «OK», escribe sus métricas y sale con 0, y `metrics.py` las compara sin mirar el estado.
- (b) `mutar.sh` es el instrumento con que el proyecto certifica que una prueba nueva vigila algo. No corre la prueba antes de mutar el archivo, toma cualquier salida 1 de pytest como «✓ falla como debe» (también un error de preparación o una prueba que ya estaba roja) y descarta la salida. Además muta el árbol real, montado en los contenedores, así que runserver, el worker y cualquier otra corrida usan el código mutado mientras tanto.
- (c) Las métricas no registran el commit, la versión de Chrome ni con qué datos se midieron. La ruta de Chrome y la URL base se repiten en siete sitios, `pages.txt` se interpreta de dos formas distintas y depende de seis slugs de la demostración que ninguna prueba vigila; uno de ellos, `resena-la-casa-vacia`, nace programado en `seed_demo` y da 404 durante unos minutos, hasta que corre beat.

**Evidencia.**

- `tools/ux/capture.js:242-263, 268` — guarda el estado, imprime «OK» y solo cuenta como fallo una excepción.
- `tools/ux/metrics.py:39-56, 75-87` — compara sin leer el estado.
- `tools/ux/mutar.sh:21-32, 34-42, 44-50` — muta el archivo real y corre pytest una vez, con la salida descartada.
- `docker-compose.override.yml:18, 27, 29, 34` — `./backend` montado en web, worker y beat.
- `tools/ux/superficies.js:27-35, 131-135`, `tools/ux/variantes.js:27-28, 66` y `tools/ux/smoke.py:17, 60-63` — estos sí fallan ante un código distinto de 200, y repiten la ruta y la URL.
- `tools/ux/pages.txt:4, 6, 8, 10, 12, 15` y `backend/apps/content/management/commands/seed_demo.py:779-796` — los slugs y la reseña programada.

**Por qué importa a futuro.** Alguien renombra en `seed_demo` el slug de una integrante y regenera los datos: `capture.js` mide el 404 y sale con 0, y `metrics.py` muestra cambios de alto y de título sin decir que la fila es una página de error. El agente informa al dueño de una «mejora» que es un 404. Otro agente añade una prueba que ya falla por otra razón, o cuya preparación falla con la mutación, corre `mutar.sh` y obtiene «✓»: el dueño, que no lee código, recibe como vigilado un comportamiento que nadie vigila.

**Recomendación.**

1. `capture.js`: contar como fallo cualquier estado distinto de 200; `metrics.py`: mostrar el estado y negarse a comparar filas que no sean 200.
2. `mutar.sh`: correr primero la prueba sin mutar y exigir salida 0; tras la mutación, exigir salida 1 con «failed» y sin «error» en el resumen; y trabajar sobre una copia (un `git worktree` temporal) en vez del árbol vivo.
3. Un módulo común `tools/ux/comun.js` con la URL base, la ruta de Chrome (con `chromium.executablePath()` de reserva), `leerPaginas()` y las opciones de lanzamiento. Cada `metrics.json` debería guardar el commit, `browser.version()` y el sha256 de `datos.json`, y `comparar` debería avisar si difieren.
4. Una prueba que compruebe que cada ruta de `pages.txt` existe en `datos.json`.

**Matiz de la verificación.** Es falso que solo `superficies.js` y `ver.js` fallen ante un código distinto de 200: también lo hacen `variantes.js` y `smoke.py`. `capture.js` es el único instrumento de medición que no lo hace, e imprime el código junto a «OK» (por ejemplo «OK integrante-d1440 404 …»), así que el 404 no pasa en silencio en la consola: se pierde en `metrics.py`. En `mutar.sh`, las salidas 2, 4 y 5 no cuentan como detección; los falsos «✓» que quedan son una prueba ya roja, que la suite o el CI delatarían antes de fusionar, y un error de preparación provocado por la mutación. Cargar la copia en lugar de `seed_demo` no rompe nada, porque `datos.json` tiene los seis slugs. Severidad de media a baja.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4 (rediseño), el cierre del 2026-10-14 con las métricas sin cumplir (decisión relacionada). Esas cifras salieron de estas herramientas. Las conclusiones siguen siendo plausibles, pero las próximas mediciones deberían exigir un 200.

#### HER-7 · Decisiones del sitio copiadas a mano fuera de su fuente quedaron obsoletas sin que nada lo detecte

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El cambio de la fuente de titulares de Syne a Bricolage Grotesque (2026-10-20) se aplicó a `site.css`, a las fuentes y a `seed_material_generico`, pero no a otros sitios. `capture.js` clasifica la fuente «display» con `/syne/i`, así que ahora cuenta Bricolage como «lectura». `iconos.js` dibuja con Syne y exige que esa fuente esté cargada, aunque el sitio ya no la sirve: el favicon y los iconos versionados ya no se pueden regenerar con la letra actual. El README de `tools/ux/` también la nombra. LICENSE y NOTICE.md siguen declarando Syne como fuente distribuida en `backend/static/fonts/` y no inventarían Bricolage, aunque su aviso y su licencia sí viajan con la fuente, en `NOTICE.txt`. Aparte, `preparar-entorno.sh` justifica sus 12 integrantes por `UMBRAL_CINTA`, una constante eliminada en el commit `a4df9cf`, y copia el 12 a mano. Y cinco archivos versionados citan, 15 veces, documentos de `docs/` que el índice marca como borrados.

**Evidencia.**

- `tools/ux/capture.js:56, 110-115, 192` — la expresión `/syne/i`; `tools/ux/metrics.py:40-56` solo usa la cifra de monoespaciada, así que hoy ninguna métrica informada cambia.
- `backend/static/css/site.css:54, 187` — `--display` es Bricolage Grotesque; no hay ningún `@font-face` de Syne.
- `tools/ux/iconos.js:3, 34, 36, 40-51, 72-73` — dibuja con Syne y exige `document.fonts.check('700 20px Syne')`.
- `LICENSE:9-10` y `NOTICE.md:38-45` frente a `backend/static/fonts/NOTICE.txt:1-7` — el inventario antiguo frente al aviso al día.
- `tools/ux/preparar-entorno.sh:3, 11-12, 119, 148` — la constante fantasma y las referencias a un documento borrado.
- `tools/ux/final/home-d1440-metrics.json` — la referencia de medición guarda `familia = 'Syne'`.

**Por qué importa a futuro.** El dueño pide un favicon nuevo y un agente ejecuta `node tools/ux/iconos.js`. O el guion se detiene con «La Syne del sitio no cargó», o, si Chrome da por buena una familia sin fuente, sobrescribe los iconos y el favicon con la letra de reserva sin avisar. El próximo cambio de identidad (un logo, una segunda fuente) repetirá el mismo patrón, y el inventario legal seguirá declarando una fuente que no se distribuye y omitiendo una que sí.

**Recomendación.** Leer la fuente del sitio en ejecución en vez de nombrarla: `capture.js` e `iconos.js` pueden tomarla de `getComputedStyle(document.documentElement).getPropertyValue('--display')`, como ya hace `superficies.js` con `--ink`, y comprobar `document.fonts.check` con esa familia. Una prueba barata que compare las familias de los `@font-face` de `site.css` con las que lista NOTICE.md. Quitar la referencia a `UMBRAL_CINTA` y el 12 copiado. Cuando se confirme el borrado de los documentos de `docs/`, actualizar o retirar las 15 menciones.

**Matiz de la verificación.** Los «seis lugares» que nombran Syne son un recuento conceptual: el grep que distingue mayúsculas da 8 líneas en 4 archivos. Las 15 menciones todavía no están rotas en HEAD ni en el repositorio público: dependen de que se confirme el borrado. La licencia de la fuente se cumple de fondo; lo que está mal es el inventario de alto nivel.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D17 (Bricolage Grotesque en lugar de Syne; «las cubiertas de demostración son imágenes y conservan Syne»), y §4, la medición pendiente de monoespaciada y mayúsculas (decisión relacionada). D17 solo dejó Syne a conciencia en las cubiertas de demostración, así que esa excepción no ampara a las herramientas ni al inventario. Y como `capture.js` cuenta Bricolage como «lectura», la medición pendiente saldría falseada.

#### HER-8 · Las guardas de higiene del repositorio están inactivas o despistan

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `.pre-commit-config.yaml` declara check-added-large-files (2 MB), gitleaks y ruff, pero en `.git/hooks` solo están los ejemplos: no está instalado. El CI corre ruff y gitleaks, pero ningún control de tamaño ni los demás hooks. El historial es pequeño (ningún blob supera los 450 KB), pero hay binarios regenerables cuyo crecimiento nada limita: los medios de desarrollo (84 archivos, 5,7 MB), las capturas de `tools/ux/` y las 15 variantes de la lámina de portada (unos 2,1 MB), que no tienen receta en el repositorio. El ruido de las imágenes de las siembras sale de una secuencia global del proceso: con `--regenerar`, un elemento nuevo cambia los bytes de todo lo que se dibuja después, y la siguiente exportación lo vuelve a versionar. El `.dockerignore` de la raíz no lo usa ningún build. Y hay un documento personal, sin seguimiento ni regla de exclusión, en el `docs/` de un repositorio público.

**Evidencia.**

- `.pre-commit-config.yaml:1-2, 11-12, 16-28` y `.git/hooks` (solo `*.sample`; `core.hooksPath` sin definir) — hooks declarados y sin instalar.
- `.github/workflows/ci.yml:64-68, 209-235` — ruff y gitleaks; ningún paso de pre-commit ni de tamaño.
- `CONTRIBUTING.md:59-64` — la instalación ya está documentada.
- `.dockerignore:12-13` frente a `backend/.dockerignore:1-2` — todos los builds usan como contexto `./backend` o `./infra/backup`.
- `backend/apps/media/templatetags/images.py:11, 81-94` y `backend/tests/test_portada_obra.py:60-79` — la lámina se usa y se comprueba, pero nada la genera.
- `backend/apps/media/management/commands/seed_material_generico.py:105-108, 469-491` y `backend/apps/content/management/commands/datos_de_desarrollo.py:114-119` — el ruido sin semilla y la exportación que reescribe los medios.

**Por qué importa a futuro.** Al cerrar un lote, un agente hace `git add -A` o `git add docs/` y entra el documento personal, o un audio de registro de varias decenas de MB. El hook no está instalado y el CI no mide tamaños: el PR pasa en verde y el archivo queda para siempre en el historial público. Hoy solo lo evita la costumbre de no añadir carpetas enteras. Otro agente añade una exclusión al `.dockerignore` de la raíz creyendo que protege la imagen.

**Recomendación.** Un job de CI con `pre-commit run --all-files`, o al menos check-added-large-files sobre el diff del PR; eso bloquea la fusión, aunque el archivo ya habría subido a la rama del PR, así que la guarda que de verdad sirve es el hook local instalado. Poner el documento personal en `.git/info/exclude`, que es local, o sacarlo del repositorio. Borrar el `.dockerignore` de la raíz. Versionar la imagen maestra de la lámina junto al guion que genera sus variantes. Sembrar el ruido de forma determinista por pieza y, si los medios de desarrollo van a crecer, pasarlos a Git LFS.

**Matiz de la verificación.** Las líneas del CI son 64-68 (ruff) y 209-235 (gitleaks). «Documentar `pre-commit install`» ya está hecho: lo que falta es imponerlo. Los directorios vacíos `apps/` y `templates/` de la raíz no forman parte del repositorio (git no versiona directorios vacíos). Las capturas versionadas de `tools/ux/` son 16 imágenes y unos 1,9 MB. El vaivén de bytes del ruido es hipotético (solo ocurre con `--regenerar` y aún no ha pasado), y una subida de Pillow cambiaría los bytes de todos modos. Que el documento de `docs/` sea personal se deduce de su nombre: no se leyó.

**Decisión registrada.** El bloque final de `docs/deferidos-y-decisiones.md`, sobre el CI («test» con ruff y «security» con gitleaks) (decisión relacionada). Esas comprobaciones corren, pero solo en el CI; el control de tamaño y los hooks locales no corren en ningún sitio, y ninguna decisión lo justifica.

### 4.15 Auditorías complementarias: accesibilidad y permanencia de las URL (COM)

Seis fichas vienen de la revisión de accesibilidad de los componentes propios en un navegador con el JS en marcha (COM-2, COM-3, COM-4, COM-7, COM-10 y COM-11), y seis de la revisión de la permanencia de las URL públicas y de los identificadores de los feeds (COM-1, COM-5, COM-6, COM-8, COM-9 y COM-12).

#### COM-1 · Los GUID de los dos feeds son el enlace absoluto: cambian con el slug, el host y el esquema, y el pódcast duplicaría episodios

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Ninguno de los dos feeds define `item_guid` ni `item_guid_is_permalink`. Django usa entonces como GUID el enlace absoluto que arma con el host y el esquema de la petición (como `django.contrib.sites` no está instalado, usa `RequestSite`). El GUID depende así de tres cosas que pueden cambiar: el slug, que se edita en el panel (COM-5); el dominio; y el esquema. Se emite sin `isPermaLink`, y RSS 2.0 lo interpreta entonces como permalink: el feed promete como identidad justo lo que cambia. Para un lector RSS, un GUID nuevo es un ítem nuevo; para Apple Podcasts, Spotify o Pocket Casts, un episodio nuevo, que se vuelve a descargar.

**Evidencia.**

- `backend/apps/content/feeds.py:35-59` — `item_link` con `reverse(..., args=[item.slug])` (48-49); ni `item_guid` ni `item_guid_is_permalink`.
- `backend/apps/media/feeds.py:88-98` — `item_link = item.get_absolute_url()` y el enclosure con `build_absolute_uri`.
- `backend/apps/media/models.py:331, 409-412` y `backend/apps/media/admin.py:26-29` — el slug se llama «dirección», sin texto de ayuda, y se puede editar después de publicar.
- Django instalado, `contrib/syndication/views.py:140-143, 220-222` — el GUID es el enlace absoluto si no hay `item_guid`, y el atributo `isPermaLink` no se emite.
- Comprobado con curl: el mismo registro sale con GUID distintos según el Host de la petición, y lo mismo pasa con el enclosure.

En los dos feeds, de 20 ítems cada uno, `grep -rn item_guid backend/apps` no encuentra nada.

**Por qué importa a futuro.** Un editor corrige la «dirección» de un registro de audio ya publicado, por ejemplo de `umbral-lectura` a `umbral-lectura-2026`. En la siguiente lectura, el feed de registros emite un GUID nuevo, y un cliente de pódcast suscrito lo toma como un episodio nuevo: lo descarga otra vez y conserva el viejo con el enlace roto. Mudar el sitio a otro dominio produce lo mismo en los 20 ítems de cada feed a la vez. Y cambiar el esquema de GUID más adelante provoca, por sí mismo, una duplicación única: conviene decidirlo antes de anunciar el RSS o de enviar el pódcast a los directorios.

**Recomendación.** En los dos feeds, un `item_guid(item)` con un identificador que no dependa del slug ni del host, por ejemplo `f"tag:{settings.FEED_GUID_AUTORIDAD},2026:{item._meta.model_name}/{item.pk}"`, donde `FEED_GUID_AUTORIDAD` es una constante que no se toca aunque cambie el dominio, e `item_guid_is_permalink = False`. Si se prevé mover contenido entre bases, mejor un `UUIDField` `guid` con `default=uuid4` en Article y Recording, rellenado por migración. Si ya hubiera suscriptores, devolver el GUID antiguo para los ítems publicados antes de una fecha de corte. Prueba: el `<guid>` de un ítem no cambia al cambiar su slug ni al pedir el feed con otro Host, y lleva `isPermaLink="false"`.

**Matiz de la verificación.** En producción el host y el esquema no varían de una petición a otra: Caddy solo enruta el dominio configurado, web no se publica y `SECURE_PROXY_SSL_HEADER` fija el esquema. La demostración con distintos Host solo funciona contra el servidor de desarrollo, y que `ALLOWED_HOSTS` incluya `127.0.0.1` y `localhost` no es un vector para los suscriptores. El valor de ejemplo de `.env.prod.example` no prueba que el dominio definitivo esté sin fijar. Quedan dos disparadores reales: el cambio de dominio y la edición del slug de lo publicado, que además rompe la URL antigua (COM-5). El pódcast todavía no está listo para los directorios, porque le falta `itunes:image`. Severidad de alta a media.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4, «Portada de podcast cuadrada (itunes:image)», pendiente para publicar el feed de registros en Apple Podcasts (decisión relacionada). Antes de cerrar ese pendiente hay que fijar GUID estables: si no, cada cambio de slug o de dominio duplicaría episodios a los suscriptores.

#### COM-2 · Contraste insuficiente en los sellos de la portada, con un par que la prueba de paleta declara prohibido sin comprobar su uso real (1.4.3)

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** Los sellos 2 y 3 del cierre de la portada («Para programadores y jurados») pintan su rótulo de 12 px en `--caratula` (`#1f73c7`) sobre el papel (`#d9e8f7`), con un contraste de 3,88:1, cuando el mínimo para texto normal es 4,5:1 (WCAG 1.4.3). `test_contraste_paleta.py` enumera justo ese par entre los prohibidos, y su prueba de reglas lee `site.css`, pero solo revisa las reglas que fijan color y fondo en el mismo bloque. La de los sellos no declara fondo (lo hereda de la página), así que pasa, con un docstring que garantiza más de lo que comprueba. Ninguna comprobación ejecuta la página: el CI no tiene axe ni Playwright.

**Evidencia.**

- `backend/static/css/site.css:1272-1274, 1278-1279, 1281` — los sellos 2 y 3 en `var(--caratula)` y el rótulo que hereda el color.
- `backend/static/css/site.css:23, 47, 123, 232, 596-599` — el papel, el azul, `--caratula-rotulo` (`#0e3358`, 10,3:1 sobre el papel, que sirve como arreglo) y el rótulo a 12 px.
- `backend/templates/content/home.html:226-228` — los sellos «Notas y entrevistas» (Prensa) y «Quiénes nos apoyan» (Aliados).
- `backend/tests/test_contraste_paleta.py:110-118, 131-138, 157-181` — los siete pares prohibidos y la prueba que salta las reglas sin fondo declarado.
- `.github/workflows/ci.yml` — ningún paso con Playwright, axe, pa11y ni Lighthouse.

Son dos nodos de la portada, y el único fallo de contraste que axe detectó en 21 páginas a dos anchos.

**Por qué importa a futuro.** El próximo ajuste de color (un sello nuevo, otro territorio, el amarillo en otro sitio) puede usar un par prohibido sobre un fondo heredado, y la suite seguirá en verde: la lista de prohibidos da una garantía que nada impone en ese caso.

**Recomendación.** Sin rediseñar los sellos, que el dueño aprobó: dar al rótulo de esos dos sellos `--caratula-rotulo` y conservar el azul en el enlace grande, que cuenta como texto grande; enseñárselo al dueño antes de cambiarlo. Ampliar la prueba de paleta a los fondos heredados (por ejemplo, prohibir `color: var(--caratula)` en reglas de texto pequeño sin fondo declarado) o, al menos, corregir su docstring. Añadir a `tools/ux/`, que ya trae playwright-core, un guion que pase axe-core con la regla de contraste por `pages.txt` a 951 y 375 px y falle si encuentra algo, y correrlo en el CI contra el stack de pruebas.

**Matiz de la verificación.** Es falso que la prueba «nunca mire qué pares usa site.css» y que nada impida usar los pares prohibidos: los bloquea cuando color y fondo van en la misma regla. El hueco real son los fondos heredados, más un docstring que promete lo que no cumple. La cifra de axe sobre 21 páginas no se reprodujo; el 3,88:1 sí, a mano.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §3, #33, accesibilidad automatizada con pa11y o axe sobre las páginas clave (diferido conocido). Comprobar el contraste sobre la página renderizada era parte de ese diferido; sin eso, la prueba de paleta enumera pares sin ver dónde se usan. El hallazgo es un argumento para retomarlo.

#### COM-3 · Registros sin alternativa textual garantizada: el `<video>` no admite subtítulos, el audio publicado no tiene transcripción y el modelo impide enlazar el poema a una segunda lectura (1.2.1/1.2.2)

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `_player.html` emite `<video controls>` y `<audio controls>` sin `<track>` ni nombre accesible. Recording no tiene campo de subtítulos ni de transcripción. El único vínculo con el texto es `Poem.recording`, una clave foránea: cada poema tiene un solo registro, así que una segunda lectura del mismo poema no puede apuntar a él. Cuando el vínculo existe, la ficha del registro lo muestra al final de la página, como «Poema registrado» en el pie, y no junto al reproductor. En desarrollo hay un audio publicado sin texto (`umbral-lectura`) y dos vídeos de archivo sin publicar. Además, la ficha del poema emite `<audio>` con cualquier archivo, aunque el registro sea un vídeo.

**Evidencia.**

- `backend/templates/media/partials/_player.html:31-40` — `<video>` y `<audio>` sin `<track>` ni `aria-label`.
- `backend/apps/media/models.py:318-400` — ningún campo para subtítulos ni transcripción.
- `backend/apps/content/models.py:238-245` — `Poem.recording` es una ForeignKey con `related_name="poems"`.
- `backend/apps/media/views.py:21-33` y `backend/templates/media/recording_detail.html:26, 28, 40` — el poema solo aparece como puerta del pie, después del reproductor y de la descripción.
- `backend/templates/content/poem_detail.html:42-50` — en la ficha del poema, el audio va junto al texto (una mitigación), pero con `<audio>` también para un vídeo.
- Consulta de solo lectura en desarrollo y curl de `/registro/umbral-lectura/` — el audio publicado sin texto y sin enlace al poema.

**Por qué importa a futuro.** El colectivo sube como archivo el vídeo de un recital, lo publica y queda sin ninguna forma de añadirle subtítulos (WCAG 1.2.2, nivel A). Graba una lectura aparte de un poema que ya está enlazado al vídeo del recital, y no puede enlazar su texto. En un sitio de poesía, la transcripción es el poema mismo, así que la falta se nota justo en la obra.

**Recomendación.** Pasar la relación a ManyToMany entre Recording y Poem, o añadir `Recording.transcripcion` (TextField). Un FileField opcional de subtítulos `.vtt`, emitido como `<track kind="captions" srclang="es" default>`; la CSP (`media-src 'self'`) ya lo permite. En la ficha del registro, «Leer el poema» o «Transcripción» justo después del reproductor. En el admin, exigir un poema o una transcripción cuando el registro tenga un archivo de audio. Dar al reproductor un `aria-labelledby` hacia el título. Corregir que la ficha del poema emita `<audio>` para un vídeo.

**Matiz de la verificación.** No es cierto que no haya dónde poner una transcripción: `description` se muestra justo debajo del reproductor; lo que falta es un campo propio y exigirlo. Para los registros enlazados a un poema, la ficha del poema ya cumple 1.2.1 por la excepción de alternativa al texto. El hueco real está en la ficha del registro, en las lecturas que la clave foránea no deja enlazar y en los vídeos subidos como archivo. Que el reproductor no tenga nombre accesible no es un fallo de nivel A ni AA.

#### COM-4 · «Las voces»: el relevo automático no tiene control de pausa (dato frente a 2.2.2) y reordena el DOM bajo el cursor del lector de pantalla

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Se anota como dato para que decida el dueño, porque el relevo sin pausa es una decisión aprobada. Cada 1,8 s, un intervalo mueve nodos de la lista (`viejo.before(nuevo)` y `lista.append(viejo)`) y alterna `hidden`. Solo se detiene con el puntero encima o el foco dentro, fuera de la vista o con la pestaña oculta; no hay un botón para pausarlo o detenerlo. Corre en dispositivos con un puntero que pueda posarse y sin preferencia de movimiento reducido, que es justo el escritorio de quien usa un lector de pantalla. Y el cursor virtual del lector no activa `:focus-within`: los enlaces cambian de orden o desaparecen mientras se leen.

**Evidencia.**

- `backend/static/js/integrantes.js:16-17` — solo corre con `(hover: hover) and (prefers-reduced-motion: no-preference)`.
- `backend/static/js/integrantes.js:60-65, 78-85` — el relevo que mueve nodos y el intervalo de 1.800 ms con sus condiciones de pausa.
- `backend/templates/content/home.html:154-166` — la sección, sin ningún control de pausa.
- `backend/templates/people/partials/_member_card_portada.html:8-20` — cada elemento es un enlace a una ficha; los que esperan llevan `hidden`.
- `GET /` — 12 integrantes: 5 a la vista y 7 escondidas.

**Por qué importa a futuro.** Una persona ciega en escritorio, con NVDA en modo exploración y sin pedir menos movimiento, recorre con las flechas «Las voces». Cada 1,8 s, el enlace que está leyendo pasa a `hidden` y se va al final de la lista, y otro ocupa su lugar: el cursor salta o anuncia un nombre distinto, y nada le permite detenerlo. Un jurado o un fondo que pida conformidad con WCAG 2.1 AA marcará el criterio 2.2.2.

**Recomendación.** Opciones para el dueño, sin rediseñar el relevo: (1) un botón pequeño «Pausar el relevo», con `aria-pressed`, en la cabecera de la sección, que es el mecanismo que pide 2.2.2; (2) que el relevo se detenga solo tras unos ciclos y se retome a petición; (3) mantenerlo y dejar registrada la excepción. Cualquiera de ellas se resuelve en `integrantes.js` sin tocar la tinta. Aparte, el reordenamiento bajo el lector se puede resolver sin añadir controles, por ejemplo ofreciendo al lector una lista estable de todas las integrantes y dejando el relevo solo en la capa visual; conviene probarlo con un lector de pantalla real.

**Matiz de la verificación.** El umbral de 5 s de 2.2.2 rige para el contenido que se mueve; para el que se actualiza solo no hay umbral, y este caso encaja mejor como actualización automática, lo que refuerza el hallazgo. La medición en navegador no se repitió: el comportamiento se verificó leyendo el código y contando los elementos del HTML servido.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (UX), D1 (la cinta sin control de pausa: «WCAG 2.2.2 queda discutible; no volver a proponerlo salvo que él lo pida») y D23 («Las voces» en relevo, con la misma regla). El hallazgo contradice la decisión, y por eso se presenta solo como dato, respetándola. Lo que la decisión no cubre es que el DOM se reordene bajo el lector, algo que tampoco se ha comprobado (§4, «Sin comprobar con un lector de pantalla»), y eso se puede corregir sin añadir controles.

#### COM-5 · El slug de lo publicado se cambia desde el panel sin aviso, sin historial ni redirección: 14 rutas públicas dan 404

**Severidad:** media · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** Los 14 modelos con slug lo tienen editable en su admin (`prepopulated_fields`). `EditorialItemAdmin.get_readonly_fields` solo bloquea `status`, `published_at` y `owner` (además de los campos de solo lectura propios de cada clase), así que un editor puede cambiar el slug de un texto o un poema publicados; las colecciones, páginas, secciones, eventos, publicaciones, registros, personas y obras ni siquiera tienen `get_readonly_fields`. Las fichas buscan con `get_object_or_404(slug=...)` y no tienen respaldo: no hay `django.contrib.redirects`, ni historial de slugs, ni `RedirectView` (comprobado: un slug inexistente da 404). El canonical, el `og:url` y el sitemap pasan en silencio a la URL nueva, y la vieja desaparece del sitemap sin un 301 que traspase la indexación. En el RSS y en el pódcast, el GUID cambia (COM-1). El JS de prepopulate de Django no reescribe el slug de un objeto ya guardado, así que el riesgo viene de la edición manual; pero el campo está a la vista, y en Recording se llama «dirección», sin un texto de ayuda que advierta la consecuencia.

**Evidencia.**

- `backend/apps/content/admin.py:193-200` — los campos de solo lectura no incluyen el slug; `257, 275, 289, 295, 315, 325` — `prepopulated_fields` en artículo, poema, sección, etiqueta, colección y página.
- `backend/apps/content/permissions.py:20-26` — el editor puede editar cualquier pieza en cualquier estado.
- `backend/apps/media/admin.py:22-29` y `backend/apps/media/models.py:331` — el registro, con el slug «dirección» editable.
- `backend/apps/people/admin.py:16` — persona; igual en `agenda/admin.py:17`, `showcase/admin.py:47`, `reviews/admin.py:10, 17, 25` y `submissions/admin.py:12`.
- Las 14 rutas con `<slug:slug>`: `content/urls.py:11-19`, `reviews/urls.py:8-10`, `media/urls.py:9`, `people/urls.py:9`, `agenda/urls.py:11` y `showcase/urls.py:10`.
- `backend/apps/content/sitemaps.py:56-57, 67-68, 92-93, 103-104` — solo el slug vigente.

En total: 14 SlugField únicos, 14 `prepopulated_fields` en siete admins y 14 rutas públicas con slug sobre 13 modelos (Call tiene slug, pero no ruta pública). `grep -rn 'contrib.redirects\|RedirectView\|permanent=True' backend` no encuentra nada.

**Por qué importa a futuro.** Un editor corrige el título de un poema publicado y, por coherencia, cambia también su dirección. `/poema/<slug-viejo>/`, ya enlazado desde una nota de prensa y desde el dossier, pasa a dar 404 sin redirección, y nada lo avisa, porque no hay seguimiento de los 404. El sitemap y el canonical cambian en silencio, y si es un registro de audio, el episodio reaparece en el pódcast con un GUID nuevo.

**Recomendación.** Una regla mínima: congelar el slug una vez público. Un mixin `SlugFijoAlPublicar` para los 13 admins con ruta pública: `get_readonly_fields` añade `slug` cuando el objeto existe y es público (en Section, Tag, Contributor, Work, Publisher y BookAuthor, en cuanto existe), y `get_prepopulated_fields` devuelve `{}` en ese caso; si no, el formulario del admin falla con KeyError, porque un campo de solo lectura no está en el formulario. Si alguna vez hace falta renombrar, un modelo `SlugAnterior` (tipo y slug viejo hacia el objeto) que rellena un `pre_save` al detectar el cambio, y un respaldo en las fichas que, si no encuentra el slug, lo busca ahí y responde 301 a `obj.get_absolute_url()`. Prueba por HTTP: la ficha de cambio de un texto publicado muestra el slug como de solo lectura.

#### COM-6 · El sitio no tiene un origen fijo: canonical, og:url, imágenes sociales, JSON-LD, sitemap, robots y enclosure se arman con el Host y el esquema de cada petición

**Severidad:** media · **Esfuerzo:** M · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** No hay un `SITE_URL` ni `contrib.sites`. Las 18 líneas que construyen URL absolutas usan `request.scheme`, `request.get_host()` o `build_absolute_uri`, y el sitemap y los feeds usan `RequestSite` por dentro. En producción hoy funciona porque Caddy sirve un solo dominio y sobrescribe las cabeceras `X-Forwarded-*` del cliente, pero nada lo fija:

- (a) Caddy no tiene ningún bloque para el subdominio www, así que la corrección natural cuando alguien avise de que «www no funciona» (añadir www a `SITE_ADDRESS` y a `ALLOWED_HOSTS`) serviría el sitio en dos hosts, con un canonical autorreferente en cada uno, contenido duplicado y GUID dobles.
- (b) Ya hay divergencia entre dos formas de calcular la identidad de una página: en la ficha de evento, el JSON-LD usa `request.build_absolute_uri`, con la query string completa (comprobado: canonical `…/evento/recital-de-invierno/` frente a un JSON-LD con `?utm_source=boletin&amp;fbclid=abc`).
- (c) Por construir el enclosure con la request hubo que guardarla en `self` y luego instanciar el feed en cada petición para arreglar una carrera entre hilos. `LatestArticlesFeed` sigue registrado como instancia compartida, así que copiar ese patrón para dar enclosure a los textos reintroduciría el fallo.

**Evidencia.**

- `backend/apps/content/context_processors.py:82-90` — el canonical con `request.scheme` y `request.get_host()` (86).
- `backend/templates/base.html:9, 20, 25, 35-36` — canonical, `og:url`, `og:image` y el JSON-LD de la organización.
- `backend/templates/agenda/event_detail.html:11, 30, 33` — el JSON-LD del evento con `request.build_absolute_uri`.
- `backend/apps/media/feeds.py:63-75, 95-98, 112-120` y `backend/config/urls.py:16, 17, 21` — la request guardada en `self`, la fábrica por petición y el feed de textos compartido.
- `infra/caddy/Caddyfile:35, 77` y `backend/config/settings.py:267-275` — un solo bloque de sitio; el esquema lo fija `SECURE_PROXY_SSL_HEADER`, con la redirección a HTTPS activa por defecto.
- `backend/apps/content/views.py:530-537` y `backend/apps/community/views.py:85-88` — robots y los enlaces del boletín, también con la request.

Son 18 líneas en 11 archivos (`grep -rn 'build_absolute_uri\|request.get_host\|request.scheme' backend/apps backend/config backend/templates`), entre ellas las `og:image` de artículo, poema, evento, publicación y registro, y el «Sitio» que imprime el dossier.

**Por qué importa a futuro.** El dueño añade `www.<dominio>` a `SITE_ADDRESS` y a `DJANGO_ALLOWED_HOSTS`. Desde ese momento, cada pieza se sirve en dos hosts, cada uno con su canonical, su `og:url` y su JSON-LD autorreferentes, y el dossier impreso muestra el host con que se abrió. Cuando después se redirija www al dominio principal, los suscriptores que usaban www recibirán todos los GUID cambiados y verán duplicados los textos y los episodios. Ninguna prueba ni guarda lo detecta.

**Recomendación.** Un ajuste `SITE_URL` (por ejemplo `https://dominio`), obligatorio con `DEBUG=0` y validado por envguard (https y host incluido en `ALLOWED_HOSTS`). Un ayudante `url_absoluta(path)` que lo use, con la request como respaldo solo en desarrollo, para el canonical, la base, las `og:image`, el JSON-LD (el del evento, a partir de `canonical_url`), robots, el `item_link` y el enclosure de los feeds (`add_domain` respeta las URL que ya empiezan por http), y una clase base de Sitemap con `get_domain` y `get_protocol`. Así desaparecen el `self.request` y el envoltorio del feed de registros. En Caddy, un bloque `www.<dominio> { redir https://<dominio>{uri} permanent }` si existe el DNS de www.

**Matiz de la verificación.** Se retiró el caso de un CDN que termine TLS delante de Caddy: con `DEBUG=0`, la redirección a HTTPS viene activa por defecto y Django respondería con una redirección en cada petición (el bucle clásico), en lugar de servir en silencio un canonical con http; solo pasaría si además se apaga esa redirección, y con TLS hasta el origen Caddy propaga bien el esquema. El caso de www es plausible, pero «los feeds duplican sus ítems» es impreciso: cada suscriptor lee siempre por el mismo host; la duplicación llega cuando cambia el host de la suscripción, por ejemplo al normalizar después www hacia el dominio. El JSON-LD del evento lleva además un `&amp;` literal.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §1 (técnicas), D1, «Caddy es el ÚNICO proxy de borde» (decisión relacionada). El sitio funciona hoy por el mismo supuesto crítico que D1: Caddy, único proxy, sirve un solo dominio y reescribe las cabeceras reenviadas. Con un CDN delante o un segundo dominio fallarían a la vez la IP de D1 y el origen de las URL absolutas; un `SITE_URL` fijo quitaría esta segunda dependencia.

#### COM-7 · Menú del teléfono: el foco sale del panel abierto y cae en contenido que el panel tapa por completo (2.4.11)

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** «Menú» es un `<details>` que se queda abierto cuando el foco sale de él: ningún guion escucha `focusout`, y en el teléfono el panel cubre la pantalla bajo la cabecera fija. Al tabular más allá del último enlace del mapa, el foco pasa a las tarjetas de la página, que quedan debajo del panel. La excepción de WCAG 2.4.11 («el usuario puede revelar el componente sin mover el foco») no aplica: Escape cierra el menú, pero `buscador.js` devuelve el foco al botón. `cabecera.js`, además, congela la forma de la cabecera mientras haya un panel abierto.

**Evidencia.**

- `backend/templates/base.html:88-92` — el `<details>` con la barra, oculta en el teléfono, y el mapa.
- `backend/static/js/buscador.js:21-30` — Escape cierra y devuelve el foco al botón; un grep de `focusout` o `blur` en los guiones no encuentra nada.
- `backend/static/js/cabecera.js:28-31, 45` — no recalcula la cabecera mientras haya un panel abierto.
- `backend/static/css/site.css:291, 404-406` — la cabecera fija y el panel del teléfono, con `max-height: calc(100dvh - var(--alto-cabecera))`; `458-460` es la variante cápsula.
- `backend/static/css/site.css:549` — `#search-results` se oculta cuando la búsqueda pierde el foco: por eso la lupa no tiene el problema.
- curl de `/poemas/` — el menú tiene 17 enlaces; tras ellos y la lupa, la siguiente parada es la primera tarjeta.

Afecta a un componente presente en todas las páginas, en todo ancho por debajo de 900 px, incluida la ventana de 951 px con zoom del 110 % o más. Se midió con Playwright, tabulando y muestreando cinco puntos del elemento enfocado.

**Por qué importa a futuro.** Quien navega con teclado en el teléfono, en una tableta con teclado o con zoom alto abre «Menú», sigue tabulando y deja de ver dónde está; si pulsa Escape, el foco vuelve a «Menú» y pierde el sitio. Si alguien añade otro panel desplegable a la cabecera, lo copiará de este y heredará el defecto.

**Recomendación.** En `buscador.js`, escuchar `focusout` en fase de captura sobre `.busqueda, .nav-disclosure` y, si `!panel.contains(evento.relatedTarget)`, cerrar el panel con `panel.open = false` sin mover el foco: así el foco queda donde el usuario lo llevó, y ya visible. Una prueba de Playwright: abrir «Menú» a 375 px, tabular hasta salir y comprobar que el `details` está cerrado y que el elemento enfocado no queda bajo la cabecera.

**Matiz de la verificación.** A 375×812 el panel deja abajo una franja de unos 110 px, así que solo quedan tapadas las primeras paradas (tres, según la medición), no «decenas»; eso solo vale en teléfonos bajos, de unos 667 px de alto. Entre 720 y 899 px el mapa va a cuatro columnas y el panel mide alrededor de un tercio del alto, de modo que en la ventana de 951 px con zoom el efecto se reduce a lo que cae debajo del panel. Severidad de media a baja.

#### COM-8 · La URL de una persona depende de si es integrante: quien deja el colectivo pierde `/integrante/<slug>/` con un 404

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `Contributor.get_absolute_url` elige la ruta según `is_member`: `/integrante/<slug>/` o `/colaborador/<slug>/`. `contributor_detail` redirige a las integrantes hacia su perfil, con un 302, pero `member_detail` filtra `is_member=True` y no tiene el camino inverso: si se desmarca «integrante», la URL que circula da 404, aunque la persona y sus textos sigan publicados en `/colaborador/<slug>/`. Comprobado con curl: `/colaborador/andres-caceres/` redirige con un 302 a `/integrante/andres-caceres/`; `/integrante/diego-salinas/` da 404 y `/colaborador/diego-salinas/`, 200.

**Evidencia.**

- `backend/apps/people/models.py:33-38` — `is_member` («Integrante del colectivo (aparece en /integrantes/).») y `active` («desmarcado = histórico»), sin `verbose_name`.
- `backend/apps/people/models.py:60-75` — `members()` y `get_absolute_url`, que cambia de ruta según la membresía.
- `backend/apps/people/views.py:15-19` — «los integrantes históricos (active=False) conservan su perfil accesible», y `get_object_or_404(..., is_member=True)` sin respaldo.
- `backend/apps/content/views.py:275-279` — la redirección, en un solo sentido.
- `backend/apps/people/admin.py:19-36` — el bloque «Integrante del colectivo», con las dos casillas.

**Por qué importa a futuro.** Una integrante deja el colectivo y el editor, en vez de desmarcar «Active», desmarca «Is member», cuyo texto de ayuda dice «aparece en /integrantes/». Su ficha `/integrante/<slug>/`, ya enlazada en programas de festivales, notas de prensa y biografías en otros sitios, da 404, aunque sus textos sigan publicados.

**Recomendación.** En `member_detail`, si existe una persona con ese slug que no es integrante, redirigir a `contributor_detail` con un 302, no un 301: la membresía puede volver a cambiar, y un 301 guardado por el navegador en cada sentido terminaría en un bucle. Alternativa a largo plazo: una sola ruta por persona, que no dependa del rol. Dar `verbose_name` en castellano a las dos casillas y un texto de ayuda en `is_member` que remita a `active`. Añadir las pruebas de las dos direcciones.

**Matiz de la verificación.** Falta la mitigación por diseño: `active=False` marca a las integrantes históricas y conserva su `/integrante/<slug>/`. El riesgo real es una confusión entre dos casillas del panel, no que «la persona sale». Diego Salinas nunca fue integrante, así que el curl demuestra el filtro de la ruta, no una salida. Severidad de media a baja.

#### COM-9 · Las pruebas fijan que el enclosure siga al Host de la petición, y nada fija la estabilidad de GUID, slugs ni direcciones

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** parcial

**Qué pasa.** `test_feed_isolation.py` convierte en contrato la dependencia del Host: `test_el_enclosure_usa_el_host_de_su_peticion` exige que la respuesta contenga `http://{host}/media/` para cada Host enviado, y la prueba de concurrencia exige lo mismo en cada hilo. Quien introduzca un origen fijo (COM-6) verá fallar dos pruebas que parecen de seguridad. Lo que sí importa no lo prueba nadie: no hay pruebas sobre los GUID, sobre que el slug de lo publicado no se pueda cambiar, sobre las redirecciones ni sobre el sentido integrante → colaborador. Otras pruebas fijan también el host de la petición: el canonical y el `og:url` en `test_seo` y el «Sitio» del dossier.

**Evidencia.**

- `backend/tests/test_feed_isolation.py:52-59, 62-90` — el host de cada petición en el enclosure, también bajo concurrencia.
- `backend/tests/test_feed_identidad.py:26-67` — título, identidad y artículos; ninguna mira el `<guid>`.
- `backend/tests/test_get_absolute_url.py:25-31, 90-94` — rutas literales y un sitemap que responde 200.
- `backend/tests/test_recordings.py:184-205` — el enclosure es absoluto; no mira qué host.
- `backend/tests/test_seo.py:101-115` y `backend/tests/test_dossier.py:202` — otras pruebas que fijan el host del cliente de pruebas.
- `backend/apps/people/views.py:15-19` — la ficha de integrante, sin redirección a la de colaborador.

`grep -rn 'guid\|enclosure\|HTTP_HOST' backend/tests/*.py` no encuentra ninguna prueba de GUID, y ninguna prueba comprueba un slug de solo lectura.

**Por qué importa a futuro.** Un agente renombra la ruta de los registros o cambia el `item_link` de un feed: todos los GUID cambian y las aplicaciones de pódcast duplican los episodios, sin que falle ninguna prueba. Otro pasa a una persona a no integrante y su ficha empieza a dar 404 sin que nada lo detecte.

**Recomendación.** Al introducir `SITE_URL`, reescribir `test_feed_isolation.py` para fijar el contrato real: con `SITE_URL` definido, el enclosure y el GUID son iguales sea cual sea el Host. La prueba de concurrencia sobra si la request deja de guardarse en `self`; la prueba estructural de que la vista registrada no es una instancia compartida conviene conservarla mientras quede algún estado por petición. Añadir: GUID estable al cambiar el slug y el Host, con `isPermaLink="false"`; la ficha de cambio de una pieza publicada, por HTTP, con el slug de solo lectura; y `/integrante/<ex-integrante>/` que redirige a `/colaborador/`.

**Matiz de la verificación.** No son dos las pruebas que fijan el host, sino al menos cinco: las dos de `test_feed_isolation`, dos de `test_seo` y una del dossier, todas con el host por defecto del cliente de pruebas y benignas mientras exista el respaldo con la request. Que alguien lea esas pruebas como contrato y revierta el cambio es poco probable, porque su docstring explica el motivo. La falta de pruebas de GUID, slug y redirección viene de que el código no ofrece esas garantías: se resuelve junto con COM-1, COM-5 y COM-8. Severidad de media a baja.

#### COM-10 · Anuncios: el buscador vuelca la lista entera en la región viva y anuncia «Sin resultados» con una letra; la tirada anuncia dos veces el mismo cambio

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** `#search-results` es a la vez el contenedor de la lista y la región `aria-live="polite"`, así que cada respuesta de htmx hace leer los encabezados y todos los enlaces, sin una línea de recuento. El panel corta en cinco resultados por grupo y hay seis grupos: una respuesta puede traer hasta 30 resultados más «Abrir estos resultados en una página». `minlength="2"` no frena a htmx y la vista busca con cualquier largo, así que con la primera letra se anuncia «Sin resultados». El campo tampoco tiene `aria-controls` ni `aria-describedby` hacia los resultados. En la tirada, el clic en un contacto escribe «Registro i de n: título» en la región viva y, además, mueve el foco al título, que el lector vuelve a leer.

**Evidencia.**

- `backend/templates/base.html:101-109` — el campo con `minlength="2"` y `hx-trigger="input changed delay:300ms, search"`, sin `aria-controls`; `#search-results` con `aria-live="polite"`.
- `backend/templates/content/partials/_search_results.html:6-26` — grupos, enlaces y «Sin resultados para…», sin recuento.
- `backend/apps/content/views.py:356-357, 416-423, 453-458` — cinco por grupo y ningún largo mínimo para la búsqueda de texto.
- htmx 2.0.10 vendorizado — la validación del campo solo actúa en formularios o con `hx-validate="true"`.
- `backend/static/js/registros.js:57-71, 74-79` y `backend/templates/content/partials/_tirada.html:60, 65` — el anuncio y el movimiento del foco en el mismo clic.
- curl de `/buscar/?q=c` con `HX-Request` («Sin resultados para “c”») y de `?q=casa` (dos grupos y diez enlaces).

**Por qué importa a futuro.** Una persona con NVDA abre la lupa y escribe «casa». A los 300 ms de la primera letra oye «Sin resultados para c»; con la palabra completa, dos encabezados y nueve títulos más «Abrir estos resultados en una página», sin saber cuántos hay. Si se sube el tope del panel o se añaden grupos, la lectura en cada pausa crece en proporción.

**Recomendación.** Sacar `aria-live` de `#search-results` y añadir un `<p class="sr-only" role="status">` que la parcial rellene (con `hx-swap-oob`) con «N resultados para «q»». Para el mínimo de letras, `hx-validate="true"` en el campo hace que htmx respete `minlength` sin necesitar un filtro de disparo con eval, que la CSP bloquearía (al borrar hasta dejar una letra hay que limpiar los resultados viejos); otra opción es que la vista responda con una pista si la consulta tiene menos de dos letras. En `registros.js`, escribir en la región viva solo cuando el foco no se mueve (el deslizamiento con el dedo), no al pulsar un contacto.

**Matiz de la verificación.** Los «hasta 10 enlaces» del texto original eran el caso medido, no el tope, que es mayor. El «Sin resultados» con una letra no es falso en sentido estricto: confunde porque llega a mitad de la escritura.

**Decisión registrada.** `docs/deferidos-y-decisiones.md`, §4 (rediseño), «Sin comprobar con un lector de pantalla», sobre cómo anuncia la región viva del buscador los resultados agrupados, y §1 (UX), D2 y D16 (diferido conocido). Estaba anotado que no se había comprobado, y el hallazgo confirma que anuncia mal. Ya se puede corregir sin lector de pantalla: una región viva aparte para el recuento y un mínimo de letras.

#### COM-11 · Alta del boletín: sin `autocomplete="email"` (1.3.5), consentimiento sin asociar y errores que vuelven como aviso arriba, saltado por «Saltar al contenido»

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** alta · **Verificación:** confirmado

**Qué pasa.** El campo del boletín, en el pie de todas las páginas, no declara su propósito, a diferencia del formulario de `/enviar/`, que sí usa `autocomplete` para el nombre y el correo: la convención no es uniforme. El texto de consentimiento no está ligado al campo. Y la vista responde a cualquier error con un mensaje y una redirección: el aviso se pinta en `.mensajes`, antes de `<main>` y sin ningún `role`; el destino del enlace de salto (`#main`, o `#contenido` en la portada) queda después del aviso; el correo tecleado se pierde y el campo no recibe `aria-invalid`.

**Evidencia.**

- `backend/templates/base.html:159-168` — el formulario escrito a mano: `<input id="news-email" type="email" …>` sin `autocomplete`, y el texto de consentimiento sin id ni `aria-describedby`.
- `backend/templates/base.html:68, 118-125, 133` — el enlace de salto, `.mensajes` sin rol y `<main>` después.
- `backend/templates/content/home.html:4, 45` — en la portada el salto va a `#contenido`, también después del aviso.
- `backend/apps/community/views.py:58-65` — con el límite de tasa o un formulario inválido, mensaje y redirección, sin ancla al campo ni el valor de vuelta.
- `backend/apps/community/forms.py:1-11` — el pie no se pinta desde este formulario, así que el arreglo va en `base.html`.
- `backend/apps/submissions/forms.py:102-106` — el contraejemplo, con `autocomplete` en nombre y correo.

**Por qué importa a futuro.** Una gestora que usa lector de pantalla teclea mal su correo en el pie de una reseña y envía. La redirección la deja arriba de la misma página, con el campo vacío, y «Revisa el correo ingresado.» queda en un párrafo sin rol entre la cabecera y `<main>`; si usa «Saltar al contenido», se lo salta, y al volver al pie no hay ningún error junto al campo. El navegador tampoco le ofrece su correo, porque el campo no declara `autocomplete="email"`. El próximo formulario se copiará del pie, que se ve en todas partes, y no de `/enviar/`.

**Recomendación.** Añadir `autocomplete="email"` y un `aria-describedby` hacia el texto de consentimiento, con su id. Ante un error, redirigir a `next + "#news-email"` para volver al campo (o mover el foco al aviso), pintar el error junto al campo con `aria-invalid` y reponer el valor desde la sesión. Poner `role="status"` o `"alert"` en `.mensajes` ayuda poco aquí: el aviso llega en una página nueva, y las regiones vivas no anuncian de forma fiable lo que ya está presente al cargar.

**Matiz de la verificación.** El formulario aparece en toda página que extienda `base.html` (35 plantillas), no solo en las 21 que se midieron.

#### COM-12 · No hay política para renombrar rutas públicas, y el vocabulario de las rutas ya invita a hacerlo

**Severidad:** baja · **Esfuerzo:** S · **Confianza:** media · **Verificación:** confirmado

**Qué pasa.** Las rutas se han renombrado sin dejar redirección: el commit `b5250ae` cambió `dosieres/` y `dosier/<slug>/` por `colecciones/` y `coleccion/<slug>/` y borró las viejas; fue antes del lanzamiento, así que entonces no costó nada. Hoy el archivo de textos es `/textos/` pero la ficha sigue en `/articulo/<slug>/`, un desajuste que un agente «ordenado» tenderá a corregir. Como los feeds, el sitemap y `get_absolute_url` usan `reverse`, todo seguiría al cambio salvo lo que importa: las URL ya difundidas darían 404 y los GUID de todos los textos cambiarían a la vez (COM-1).

**Evidencia.**

- `backend/apps/content/urls.py:9, 11, 17-18` — `textos/` frente a `articulo/<slug>/`; `colecciones/` y `coleccion/<slug>/`.
- `git show b5250ae -- backend/apps/content/urls.py` — el renombre sin redirección.
- `git log -p` de los `urls.py` — solo dos commits borran rutas: `b5250ae` (el renombre) y `b5de545` (la misma ruta con otra vista).
- `backend/apps/content/feeds.py:35-49` — `item_link` con `reverse` y sin `item_guid`: el GUID es la URL.
- `infra/caddy/Caddyfile:1-96` — sin `redir` ni `rewrite`.
- `backend/tests/test_get_absolute_url.py:25-31` — mitigación parcial: fija `/articulo/un-texto/`, `/coleccion/una-coleccion/` y `/pagina/una-pagina/`, aunque su docstring habla del botón «Ver en el sitio» y nada impide actualizar las aserciones.

**Por qué importa a futuro.** Una sesión que unifique el vocabulario pasa `articulo/<slug>/` a `texto/<slug>/`, actualiza las tres aserciones de la prueba y la suite vuelve a verde. Desde ese despliegue, todos los enlaces a reseñas difundidos en prensa, redes y correos dan 404, y los lectores RSS ven los 20 textos del feed como ítems nuevos.

**Recomendación.** Una regla escrita en `config/urls.py`, donde la verá el próximo agente: las rutas públicas son permanentes, y renombrar una exige dejar la vieja con `RedirectView(permanent=True)`. Una metaprueba con la lista congelada de prefijos públicos (`articulo/`, `poema/`, `registro/`, `integrante/`…) que falle si alguno deja de resolver o de redirigir; `test_get_absolute_url.py` es su embrión natural: basta ampliarla y declarar en ella la regla. Y GUID estables (COM-1), para que los feeds no dependan de la ruta.

## 5. Orden sugerido de ataque

El orden combina tres criterios: lo que ya puede causar daño o pérdida, lo que es requisito de otras correcciones y lo que cuesta poco. Todos los hallazgos aparecen al menos una vez; cuando uno se reparte entre pasos, se indica qué parte va en cada uno.

### Antes de seguir agregando funcionalidades

1. **Que los respaldos sirvan:** RES-2 y OPE-3. Que un fallo de `tar` aborte y avise, que restic agrupe bien la retención y que `restore.sh` sea atómico y sepa restaurar desde restic. Hoy un respaldo incompleto se reporta como completo.
2. **Que el despliegue migre antes de arrancar:** OPE-1. Un servicio `release` en el compose, o como mínimo reordenar la guía y quitar el «si hubo migraciones». Un campo nuevo en SiteProfile tumbaría todo el sitio.
3. **Que nada privado llegue al repositorio ni a la web:**
   - HER-1, con la parte de ARQ-7 y SEG-2 que toca a la exportación: filtro por fila y una prueba sobre `datos.json`. Y el paso trivial de HER-8: excluir el documento personal de `docs/`.
   - RES-1, con lo barato de RES-8: una lista permitida de formatos, reescribir siempre el original, registrar los fallos y bajar el tope de píxeles.
   - El punto 2 de AGE-1: `Recording.evento_publico` en las cinco salidas del evento.
4. **Corregir hoy los comentarios que afirman garantías falsas,** porque los agentes los obedecen: el punto 1 de TAR-1 (acks_late, límites de tiempo), las cinco afirmaciones de SEG-2 y la «Estructura» del README de ARQ-7.
5. **La visibilidad, en este orden:** primero la matriz de pruebas de PRU-1, después el QuerySet `.publicados()` de AGE-1 y la visibilidad derivada de WEB-1. Centralizar el filtro sin la matriz puede volver a publicar lo archivado sin que nada falle.
6. **Roles que funcionen y se puedan revocar:** AGE-2, DOM-2 y PRU-4 juntos. Matriz de roles, permisos de poema para el autor, preguntar al dueño por agenda y showcase, `has_perm` y `allowed_permissions` en las transiciones y pruebas HTTP del panel con los grupos reales.
7. **Correcciones pequeñas con efecto visible:** REN-1 (`F("search_vector")`), DAT-1 (firmas en orden), FRO-3 (los versos del poema destacado), WEB-2 (proteger las páginas legales), FRO-7 (`[hidden]` global), WEB-5 (HEAD en la búsqueda), WEB-6 (`next` del boletín) y REN-8 (`CONN_HEALTH_CHECKS`).
8. **Antes de definir `SENTRY_DSN`:** RES-3, TAR-4 y RES-4. En RES-4, la redacción recursiva va antes de tocar el logging de Celery, para no abrir una fuga peor.
9. **Antes de anunciar el RSS o enviar el pódcast a los directorios:** COM-1 y COM-5. GUID estables y slug congelado al publicar.

### En las próximas semanas

- **Flujo editorial:** ARQ-2 y DOM-1 juntos (la tarea programada pasa por `perform_transition`; validar la fecha; desprogramar), con el punto 1 de AGE-4. Después, DOM-3 (vista previa), DOM-5 (estados del boletín y de los envíos de solo lectura) y DOM-6 (bitácora).
- **Archivos e imágenes:** DAT-4 (borrar en `on_commit`), TAR-5 (registro automático y metaprueba), DAT-2 (`PROTECT` y usos de cada imagen), DOM-4 (archivos de lo despublicado) y TAR-2 con el resto de RES-8 (un único `procesar_imagen`). TAR-6 y RES-5 se resuelven juntos (el color en una columna; caché sin claves eternas o separada del broker), y con ellos OPE-7 (una sola regla para las URL de Redis).
- **Correo y tareas:** el resto de TAR-1, TAR-3 (ciclo del suscriptor y fecha de resolución de los envíos), TAR-7, TAR-8 y RES-10.
- **Configuración y operación:** OPE-2 (settings de pruebas y prueba de estáticos), OPE-4 (cargar el compose de producción en el CI), OPE-5, OPE-6, OPE-8, RES-6 (latido de beat y monitor), RES-7 (plazos), RES-9 y REN-4. REN-2 y HER-4 juntos: TinyMCE con la versión en la ruta y un manifiesto de lo vendorizado.
- **Pruebas:** PRU-2 (`node --check` y prueba de humo con navegador) junto con FRO-2 (la marca la pone el guion), PRU-3 y PRU-5 (metapruebas y migraciones de datos), PRU-6 (un analizador de CSS) y FRO-8 (borrar las reglas muertas y la prueba que exige una).
- **Seguridad y datos:** SEG-1 (`|safe` con garantía a la salida), SEG-3, SEG-5 y DAT-3 (una sola regla de acentos en la búsqueda).
- **Accesibilidad:** COM-2, COM-3, COM-7, COM-10 y COM-11. COM-4 se lleva al dueño como decisión.
- **URL y feeds:** COM-6 (`SITE_URL`), COM-8, COM-9 y COM-12.
- **Herramientas de desarrollo:** HER-2 (una app de desarrollo y una sola guarda), HER-3 (un solo camino para poblar desarrollo) y HER-6 (que las mediciones exijan un 200).

### Cuando se toque la zona

- **Arquitectura:** ARQ-4 (la app de sitio, por etapas), ARQ-8 (el comentario de las capas y un contrato de imports), ARQ-1, ARQ-3, ARQ-5 y ARQ-6.
- **Capa HTTP:** WEB-3 (composición en plantillas), WEB-4 (queryset `para_fila()`), WEB-7, WEB-8 y WEB-9.
- **Plantillas, CSS y JS:** FRO-1 (una fuente por cada medida), FRO-4 (`@layer` y la cabecera), FRO-5, FRO-6, FRO-9 (una sola estructura de navegación, tras decidir dónde va Prensa) y FRO-10.
- **Seguridad:** SEG-4.
- **Pruebas:** PRU-7 (reorganizar por componente), PRU-8, PRU-9 y PRU-10.
- **Mantenibilidad:** MAN-1 (regla de idioma y las claves trampa), MAN-2, AGE-3 (la pasada de comentarios) y el resto de AGE-4.
- **Rendimiento:** REN-3, REN-5, REN-6 y REN-7.
- **Datos y herramientas:** DAT-5 (decidir los campos sin efecto), HER-5, HER-7 y el resto de HER-8.

## 6. Cómo trabajar con agentes para que esto no se repita

Casi ningún hallazgo es un error de un día: son el resultado de muchas sesiones que resolvieron bien su tarea sin ver el conjunto. La defensa no es revisar más a mano, sino convertir cada regla importante en algo que falle solo cuando se rompe, y dejar escrito lo que no se puede automatizar.

### 6.1 Reglas que se pueden imponer en el CI

- **Metapruebas de completitud** (ARQ-1, TAR-5, PRU-3, AGE-2, COM-12). Una prueba que recorra `apps.get_models()` y exija, para cada modelo de `apps.*`, que: sus FileField tengan los receptores de filecleanup; si tiene página pública, esté en `SITEMAPS` o en una lista explícita de excluidos; esté en `MODELOS` o en `NO_VIAJAN`; y esté en la matriz de roles. Otra que compruebe que cada tarea del schedule de beat está registrada, y otra con la lista congelada de prefijos públicos, que falle si alguno deja de resolver o de redirigir.
- **Contratos de dominio** (AGE-1, PRU-1, WEB-1, SEG-1). Una prueba «canario» por modelo publicable: un objeto oculto, enlazado desde objetos publicados, no aparece en ninguna superficie. Una prueba que falle si aparece `published=True` o `status=…PUBLISHED` fuera de los QuerySets, y otra que prohíba `|safe` en las plantillas salvo el filtro aprobado.
- **JavaScript en un navegador de verdad** (PRU-2, FRO-2, FRO-10, COM-2, COM-7). `node --check` y un ESLint mínimo que fije un dialecto; una prueba de humo con el Playwright que ya trae `tools/ux/`, a 951 y 375 px, que falle ante cualquier error de página o de consola; y axe con la regla de contraste sobre `pages.txt`.
- **CSS analizado, no buscado como texto** (PRU-6, FRO-8). Un único helper con un analizador real para las pruebas de la hoja, y una prueba de que cada selector casa en alguna página renderizada.
- **El despliegue, ensayado** (OPE-1, OPE-4, OPE-8, HER-8). `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q` y el compose de producción levantado en el CI; las imágenes del CI fijadas por digest, con la prueba de fijado extendida a los workflows; un `.python-version` y pip con versión; `pre-commit run --all-files` (con el control de tamaño) como job.
- **Comentarios que no narran** (AGE-3, SEG-2). Un paso que falle si aparece en el código un identificador de decisión nuevo (S-NN, «ticket N», «hallazgo», «paso N», «Lote») fuera de las migraciones.
- **Una configuración de pruebas explícita** (OPE-2, MAN-1). Un módulo de settings para pytest, con `CELERY_TASK_EAGER_PROPAGATES`, `string_if_invalid` que haga fallar las claves equivocadas en las plantillas y una prueba de que cada `{% static %}` existe.
- **Las capas, congeladas** (ARQ-8). Un contrato de import-linter que registre las aristas actuales entre apps y falle si aparece una nueva.

### 6.2 Convenciones para escribir en CLAUDE.md o CONTRIBUTING.md

Estas reglas no se pueden comprobar del todo con herramientas, pero un agente las sigue si las lee antes de empezar:

1. **Dónde va cada cosa** (ARQ-6, ARQ-4). Las consultas reutilizables son métodos de QuerySet; los cambios de estado van en `services.py` o `workflow.py`; los cálculos visuales, en templatetags o presentadores; las señales, en `signals.py`; lo transversal, en la app de sitio o en `config/`, nunca en la app que se esté tocando.
2. **Lo publicable** (AGE-1, WEB-1, ARQ-5). Todo modelo con página pública tiene `.publicados()` (o `visibles()`), `get_absolute_url` y un accesor que respete el estado en cada relación hacia algo publicable. El filtro de visibilidad nunca se escribe a mano.
3. **Una sola fuente por dato** (FRO-1, ARQ-3, FRO-9). Los números del diseño viajan del servidor al CSS y al JS como atributos `data-` o propiedades CSS; las rutas, con `reverse()`; las listas de navegación, desde una estructura.
4. **Comentarios** (AGE-3, SEG-2). Dicen qué hace el código hoy y qué restricción lo explica; la historia va en el commit. Una garantía de seguridad o de privacidad no se escribe en un comentario: se escribe una prueba.
5. **Pruebas** (PRU-2, PRU-8, PRU-4). Comprueban lo que ve o hace una persona. Solo se lee `.css` o `.js` para afirmar una invariante. Toda prueba de «no aparece» lleva un control positivo. Los permisos se prueban por HTTP, con los grupos reales. Si una prueba falla tras un cambio de diseño, no se copia el valor nuevo sin preguntarse qué vigilaba.
6. **Errores** (RES-1, RES-2, RES-9). Nada de `except Exception: return` sin registro; lo inesperado, con `logger.exception`; los controles de privacidad fallan cerrados; un proceso solo declara éxito cuando lo verificó.
7. **URL públicas** (COM-5, COM-12, COM-1). El slug de lo publicado no se cambia; renombrar una ruta exige dejar la vieja con `RedirectView(permanent=True)`; el GUID de un ítem de feed no cambia nunca.
8. **Lo que sale del sistema** (HER-1, RES-3, TAR-4). Exportaciones, logs, Sentry y archivos: listas blancas por fila y por campo, y a las tareas se les pasan identificadores, no datos personales. Nunca `git add` de carpetas enteras.
9. **Tareas y migraciones** (TAR-1, PRU-5, OPE-1, AGE-2). Cada tarea declara sus límites, su política de reintento y si es idempotente, y se encola con `delay_on_commit`. Toda migración de datos lleva su prueba; los cambios de esquema se hacen en dos pasos (primero añadir, después quitar); los permisos de un modelo nuevo llegan por migración.
10. **Idioma de los identificadores** (MAN-1). Una sola regla, escrita, para el código nuevo.
11. **Herramientas de desarrollo** (HER-2, HER-3). Viven en su propia app, fuera de la imagen; hay un único camino para poblar desarrollo; `--force` no existe.

### 6.3 Qué exigir en cada PR

Una lista corta en la plantilla del PR, que el agente rellena y el dueño puede leer sin leer código:

- ¿Cambia el comportamiento de alguna regla? ¿Se actualizaron su comentario y su prueba de contrato?
- ¿Añade un modelo, un campo de archivo, una ruta pública, una tarea o un ajuste de entorno? ¿Pasan las metapruebas, y se decidió de forma explícita el sitemap, la exportación, los roles y la limpieza?
- ¿Las pruebas nuevas comprueban comportamiento? ¿Se copió algún literal de CSS o JS en una prueba?
- ¿Hay migración? ¿Es de datos, y tiene prueba? ¿Funciona con el código anterior mientras se despliega?
- ¿Toca algo que sale del sistema (logs, Sentry, exportación, archivos servidos)? ¿Qué datos viajan ahora?
- ¿Se probó también con `DEBUG=0`, en la vista previa de producción, y no solo en desarrollo?
- La descripción explica el porqué del cambio: es lo que ya no va en los comentarios.

## Apéndice A. Método y cifras

**Alcance.** Repositorio completo en el commit `38fdf03` (2026-10-27). Catorce dimensiones:

1. Arquitectura y límites entre módulos.
2. Modelo de datos, migraciones e integridad.
3. Capa HTTP: vistas, URLs, formularios y consultas.
4. Plantillas, CSS y JavaScript.
5. Seguridad como propiedad del código.
6. Tareas en segundo plano, correo, caché y ciclo de vida de archivos.
7. Configuración, despliegue, CI y operación.
8. Calidad y estrategia de la suite de pruebas.
9. Mantenibilidad y salud del código Python.
10. Huellas de código generado por agentes de IA.
11. Rendimiento y eficiencia.
12. Manejo de errores, resiliencia y observabilidad.
13. Dominio editorial: flujo de estados, visibilidad, permisos y admin.
14. Herramientas de desarrollo, datos de demostración y salud del repositorio.

A ellas se sumaron dos auditorías complementarias, para huecos que el rastreo inicial no cubría: la accesibilidad de los componentes propios, comprobada en un navegador con el JS en marcha, y la permanencia de las URL públicas y de los identificadores de los feeds.

**Proceso.** Antes de redactar intervinieron 101 agentes: un rastreo por dimensión, la deduplicación, la verificación de cada hallazgo, un crítico de completitud, las dos auditorías complementarias con su propia verificación y el cruce con `docs/deferidos-y-decisiones.md`. El rastreo produjo 162 hallazgos brutos, que la deduplicación redujo a 101; con los 12 de las auditorías complementarias quedaron 113.

**Verificación.** Cada hallazgo pasó por un verificador que intentó refutarlo: releyó la evidencia, reprodujo lo que se podía reproducir sin escribir en la base y lo contrastó con el contexto del proyecto. Los propuestos con severidad alta pasaron por un panel de tres verificadores con enfoques distintos (evidencia general, reproducción y contexto), que decidió por mayoría; los de severidad baja se verificaron en lotes. Resultado: 47 confirmados, 66 parciales (sostenidos con correcciones, recogidas en cada ficha) y ninguno refutado ni sin verificar. La severidad final quedó en 10 altas, 66 medias y 37 bajas. La verificación bajó la severidad de 24 hallazgos y subió la de uno (ARQ-7). Además, 63 hallazgos se relacionan con una entrada del registro de decisiones: 50 como decisión relacionada, 9 como diferido ya conocido y 4 que la contradicen (DAT-3, RES-3, RES-5 y COM-4).

**Línea base medida.**

- `ruff check` sin errores (reglas E, W, F, I, UP, B y C4); `ruff format --check`: 192 archivos ya formateados.
- `makemigrations --check --dry-run` sin cambios pendientes; `manage.py check` sin problemas.
- pytest: 985 pruebas recolectadas, todas en verde (6 omitidas; 5 marcadas «integration»). Cobertura de ramas del 95 %: 3.128 sentencias, 111 sin cubrir, 45 archivos al 100 %.
- Menor cobertura: `config/redaction.py` (61 %), `apps/submissions/admin.py` (75 %), `config/context_processors.py` (85 %), `apps/media/models.py`, `apps/media/filecleanup.py` y `apps/content/permissions.py` (88 %), `apps/media/feeds.py` (90 %), `apps/content/sitemaps.py` (93 %) y `apps/content/views.py` (94 %).
- Tamaño: unas 8.400 líneas de Python de aplicación (sin migraciones ni pruebas), 11.800 de pruebas (83 archivos `test_*.py`, más `conftest.py` y `factories.py`), 2.300 de plantillas, un `site.css` de 1.970 líneas y unas 460 de JS propio; 39 migraciones (47 archivos si se cuentan los `__init__.py`, que es la cifra que dio la medición inicial).
- Historial: 488 commits entre el 2026-07-09 y el 2026-10-27. Los archivos de código más reescritos: `site.css` (79 commits), `apps/content/views.py` (40), `templates/content/home.html` (39), `templates/base.html` (36), `tests/test_css_sistema.py` (32), `config/settings.py` (22) y `.github/workflows/ci.yml` (21).

**Lo que no se cubrió.**

- Los agentes no ejecutaron la suite ni levantaron otros stacks: la línea base se midió una vez, al principio. Todas las mediciones fueron de solo lectura sobre el stack de desarrollo (shell de Django, `curl`, peticiones con el cliente de pruebas, Playwright), salvo una lectura pasiva de `docker stats` de la vista previa de producción. Nada se midió en el VPS real ni en GitHub Actions.
- No se provocaron fallos reales (Redis colgado, disco lleno, falta de memoria, SMTP caído con Sentry activo): su comportamiento se dedujo del código de las librerías instaladas en el contenedor y de mediciones en memoria.
- Las fugas que exigían escribir en la base para reproducirse (un registro publicado con su evento oculto, el coautor externo de un poema) se establecieron siguiendo el código.
- El panel de administración no se midió con sesiones reales, porque iniciar sesión escribe en la base: se usó RequestFactory y el código de Django. Un posible N+1 en el inline de la bitácora editorial quedó sin verificar.
- No se probó con lectores de pantalla reales ni con Firefox o Safari; tampoco el zoom solo de texto, el espaciado de texto ni la impresión del dossier.
- Casi todas las dimensiones dejaron fuera `docs/`, para no heredar conclusiones previas: las citas de `docs/despliegue.md` y `docs/respaldos.md` las aportó el rastreo de operación, y algunos verificadores no pudieron contrastarlas; el registro de decisiones solo se usó para el cruce. Tampoco se consultaron avisos de seguridad de TinyMCE 7.9.3 ni de htmx 2.0.10, ni se revisaron en detalle los comandos de siembra (solo sus guardas), el código vendorizado o algunas plantillas largas. Los permisos de los grupos se midieron en la base de desarrollo, no en la de producción.

## Apéndice B. Hallazgos descartados en la verificación

La verificación no refutó ningún hallazgo entero. Sí retiró o corrigió afirmaciones concretas dentro de los 66 hallazgos parciales. Estas son las que una auditoría futura no debería volver a levantar tal cual:

- «La extensión unaccent se usa desde cuatro apps sin declarar la dependencia» — los cuatro lookups están en `content/services.py`, la app que crea la extensión (DAT-3).
- «filecleanup no mira `raw`, y loaddata dispara borrados» — loaddata construye instancias nuevas y el manejador sale antes de borrar (DAT-4).
- «Cada guardado de una imagen tarda segundos, y la señal y `SiteProfile.save` repiten el trabajo» — las copias solo se codifican si faltan (TAR-2).
- «Generar las copias de portada antes de limpiar el EXIF filtra el GPS» — los guardadores de Pillow no copian el EXIF (TAR-2).
- «El procesado de imágenes se acerca al `--timeout` de gunicorn» — con workers gthread ese plazo no limita la petición (TAR-2, RES-7).
- «Con gthread, `/healthz/` sigue respondiendo con todos los hilos ocupados» — pasa por el mismo pool y el contenedor queda unhealthy (RES-7).
- «redis-py espera indefinidamente a un Redis colgado» — con redis 8.1.0 rigen 5 s por operación (TAR-8).
- «Los resultados de Celery se acumulan en Redis» — caducan al día (RES-5, OPE-7).
- «Un `cache_page` o un `get_or_set` sin caducidad crean claves eternas» — Django aplica 300 s por defecto (RES-5).
- «En modo eager, Celery no serializa los argumentos» — Celery 5.6.3 sí los serializa (OPE-2).
- «Una tarea con `acks_late` nunca se reencola» — sí, si muere el proceso principal; el comentario falla en los demás casos (TAR-1).
- «El GUID de los feeds cambia con el Host de cada petición en producción» — Caddy fija el host y `SECURE_PROXY_SSL_HEADER`, el esquema (COM-1).
- «Con un CDN delante, el canonical pasa a http» — la redirección a HTTPS provocaría un bucle visible, no un canonical en http (COM-6).
- «El JS de prepopulate reescribe el slug al cambiar el título» — no lo hace en un objeto ya guardado (WEB-2, COM-5).
- «La redirección de colaborador a integrante debería ser un 301» — sería dañino, porque la membresía es mutable (WEB-8, COM-8).
- «Faltan `Cache-Control` y `Vary: Cookie`» — es el comportamiento estándar de Django y no tiene efecto sin una caché compartida (WEB-8).
- «El docstring de la baja del boletín miente sobre el CSRF» — declara la exención y su motivo; lo que falta es una prueba que la fije (SEG-2).
- «Los comentarios de `setup_groups` y de `content/permissions.py` son falsos» — son ciertos (ARQ-7).
- «Los guiones mienten al decir que la CSP no les deja escribir estilos» — `style-src 'self'` bloquea los atributos `style`: es impreciso, no falso (AGE-3).
- «Los códigos de decisión de los comentarios perdieron su razón» — siguen documentados en `docs/deferidos-y-decisiones.md`, y la razón está escrita en prosa (WEB-3, AGE-3).
- «La agrupación por año de la trayectoria no se prueba» — la fija `test_filas.py:203-236` (PRU-8).
- «Solo tres vistas tienen prueba de escalado de consultas» — hay al menos ocho (PRU-8).
- «La prueba del dossier sobre lo oculto no tiene control positivo» — lo cubre `test_dossier_aggregates_everything` (PRU-8).
- «Un formateador rompe las aserciones hechas con `_regla`» — `_regla` normaliza espacios; los que se rompen son los cortes por texto (PRU-2).
- «Una prueba de navegador habría detectado el fallo de `registros.js`» — fue la caché del navegador (PRU-2).
- «`--import-mode=importlib` rompería `test_media_aislado`» — es falso con `pythonpath = .` (PRU-10).
- «Las pruebas de la política de seguridad deberían derivar los valores de las constantes» — afirmar literales ahí es correcto; lo que falta es la prueba de coherencia entre copias (SEG-4).
- «El `data:` de `img-src` diverge de nh3» — lo usan el grano del CSS y las pieles de TinyMCE (SEG-4).
- «`/readyz/` público es un vector de saturación» — no cuesta más que cualquier página (SEG-3, RES-6).
- «El `|safe` expone hoy contenido sin sanear» — los tres caminos actuales llevan contenido ya limpio; es una garantía a futuro (SEG-1).
- «`allowEval` de htmx abre una vía de ataque» — la CSP sin `'unsafe-eval'` lo neutraliza; el riesgo real son los atributos `hx-*` (SEG-1).
- «Que `MODELOS` sea opt-in es un defecto» — es una salvaguarda de privacidad que falla del lado seguro (ARQ-1).
- «Hace falta un registro central de tipos de contenido» — es desproporcionado: bastan metapruebas (ARQ-1).
- «Hay que mover Recording a otra app e invertir el OneToOne de Work» — es desproporcionado para esta deuda (ARQ-8).
- «Hay que publicar la imagen en un registro y desplegar esa» — es desproporcionado para un solo VPS: basta con cargar el compose real en el CI (OPE-4).
- «HSTS con `includeSubDomains` y `preload` es irreversible y está fijado en el código» — `DJANGO_HSTS_SECONDS` lo controla, y `preload` no actúa sin enviar el dominio (OPE-6).
- «El worker supera su límite de memoria en un VPS típico» — solo con 10 o más vCPU (REN-4).
- «Una copia de 192 px bastaría para las miniaturas» — las recortadas necesitan entre 290 y 430 px (REN-3).
- «Los `.gz` sin uso y las copias sin hash con caché inmutable cuestan rendimiento» — no tienen efecto práctico (REN-2).
- «`nav_sections` cuesta consultas» — es un queryset perezoso que nunca se evalúa (ARQ-5, REN-5).
- «La UNION de la búsqueda puede romperse solo con ciertos datos» — sus tipos se resuelven al analizar la consulta (RES-9).
- «Una ficha nueva perdería la sub-fila del colectivo» — esa sub-fila solo existe en los seis índices del colectivo (FRO-6).
- «En producción, `exportar` alcanza el repositorio» — la imagen no lo monta; el riesgo real es una copia de producción restaurada en local (HER-1).
- «Borrar una pieza con su bitácora es silencioso» — la confirmación lista las transiciones y el LogEntry registra el borrado (DOM-6).
- «Los cambios de estado hechos en el panel no dejan rastro» — dejan un LogEntry con usuario, hora y campos (DOM-1, DOM-5).
- «Los huérfanos del volumen de desarrollo miden el defecto de limpieza» — son restos de pruebas anteriores al aislamiento de los medios (TAR-5).
- «Un JPEG truncado con GPS se ve bien» — se pinta con una franja gris y sin derivados; el AVIF sí se ve bien (RES-1).
