# Backlog de la auditoría de código

> **Fuente:** [`docs/auditoria-codigo.md`](auditoria-codigo.md), commit `38fdf03` (2026-10-27), con 113 hallazgos.
> **Decisiones:** C1 a C29, tomadas por el dueño el 2026-10-28. El porqué de cada una está en [`docs/deferidos-y-decisiones.md`](deferidos-y-decisiones.md) §1, y lo diferido, en su §3.
> **Avance:** 0 de 79 tickets cerrados (32 S, 43 M y 4 L). Antes del lanzamiento son imprescindibles 30: los marcados «sí», más B07, que es urgente.

## Cómo se usa

- **Un ticket, un PR.** Los de tamaño L se hacen por etapas, un PR por etapa, y el ticket dice cuáles son.
- **Antes de empezar, leer en la auditoría las fichas que cita el ticket.** Allí están la evidencia, la recomendación y lo que corrigió la verificación. El ticket solo añade lo que no está en la ficha: el alcance decidido, el orden y cuándo está hecho. Si chocan, manda el ticket, porque recoge las decisiones del dueño.
- **El orden:** las tandas, en orden. Dentro de una tanda se respeta «Depende de», y lo que no depende de nada puede ir en paralelo, en ramas distintas.
- **El lanzamiento:** las tandas 0 a 4 van antes de lanzar. Los tickets con «sí» en «Lanzamiento» no pueden quedar pendientes.
- **Lo visual:** cuando un ticket cambia algo a la vista, o dice «decisión visual», se muestra al dueño antes de fusionar, con alternativas si hay más de una manera. Lo que él apruebe manda.
- **Hecho** quiere decir: el criterio del ticket se cumple, la suite y ruff pasan en local y el CI de GitHub Actions está en verde (pip-audit y gitleaks solo corren allí).
- **Al cerrar un ticket,** se pone el número del PR en «Estado» y se actualiza el avance. Si una parte del alcance quedó fuera, se dice en el ticket; si se decide no hacerla, va a §3 del registro de decisiones con su motivo.
- **Los identificadores de ticket** van en el título del PR y en el mensaje del commit, nunca en comentarios del código (B02).

## 1. Decisiones

| # | En una línea | Tickets |
| --- | --- | --- |
| C1 | Aún no hay producción: direcciones, identificadores y permisos se corrigen antes de lanzar, sin compatibilidad hacia atrás | B15, B28 |
| C2 | Editor: todo salvo el perfil del sitio y las cuentas. Autor: sus textos y poemas; añade obras al catálogo, no las edita | B15, B16 |
| C3 | Identificadores nuevos en inglés; castellano en los textos visibles y en el vocabulario del diseño | B02, B77 y todo ticket que cree nombres |
| C4 | La copia de desarrollo lleva solo lo público, con nombres ficticios; el historial de git no se reescribe | B07, B64 |
| C5 | `/articulo/<slug>/` pasa a `/texto/<slug>/`; desde el lanzamiento, las rutas públicas son permanentes | B02, B28 |
| C6 | El slug se congela al publicar | B02, B28 |
| C7 | Audio hasta 50 MB, PDF hasta 20 MB, imágenes hasta 12 MB (JPEG, PNG o WebP); los vídeos, solo por enlace | B08, B33 |
| C8 | Sentry y un monitor externo; la redacción, probada antes de definir el DSN | B30, B31, B32 |
| C9 | Campo «Transcripción» en los registros, con aviso en el panel | B51 |
| C10 | Vista previa, «Desprogramar» y «Reabrir» en el flujo editorial | B17, B18 |
| C11 | Fuera los campos sin efecto; se conecta la imagen para compartir del texto | B25 |
| C12 | Fichas de obra, editorial y autor de libro solo con algo publicado detrás | B14 |
| C13 | El original de cada imagen se reescribe sin metadatos, o se rechaza | B08 |
| C14 | El consentimiento y el estado de los envíos no se editan a mano en el panel | B39 |
| C15 | La bitácora editorial guarda título y actor, y es inmutable | B48 |
| C16 | Lo despublicado deja de servirse | B37 |
| C17 | Con Redis caído, las vistas limitadas siguen cerradas, con un mensaje veraz | B36 |
| C18 | `SITE_URL` fijo, sin `www` | B29 |
| C19 | Un servicio `release` migra antes de arrancar | B06 |
| C20 | restic sobre los volúmenes, con la restauración probada | B05 |
| C21 | La galería, paginada | B76 |
| C22 | «Las voces» sin control de pausa; solo se corrige lo del lector de pantalla | B54 |
| C23 | Reabre el FTS por trigger: configuración sin tildes y un solo plegado de acentos | B50 |
| C24 | Reabre qa-21: la redacción de Sentry se prueba | B31 |
| C25 | Reabre `CACHES`: la caché, en un Redis aparte | B36 |
| C26 | Modifica D16 del rediseño: fuera el panel para navegadores sin `:has()` | B72 |
| C27 | Reabre en parte #33: prueba de humo en navegador y axe en el CI | B11, B55 |
| C28 | Reabre la extracción de `SiteProfile` como una app del sitio, por etapas | B67 |
| C29 | «CD real» sigue diferido, con la premisa corregida | B41 |

**Decisiones visuales pendientes**, que se le muestran al dueño al llegar al ticket: el contraste de dos sellos de «Prensa y gestión» (B55) y dónde van Prensa y Aliados en la navegación (B73).

## 2. Plan

**Tanda 0 — Preparar el terreno**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B01 | Retirar las auditorías anteriores sin dejar referencias colgadas | — | S | no | pendiente |
| B02 | Reglas de trabajo para los agentes | — | S | no | pendiente |
| B03 | Guardas baratas en el CI | — | S | no | pendiente |

**Tanda 1 — Lo que puede causar daño**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B04 | El respaldo falla en voz alta | — | S | sí | pendiente |
| B05 | Restauración probada de punta a punta | B04 | M | sí | pendiente |
| B06 | El despliegue migra antes de arrancar | — | M | sí | pendiente |
| B07 | La copia de desarrollo solo lleva lo público | — | M | urgente | pendiente |
| B08 | Las fotos no publican su ubicación | — | M | sí | pendiente |
| B09 | Comentarios y documentos que afirman lo falso | B07 | S | no | pendiente |
| B10 | Un registro publicado no enseña su evento oculto | — | S | sí | pendiente |

**Tanda 2 — Red de pruebas y reglas de dominio con una sola fuente**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B11 | Navegador en el CI: prueba de humo | — | M | no | pendiente |
| B12 | Matriz de pruebas del flujo editorial y de la visibilidad | — | M | sí | pendiente |
| B13 | «Publicado», definido en un solo lugar | B12 | M | sí | pendiente |
| B14 | Fichas secundarias solo si algo publicado las respalda | B13 | M | sí | pendiente |
| B15 | Roles declarados y sincronizados | B06 | M | sí | pendiente |
| B16 | Permisos de Django en el flujo y en los envíos | B15 | S | sí | pendiente |
| B17 | Una sola forma de publicar y un flujo sin puertas laterales | B12 | M | sí | pendiente |
| B18 | Vista previa para el equipo | B13, B15 | M | no | pendiente |

**Tanda 3 — Correcciones pequeñas con efecto visible**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B19 | Las firmas salen en el orden de la coautoría | — | S | sí | pendiente |
| B20 | La búsqueda ordena por relevancia | — | S | sí | pendiente |
| B21 | El poema destacado conserva sus versos | — | S | no | pendiente |
| B22 | Las páginas legales no se rompen desde el panel | — | S | sí | pendiente |
| B23 | `[hidden]` en una sola regla | B11 | S | no | pendiente |
| B24 | Dos fallos de la capa HTTP: HEAD y `next` | — | S | no | pendiente |
| B25 | Campos sin efecto fuera e imagen para compartir conectada | — | S | no | pendiente |
| B26 | Medidas de la portada: lo que hoy falla | B11 | S | no | pendiente |

**Tanda 4 — Antes de lanzar: configuración, identidad pública y canales**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B27 | Variables de entorno sin ambigüedad | — | M | sí | pendiente |
| B28 | Direcciones e identificadores permanentes | — | M | sí | pendiente |
| B29 | Un origen fijo para las URL absolutas | B27 | M | sí | pendiente |
| B30 | Logs con formato y redacción en todos los procesos | — | M | sí | pendiente |
| B31 | Sentry sin datos personales ni secretos | B29, B30 | M | sí | pendiente |
| B32 | Avisos: monitor, latido y errores visibles | B31 | M | sí | pendiente |
| B33 | Límites de subida por ruta y por campo | — | S | sí | pendiente |
| B34 | Antiabuso del panel | — | S | sí | pendiente |
| B35 | Plazos y procesos acotados | B06 | S | sí | pendiente |
| B36 | Redis: la caché, aparte del broker | B27 | M | sí | pendiente |
| B37 | Lo despublicado deja de servirse | B13 | M | sí | pendiente |
| B38 | Ciclo de vida del suscriptor y de los envíos | — | M | sí | pendiente |
| B39 | El panel respeta el consentimiento y el estado de los envíos | B38 | S | sí | pendiente |
| B40 | Correo de confirmación fiable y con rastro | B27, B38 | M | sí | pendiente |
| B41 | El CI ensaya lo que se despliega | B06 | M | sí | pendiente |

**Tanda 5 — Robustez de archivos, imágenes y datos**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B42 | Los archivos se borran después de confirmar | B08 | S | no | pendiente |
| B43 | Un solo servicio de imágenes | B42 | M | no | pendiente |
| B44 | Registro de derivados | B43 | M | no | pendiente |
| B45 | Metapruebas de completitud | — | S | no | pendiente |
| B46 | Lo publicado no se pierde al borrar | — | M | no | pendiente |
| B47 | Comandos de mantenimiento que avisan | — | S | no | pendiente |
| B48 | Bitácora editorial que sobrevive | B17 | M | no | pendiente |
| B49 | El HTML de autor se sanea a la salida | — | S | no | pendiente |
| B50 | Búsqueda: una regla de acentos y tipos declarados | B20 | M | no | pendiente |
| B51 | Transcripción de los registros | — | S | no | pendiente |
| B52 | TinyMCE con la versión en la ruta y lo vendorizado con radar | — | M | no | pendiente |

**Tanda 6 — Pruebas y herramientas que vigilan**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B53 | Mejora progresiva que falla bien | B11 | S | no | pendiente |
| B54 | Anuncios y foco en los componentes con JS | B11 | M | no | pendiente |
| B55 | Contraste de los sellos y axe en el CI | B11 | M | no | pendiente |
| B56 | Formularios públicos de un solo origen y accesibles | — | M | no | pendiente |
| B57 | Configuración de pruebas explícita | — | M | no | pendiente |
| B58 | Un analizador de CSS para las pruebas | — | M | no | pendiente |
| B59 | Selectores muertos | B58 | M | no | pendiente |
| B60 | Migraciones de datos con prueba | — | M | no | pendiente |
| B61 | Higiene de la suite | — | M | no | pendiente |
| B62 | Herramientas de medición que no dan por bueno un error | — | S | no | pendiente |
| B63 | Herramientas de desarrollo en su propia app | B07 | M | no | pendiente |
| B64 | Un solo camino para poblar desarrollo | B63 | M | no | pendiente |
| B65 | Higiene del repositorio | — | S | no | pendiente |

