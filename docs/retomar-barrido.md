# Cómo retomar el barrido manual (traspaso entre equipos)

Estado a **2026-08-24**. Este documento existe para poder continuar el barrido de
`guia-pruebas-manuales.md` en otra máquina sin releer el historial.

---

## 0. Antes de cambiar de equipo

**Sube los commits pendientes.** El trabajo del barrido vive en `main`, y lo que no esté
empujado se queda en la máquina vieja:

```bash
git log --oneline origin/main..main    # ¿cuántos faltan?
git push origin main
```

Comprueba después que **CI sale verde** en la pestaña Actions (cinco jobs). Si no tienes
`gh` instalado, míralo en el navegador.

---

## 1. Dónde vamos

**91 de 104 casillas.** Completos §1, §2, §4, §5, §6, §7, §8 y §9.

| Bloque | Estado |
|---|---|
| §1 Sitio público | completo (22) |
| §2 Buscador | completo (8) |
| §3 Boletín | 7 de 10 — faltan honeypot, rate limit y correo de 260 caracteres |
| §4 Envío de propuestas | 8 de 9 — la que falta es un límite documentado, no una prueba |
| §5 Panel editorial | 16 de 17 — falta el ciclo de devolución completo |
| §6 Medios | 10 de 11 — falta «grabación inédita» |
| §7 Sindicación y SEO | completo (6) |
| §8 Controles de seguridad | completo (10) |
| §9 Comandos y tareas | completo (4) |
| **§10 Respaldos** | **0 de 4 — es lo siguiente** |
| §11 Desarrollo y CI | 0 de 3 |

El barrido ha producido **seis lotes de código**, todos por fallos que ninguna prueba
automática podía ver: `admin-acciones-por-rol`, `test-aislar-media-privado`,
`fix-dimensiones-nulas`, `feed-identidad-del-sitio`, `log-redaccion-campos-extra` y el
arreglo de la barra de navegación. La suite pasó de 452 a **472 pruebas**.

---

## 2. Lo que NO viaja con el repositorio

Al clonar en la máquina nueva faltará todo esto:

**`.env`** (ignorado por git). Créalo desde la plantilla:

```bash
cp .env.example .env
```

**Los volúmenes de Docker.** Se pierden la base de datos, los medios subidos y —esto
importa— la **bitácora editorial** que construimos en §5, con las ocho transiciones de
«Antología del margen». Para repoblar:

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo     # apunta las claves que imprime
docker compose exec web python manage.py setup_groups
```

**Las credenciales.** `seed_demo` genera contraseñas **aleatorias por corrida** y las
imprime **solo al terminar**: anótalas en ese momento, no hay forma de recuperarlas. El
superusuario no lo crea el seed; hazlo tú:

```bash
docker compose exec web python manage.py createsuperuser
```

**Los archivos de prueba** de §4 y §6. Se regeneran; su receta está en los commits
`d825f8c` (envíos) y `f91935c` (medios). Hacen falta solo si repites esos bloques.

**El `MARCADOR.txt` de `private_media`.** Es un archivo puesto a mano
(`MARCADOR-RESPALDO-lote1`) que sirve para comprobar que el respaldo incluye el
directorio privado. Recréalo antes de §10:

```bash
docker compose exec web sh -c 'echo MARCADOR-RESPALDO-lote1 > /app/private_media/MARCADOR.txt'
```

---

## 3. La vista previa de producción (`:8090`)

§8, §10 y parte de §11 necesitan Caddy y `DEBUG=0`, que el entorno de desarrollo no tiene
(sus cinco contenedores son web, worker, beat, db y redis: **sin proxy**).

La configuración vive **fuera del repositorio** y hay que recrearla. Guárdala en
`~/.local/share/resenas-prodlocal/override.yml` (no en `/tmp`, que se limpia):

```yaml
services:
  proxy:
    ports: ["8090:80", "8443:443"]
  web:
    environment:
      DJANGO_DEBUG: "0"
      DJANGO_SECRET_KEY: local-prod-demo-9f3Kx7mQ2vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN
      DJANGO_ALLOWED_HOSTS: localhost,127.0.0.1
      DJANGO_CSRF_TRUSTED_ORIGINS: https://localhost
      DJANGO_SECURE_SSL_REDIRECT: "0"
      DJANGO_HSTS_SECONDS: "0"
      DJANGO_COLLECTSTATIC: "1"
      DJANGO_SKIP_MIGRATE: "1"
      POSTGRES_PASSWORD: local-prod-demo-db-password
      REDIS_PASSWORD: local-prod-demo-redis-password
      # El compose base carga env_file: .env (DESARROLLO), que fija estas dos SIN
      # credenciales y pisa las que settings.py construye a partir de REDIS_PASSWORD.
      # Sin reponerlas, /readyz/ responde 503 con broker:false aunque Redis esté sano.
      # No es un defecto del proyecto: .env.prod.example no las define a propósito.
      CELERY_BROKER_URL: redis://:local-prod-demo-redis-password@redis:6379/0
      CELERY_RESULT_BACKEND: redis://:local-prod-demo-redis-password@redis:6379/1
