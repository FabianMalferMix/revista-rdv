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
`db.dump`, `media.tar.gz` y `private_media.tar.gz`.

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
  se sube a almacenamiento externo cifrado y deduplicado (S3/BackBlaze/rclone según el backend). El
  repo se inicializa solo la primera vez; la retención off-site la controla `RESTIC_KEEP` (30 por
  defecto). Sin `RESTIC_REPOSITORY` el paso se omite con un aviso.
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

**Retención:** local, se conservan los últimos `BACKUP_KEEP` respaldos (14 por defecto); off-site,
`RESTIC_KEEP` (30 por defecto). restic aporta cifrado y deduplicación; para política
abuelo-padre-hijo usar `restic forget --keep-daily/--keep-weekly/--keep-monthly`.

## Restaurar

⚠️ Detén `web`, `worker` y `beat` antes de restaurar en producción (evita conexiones activas).

```bash
# 1. Detener la app (mantener db arriba)
docker compose stop web worker beat

# 2. Restaurar el último respaldo (o un timestamp concreto)
#    Exige confirmación explícita nombrando la base que se va a destruir.
docker compose run --rm --entrypoint sh -e RESTORE_CONFIRM=SI-DESTRUIR-resenas \
  backup /scripts/restore.sh latest
#   … o: /scripts/restore.sh 20260709-030000

# 3. Volver a levantar
docker compose up -d
```

`restore.sh` usa `pg_restore --clean --if-exists` (recrea el esquema y los datos) y reemplaza el
contenido de `media`/`private_media`. Como el dump incluye la tabla `django_migrations`, el `migrate`
del arranque queda como no-op.

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

**Recuperación total desde cero** (host nuevo): clonar el repo, copiar `BACKUP_DIR` desde el
almacenamiento externo, `docker compose up -d db`, restaurar, `docker compose up -d`.

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

Este flujo es el procedimiento de verificación de referencia. **Debe ejecutarse tras cualquier
cambio en el esquema de respaldos y, en producción, de forma periódica** (idealmente automatizado:
un job programado que restaure el último respaldo en una BD desechable y compruebe un conteo de
filas). Un RTO/RPO objetivo (p. ej. RTO < 2 h, RPO < 24 h) debe declararse y probarse contra este
procedimiento; hoy no está automatizado.