**Tanda 7 — Orden interno**

| Ticket | Qué | Depende de | Tamaño | Lanzamiento | Estado |
| --- | --- | --- | --- | --- | --- |
| B66 | Contratos de entidad completos | — | M | no | pendiente |
| B67 | La app del sitio, por etapas | B15 | L | no | pendiente |
| B68 | Una política de contenido y una tabla de proveedores | — | S | no | pendiente |
| B69 | La composición visual sale de las vistas | B26 | M | no | pendiente |
| B70 | Parciales con contrato y filas sin N+1 | B13 | M | no | pendiente |
| B71 | Recetas de plantilla compartidas | B25, B29 | M | no | pendiente |
| B72 | La cascada de site.css en capas | B11, B58 | L | no | pendiente |
| B73 | Navegación de una sola fuente | — | S | no | pendiente |
| B74 | Guiones con un módulo común | B11 | S | no | pendiente |
| B75 | Convenciones HTTP | — | S | no | pendiente |
| B76 | Rendimiento menor | — | M | no | pendiente |
| B77 | Nombres trampa y rótulos completos | — | S | no | pendiente |
| B78 | Comentarios que dicen el presente | B03 | L | no | pendiente |
| B79 | La suite, por componente | B61 | L | no | pendiente |

## 3. Tickets

### Tanda 0 — Preparar el terreno

#### B01 · Retirar las auditorías anteriores sin dejar referencias colgadas

**Hallazgos:** AGE-3 (referencias a documentos retirados), HER-7 (las 15 menciones), HER-8 (documento personal) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** El 2026-10-27 se retiraron de `docs/` once documentos de auditorías y planes anteriores; el borrado está preparado, sin commit. Reapuntar o quitar sus referencias:

- `README.md` (líneas 155, 167 y 169) y `CONTRIBUTING.md:87`;
- `tools/ux/README.md` (3, 4, 56 y 93) y `tools/ux/preparar-entorno.sh` (3 y 148);
- el docstring de `backend/tests/test_css_sistema.py:4`;
- en `docs/deferidos-y-decisiones.md`, el encabezado, la nota de la tabla D1–D14 y la del cierre del rediseño;
- `docs/guia-pruebas-manuales.md:174`, `docs/retomar-barrido.md` y `docs/arquitectura-contenidos.md:30`. `docs/tarea-identidad-del-sitio.md` no tenía ninguna.

Donde la referencia aporte algo, remitir a `git show 38fdf03:docs/<archivo>`; si no, quitarla. Añadir `docs/Sesión 00 Bootcamp Odoo.md` a `.git/info/exclude`: es local, y el archivo no se mueve. Hacer el commit del borrado junto con la auditoría, este backlog y los cambios del registro de decisiones, nombrando cada archivo: nunca `git add docs/`.

**Hecho cuando.**

- Ninguna referencia a los once documentos apunta a un archivo que no existe: fuera de la auditoría y de este backlog, solo aparecen en párrafos que remiten a `git show 38fdf03:`.
- `git status` no muestra el documento personal.

#### B02 · Reglas de trabajo para los agentes

**Hallazgos:** ARQ-6, MAN-1, AGE-3, PRU-2, COM-12 (la regla de cada una) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3, C5, C6

**Alcance.** Un `CLAUDE.md` en la raíz, corto (unas 60 líneas, porque se carga en cada sesión), con las once convenciones de la sección 6.2 de la auditoría ajustadas a las decisiones: el idioma de C3, las direcciones permanentes de C5 y C6 y las listas blancas para lo que sale del sistema. Debe decir también:

- los comentarios dicen qué hace el código hoy; la historia va en el commit;
- los identificadores de ticket y de decisión no van en el código;
- los cambios de esquema se hacen en dos pasos (primero añadir, después quitar);
- nunca se hace `git add` de carpetas enteras.

Remite a `CONTRIBUTING.md`, que desarrolla cada regla con un ejemplo del propio código. Además: `.github/pull_request_template.md` con la lista de la sección 6.3 de la auditoría, y la regla de las rutas permanentes como comentario en `config/urls.py`.

**Hecho cuando.**

- `CLAUDE.md`, la plantilla de PR y las reglas de `CONTRIBUTING.md` existen.
- Un PR nuevo muestra la lista de comprobación.

#### B03 · Guardas baratas en el CI

**Hallazgos:** PRU-2 (`node --check`), HER-8 (hooks en el CI), AGE-3 (identificadores de decisión nuevos) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** Tres pasos del CI que protegen el resto del backlog:

- `node --check` de los guiones propios de `backend/static/js/` (fuera de `vendor/`);
- `pre-commit run --all-files`, que incluye `check-added-large-files`;
- una prueba que cuenta, archivo por archivo, los identificadores de decisión o de sesión en el código fuera de las migraciones (`D\d+`, `S-\d+`, «ticket», «hallazgo», «paso N», «Lote»), contra una línea base guardada en el repositorio. Falla si un archivo sube; cuando baja, se actualiza la línea base. B78 la lleva a cero.

**Hecho cuando.** En el PR, tres commits de prueba, revertidos antes de fusionar, ponen el CI en rojo: un guion con un error de sintaxis, un archivo de 3 MB y un comentario nuevo que cita «D35».

### Tanda 1 — Lo que puede causar daño

#### B04 · El respaldo falla en voz alta

**Hallazgos:** RES-2 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** La recomendación de RES-2 completa, salvo la parte de `restore.sh`, que va en B05:

- sin `2>/dev/null || echo`;
- el código 1 de GNU tar («file changed as we read it»), tratado aparte;
- un umbral mínimo de archivos o de tamaño para detectar un volumen montado vacío;
- `gzip -t` y `pg_restore --list` antes de declarar éxito;
- escritura en `$DEST.partial`, que pasa a `$DEST` con un archivo `OK` al final;
- rotación y `latest` solo entre respaldos con `OK`.

**Hecho cuando.**

- En el job del CI, un volumen de medios ilegible y un volumen vacío terminan con una salida distinta de 0 y disparan el ping de fallo.
- Un respaldo completo deja su `OK`, y es el único que `restore.sh latest` elige.

#### B05 · Restauración probada de punta a punta

**Hallazgos:** OPE-3, OPE-8 (procedimiento de `docs/respaldos.md`) · **Depende de:** B04 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C20

**Alcance.** La recomendación de OPE-3, con C20:

- restic respalda los volúmenes directamente, sin tar.gz;
- `restic forget` agrupado por host y etiqueta, con `--prune`, y un `restic check` semanal;
- `restore.sh --from-restic <snapshot|latest>`;
- restauración atómica: `pg_restore --single-transaction --exit-on-error`, verificar los archivos antes de borrar nada, extraer en un directorio nuevo y sustituir al final, con `--db-only` y `--media-only`.

En `docs/respaldos.md`, corregir el procedimiento de restauración (en producción nadie migra al arrancar; ver B06) y documentar la restauración desde restic.

**Hecho cuando.**

- El CI construye `infra/backup/`, respalda contra un repositorio restic local, restaura en una base con el esquema vivo y compara los conteos de filas y de archivos.
- Una restauración que falla a mitad deja la base y los medios como estaban.

#### B06 · El despliegue migra antes de arrancar

**Hallazgos:** OPE-1 · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C19

**Alcance.** La recomendación de OPE-1, con C19:

- un servicio `release` de un solo uso, con la misma imagen, que corre `migrate`, `setup_groups` y `collectstatic` con `restart: "no"`; web, worker y beat dependen de él con `service_completed_successfully`;
- `lock_timeout` en la sesión de `migrate` (RES-7);
- `entrypoint.sh` no migra salvo con `DJANGO_MIGRATE_ON_START=1`, que solo pone el override de desarrollo; fuera el `DJANGO_SKIP_MIGRATE` muerto de worker y beat;
- la imagen etiquetada con el commit (`APP_VERSION`) y el rollback documentado;
- el smoke del CI, en el mismo orden que producción.

Reescribir el redespliegue de `docs/despliegue.md` y la cabecera de `docker-compose.prod.yml`.

**Hecho cuando.**

- En el CI, `up -d` sobre una base con una migración pendiente la aplica antes de que web responda.
- Si `migrate` falla, web, worker y beat no arrancan.

#### B07 · La copia de desarrollo solo lleva lo público

**Hallazgos:** HER-1, HER-2 (nombres reales en las siembras), ARQ-7 (docstring de la exportación) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** urgente · **Decisiones:** C4

Urgente porque la copia ya está en el repositorio público.

**Alcance.** La recomendación de HER-1 (puntos 1 a 6), con C4:

- un filtro por fila, con una lista explícita `DEMO_UNPUBLISHED` de las piezas de demostración del flujo editorial que se conservan;
- solo los medios que usa alguna fila exportada;
- una guarda que no depende de `DEBUG`: una fila centinela que crean `cargar` y las siembras;
- una lista blanca por campo, que falla con un campo sin clasificar;
- cada archivo, leído con el almacén de su campo;
- escritura en una carpeta temporal, que sustituye a la anterior al final.

En `seed_demo` y en la base de desarrollo, nombres ficticios evidentes en lugar de los medios, fondos, librerías y editoriales reales: hoy El Mercurio de Valparaíso y Radio Universidad, con citas inventadas, y el Fondo Nacional de Fomento del Libro, Casa del Libro y Editorial Overol como aliados. Corregir el docstring y el README, y regenerar `datos.json`. El historial de git no se reescribe (C4).

**Hecho cuando.**

- Una prueba falla si `datos.json` trae filas no públicas fuera de la lista o un campo sin clasificar.
- `exportar` se niega en una base sin la centinela.
- Ninguno de esos cinco nombres aparece en `backend/datos_de_desarrollo/` ni en las siembras.

#### B08 · Las fotos no publican su ubicación

**Hallazgos:** RES-1, RES-8 (lo barato) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C7, C13

**Alcance.** La recomendación de RES-1 (puntos 1 a 6), con C7 y C13:

- solo JPEG, PNG y WebP, comprobando el formato real y no solo la extensión;
- el original se reescribe siempre al subirlo; si no se puede, la subida se rechaza con un mensaje que pide volver a exportar la imagen;
- un `logger` del módulo que registra el pk y el nombre del archivo;
- el fallo no se guarda en la caché, y el comando cuenta los fallos y sale con un código distinto de 0.

De RES-8: `Image.MAX_IMAGE_PIXELS` a 40 MP en `MediaConfig.ready()`, y las dimensiones validadas en el formulario leyendo solo la cabecera. Reprocesar con el comando las imágenes que ya hay en desarrollo.

**Hecho cuando.** Con un JPEG truncado con GPS, un AVIF con GPS, un JPEG con la ubicación solo en XMP y una imagen de 50 MP, ninguno queda publicado con ubicación, y los que no se admiten se rechazan con el mensaje.

#### B09 · Comentarios y documentos que afirman lo falso

**Hallazgos:** TAR-1 (punto 1), SEG-2, ARQ-7, AGE-3 (afirmaciones falsas), OPE-8 (textos del README) · **Depende de:** B07 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** Corregir las afirmaciones que enumeran las fichas:

- los cuatro comentarios de Celery y la prueba de `test_resilience.py` (TAR-1);
- las cinco de SEG-2, más el comentario caducado de `backend/tests/test_security_uploads.py:28-30`;
- las siete de ARQ-7;
- las cinco de AGE-3: los contrastes escritos a mano en `site.css` se borran, porque ya los calcula `test_contraste_paleta`, y la cifra de D33 en el registro de decisiones se corrige;
- las del README que cita OPE-8: WhiteNoise, `infra/nginx/` y el redespliegue sin `setup_groups`.

Reescribir la «Estructura» del README a partir de `INSTALLED_APPS`, con una prueba que compare las dos listas. Fijar con una prueba las decisiones deliberadas que un agente podría «arreglar», por ejemplo la baja en un clic con `Client(enforce_csrf_checks=True)`.

**Hecho cuando.**

- Ninguna de esas afirmaciones sigue en el código, en el README ni en el registro.
- La prueba del README falla si se instala una app sin documentarla.

#### B10 · Un registro publicado no enseña su evento oculto

**Hallazgos:** AGE-1 (punto 2) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** Una propiedad `Recording.public_event`, usada en las cinco salidas de `Recording.event`, y lo mismo para las demás claves foráneas hacia algo publicable que señala la ficha. La tirada precarga solo las fotos de los eventos publicados.

**Hecho cuando.** Con un registro publicado cuyo evento está oculto, ninguna página, feed ni JSON-LD contiene el texto marcador del evento.

### Tanda 2 — Red de pruebas y reglas de dominio con una sola fuente

#### B11 · Navegador en el CI: prueba de humo

**Hallazgos:** PRU-2 (navegador), FRO-10 (ESLint mínimo) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C27

**Alcance.** Un job que levanta el stack de pruebas con los datos de desarrollo y corre, con el playwright-core que ya trae `tools/ux/`, de 10 a 15 comprobaciones a 951 y a 375 px. Cada una falla ante cualquier error de página o de consola:

- enlaces de la barra de 44 px o más;
- sin desbordamiento horizontal;
- el iframe del reproductor aparece solo tras pulsar;
- el estante cambia de libro con el teclado;
- la tirada responde;
- el menú abre y cierra.

Además, un ESLint mínimo que fija un dialecto para `backend/static/js/`. Es la red de los tickets de interfaz que siguen.

**Hecho cuando.** Romper a propósito un guion (por ejemplo, un selector inexistente en `registros.js`) pone el job en rojo.

#### B12 · Matriz de pruebas del flujo editorial y de la visibilidad

**Hallazgos:** PRU-1 (puntos 1 a 3) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** La recomendación de PRU-1, puntos 1 a 3:

- una prueba parametrizada sobre `TRANSITIONS`: origen válido y destino, un rol permitido y uno denegado, y la entrada en la bitácora;
- una matriz con cada estado no público de Article y Poem contra cada superficie (portada, índices, ficha con 404, búsqueda, RSS, sitemap, ficha de integrante, colección, reseñas de obra o editorial), con un control publicado en la misma prueba;
- lo mismo con `published=False` para eventos, registros (incluido el feed de pódcast), publicaciones y páginas.

Va antes de B13: primero la red y después centralizar el filtro.

**Hecho cuando.** Quitar a propósito el filtro de cualquier superficie hace fallar la matriz. Se comprueba en el PR con una mutación que se revierte.

#### B13 · «Publicado», definido en un solo lugar

**Hallazgos:** AGE-1 (puntos 1, 3, 4 y 5), ARQ-6 (consultas reutilizables) · **Depende de:** B12 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** La recomendación de AGE-1, con nombres en inglés (C3):

- `EditorialQuerySet.published()` para las piezas editoriales y `PublishableQuerySet.published()` para los booleanos (en Partner, sobre `active`), montados como manager para que funcionen también desde las relaciones;
- `upcoming`, `past`, `members` y `open_now`, como métodos de QuerySet;
- una prueba canario parametrizada por modelo publicable, y otra que falla si aparece `published=True` o `status=…PUBLISHED` fuera de los QuerySets.

La base abstracta común (punto 5) entra solo si no exige migraciones de datos; si no entra, se dice en el ticket.

**Hecho cuando.** La matriz de B12 y el canario pasan, y la prueba que busca filtros escritos a mano no encuentra ninguno.

#### B14 · Fichas secundarias solo si algo publicado las respalda

**Hallazgos:** WEB-1, PRU-1 (punto 4) · **Depende de:** B13 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C12

**Alcance.** La recomendación de WEB-1, con C12:

- un `visible()` en los QuerySets de Work, Publisher, BookAuthor y Contributor, que usan a la vez la vista, el sitemap y la búsqueda; lo que no es visible responde 404;
- la ficha de una editorial muestra también las publicaciones del colectivo con esa editorial, y la de un colaborador, también sus poemas;
- se reescribe `test_bookauthor_detail_renders_with_its_works`, que fija el comportamiento actual.

**Hecho cuando.** Una obra sin reseña publicada ni publicación del colectivo da 404 y no aparece en el sitemap ni en la búsqueda; al publicarse su reseña, aparece en los tres.

#### B15 · Roles declarados y sincronizados

**Hallazgos:** AGE-2, PRU-4, WEB-1 (el autor edita cualquier obra) · **Depende de:** B06 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C1, C2

**Alcance.** La recomendación de AGE-2, con C2:

- la matriz de roles en `apps/people/roles.py`, con las constantes de grupo que usan `setup_groups`, `permissions` y `workflow`, y cada modelo del proyecto incluido o excluido de forma explícita;
- el editor gestiona todo salvo el perfil del sitio (`SiteProfile` y sus redes) y las cuentas;
- el autor gestiona sus textos y sus poemas, con sus autorías, y puede añadir obras al catálogo, pero no editar las existentes;
- `setup_groups` sincroniza de forma aditiva: añade lo que falta y nunca restaura lo que el operador retiró (esas exclusiones se guardan aparte). Corre en el release de B06.

De PRU-4: un solo juego de fixtures (`groups`, `autor` y `editor`) y las pruebas HTTP de la ficha. La matriz se prueba con invariantes, no con una igualdad exacta. Como aún no hay producción (C1), no hay grupos que migrar.

**Hecho cuando.**

- Con los grupos reales, el editor entra a `/admin/agenda/event/` y a `/admin/showcase/publication/`, y no al perfil del sitio.
- El autor crea un poema y no puede editar una obra ya creada.
- Un modelo nuevo sin clasificar hace fallar la prueba de la matriz.

#### B16 · Permisos de Django en el flujo y en los envíos

**Hallazgos:** DOM-2 · **Depende de:** B15 · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** C2

**Alcance.** La recomendación de DOM-2:

- permisos propios de publicar y de revisar en `EditorialItem.Meta.permissions`, comprobados con `user.has_perm` en lugar del nombre del grupo;
- `allowed_permissions` en las acciones;
- `submission_file` exige `submissions.view_submission`;
- los métodos redefinidos del admin componen con `super()`.

Los permisos nuevos entran en la matriz de B15.

**Hecho cuando.** Retirar cada permiso al grupo editor hace que su vista o su acción responda 403 o 404 (prueba parametrizada).

#### B17 · Una sola forma de publicar y un flujo sin puertas laterales

**Hallazgos:** ARQ-2, DOM-1, AGE-4 (punto 1) · **Depende de:** B12 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C10

**Alcance.** Las recomendaciones de DOM-1 (puntos 1 a 7) y de ARQ-2, con C10:

- un `CheckConstraint` que exige fecha a lo publicado, programado o archivado, con una migración previa que corrige las filas que lo violan;
- «Programar», con una página intermedia que pide la fecha;
- las transiciones `unschedule` (programada → aprobada) y `reopen` (rechazada → borrador);
- «Publicar» desde programada fija la fecha a ahora;
- `publish_due_items` pasa por `perform_transition` con un actor de sistema;
- las subclases de EditorialItem salen de `apps.get_models()`, también en `ultima_publicacion`, que sigue sumando Recording;
- Recording y Collection rellenan `published_at` al publicarse, y el orden usa `nulls_last`;
- restricciones de rango para las fechas de eventos y de convocatorias;
- `TRANSITIONS`, como NamedTuple, y los efectos asíncronos, encolados con `delay_on_commit`.

**Hecho cuando.**

- La matriz de B12 pasa con las dos transiciones nuevas.
- Para cada subclase, la publicación programada deja la misma bitácora y los mismos efectos que la manual.
- El panel no deja guardar una pieza programada sin fecha: muestra un error del formulario, no un 500.

#### B18 · Vista previa para el equipo

**Hallazgos:** DOM-3 · **Depende de:** B13, B15 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C10

**Alcance.** La recomendación de DOM-3, en la propia ficha: si quien la pide es del equipo y puede ver la pieza en el panel, la ficha sirve el borrador con la franja «Vista previa: no publicado», `noindex` y `Cache-Control: private, no-store`, y «Ver en el sitio» funciona también con los borradores. Vale para textos y poemas y para los modelos con casilla de publicado. La franja es un elemento nuevo de la interfaz: se muestra al dueño antes de fusionar.

**Hecho cuando.** Un anónimo recibe 404; la editora y la dueña de la pieza reciben 200, con la franja y `noindex`; una autora no ve los borradores ajenos.

### Tanda 3 — Correcciones pequeñas con efecto visible

#### B19 · Las firmas salen en el orden de la coautoría

**Hallazgos:** DAT-1 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** La recomendación de DAT-1: una propiedad `bylines` en EditorialItem que lee el puente ordenado por `position` y `pk`; las vistas precargan el puente, no el M2M; el filtro `firmas_sin` trabaja sobre la lista ordenada; se reemplazan las unas 20 ubicaciones.

**Hecho cuando.** Con «Zoe» en la posición 0 y «Ana» en la 1, la ficha, la tarjeta, el pie «Más de», el JSON-LD y el RSS firman «Zoe, Ana».

#### B20 · La búsqueda ordena por relevancia

**Hallazgos:** REN-1 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** `SearchRank(F("search_vector"), query)` en los dos querysets. El peso del título va en B50.

**Hecho cuando.** De dos textos publicados, el que repite el término sale antes que el que lo menciona una vez. Es una prueba de comportamiento: no afirma el SQL.

#### B21 · El poema destacado conserva sus versos

**Hallazgos:** FRO-3 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de FRO-3: el extracto se compone verso a verso con los filtros que ya existen, con clases separadas para la ficha y para el extracto, y el comentario pasa a `.verso`. Se muestra al dueño la portada sin registros destacados.

**Hecho cuando.** Una prueba cuenta los `.verso` del extracto en la portada sin registros destacados.

#### B22 · Las páginas legales no se rompen desde el panel

**Hallazgos:** WEB-2 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** La recomendación de WEB-2:

- las páginas de sistema, declaradas en un solo lugar (`LEGAL_PAGES`);
- en el panel, el slug y el estado de solo lectura, y sin borrado. El texto sigue editable, porque lo revisará un abogado desde allí;
- un check de `manage.py check --deploy` que falla si alguna falta o no está publicada.

**Hecho cuando.** Una prueba intenta despublicar y borrar cada una desde el panel y no puede, y `check --deploy` falla si falta alguna.

#### B23 · `[hidden]` en una sola regla

**Hallazgos:** FRO-7 · **Depende de:** B11 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** `[hidden]{display:none !important}` al principio de `site.css`; se borran los tres parches y la regla queda fijada con una prueba sobre la hoja.