```

> Esas credenciales son **de demostración local**. No las uses en ningún despliegue real.

Para levantarla:

```bash
export REDIS_PASSWORD=local-prod-demo-redis-password \
       POSTGRES_PASSWORD=local-prod-demo-db-password \
       SITE_ADDRESS=:80 \
       DJANGO_SECRET_KEY=local-prod-demo-9f3Kx7mQ2vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN \
       DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
       DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost

docker compose -p resenasprod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  -f ~/.local/share/resenas-prodlocal/override.yml up -d
```

Comprobación de que quedó bien: `curl -s localhost:8090/readyz/` debe devolver **200** con
`database` y `broker` en `true`. Si sale 503 con `broker:false`, faltan las dos URLs de
Celery del override.

Ambas pilas **conviven**: desarrollo en `:8000`, vista previa en `:8090`.

---

## 4. Lo siguiente: §10, respaldos

Es la parte más delicada del barrido y hay una **decisión tomada y su porqué**.

### La decisión

Hacer **también la restauración destructiva**, mientras todos los datos sean ficticios.
Un respaldo que nunca se ha restaurado no es un respaldo, es una suposición; y ésta es la
última ventana barata. En cuanto haya suscriptores reales —correos de personas, datos bajo
la Ley 21.719— ejecutar `pg_restore --clean` y `rm -rf /volumes/media/*` deja de ser una
prueba y pasa a ser una decisión que nadie querrá tomar.

### El método, que NO es el de la guía

Respaldar y restaurar sin tocar nada en medio **no demuestra nada**: el estado final es
idéntico al inicial, que es indistinguible de que el guion no haya hecho nada. Hay que
romper el estado a propósito entre una cosa y otra:

1. **Respaldar** y comprobar los tres archivos (`db.dump`, `media.tar.gz`,
   `private_media.tar.gz`) y los permisos `700` en el directorio y `600` en los archivos.
2. **Restaurar sin confirmar** → debe negarse. Gratis y no destructivo. El guion exige
   `RESTORE_CONFIRM=SI-DESTRUIR-<nombre-de-la-base>`.
3. **Romper el estado**, después del respaldo:
   - crear un artículo «MARCADOR-POST-RESPALDO» → *debe desaparecer*;
   - borrar un artículo existente → *debe reaparecer*;
   - borrar `MARCADOR.txt` de `private_media` → *debe reaparecer* (la única forma de saber
     que el directorio privado viaja de verdad en el respaldo);
   - borrar una imagen de `mediafiles` → *debe reaparecer*.
4. **Parar `web`, `worker` y `beat`** antes de restaurar, como manda el propio guion
   (`infra/backup/restore.sh`), para que no haya conexiones abiertas.
5. **Verificar los cuatro marcadores** uno por uno.

### Lo que esta prueba no demuestra

Que funcione aquí valida **el guion y el procedimiento**, no el entorno real de despliegue:
allí los volúmenes, los permisos y el usuario que corre el sidecar pueden diferir. Sigue
abierto en `deferidos-y-decisiones.md` el punto del sidecar de respaldo corriendo como
root y con el directorio en modo escritura.

---

## 5. Después: §11, desarrollo y CI

Tres casillas. Las dos primeras se corren solas:

```bash
docker compose exec web pytest                       # el orden se aleatoriza cada vez
docker compose exec web pytest -W error::DeprecationWarning
```

La tercera necesita mirar **Actions** en GitHub: cinco jobs (`test`, `build-prod`,
`security`, y los dos restantes). Instala `gh` si quieres hacerlo por consola.

---

## 6. Cabos sueltos, por si se cierran de camino

- **Cuatro mejoras pendientes** en `deferidos-y-decisiones.md`: el 404 en modo DEBUG, los
  rótulos a medias en inglés (incluido el «Account locked» de la pantalla de acceso),
  `Article` sin `get_absolute_url` —que deja al panel sin botón «Ver en el sitio»— y el
  ZIP que pasa por `.docx`.
- **Nueve ramas de Dependabot** acumuladas en el remoto, algunas ya solapadas entre sí
  (`redis-8.0.1` y `redis-8.1.0`). Conviene cerrarlas por tandas antes de que choquen.
- **Decisiones que siguen siendo tuyas**: la licencia de TinyMCE, configurar la identidad
  del sitio en el panel, y el `chown` del directorio de respaldos para que el sidecar no
  corra como root.
- **Resembrar pisa el estado editorial.** `seed_demo` usa `update_or_create` y reescribe
  el campo `status` directamente, sin pasar por el flujo: si resiembras, pierdes el
  recorrido de la bitácora y aparecen transiciones duplicadas.
