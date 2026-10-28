# Respaldos y restauración — Proyecto «Reseñas»

«Reseñas» es un **archivo permanente**: la pérdida de datos es el riesgo más grave del proyecto.
Este documento define la política de respaldos, cómo ejecutarlos y —lo más importante— cómo
**restaurar** y cómo verificar que la restauración funciona.

## Qué se respalda

| Elemento | Contenido | Mecanismo |
|---|---|---|
| **PostgreSQL** | Todo el contenido editorial, usuarios, auditoría, suscriptores | `pg_dump --format=custom` |
| **`media`** | Imágenes públicas (portadas, ilustraciones) | `tar czf` del volumen |
| **`private_media`** | Manuscritos de envíos (privados) | `tar czf` del volumen |

Cada respaldo es una carpeta con marca de tiempo en `/backups/<YYYYmmdd-HHMMSS>/` que contiene
`db.dump`, `media.tar.gz`, `private_media.tar.gz` y un archivo `OK`. `backup.sh` escribe primero en
`<marca>.partial`, verifica el dump (`pg_restore --list`) y los tar (`gzip -t`), y solo entonces le
da su nombre definitivo con `OK`: una carpeta sin `OK` nunca fue un respaldo completo, y ni la
rotación ni `restore.sh` la usan. Si algo falla (un `tar` que no puede leer, el disco lleno, un
volumen que no es un directorio o que tiene menos archivos que `BACKUP_MIN_MEDIA_FILES` o
`BACKUP_MIN_PRIVATE_FILES`, porque un volumen sin montar llega vacío), el respaldo aborta y avisa.

## Dónde se guardan (crítico)

`/backups` se monta desde `BACKUP_DIR` (por defecto `./backups`), un **bind-mount del host**, para
que los respaldos **sobrevivan a `docker compose down -v`, a un fallo de disco y a migraciones de host**.

> **En producción:** `BACKUP_DIR` debe apuntar a un disco respaldado y, además, sincronizarse a
> **almacenamiento externo**. Un respaldo que vive en el mismo host que la base **no es un respaldo**
> frente a la pérdida del host. El off-site ya está implementado en `backup.sh` (restic) — ver abajo.

## Off-site y alertas de fallo

El sidecar (`infra/backup/`, imagen `postgres:16` + `restic` + `curl`) hace dos cosas más allá del
respaldo local, **ambas opt-in por variables de entorno**:

- **Off-site cifrado (restic).** Con `RESTIC_REPOSITORY` + `RESTIC_PASSWORD` definidos, cada respaldo
  sube a almacenamiento externo cifrado (S3/BackBlaze/rclone según el backend) el dump y los
  volúmenes tal cual, sin tar.gz, para que restic deduplique los archivos que no cambian. El repo se
  inicializa solo la primera vez. La retención agrupa las instantáneas por host y etiqueta y poda
  según `RESTIC_KEEP_DAILY`, `RESTIC_KEEP_WEEKLY` y `RESTIC_KEEP_MONTHLY` (7, 5 y 12 por defecto), y
  una vez por semana `restic check` comprueba el repositorio. Sin `RESTIC_REPOSITORY` el paso se omite
  con un aviso.