**Hecho cuando.** La prueba falla si se quita la regla, y la prueba de humo de B11 sigue viendo ocultos los tres componentes.

#### B24 · Dos fallos de la capa HTTP: HEAD y `next`

**Hallazgos:** WEB-5, WEB-6 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** Las recomendaciones de WEB-5 (el límite de tasa también para HEAD, y `@require_safe`) y de WEB-6 (`_safe_next` devuelve siempre una ruta local, y la redirección usa `HttpResponseRedirect`).

**Hecho cuando.**

- Tras 61 GET, un HEAD a `/buscar/` no ejecuta ninguna consulta de búsqueda.
- `next="agenda"`, `next="//evil.com"`, `next="feed"` y `next=""` redirigen a una ruta local, nunca a un 500.

#### B25 · Campos sin efecto fuera e imagen para compartir conectada

**Hallazgos:** DAT-5, ARQ-5 (puntos 3 y 4) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3, C11

**Alcance.** Con C11:

- una migración quita `featured` de Article, Poem, Event y PressMention, `ReviewedWork.is_primary` y `Work.language`, junto con su uso en las siembras, el panel y los datos de desarrollo; el procesador deja de entregar `nav_sections`;
- un método `social_image()` por modelo (en Article, `og_image` y, si falta, `cover_image`) y una etiqueta `{% social_meta obj %}` para `og:image`, `twitter:card` y la imagen del JSON-LD, que reemplaza los seis bloques copiados;
- cada modelo documenta el mecanismo de destacado que le queda (registros y publicaciones, con su orden; el perfil del sitio, como respaldo de la tirada y del poema destacado), y `clean()` valida el tope de cinco registros destacados.

**Hecho cuando.**

- El panel ya no ofrece esos campos.
- Las seis fichas emiten la misma combinación de `og:image` y `twitter:card` según tengan imagen propia o no (una prueba por ficha).
- Un sexto registro destacado da un error de validación.

#### B26 · Medidas de la portada: lo que hoy falla

**Hallazgos:** FRO-1 (puntos 1 a 4) · **Depende de:** B11 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de FRO-1, puntos 1 a 4:

- `integrantes.js` toma de atributos `data-` el número de integrantes a la vista, que pone la plantilla desde `A_LA_VISTA`, y el CSS lo lee de una propiedad declarada una sola vez;
- una prueba compara los niveles de la pila de la tirada en `site.css` con `TOPE_TIRADA − 1`;
- el `sizes` de `_foto.html`, correcto para 1, 2, 4 y 5 fotos;
- `font-weight: 800` pasa a 700.

Si algo cambia a la vista, se le muestra al dueño. El resto de FRO-1 va en B69.

**Hecho cuando.** Cambiar `A_LA_VISTA` en Python cambia lo que muestra el navegador sin tocar CSS ni JS (se comprueba con B11), y la prueba de la pila falla si cambia `TOPE_TIRADA` sin su nivel.

### Tanda 4 — Antes de lanzar: configuración, identidad pública y canales

#### B27 · Variables de entorno sin ambigüedad

**Hallazgos:** OPE-6, SEG-5, TAR-7 (valores de plantilla) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** La recomendación de OPE-6, con un módulo propio y sin dependencias nuevas:

- `config/env.py` con `env_bool`, `env_int` y `env_list`. `env_bool` acepta 1, 0, true, false, yes, no, on y off sin distinguir mayúsculas; ante cualquier otro valor, lanza un error que nombra la variable. Se usa en las 38 lecturas;
- envguard valida los valores ya interpretados;
- `.env.prod.example` deja vacíos los valores del correo.

De SEG-5:

- con `DEBUG=0`, el arranque se niega si axes, ratelimit, el modo report-only o HSTS están apagados, salvo que `DJANGO_ALLOW_WEAKENED` los nombre;
- se comprueba que `PRIVATE_MEDIA_ROOT` no cae dentro de `MEDIA_ROOT`;
- el almacenamiento privado lanza una excepción si se le pide `url()`;
- `report-to`, si se mantiene el modo report-only.

**Hecho cuando.**

- Una prueba parametrizada cubre «true», «TRUE», «1», «yes», «0» y «off», y «verdadero» falla nombrando la variable.
- El guard rechaza cada defensa apagada sin autorización.

#### B28 · Direcciones e identificadores permanentes

**Hallazgos:** COM-12, COM-5, COM-1, COM-8, COM-9 (GUID, slug y redirección) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C1, C5, C6

**Alcance.**

- La ruta `articulo/<slug>/` pasa a `texto/<slug>/`, sin redirección (C1 y C5), y se actualizan las pruebas, `tools/ux/pages.txt` y los documentos.
- Una prueba con la lista congelada de los prefijos públicos falla si alguno deja de resolver o de redirigir; amplía `test_get_absolute_url.py`.
- El slug pasa a solo lectura cuando la pieza es pública (C6): un mixin para los 13 admins con ruta pública, con `get_readonly_fields` y un `get_prepopulated_fields` vacío (si no, el formulario falla). En Section, Tag, Contributor, Work, Publisher y BookAuthor, en cuanto existen. El campo «dirección» de Recording lleva un texto de ayuda.
- El GUID de los dos feeds es un `tag:` con una autoridad constante (`FEED_GUID_AUTHORITY`), con `isPermaLink="false"` y sin compatibilidad con los GUID viejos (C1).
- `/integrante/<slug>/` de quien no es integrante redirige con un 302 a `/colaborador/<slug>/`. Las dos casillas de membresía llevan `verbose_name` en castellano, y la ayuda de `is_member` remite a `active`.

**Hecho cuando.** Pasan estas pruebas:

- el GUID no cambia al cambiar el slug ni el Host, y lleva `isPermaLink="false"`;
- por HTTP, la ficha de cambio de un texto publicado muestra el slug de solo lectura;
- `/integrante/<ex-integrante>/` redirige con un 302;
- la lista de prefijos está congelada.

#### B29 · Un origen fijo para las URL absolutas

**Hallazgos:** COM-6, WEB-8 (feeds), COM-9 (enclosure y Host) · **Depende de:** B27 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C3, C18

**Alcance.** La recomendación de COM-6, con C18:

- `SITE_URL` obligatorio con `DEBUG=0`, validado por envguard: https, y el host incluido en `ALLOWED_HOSTS`;
- un ayudante `absolute_url(path)` para el canonical, la base, las `og:image`, el JSON-LD (sin el `&amp;` literal del evento), robots, el `item_link` y el enclosure;
- una clase base de Sitemap con `get_domain` y `get_protocol`;
- los dos feeds, registrados de la misma forma y sin estado en `self`, con el título desde el perfil y el `link` con `reverse_lazy` (WEB-8);
- en Caddy, la redirección de `www` si existe su DNS.

Se reescriben `test_feed_isolation.py` y las pruebas que fijan el Host (COM-9).

**Hecho cuando.** Con `SITE_URL` definido, pedir cualquier página, el sitemap o los feeds con otro Host no cambia ninguna URL absoluta; sin `SITE_URL`, el arranque con `DEBUG=0` falla.

#### B30 · Logs con formato y redacción en todos los procesos

**Hallazgos:** RES-4, ARQ-3 (regex con `reverse()`), OPE-8 (prueba del Caddyfile), RES-3 (filtro de Caddy) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C8

**Alcance.** La recomendación de RES-4, en su orden:

1. la redacción recursiva del formateador JSON;
2. después, `setup_logging` de Celery;
3. gunicorn con `--log-config-dict`, y la rotación con un ancla `x-logging` en todos los servicios;
4. una prueba del handler raíz tras `setup_logging_subsystem()`.

La regex de redacción se construye con `reverse()` (ARQ-3). Una prueba comprueba que el filtro del Caddyfile cubre las rutas con token de `community/urls.py` (OPE-8), y el filtro añade `Referer` y `Hx-Current-Url` (RES-3).

**Hecho cuando.**

- Una línea del worker con un extra que contiene una URL con token sale en JSON y redactada.
- Cambiar la ruta de confirmación sin tocar la regex no rompe la redacción.

#### B31 · Sentry sin datos personales ni secretos

**Hallazgos:** RES-3, TAR-4 · **Depende de:** B29, B30 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C8, C24

**Alcance.** Las recomendaciones de RES-3 y de TAR-4, con C24:

- `init_sentry()`, extraída para poder probarla;
- `include_local_variables=False`, `max_request_body_size="never"` y un `EventScrubber` recursivo con la lista ampliada;
- `before_send` quita `Referer`, `Hx-Current-Url` y `request.data`, y ante una excepción no envía nada;
- `Referrer-Policy: no-referrer` en las páginas con token;
- la tarea del correo recibe solo el id del suscriptor y construye las URL con `SITE_URL`; se encola con `delay_on_commit`.

Sacar el token de la ruta queda diferido (§3 del registro).

**Hecho cuando.**

- Con un transporte de prueba del SDK, un error en el alta y otro en el envío del correo producen eventos sin el correo, el nombre, el cuerpo ni los tokens.
- Si `before_send` falla, el evento no se envía.

#### B32 · Avisos: monitor, latido y errores visibles

**Hallazgos:** RES-6, RES-9 · **Depende de:** B31 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C8

**Alcance.** La recomendación de RES-6, con C8:

- cada comprobación de `/readyz/` registra su causa;
- un latido de punta a punta: `publish_due_items` guarda una marca de tiempo y `/readyz/` falla si tiene más de cinco minutos, o la tarea hace ping al monitor;
- una comprobación de piezas programadas vencidas, y otras de migraciones pendientes y de disco;
- envguard exige `SENTRY_DSN` con `DEBUG=0`;
- `stop_grace_period` por encima de los plazos de gunicorn y de Celery;
- el monitor externo, documentado en `docs/despliegue.md`. No se añade autoheal (§3 del registro).

De RES-9: WARNING sin traza para lo esperado y `logger.exception` para lo inesperado; el buscador captura solo `OperationalError`; la caché registra un ERROR por intervalo; filecleanup registra el modelo, el pk y el archivo.

**Hecho cuando.**

- Con beat detenido, `/readyz/` da 503 antes de seis minutos y el log dice por qué.
- Un error de programación en el buscador llega a Sentry como ERROR (con el transporte de prueba).

#### B33 · Límites de subida por ruta y por campo

**Hallazgos:** OPE-5, WEB-9 (límites del formulario público) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** C7

**Alcance.** La recomendación de OPE-5, con C7:

- validadores por campo (audio 50 MB, PDF 20 MB, imagen 12 MB), con mensajes claros;
- `Recording.file` deja de aceptar vídeo, que se publica por enlace;
- en Caddy, `/admin/*` con un `max_size` algo mayor que el tope más alto (por ejemplo 60 MB) y 12 MB para el resto. `read_body` se elige sabiendo que una subida lenta retiene un hilo;
- `DATA_UPLOAD_MAX_NUMBER_FIELDS` vuelve a 1000;
- `paste_data_images: false` en TinyMCE.

De WEB-9: los textos de ayuda del formulario público se generan desde las constantes, y una prueba compara el `max_size` del Caddyfile con los topes.

**Hecho cuando.** Con el Caddy real del CI, un audio de 40 MB sube desde el panel, uno de 55 MB da el error del formulario (no un 413 sin cuerpo) y un evento con 40 fotos se guarda.

