# Diferidos y decisiones — referencia para desarrollo futuro

Documento vivo que consolida **las decisiones importantes** (con su porqué) y **todo
lo diferido conscientemente** a lo largo de las tres auditorías y sus remediaciones
(PRs #5–#72). Objetivo: que quien retome el proyecto entienda *qué se decidió y por
qué*, y *qué quedó pendiente, por qué, y cómo abordarlo*.

Auditorías de referencia: `docs/auditoria-mvp.md` (#1), `docs/auditoria-post-fase3.md`
(#2), `docs/auditoria-qa.md` (#3 + plan de remediación). Estado al cierre: **P0+P1+P2
y los accionables de P3 completos, CI verde**; lo que sigue es lo que resta.

---

## 1. Decisiones importantes (y su porqué)

### Decisiones de producto/negocio

- **D2 — Newsletter como lista LATENTE** (`apps/community`). Se decidió **no construir
  el camino de envío** (sin campañas ni comando de difusión): solo se capta y confirma
  con doble opt-in, y los suscriptores nunca confirmados se purgan periódicamente
  (`purge_stale_data`, beat lunes 04:30). *Porqué:* minimización de datos; no hay uso
  real todavía. *Implicación:* construir el envío (con `List-Unsubscribe-Post` de
  un-clic y confirmación por POST) recién cuando exista una campaña.

- **Tienda = solo vitrina.** El catálogo (`showcase.Publication` + `WhereToBuy`) no
  procesa pagos; enlaza a puntos de venta externos. *Porqué:* el sitio es un dossier
  vivo de un colectivo de poesía, no un e-commerce.

- **Texto legal de privacidad (Ley 21.719) es un BORRADOR.** Redactado por la IA,
  aplicado en la migración de datos `content.0010`. **Debe revisarse con un abogado
  antes de considerarlo definitivo.**

### Decisiones técnicas transversales

- **D1 — Resolución de IP unificada tras el proxy** (`config/clientip.py`). Un único
  resolver `client_ip` (django-ipware, `proxy_order='right-most'`) lo comparten
  `django-ratelimit` (`RATELIMIT_IP_META_KEY`) y `django-axes` (`AXES_CLIENT_IP_CALLABLE`)
  para que ambos cuenten por la misma IP. *Porqué:* toma la IP que Caddy añade al final
  de `X-Forwarded-For` (a prueba de spoofing). **Supuesto crítico:** Caddy es el ÚNICO
  proxy de borde. **Si se antepone un CDN/balanceador, hay que revisar cuántos proxies
  de confianza hay** (el right-most dejaría de ser la IP real del cliente).

- **D3 — Búsqueda insensible a acentos** (`unaccent`). Implementado: migración
  `content.0011` con funciones de trigger propias que construyen el `search_vector` con
  `to_tsvector('spanish', unaccent(...))`, y `_strip_accents()` en la vista de búsqueda.
  **Supuesto:** el usuario de la BD puede `CREATE EXTENSION` (el Postgres propio del
  proyecto corre como superusuario). **En una BD gestionada (RDS, etc.), un admin debe
  pre-crear la extensión `unaccent`** o la migración fallará.

- **D4 — Rendimiento: guardia de queries sí, carga con umbral no (aún).** Se añadieron
  presupuestos de consultas anti-N+1 (`django_assert_max_num_queries`, `test_performance.py`).
  El smoke de carga (k6/locust) con umbral p95 se difirió: empezar sin umbral bloqueante
  y calibrar (ver §2).

- **FTS por trigger de Postgres, no `GeneratedField`.** El `search_vector` lo mantiene un
  trigger (migraciones 0009→0011). *Porqué:* `unaccent` no es `IMMUTABLE`, así que no
  sirve en un `GeneratedField`/índice de expresión; el trigger sí lo permite y además
  cubre `bulk_update`/`QuerySet.update`/imports (que no pasan por `save()`).

- **`CACHES` → Redis (db 2) en prod, LocMem en dev/tests.** Necesario para que los
  contadores de `django-ratelimit` se compartan entre workers. Seguro con `noeviction`
  gracias a los TTLs.

- **`CELERY_TASK_ALWAYS_EAGER` en tests** (`"pytest" in sys.modules`). *Porqué:*
  hermeticidad. *Consecuencia importante:* **la suite normal NO ejecuta reintentos ni
  concurrencia de Celery** (en eager las tareas no reintentan — es diseño de Celery). Por
  eso la concurrencia se prueba aparte con `transaction=True` + hilos (`test_concurrency.py`,
  marcados `integration`) y la política de reintento con tests de contrato.

- **`serialized_rollback` descartado.** Los tests `transaction=True` vacían la tabla y
  con ella las páginas legales de migración; se intentó `serialized_rollback=True` pero
  es **inestable con `--reuse-db`**. Solución adoptada: fixture `legal_pages` (reutiliza
  las funciones `RunPython` de las migraciones 0007/0010) en los tests que las consultan.

- **`filterwarnings = error` + `pytest-randomly`.** Los warnings fallan la suite (obliga
  a atender deprecations de cara a Django 6.x) y el orden se aleatoriza (detecta
  dependencias de orden). Hay un `ignore` acotado para el warning benigno de WhiteNoise
  «No directory at: staticfiles/» (en tests no se corre collectstatic).

---

## 2. Diferidos que dependen de INFRAESTRUCTURA del usuario

Estos esperan que el usuario provea DNS/SMTP/registry. Las partes que no necesitaban
infra ya se hicieron (se indican).

| Ítem | Qué falta | Cómo retomar |
|---|---|---|
| **Correo SMTP / deliverability** | Servidor SMTP real + **SPF/DKIM/DMARC** en DNS. La estructura MIME (`EmailMessage`) y la cabecera `List-Unsubscribe` **ya están** (`community/tasks.py`). | Configurar `EMAIL_HOST/PORT/USER/PASSWORD/USE_TLS` y `DEFAULT_FROM_EMAIL`; publicar SPF/DKIM/DMARC; smoke de entrega contra un buzón real. |
| **Respaldo off-site (restic)** | Un repo restic (S3/BackBlaze/rclone) + `RESTIC_REPOSITORY`/`RESTIC_PASSWORD`. El **roundtrip `pg_dump`/`pg_restore` ya se verifica en CI** (job `backup-restore`). | Definir el repo y las credenciales; `infra/backup/backup.sh` ya tiene la rama restic. Probar un `restic restore` real en staging (RTO/RPO). |
| **CD real** | Registry de contenedores + target de despliegue + rollback. | Job de release que taggee la imagen (`docker build --target prod`), la publique y despliegue con estrategia de rollback. El `build-prod` de CI ya construye y valida la imagen. |
| **Alerta de fallo de respaldo (dead-man's-switch)** | `BACKUP_PING_URL` (healthchecks.io o similar). El script ya hace el ping OK/fail. | Definir la URL y probar que un fallo dispara la alerta. |

---

## 3. Diferidos por BAJO VALOR o esfuerzo desproporcionado

Decisiones conscientes de no hacer (aún); documentadas para no re-descubrir el análisis.

- **qa-21 — Test de captura de Sentry + ping de backup.** La integración de Sentry es
  *inline* en `config/settings.py` (opt-in por `SENTRY_DSN`). Un test con valor exigiría
  extraerla a una función (`init_sentry`) y mockear `sentry_sdk.init`; para algo que es
  opt-in estándar y bien entendido, el refactor no se justifica ahora. *Si se retoma:*
  extraer `init_sentry(dsn, debug)` y afirmar `send_default_pii=False` y
  `traces_sample_rate` por defecto (guardas de privacidad/costo).

- **qa-23 — Test de DST + higiene de beat.** El `celerybeat-schedule` **ya está en
  `.gitignore`**. `publish_due_items` ya es **DST-safe por diseño** (compara `published_at`
  vs `timezone.now()` en UTC); un test con `freezegun` solo *confirmaría* eso, y añadir la
  dependencia no se justifica. El fallback htmx sin-JS ya se cubrió (qa-10).

- **#33 — a11y/rendimiento automatizados (pa11y/axe, Lighthouse, k6).** Requieren Node +
  un servidor corriendo en CI (setup propio). La a11y ya mejoró (qa-9) y hay aserciones
  estructurales con BeautifulSoup (qa-11). *Si se retoma:* `pa11y-ci` o `axe-core` sobre
  las páginas clave levantando la app; k6 nocturno con presupuesto p95 (empezar sin
  umbral bloqueante — D4).

- **#27 — Restringir `/readyz` al monitor.** El endpoint está **diseñado para monitoreo
  externo de uptime**, así que restringirlo bien depende de la capa de monitoreo que se
  elija (token compartido, allowlist de IPs, o restricción en el proxy). Se aborda cuando
  se defina esa capa; hoy expone solo estado BD/broker (fuga menor, info).

- **mypy + type hints incremental.** Bajo valor/alto esfuerzo a esta escala.

- **Extracción `SiteProfile` → app `siteconfig`.** Migración cross-app de 2 modelos + FKs;
  severidad baja (cohesión). Hacer aparte si el proyecto crece.

---

## 4. Menores / nice-to-have pendientes

- **Portada de podcast cuadrada (`itunes:image`).** Para publicar el feed
  `/feed/registros/` en Apple Podcasts falta un asset cuadrado ≥1400px en `SiteProfile`.
  El namespace iTunes ya se emite (`media/feeds.py`).
- **Configurar identidad del sitio.** `SiteProfile.name` es el placeholder «Reseñas» y
  `og_image` está sin asignar: configurarlos en el admin (afecta título, OG y JSON-LD).
- **Índice `Event(published, starts_at)`**, `LIMIT` explícito en la consulta FTS,
  `prefers-reduced-motion`, epigraph en el trigger FTS de Poem — micro-optimizaciones de
  la auditoría #2, sin impacto observado.
- ~~**Páginas 404 y 500 con la identidad del sitio.**~~ **CERRADO** (`fix-paginas-error`,
  2026-09-02). El 404 pasa de 179 a 5117 bytes con cabecera, pie y cuatro salidas.

  Las dos plantillas se tratan **distinto a propósito**: 404.html extiende `base.html`
  —`page_not_found` renderiza con request y procesadores de contexto, y en un 404 el sitio
  está sano—, pero **500.html no hereda de nada**. `server_error` renderiza sin contexto, y
  el procesador `site_profile` hace `SiteProfile.load()`, una CONSULTA: la causa más común
  de un 500 es que la base no responda, así que una página de error que la consultara
  fallaría justo cuando se la necesita. La prueba usa `django_assert_num_queries(0)` para
  que nadie "unifique" ambas más adelante.

- ~~**Rótulos del panel a medias en inglés.**~~ **CERRADO** (`i18n-rotulos-panel`,
  2026-09-02). `verbose_name` en los AppConfig de content, people, reviews y community
  —que ni siquiera tenían `apps.py`—, en los nueve modelos de relación y auditoría, y en
  los campos que se leen como cabecera de la ficha. El índice queda entero en español.

  Se tradujo además la pantalla de bloqueo por intentos fallidos vía
  `AXES_LOCKOUT_TEMPLATE`, que era el rótulo sin traducir **más visible del proyecto**: no
  está en el panel sino en `/admin/login/`, y la veía cualquiera, no solo el equipo.

  **Residuo conocido:** la sección «Axes» y sus tres modelos siguen en inglés.
  `LANGUAGE_CODE = "es"` y `USE_I18N = True` están bien puestos; el motivo es que
  django-axes **no distribuye traducción al español** (trae ar, de, fa, fr, id, pl, ru,
  tr). Cerrarlo exigiría mantener un catálogo propio de una app de terceros que solo ve el
  superusuario. Se deja así a conciencia.

- **La firma de archivo no distingue un `.docx` de un ZIP cualquiera.** `SubmissionForm`
  valida que los bytes iniciales correspondan a la extensión declarada —lo que rechaza un
  PNG renombrado a `.pdf`, comprobado a mano—, pero `docx` y `odt` **son** contenedores
  ZIP, así que su firma `PK\x03\x04` la cumple cualquier ZIP. Cerrarlo exigiría abrir el
  contenedor y exigir `[Content_Types].xml` y `word/document.xml` dentro. Gravedad baja y
  por eso queda diferido: el archivo va a almacenamiento privado, solo lo descarga quien
  tiene rol de editor por `/envios/<pk>/archivo/`, y se sirve con `nosniff` y CSP
  `sandbox`; nunca se ejecuta ni se interpreta. *Detectado en las pruebas manuales del §4,
  2026-08-18.*

- **El endurecimiento de permisos no alcanza a los respaldos ya existentes.** `backup.sh`
  aplica `umask 077` desde el lote sec-6, así que los respaldos NUEVOS quedan en `700`/`600`
  —verificado—. Pero los anteriores a esa corrección siguen como se crearon: en la máquina
  de desarrollo había tres directorios de julio en `755` con sus archivos en `644`, es
  decir el volcado completo de la base —correos de suscriptores, hashes de contraseñas— y
  los manuscritos, legibles por cualquier usuario local. Una corrección de permisos no es
  retroactiva y eso es fácil de pasar por alto: en un servidor real la exposición sobrevive
  a la remediación que supuestamente la cerró. Se cierra con `chmod -R go-rwx` sobre el
  directorio de respaldos, y conviene comprobarlo tras cualquier despliegue que cambie el
  usuario o el `umask` del sidecar. *Detectado en las pruebas manuales del §10, 2026-08-26;
  los del entorno local ya se ajustaron.*

- ~~**`Article` no tiene `get_absolute_url`.**~~ **CERRADO** (`fix-get-absolute-url`,
  2026-09-02). Añadido a Article, Page y Collection siguiendo el patrón de Poem, así que
  el panel vuelve a ofrecer «Ver en el sitio». La prueba sigue la redirección
  `/admin/r/<tipo>/<id>/` con sesión de staff y afirma dónde aterriza: que el método
  devolviera una cadena con buena pinta no bastaba.

- **test** — ruff, pip-audit, `makemigrations --check`, **reversibilidad de migraciones**,
  pytest con cobertura (piso 80% + **umbrales por-módulo** para sanitize/feeds/sitemaps),
  `check --deploy`.
- **build-prod** — build de la imagen prod + smoke gunicorn + **collectstatic DEBUG=0** +
  **trivy** (informativo).
- **security** — **gitleaks** (con `.gitleaks.toml`) + **bandit** + dependency-review
  (informativo).
- **prod-runtime** — levanta la imagen prod en DEBUG=0 y verifica cabeceras de seguridad,
  `/readyz`, estático hasheado y los healthchecks de web/worker/beat.
- **backup-restore** — roundtrip `pg_dump`/`pg_restore` del esquema real (DR).