- **Alerta de fallo (dead-man's-switch).** Con `BACKUP_PING_URL` (p. ej. healthchecks.io), se hace
  `GET` a la URL al terminar OK y a `<URL>/fail` si el respaldo aborta (vía `trap`). Así un sidecar
  que falla en silencio **dispara una alerta** en lugar de pasar semanas sin backups válidos.

Configúralas en `.env` (ver `.env.prod.example`).

## Ejecutar un respaldo

Puntual (on-demand):

```bash
docker compose run --rm --entrypoint sh backup /scripts/backup.sh
```

Programado (sidecar, producción) — corre `backup.sh` cada `BACKUP_INTERVAL_SECONDS` (24 h por defecto):

```bash
docker compose --profile backup up -d backup
```

Alternativa: **cron del host** invocando el comando puntual (p. ej. `0 3 * * *`).

**Retención:** local, se conservan los últimos `BACKUP_KEEP` respaldos completos (14 por defecto);
off-site, la política diaria, semanal y mensual de arriba.

## Restaurar

⚠️ Detén `web`, `worker` y `beat` antes de restaurar en producción (evita conexiones activas).

```bash
# 1. Detener la app (mantener db arriba)
docker compose stop web worker beat

# 2. Restaurar el último respaldo completo (o una marca de tiempo concreta)
#    Exige confirmación explícita nombrando la base que se va a destruir.
docker compose run --rm --entrypoint sh -e RESTORE_CONFIRM=SI-DESTRUIR-resenas \
  backup /scripts/restore.sh latest
#   … o: /scripts/restore.sh 20260709-030000
#   … o, desde el off-site: /scripts/restore.sh --from-restic latest   (o un id de instantánea)
#   … y solo una parte: --db-only o --media-only, delante de lo anterior

# 3. Volver a levantar: el servicio release aplica antes las migraciones que falten, si el
#    código es más nuevo que el respaldo
docker compose up -d
```

`restore.sh` no deja nada a medias:

1. Primero verifica el dump (`pg_restore --list`) y los medios (`tar tzf`).
2. Después prepara los medios en una carpeta aparte dentro de cada volumen.
3. Restaura la base en una sola transacción (`pg_restore --single-transaction --exit-on-error`):
   si algo falla, la base queda como estaba y la carpeta preparada se borra.
4. Solo con la base ya restaurada, sustituye el contenido de `media` y `private_media`.

El esquema queda como en el respaldo. Si el código desplegado es más nuevo, el servicio `release`
aplica las migraciones que falten al levantar (paso 3), antes de que arranque `web`.

> **Confirmación obligatoria.** `restore.sh` es destructivo y antes bastaba con invocarlo sin
> argumentos (`latest` era el valor por defecto) para arrasar la base y los medios. Ahora exige
> `RESTORE_CONFIRM=SI-DESTRUIR-<nombre-de-la-base>`, que debe coincidir con `POSTGRES_DB`.
>
> **Endurecimiento pendiente del sidecar (requiere una decisión sobre tu host).** El
> contenedor de respaldos corre como **root** y monta `media`/`private_media` en
> lectura-escritura. Ambas cosas se pueden cerrar, pero no a ciegas: añadir `user: postgres`
> (uid 999) exige que `BACKUP_DIR` pertenezca a ese uid en el host —si no, los respaldos
> dejan de escribirse **en silencio**—, y montar los volúmenes `:ro` rompería `restore.sh`,
> que necesita escribirlos. Un respaldo roto es peor que un contenedor con privilegios, así
> que se deja como paso manual: `chown -R 999:999 "$BACKUP_DIR"` y luego `user: postgres`
> en el servicio; y si se quiere `:ro`, separar el sidecar programado del servicio de
> restauración. Lo que sí está hecho: el sidecar ya **no** recibe el `.env` completo (antes
> le llegaban `DJANGO_SECRET_KEY` y las credenciales de SMTP, que no necesita).
>
> **Permisos.** `backup.sh` corre con `umask 077` y deja los artefactos en `0600` dentro de un
> directorio `0700`: contienen la base completa (correos, PII de envíos, hashes) y los manuscritos
> privados. `BACKUP_DIR` debe pertenecer a un usuario dedicado y **nunca** apuntar al directorio del
> repositorio. El cifrado en reposo lo aporta restic en el off-site; el respaldo local va en claro.

**Recuperación total desde cero** (host nuevo): si se perdió el host, se perdió también
`BACKUP_DIR`, y el respaldo está en restic. Clonar el repo, poner en `.env` las variables de restic,
`docker compose up -d db`, restaurar con `restore.sh --from-restic latest` y `docker compose up -d`
(el release migra si hace falta).

## Prueba de restauración (obligatoria)

Un respaldo no probado no cuenta. Verificación de extremo a extremo (destruye y recupera los datos):

```bash
docker compose run --rm --entrypoint sh backup /scripts/backup.sh   # 1. respaldar
docker compose down -v                                              # 2. simular pérdida total
docker compose up -d db redis                                       # 3. base vacía
docker compose run --rm --entrypoint sh -e RESTORE_CONFIRM=SI-DESTRUIR-resenas \
  backup /scripts/restore.sh latest                                 # 4. restaurar
docker compose up -d                                                # 5. levantar app
# 6. verificar que el contenido volvió (home con artículos, adjuntos presentes)
```

Este flujo es el procedimiento de verificación de referencia. **Debe ejecutarse en producción de
forma periódica**: el CI no ve el VPS. Lo que sí prueba el CI en cada cambio (job `backup-restore`):

- `backup.sh` deja un respaldo completo y cerrado (`OK`, permisos 700 y 600);
- falla y avisa con un volumen vacío, con un volumen que no es un directorio y con el disco lleno;
- `restore.sh latest` salta los respaldos a medias;
- la base y los medios vuelven desde un repositorio restic, y la retención de restic poda;
- una restauración que falla a mitad deja la base y los medios como estaban;
- `--media-only` no toca la base.

Un RTO/RPO objetivo (p. ej. RTO < 2 h, RPO < 24 h) debe declararse y probarse contra este
procedimiento en el VPS.