#### B34 · Antiabuso del panel

**Hallazgos:** SEG-3 (axes) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** La parte de axes de SEG-3: `AXES_RESET_ON_SUCCESS = False` (o reiniciar solo la combinación de usuario e IP) y `AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]`, con un umbral por usuario alto y un enfriamiento progresivo. El tope de reenvíos de la confirmación va en B38. El segundo factor queda diferido.

**Hecho cuando.** Los intentos fallidos desde una IP contra una cuenta la bloquean para esa IP, y el login correcto de otra cuenta no reinicia el contador.

#### B35 · Plazos y procesos acotados

**Hallazgos:** RES-7, REN-8, REN-4 · **Depende de:** B06 · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** —

**Alcance.** La recomendación de RES-7:

- `connect_timeout` y `statement_timeout`, configurables por entorno;
- `CONN_HEALTH_CHECKS = True` (REN-8);
- junto al ajuste de hilos, dejar escrito que con gthread `--timeout` no es un plazo por petición, y corregir el comentario del Caddyfile.

El `lock_timeout` va en la sesión de `migrate` del release (B06), y los plazos de la caché, en B36. De REN-4: `--concurrency ${CELERY_CONCURRENCY:-2}` y `--max-tasks-per-child 200`, documentados junto a `WORKER_MEM_LIMIT`.

**Hecho cuando.** Una consulta que supera el `statement_timeout` falla con un error (prueba con `pg_sleep`), y el worker arranca con dos procesos aunque la máquina tenga ocho núcleos.

#### B36 · Redis: la caché, aparte del broker

**Hallazgos:** RES-5, OPE-7, TAR-8 · **Depende de:** B27 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C17, C25

**Alcance.** La recomendación de RES-5, con C25:

- un segundo servicio Redis para la caché, con `allkeys-lru` y su propio `maxmemory`; `noeviction`, solo en el broker;
- `CELERY_TASK_IGNORE_RESULT = True`;
- un envoltorio genérico de RedisCache, con una prueba que compara sus métodos con los de la clase original.

De OPE-7: una sola variable base para las URL de Redis, con la misma regla de sobrescritura; el guard comprueba las URL efectivas; `/readyz/` incluye la caché; se corrigen los comentarios del compose.

De TAR-8, con C17: `socket_timeout` y `socket_connect_timeout` en la caché y en el broker. Con Redis caído, las vistas con límite de tasa responden «El servicio no está disponible en este momento. Prueba en unos minutos.», y la prueba lo afirma.

**Hecho cuando.**

- En el stack local, con el Redis de la caché detenido, el broker sigue encolando, y con el del broker lleno, la caché sigue escribiendo.
- La prueba afirma el mensaje.

#### B37 · Lo despublicado deja de servirse

**Hallazgos:** DOM-4 · **Depende de:** B13 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C16

**Alcance.** La recomendación de DOM-4, con C16: el audio y los PDF que cita la ficha se sirven desde una vista que da 404 si la pieza no está publicada y delega la entrega en Caddy (X-Accel-Redirect o `handle_response`), o usa `FileResponse`; nombres aleatorios en `upload_to`. El PDF del dossier del perfil sigue siendo público.

**Hecho cuando.** Con el Caddy real del CI, la URL del archivo de un registro despublicado deja de responder 200, y el feed de pódcast sigue entregando los publicados.

#### B38 · Ciclo de vida del suscriptor y de los envíos

**Hallazgos:** TAR-3, WEB-9 (normalizar el correo), SEG-3 (reenvíos), ARQ-6 (lógica del boletín) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** La recomendación de TAR-3:

- las transiciones del suscriptor, como métodos del modelo (`request_confirmation()`, `confirm()` y `unsubscribe()`) que fijan `status_changed_at` y limpian lo que corresponde; lo que hoy vive en las vistas pasa a `community/services.py` (ARQ-6);
- el correo normalizado y, tras deduplicar, `UniqueConstraint(Lower("email"))`;
- `resolved_at` en Submission, fijado al rechazar o retirar y rellenado por migración;
- la purga mide desde esas fechas, y el comentario invertido se corrige.

De SEG-3: la confirmación no se reenvía si se envió hace menos de N minutos, con la misma respuesta.

**Hecho cuando.** Pasan las pruebas de re-suscripción cruzada con la purga y de resolución tardía, y dos altas con mayúsculas distintas dejan una sola fila.

#### B39 · El panel respeta el consentimiento y el estado de los envíos

**Hallazgos:** DOM-5 · **Depende de:** B38 · **Tamaño:** S · **Lanzamiento:** sí · **Decisiones:** C14

**Alcance.** La recomendación de DOM-5, con C14:

- en los suscriptores, el estado y las fechas de solo lectura, los tokens fuera del formulario y una acción «Dar de baja»; agregar uno a mano le envía la confirmación;
- en los envíos, el autor, el correo, el título y el cuerpo de solo lectura; los cambios de estado, con acciones que fijan `resolved_at` y registran el valor anterior; `reviewer`, asignado a quien revisa.

**Hecho cuando.** Por HTTP, el panel no deja guardar a mano un suscriptor como confirmado, y agregar uno encola su confirmación.

#### B40 · Correo de confirmación fiable y con rastro

**Hallazgos:** TAR-1 (puntos 2, 3 y 5), TAR-7 · **Depende de:** B27, B38 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C3

**Alcance.** La recomendación de TAR-1, puntos 2, 3 y 5:

- `autoretry_for` con los errores de red y `SoftTimeLimitExceeded`, sin reintentar los rechazos permanentes, con un backoff de 30 a 900 s y unos 8 reintentos;
- `EMAIL_TIMEOUT`, coherente con el límite blando;
- una prueba con un backend de correo que falla, simulando `task.retry`.

De TAR-7:

- envguard exige un `DEFAULT_FROM_EMAIL` explícito y rechaza los valores de plantilla, con un remitente por defecto inofensivo;
- `confirmation_sent_at` y el último error, visibles en el panel con una acción para reenviar;
- el asunto y el cuerpo, en `templates/community/email/`, con el nombre del perfil.

El punto 4 de TAR-1 (el envío masivo) queda diferido.

**Hecho cuando.** Un SMTP que falla dos veces y después acepta entrega el correo y deja `confirmation_sent_at`, y un rechazo permanente no se reintenta y queda visible en el panel.

#### B41 · El CI ensaya lo que se despliega

**Hallazgos:** OPE-4, OPE-8 (versiones de las herramientas), HER-8 (`.dockerignore` de la raíz) · **Depende de:** B06 · **Tamaño:** M · **Lanzamiento:** sí · **Decisiones:** C29

**Alcance.** La recomendación de OPE-4:

- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q`, como lint;
- prod-runtime con el compose real y un `ci/prod.env`, o, como mínimo, el comando de gunicorn en `backend/gunicorn.conf.py`;
- las imágenes del CI fijadas por digest, con `test_image_pinning.py` extendido a `.github/workflows/`;
- construir `infra/backup/`;
- una sola `image:` para web, worker y beat, y `pytest -n auto`;
- trivy con `--exit-code 1` para las vulnerabilidades críticas que tienen corrección;
- corregir el comentario de `ci.yml:255-259`.

De OPE-8: el hook de ruff como `repo: local`; pip-tools y pip fijados; un `.python-version` con una prueba contra el `FROM` del Dockerfile; se borra el `.dockerignore` de la raíz. Al terminar, se actualiza la fila «CD real» del registro (C29).

**Hecho cuando.** Un cambio que rompe `docker-compose.prod.yml` pone el CI en rojo, y el CI arranca web con el mismo comando de gunicorn que producción.

### Tanda 5 — Robustez de archivos, imágenes y datos

#### B42 · Los archivos se borran después de confirmar

**Hallazgos:** DAT-4 · **Depende de:** B08 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de DAT-4:

- todo borrado va en `transaction.on_commit`;
- el nombre viejo se anota en `pre_save` y se borra en `post_save`, con `on_commit`;
- `strip_metadata` escribe la copia limpia con un nombre temporal y sustituye con `os.replace`.

Se mantiene filecleanup: no se adopta django-cleanup.

**Hecho cuando.** En pruebas con `django_capture_on_commit_callbacks` y con una excepción forzada después del guardado, el original sigue en disco.

#### B43 · Un solo servicio de imágenes

**Hallazgos:** TAR-2, TAR-6, RES-8 (resto), ARQ-6 (señales y servicio) · **Depende de:** B42 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La recomendación de TAR-2:

- un servicio `process_image(asset_id)` que limpia los metadatos y genera el `srcset`, las copias de portada y el color de borde. Se encola con `transaction.on_commit` y lleva su propio `soft_time_limit`;
- excepciones estrechas y registradas, y `getexif()` antes de `load()`;
- un campo `metadata_stripped_at`;
- showcase pide las copias al servicio, y `SiteProfile.save()` deja de llamarlo;
- el comando usa el mismo servicio e informa los fallos.

De TAR-6: el color del lomo pasa a una columna `border_color`, que calcula el servicio y rellena `generate_image_derivatives`; se borra su caché, se corrige el comentario del compose y se actualiza D28 en el registro. De RES-8: las copias se encadenan, con un solo redimensionado por ancho, y el color se calcula sobre una versión reducida.

**Hecho cuando.**

- Guardar un recurso no decodifica la imagen dentro de la petición.
- La portada con Redis caído no abre ninguna imagen (una prueba cuenta las aperturas de Pillow).
- Un archivo ilegible deja un WARNING con su pk y su nombre, y el comando sale con un código distinto de 0.

#### B44 · Registro de derivados

**Hallazgos:** REN-3, TAR-5 (punto 2) · **Depende de:** B43 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de REN-3:

- un ancho de 240 px en `SRCSET_WIDTHS`;
- un JSONField con los anchos y los formatos generados, que escriben `ensure_derivatives` y `ensure_portada_derivatives`, y del que sale el `srcset` sin tocar el almacenamiento.

De TAR-5, punto 2: la limpieza borra los derivados según ese registro, no por nombres calculados. Las copias se regeneran con `generate_image_derivatives`. El póster de vídeo no aplica, porque los vídeos van por enlace (C7).

**Hecho cuando.** Una página con 20 imágenes no consulta el almacenamiento para armar el `srcset`, y borrar `foto.jpg` no toca las copias de un `foto.png` del mismo mes.

#### B45 · Metapruebas de completitud

**Hallazgos:** ARQ-1 (puntos 1 a 3), PRU-3, TAR-5 (punto 1), ARQ-3 (tareas de beat) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** Las recomendaciones de ARQ-1 y de PRU-3:

- los FileField se registran solos en `MediaConfig.ready()`, con una lista explícita de excepciones;
- todo modelo con página pública está en `SITEMAPS` o en `EXCLUDED_FROM_SITEMAP` (hay que decidir sobre colaboradores y etiquetas);
- todo modelo está en `MODELOS` o en `NOT_EXPORTED`;
- cada entrada de `CELERY_BEAT_SCHEDULE` está registrada, tras forzar el autodiscover;
- toda ruta pública con nombre tiene una categoría.

La pertenencia a la matriz de roles la prueba B15.

**Hecho cuando.** En el PR, dos cambios temporales que se revierten hacen fallar la suite: un FileField nuevo sin registrar y una tarea de beat con el nombre mal escrito.

#### B46 · Lo publicado no se pierde al borrar

**Hallazgos:** DAT-2 · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de DAT-2:

- `on_delete=PROTECT` en las autorías, en `ReviewedWork.work` y en las referencias públicas a MediaAsset;
- el `get_deleted_objects` de MediaAssetAdmin lista los usos, y el listado lleva una columna «Usado en»;
- un `__str__` legible en ArticleContributor, PoemContributor y ReviewedWork.

Borrar a una persona que firma algo publicado queda bloqueado, con un mensaje que pide reasignar sus textos. La anonimización queda diferida (§3 del registro).

**Hecho cuando.** En el panel, intentar borrar una imagen que usa un texto publicado, o a una persona que firma uno, muestra los usos y no borra nada.

#### B47 · Comandos de mantenimiento que avisan

**Hallazgos:** RES-10, MAN-2 (punto 4) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de RES-10:

- la purga deja el borrado de los archivos a la señal (MAN-2), aísla cada grupo con su `try` y `logger.exception`, y sale con un código distinto de 0 si algo falló; su tarea reintenta ante `OperationalError`;
- el comando de derivados lleva un `try` por recurso, con el pk en el mensaje, y un recuento de fallos.

Lo de `setup_groups` lo cubre B15, y lo de `exportar`, B07.

**Hecho cuando.** Un adjunto que no se puede borrar no impide purgar los suscriptores ni los registros de axes, y la tarea termina con un error visible.

#### B48 · Bitácora editorial que sobrevive

**Hallazgos:** DOM-6 · **Depende de:** B17 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C15

**Alcance.** La recomendación de DOM-6, con C15:

- cada transición guarda una copia del título de la pieza y del nombre de quien la hizo, y la GenericRelation se sustituye por una consulta, para que borrar la pieza no borre su bitácora;
- `EditorialTransition.save()` rechaza las actualizaciones y `delete()` lanza una excepción; si cabe, también un trigger `BEFORE UPDATE OR DELETE`;
- el actor de sistema es el de B17;
- en las notas, `author = request.user` en `save_formset`, el autor de solo lectura y sin poder editar ni borrar las notas ajenas.

**Hecho cuando.** Borrar una pieza deja sus transiciones con título y actor, y modificar una transición desde el ORM lanza un error.

#### B49 · El HTML de autor se sanea a la salida

**Hallazgos:** SEG-1 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La primera opción de SEG-1:

- un filtro `authored_html` que llama a `clean_html` y marca el resultado como seguro, memoizado por hash y con el `nosec` justificado;
- una prueba que recorre las plantillas y prohíbe `|safe` salvo ese filtro;
- `hx-disable` en los contenedores de HTML de autor.

**Hecho cuando.** Un cuerpo con `<script>` escrito con `update()` no ejecuta nada en la ficha, y un `|safe` nuevo en una plantilla hace fallar la suite.

#### B50 · Búsqueda: una regla de acentos y tipos declarados

**Hallazgos:** DAT-3, ARQ-1 (tipos de la búsqueda), WEB-3 (resultados por tipo), MAN-2 (punto 5), AGE-4 (punto 3), REN-1 (peso del título) · **Depende de:** B20 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3, C23

**Alcance.** La recomendación de DAT-3, con C23:

- una configuración de búsqueda `spanish_unaccent` creada en una migración, que se usa al indexar y al buscar; fuera `_strip_accents` del FTS, y un único `strip_accents()` en un módulo de utilidades para lo que siga necesitándolo;
- `GeneratedField` se prueba en una rama y, si sirve, sustituye a los triggers. Si no, los triggers se quedan, con una prueba que compara sus columnas con las del modelo;
- el título pesa más que el cuerpo (`setweight` A frente a D), y se reindexa;
- los tipos de la búsqueda salen de una tupla que comparten `services.py` y `views.py`, con un diccionario de tipo a ruta y formateador que lanza un error ante un tipo desconocido.

Al terminar, se actualizan en el registro D3 (técnicas) y la entrada del FTS.

**Hecho cuando.**

- «Wisława», «Søren» y «canción» se encuentran, escritos con y sin diacríticos, en textos, poemas y personas.
- Un texto con el término en el título sale antes que uno que solo lo tiene en el cuerpo.
- Un tipo desconocido lanza un error.

#### B51 · Transcripción de los registros

**Hallazgos:** COM-3 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3, C9

**Alcance.** La recomendación de COM-3, con C9:

- un campo `Recording.transcript`, visible justo después del reproductor;
- el panel avisa, sin bloquear, al publicar un audio sin poema enlazado ni transcripción;
- «Leer el poema» o «Transcripción», junto al reproductor;
- `aria-labelledby` del reproductor hacia el título;
- la ficha del poema emite el elemento que corresponde al tipo de archivo.

Los subtítulos `.vtt` y las varias lecturas por poema quedan fuera (C7 y C9).

**Hecho cuando.** La ficha de un registro con transcripción la muestra después del reproductor, y el panel avisa al guardar un audio publicado sin texto.

#### B52 · TinyMCE con la versión en la ruta y lo vendorizado con radar

**Hallazgos:** REN-2, HER-4 · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de REN-2:

- la versión en la ruta (`vendor/tinymce-7.9.3/`), tomada de una constante que usan `unhashed_prefixes` y `RichTextWidget.Media`;
- un paso del CI que pide un archivo de TinyMCE a través de Caddy y falla si llega como inmutable;
- los comentarios del Caddyfile y del compose, corregidos.

De HER-4:

- un manifiesto de lo vendorizado (`manifest.json`, con la versión, el paquete, la integridad y el sha256 de cada archivo), que la prueba compara con el árbol;
- un guion `tools/vendor/update.py`;
- una prueba de los plugins que pide `richtext_init.js`;
- un `package.json` que no se instala, con su entrada npm en `dependabot.yml`.

**Hecho cuando.** Cambiar la versión de TinyMCE cambia su URL; un archivo de más o de menos en `vendor/` hace fallar la prueba; Dependabot ve la versión de TinyMCE.

### Tanda 6 — Pruebas y herramientas que vigilan

#### B53 · Mejora progresiva que falla bien

**Hallazgos:** FRO-2 · **Depende de:** B11 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de FRO-2:

- la marca la pone el propio guion al montarse, y el CSS depende de ella; su primera línea va en el `<head>`, para no parpadear;
- `registros.js` deshace su estado si algo falla;
- cada `montar` comprueba los nodos que necesita y sale sin tocar nada si falta alguno;
- el lomo y la ficha del estante se enlazan por id;
- se borra la rama sin IntersectionObserver.

**Hecho cuando.** En la prueba de humo, bloquear la carga de cada guion deja la página usable: la cabecera clásica, la tirada estática y el estante navegable por enlaces.

#### B54 · Anuncios y foco en los componentes con JS

**Hallazgos:** COM-4 (lector de pantalla), COM-7, COM-10 · **Depende de:** B11 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C22

**Alcance.**

- De COM-7: al salir el foco del panel abierto, el panel se cierra sin mover el foco.
- De COM-10: fuera el `aria-live` de `#search-results`, y una región `role="status"` aparte con el recuento, que rellena la parcial; `hx-validate` y `minlength`; la tirada anuncia solo al deslizar.
- De COM-4, sin control de pausa (C22): el lector recibe una lista estable de todas las integrantes, y el relevo queda solo en la capa visual.

**Hecho cuando.** En pruebas de Playwright:

- a 375 px, tabular fuera del menú abierto lo cierra, y el foco no queda tapado;
- el árbol de accesibilidad de «Las voces» no cambia entre relevos;
- el buscador anuncia una sola vez «N resultados para “q”».

Si no se prueba con un lector de pantalla real, se dice en el ticket.

#### B55 · Contraste de los sellos y axe en el CI

**Hallazgos:** COM-2 · **Depende de:** B11 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C27, decisión visual del dueño

**Alcance.** La recomendación de COM-2:

- antes de cambiar nada, se le muestran al dueño los sellos 2 y 3 con el rótulo en `--caratula-rotulo`, y otra alternativa si la hay, porque son un diseño aprobado (D31);
- la prueba de paleta cubre los fondos heredados, o al menos su docstring se corrige;
- un guion de axe-core con la regla de contraste corre sobre `pages.txt` a 951 y a 375 px, en el CI.

**Hecho cuando.** El dueño aprobó los sellos, y axe no encuentra problemas de contraste en `pages.txt`.

#### B56 · Formularios públicos de un solo origen y accesibles

**Hallazgos:** COM-11, WEB-9 (tipos, honeypot y formulario del pie), FRO-5 (punto 4), MAN-1 (punto 3), MAN-2 (punto 3: honeypot), AGE-4 (punto 2) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** De COM-11: `autocomplete="email"` y `aria-describedby` hacia el texto de consentimiento; ante un error, se vuelve a `#news-email`, con el error junto al campo, `aria-invalid` y el valor repuesto. De WEB-9 y MAN-1:

- `Submission.Type`, como TextChoices con claves sin tilde, `choices` en el campo y una migración de datos; los tipos que se ofrecen no cambian;
- un `HoneypotMixin` común, siempre como campo de texto oculto con CSS;
- el formulario del pie, pintado desde `SubscribeForm` con una inclusion tag.

**Hecho cuando.** El pie y la página del boletín pintan el mismo formulario desde `SubscribeForm`; un correo inválido vuelve al campo con el mensaje junto a él; ya no quedan valores con tilde en `Submission.type`.

#### B57 · Configuración de pruebas explícita

**Hallazgos:** OPE-2, MAN-1 (`string_if_invalid`) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de OPE-2, sin partir `settings.py` (§3 del registro):

- un `DJANGO_SETTINGS_MODULE` de pruebas en `pytest.ini` que fija `AXES_ENABLED`, `CELERY_TASK_ALWAYS_EAGER` y `CELERY_TASK_EAGER_PROPAGATES` sin mirar `sys.modules`, y un `string_if_invalid` que hace fallar las claves equivocadas en las plantillas;
- una prueba de que existe cada referencia estática de las plantillas, de los Media de los formularios y de los `static()`;
- otra que ejecuta `collectstatic` con el almacenamiento de producción en un directorio temporal y renderiza una página de cada tipo.

Al terminar, se actualiza la entrada «`CELERY_TASK_ALWAYS_EAGER` en tests» del registro.

**Hecho cuando.** Una clave de plantilla mal escrita o un `{% static %}` inexistente hacen fallar la suite.

#### B58 · Un analizador de CSS para las pruebas

**Hallazgos:** PRU-6, PRU-2 (invariantes e instantáneas) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de PRU-6: un único ayudante basado en tinycss2 que devuelve cada regla con su contexto (`@media`, `@supports` o `@container`); se busca por contexto y selector, nunca por posición ni anclando en comentarios; se borran las seis copias. De PRU-2: las invariantes de hoja completa pasan a la hoja analizada, y las instantáneas de valores y las lápidas de los archivos que se migran se borran o se sustituyen por comprobaciones de B11.

**Hecho cuando.** Ninguna prueba corta `site.css` como texto, y sacar una regla de su `@media` hace fallar la prueba que la vigila.

#### B59 · Selectores muertos

**Hallazgos:** FRO-8 · **Depende de:** B58 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de FRO-8: se borran las cinco reglas y se reapunta la aserción de `test_css_sistema.py:285`. Una prueba con bs4 y soupsieve exige que cada selector case en alguna página renderizada, con datos que cubren los estados opcionales y una lista explícita de las marcas que pone el JS.

**Hecho cuando.** Una regla nueva que no casa en ninguna página hace fallar la suite.

#### B60 · Migraciones de datos con prueba

**Hallazgos:** PRU-5 · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de PRU-5:

- django-test-migrations, o un ayudante con `MigrationExecutor`, y una prueba por cada `RunPython`: la ida con modelos históricos y, si existe, la vuelta;
- el contenido de las páginas legales, en `apps/content/legal.py`, que usan la migración y el fixture.

Al terminar, se actualiza la entrada «`serialized_rollback` descartado» del registro.

**Hecho cuando.** 0007 y 0010 tienen prueba de ida (y de vuelta, si existe), y la migración y el fixture leen el texto legal de la misma función.

#### B61 · Higiene de la suite

**Hallazgos:** PRU-8, PRU-9, PRU-10, AGE-4 (punto 6) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.**

- De PRU-8: los cuatro casos de la ficha, y toda prueba de «no aparece», con un control positivo en la misma respuesta.
- De PRU-9: un solo mecanismo de fábricas; `make_published_article` y `make_published_poem`, con fecha; `itertools.count` para los slugs; un `soup(client, url)` que además afirma el 200.
- De PRU-10: `BASE_DIR` apunta a una copia en `tmp_path`; las marcas de base de datos, solo donde se usa; fuera el `cache.clear()` redundante.

**Hecho cuando.** Después de correr la suite, `git status` no muestra cambios, y las fábricas viven en un solo módulo.

#### B62 · Herramientas de medición que no dan por bueno un error

**Hallazgos:** HER-6, HER-7 (fuentes) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La recomendación de HER-6:

- `capture.js` y `metrics.py` exigen un 200;
- `mutar.sh` corre primero sin mutar, y trabaja sobre un worktree temporal;
- un `tools/ux/common.js` con la URL base, la ruta de Chrome y la lectura de las páginas;
- cada `metrics.json` guarda el commit, la versión del navegador y la huella de `datos.json`;
- una prueba de que cada ruta de `pages.txt` existe en `datos.json`.

De HER-7: la fuente de titulares se lee de `--display` en ejecución, una prueba compara los `@font-face` con NOTICE.md y se quita la referencia a `UMBRAL_CINTA`.

**Hecho cuando.** Una página que da 404 hace fallar `capture.js`, y cambiar la fuente de titulares no deja ninguna herramienta midiendo la anterior.

#### B63 · Herramientas de desarrollo en su propia app

**Hallazgos:** HER-2 (puntos 1 y 2), MAN-2 (punto 3: la guarda común) · **Depende de:** B07 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La recomendación de HER-2:

- una app `apps.devtools` con los cuatro comandos, `seed_assets/` y `textos_largos/`, instalada solo con `DEBUG` o con `DJANGO_DEV_TOOLS=1`, y excluida de la imagen en `backend/.dockerignore`;
- una clase base de comando con una sola guarda y sin `--force`: exige `DEBUG` y que el entorno no se declare de producción (`DJANGO_ENVIRONMENT=production` en `docker-compose.prod.yml`).

Las pruebas fijan `settings.DEBUG = True`.

**Hecho cuando.** En la imagen de producción, `manage.py help` no lista los comandos de desarrollo, y ninguno acepta `--force`.

#### B64 · Un solo camino para poblar desarrollo

**Hallazgos:** HER-3, HER-5, AGE-4 (punto 7) · **Depende de:** B63 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3, C4

**Alcance.** De HER-3:

- `datos.json`, como estado canónico: el guion de preparación llama a `cargar`;
- la identidad, en un solo módulo;
- `seed_demo` pasa a fixture de pruebas o se retira;
- una función `is_placeholder(asset)` para los marcadores;
- un solo camino en el README y en CONTRIBUTING.

De HER-5:

- las filas que crean las migraciones no se exportan, o viajan con claves naturales;
- una prueba de que `cargar` no pisa las páginas que deja `migrate`;
- `exported_at` en el JSON, y las fechas desplazadas al cargar;
- el JSON no lleva el vector de búsqueda.

**Hecho cuando.** Una base nueva se puebla con un solo comando y queda como la del dueño, y cargar una copia vieja no pisa el texto legal vigente.

#### B65 · Higiene del repositorio

**Hallazgos:** HER-8 (resto) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** Lo que queda de HER-8: la imagen maestra de la lámina, versionada junto al guion de sus variantes (si el dueño la tiene fuera del repositorio, se le pide), y el ruido de las siembras, determinista por pieza. Git LFS queda diferido.

**Hecho cuando.** Regenerar las variantes de la lámina desde el repositorio da los mismos bytes, y `--regenerar` con un elemento nuevo no cambia los bytes de los demás.

### Tanda 7 — Orden interno

#### B66 · Contratos de entidad completos

**Hallazgos:** ARQ-5 (puntos 1, 2 y 5), MAN-2 (punto 1) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.**

- `get_absolute_url` en Work, Publisher, BookAuthor, Section y Tag, usado en las plantillas, en los sitemaps (`location` por defecto) y en la búsqueda;
- una sola función `url_for_person(slug, is_member)` para la regla de integrante o colaborador;
- `created_at` y `updated_at` en Event, Publication, PressMention, Partner y Recording, con una base abstracta, y `lastmod` en sus sitemaps.

**Hecho cuando.** Una prueba exige `get_absolute_url` a todo modelo con página, y ninguna plantilla arma con `{% url %}` la dirección de una entidad que lo tiene.

#### B67 · La app del sitio, por etapas

**Hallazgos:** ARQ-4, ARQ-8, WEB-8 (sondas, robots y favicon), ARQ-6 (presentadores) · **Depende de:** B15 · **Tamaño:** L · **Lanzamiento:** no · **Decisiones:** C3, C28

**Alcance.** La recomendación de ARQ-4, con C28, en dos PR.

- **Etapa 1:** `healthz`, `readyz`, `robots` y `favicon` pasan a `config/views.py` (WEB-8); las parciales comunes, a `templates/partials/`; se corrige el comentario de capas de `settings.py`.
- **Etapa 2:** una app `apps.site` con el pie, la portada (un constructor por bloque y una vista delgada), la búsqueda, los procesadores de contexto y los sitemaps. `is_editor` pasa al módulo de roles de B15, y los imports perezosos innecesarios suben al encabezado (ARQ-8). Un contrato de import-linter en el CI congela las aristas actuales.

Mover `SiteProfile` queda diferido.

**Hecho cuando.** El contrato de import-linter falla ante una arista nueva entre apps, y `content` ya no aloja lo transversal.

#### B68 · Una política de contenido y una tabla de proveedores

**Hallazgos:** SEG-4, ARQ-3 (proveedores, aliados y tinta) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La recomendación de SEG-4:

- `config/content_policy.py`, con `EMBED_PROVIDERS` y las listas de etiquetas y atributos;
- `csp.py` construye `frame-src` desde ahí, y `embeds.py`, el `help_text` y `richtext_init.js` leen de la misma fuente;
- decidir de forma explícita si las imágenes que admite nh3 se limitan al mismo origen;
- el prefijo del panel, con `reverse()`;
- pruebas de coherencia.

De ARQ-3: los grupos de aliados salen de `Partner.Kind`, con «Otros» para lo desconocido, y la tinta queda en una constante o comparada con `--ink`.

**Hecho cuando.** Las pruebas comprueban que `frame-src` contiene exactamente los hosts de los proveedores y que los `valid_elements` de TinyMCE coinciden con nh3.

#### B69 · La composición visual sale de las vistas

**Hallazgos:** WEB-3, FRO-1 (resto) · **Depende de:** B26 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de WEB-3: la vista se queda con las consultas, y los textos, los plurales y las comillas pasan a la plantilla; los números que comparten capas se emiten una vez, como atributo `data-` o propiedad CSS; un ayudante arma la URL del año de la agenda. Lo que queda de FRO-1:

- un módulo de cortes con nombre y una etiqueta `{% sizes … %}`, con una prueba de que cada corte existe en `site.css`;
- `--ease`, leída con `getComputedStyle`;
- pruebas de relación entre la fuente y las copias.

Además, unificar o justificar `TITULO_LARGO = 34` frente al umbral de 90 letras de §4 del registro.

**Hecho cuando.** Ningún `views.py` arma textos visibles, y cada número compartido entre capas tiene una sola fuente y una prueba de relación.

#### B70 · Parciales con contrato y filas sin N+1

**Hallazgos:** FRO-5 (puntos 1 a 3), WEB-4 · **Depende de:** B13 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** De FRO-5:

- `include … only`, con parámetros explícitos y el contrato en la cabecera de cada parcial, y una prueba que renderiza cada una solo con lo que declara;
- el nivel de encabezado de las tarjetas, como parámetro;
- `_article_list` recibe la página aparte.

De WEB-4:

- `published().for_row()` en Article y en Poem, que se usa también como Prefetch;
- las reseñas se paginan, o la parcial falla si no recibe una página;
- la prueba de miniaturas cubre las cinco vistas, con 2 y con 6 filas.

**Hecho cuando.** Las cinco vistas cuestan las mismas consultas con 2 y con 6 filas, e incluir una tarjeta sin un parámetro declarado falla.

#### B71 · Recetas de plantilla compartidas

**Hallazgos:** FRO-6 · **Depende de:** B25, B29 · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de FRO-6:

- una etiqueta que une con « · » y omite los vacíos;
- el título de la página, con un solo respaldo del nombre del sitio, el mismo que escribe el 500;
- las URL absolutas, con el ayudante de B29, y la imagen social, con la etiqueta de B25;
- `_index_head.html` en sección, etiqueta y colección;
- parciales para participantes, tapa y retrato o monograma;
- la cejilla y el umbral de título largo, como propiedades del modelo;
- una clase de enlace total que incluye la regla de los enlaces secundarios.

**Hecho cuando.** Un separador sin año o sin país ya no deja un « · » colgando, y todas las páginas y el 500 toman el nombre del sitio de la misma fuente.

#### B72 · La cascada de site.css en capas

**Hallazgos:** FRO-4 · **Depende de:** B11, B58 · **Tamaño:** L · **Lanzamiento:** no · **Decisiones:** C26

**Alcance.** La recomendación de FRO-4, por etapas y con B11 como red:

- la página, marcada en el `<body>` (`data-pagina`) y usada por el CSS y por `cabecera.js`;
- la cascada en `@layer` (tokens, base, lienzo, componentes, estados e impresión), sin los prefijos que solo existen para ganar a reglas posteriores;
- los resultados de la búsqueda, estilizados por clase;
- fuera el panel para navegadores sin `:has()` (C26);
- `site.css`, partido por capas, y una escala de `z-index` en tokens.

La poda de comentarios va en B78.

**Hecho cuando.** Ninguna regla usa especificidad de más solo para ganarle a otra, la prueba de humo sigue pasando y las capturas de `tools/ux/` a 951 px no cambian.

#### B73 · Navegación de una sola fuente

**Hallazgos:** FRO-9 · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** decisión visual del dueño

**Alcance.** La recomendación de FRO-9. Antes de unificar, se le muestra al dueño, con alternativas, dónde van Prensa y Aliados («Colectivo» o «Prensa y gestión») y en qué orden van Agenda y Trayectoria y Registros y Publicaciones, que hoy difieren entre la barra, la sub-fila y el mapa. Después, una estructura en Python de la que salen la barra, la sub-fila, el mapa del pie y el menú del teléfono.

**Hecho cuando.** Cambiar un enlace en la estructura lo cambia en la barra, en el pie y en el menú del teléfono (prueba).

#### B74 · Guiones con un módulo común

**Hallazgos:** FRO-10 · **Depende de:** B11 · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** La recomendación de FRO-10:

- un `static/js/common.js`, o módulos ES (compatibles con `script-src 'self'`), con los ayudantes que hoy están copiados, que conservan sus nombres;
- un montaje idempotente, registrado también con `htmx.onLoad`;
- ESLint pasa a exigir el dialecto que fijó B11.

**Hecho cuando.** Ningún ayudante está copiado en dos guiones, y montar dos veces un componente no duplica sus escuchas.

#### B75 · Convenciones HTTP

**Hallazgos:** WEB-7, WEB-8 (resto), MAN-2 (punto 2), AGE-4 (punto 4) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** De WEB-7: un ayudante `paginate(request, qs, per_page=12)` en todas las vistas, que responde 404 ante valores no enteros o fuera de rango y deja en la petición la página servida; el canonical añade `?page=N` solo si esa página se sirvió. Lo que queda de WEB-8:

- `@vary_on_headers("HX-Request")`, y el fragmento decidido por `HX-Target`;
- `require_http_methods` y `require_safe`;
- 429 con `Retry-After` en las páginas completas, desde un decorador `rate_limited(rate)` que envuelve ratelimit (MAN-2);
- `FileNotFoundError` convertido en `Http404` en `submission_file`;
- el bloque de texto completo, en `transaction.atomic()`.

**Hecho cuando.** `?page=0`, `?page=99999` y `?page=01` dan 404, y la respuesta de `/buscar/` declara `Vary: HX-Request`.

#### B76 · Rendimiento menor

**Hallazgos:** REN-5, REN-6, REN-7, AGE-4 (punto 5) · **Depende de:** — · **Tamaño:** M · **Lanzamiento:** no · **Decisiones:** C21

**Alcance.**

- De REN-5: el perfil se lee una vez por petición, de forma perezosa y con sus relaciones precargadas, con un ayudante para las vistas y los feeds; fuera la copia `profile` del contexto del dossier.
- De REN-6: la galería precarga tres fotos por evento, con un `Count` aparte, y la tirada, una; la galería se pagina como los demás índices (C21); `only()` en los sitemaps; `cache_page` de una hora en el sitemap y en los feeds; respuestas 304 con `ConditionalGetMiddleware`.
- De REN-7: `site.css` se sirve sin comentarios ni espacios, quitados en `post_process` antes del hash, comprobando los `url()` de las fuentes y las precargas.

Medir el LCP en la vista previa de producción antes y después, como pide §4 del registro.

**Hecho cuando.** La portada y el dossier leen el perfil una vez; la galería con 30 eventos cuesta las mismas consultas que con 3; el `site.css` servido no tiene comentarios.

#### B77 · Nombres trampa y rótulos completos

**Hallazgos:** MAN-1 (punto 2), AGE-4 (punto 8) · **Depende de:** — · **Tamaño:** S · **Lanzamiento:** no · **Decisiones:** C3

**Alcance.** Con C3:

- `stats()` devuelve `festivals_and_fairs` para la suma y `festivals` solo para los festivales, y se corrigen su docstring y los comentarios de `test_agenda.py`;
- fuera la clave `integrantes` del contexto de la portada;
- se completan los `verbose_name` que faltan, con una prueba de rótulos que recorre todos los campos.

Las anotaciones de tipo del punto 4 de MAN-1 no entran: siguen diferidas («mypy + type hints incremental», §3 del registro). De ese punto, `string_if_invalid` va en B57.

**Hecho cuando.** Ninguna clave del contexto tiene una gemela con otro significado, y un campo sin `verbose_name` hace fallar la prueba de rótulos.

#### B78 · Comentarios que dicen el presente

**Hallazgos:** AGE-3 (la pasada), ARQ-7 (docstrings de módulo), OPE-8 (identificadores externos), SEG-2 (referencias «S-NN») · **Depende de:** B03 · **Tamaño:** L · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** El punto 2 de AGE-3, área por área, con un PR por app y otro para `site.css`:

- fuera los «Antes…», «Medía…» y «el dueño…», y los identificadores de decisión y de sesión;
- queda, en una frase, la restricción vigente que explica el código;
- el registro de decisiones se enlaza solo donde hace falta.

Cada PR baja la línea base de B03.

**Hecho cuando.** La línea base de identificadores queda en cero fuera de las migraciones (o en una lista corta de excepciones justificadas), y los comentarios de `site.css` solo explican restricciones.

#### B79 · La suite, por componente

**Hallazgos:** PRU-7 · **Depende de:** B61 · **Tamaño:** L · **Lanzamiento:** no · **Decisiones:** —

**Alcance.** La recomendación de PRU-7, con un PR por app:

- `tests/<app>/test_<comportamiento>.py`, con los duplicados fusionados y docstrings que enuncian la regla vigente;
- `__init__.py` en cada subcarpeta (conservando `import tests.factories`), o `--import-mode=importlib`;
- comparar `pytest --co -q` antes y después;
- actualizar las referencias del registro de decisiones a los archivos de prueba.

**Hecho cuando.** El número de pruebas no baja, salvo por duplicados fusionados que el PR lista, y ningún archivo de prueba se llama como una decisión o un lote.

## 4. Cobertura de los hallazgos

Cada hallazgo de la auditoría y los tickets que lo cierran. Un hallazgo queda cerrado cuando todos sus tickets lo están. Si un ticket cubre solo una parte, su ficha dice cuál.

- **Arquitectura y límites entre módulos (ARQ):** ARQ-1 → B45, B50 · ARQ-2 → B17 · ARQ-3 → B30, B45, B68 · ARQ-4 → B67 · ARQ-5 → B25, B66 · ARQ-6 → B02, B13, B38, B43, B67 · ARQ-7 → B07, B09, B78 · ARQ-8 → B67
- **Modelo de datos, migraciones e integridad (DAT):** DAT-1 → B19 · DAT-2 → B46 · DAT-3 → B50 · DAT-4 → B42 · DAT-5 → B25
- **Capa HTTP: vistas, URLs, formularios y consultas (WEB):** WEB-1 → B14, B15 · WEB-2 → B22 · WEB-3 → B50, B69 · WEB-4 → B70 · WEB-5 → B24 · WEB-6 → B24 · WEB-7 → B75 · WEB-8 → B29, B67, B75 · WEB-9 → B33, B38, B56
- **Plantillas, CSS y JavaScript (FRO):** FRO-1 → B26, B69 · FRO-2 → B53 · FRO-3 → B21 · FRO-4 → B72 · FRO-5 → B56, B70 · FRO-6 → B71 · FRO-7 → B23 · FRO-8 → B59 · FRO-9 → B73 · FRO-10 → B11, B74
- **Seguridad como propiedad del código (SEG):** SEG-1 → B49 · SEG-2 → B09, B78 · SEG-3 → B34, B38 · SEG-4 → B68 · SEG-5 → B27
- **Tareas en segundo plano, correo, caché y ciclo de vida de archivos (TAR):** TAR-1 → B09, B40 · TAR-2 → B43 · TAR-3 → B38 · TAR-4 → B31 · TAR-5 → B44, B45 · TAR-6 → B43 · TAR-7 → B27, B40 · TAR-8 → B36
- **Configuración, despliegue, CI y operación (OPE):** OPE-1 → B06 · OPE-2 → B57 · OPE-3 → B05 · OPE-4 → B41 · OPE-5 → B33 · OPE-6 → B27 · OPE-7 → B36 · OPE-8 → B05, B09, B30, B41, B78
- **Calidad y estrategia de la suite de pruebas (PRU):** PRU-1 → B12, B14 · PRU-2 → B02, B03, B11, B58 · PRU-3 → B45 · PRU-4 → B15 · PRU-5 → B60 · PRU-6 → B58 · PRU-7 → B79 · PRU-8 → B61 · PRU-9 → B61 · PRU-10 → B61
- **Mantenibilidad y salud del código Python (MAN):** MAN-1 → B02, B56, B57, B77 · MAN-2 → B47, B50, B56, B63, B66, B75
- **Huellas de código generado por agentes de IA (AGE):** AGE-1 → B10, B13 · AGE-2 → B15 · AGE-3 → B01, B02, B03, B09, B78 · AGE-4 → B17, B50, B56, B61, B64, B75, B76, B77
- **Rendimiento y eficiencia (REN):** REN-1 → B20, B50 · REN-2 → B52 · REN-3 → B44 · REN-4 → B35 · REN-5 → B76 · REN-6 → B76 · REN-7 → B76 · REN-8 → B35
- **Manejo de errores, resiliencia y observabilidad (RES):** RES-1 → B08 · RES-2 → B04 · RES-3 → B30, B31 · RES-4 → B30 · RES-5 → B36 · RES-6 → B32 · RES-7 → B35 · RES-8 → B08, B43 · RES-9 → B32 · RES-10 → B47
- **Dominio editorial: flujo de estados, visibilidad, permisos y admin (DOM):** DOM-1 → B17 · DOM-2 → B16 · DOM-3 → B18 · DOM-4 → B37 · DOM-5 → B39 · DOM-6 → B48
- **Herramientas de desarrollo, datos de demostración y salud del repositorio (HER):** HER-1 → B07 · HER-2 → B07, B63 · HER-3 → B64 · HER-4 → B52 · HER-5 → B64 · HER-6 → B62 · HER-7 → B01, B62 · HER-8 → B01, B03, B41, B65
- **Auditorías complementarias: accesibilidad y permanencia de las URL (COM):** COM-1 → B28 · COM-2 → B55 · COM-3 → B51 · COM-4 → B54 · COM-5 → B28 · COM-6 → B29 · COM-7 → B54 · COM-8 → B28 · COM-9 → B28, B29 · COM-10 → B54 · COM-11 → B56 · COM-12 → B02, B28

## 5. Lo diferido

Lo que se decidió no hacer ahora está, con su motivo y cómo retomarlo, en §3 del registro de decisiones, bajo «De la auditoría de código (2026-10-28)»:

- la fiabilidad del envío masivo del boletín (TAR-1, punto 4);
- sacar los tokens del boletín de la ruta (RES-3);
- sustituir django-ratelimit antes de Django 6 (OPE-8);
- el segundo factor para el panel (SEG-3);
- la anonimización de una persona con obra publicada (DAT-2);
- Git LFS para los medios de desarrollo (HER-8);
- los subtítulos `.vtt` y las varias lecturas por poema (COM-3);
- autoheal y la división de `settings.py`, que no se harán (RES-6, OPE-2).

Siguen diferidos además: mover `SiteProfile` de app (ARQ-4, etapa 3), el «CD real» (OPE-4) y las anotaciones de tipo (MAN-1, punto 4).
