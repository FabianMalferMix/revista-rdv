# Cómo retomar el barrido manual (traspaso entre equipos)

Estado a **2026-10-14**. Este documento existe para poder continuar el barrido de
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

**El barrido se completó el 2026-09-02: 104 de 104 casillas.** La última era un límite
conocido del §4 (un ZIP renombrado a `.docx` pasaba como manuscrito), y la cerró
`fix-firma-zip`. El barrido produjo además varios lotes de código por fallos que ninguna
prueba automática podía ver, entre ellos `admin-acciones-por-rol`, `fix-dimensiones-nulas`,
`feed-identidad-del-sitio` y el propio `fix-firma-zip`.

**Después, el rediseño UX/UI** (`docs/plan-ejecucion-ux.md`, 25 pasos, del 2026-10-08 al
2026-10-14) cambió el sitio público. La guía tiene ahora **112 casillas: 100 comprobadas y
12 por comprobar**, que son las que describen lo que cambió:

| Bloque | Estado |
|---|---|
| §1 Sitio público | 9 por comprobar: la portada, el dossier, la ficha de un evento y las seis de §1.5 (cabecera, menú, cinta, índices, teclado y textos largos) |
| §2 Buscador | 3 por comprobar: la búsqueda por grupos |
| §3 a §11 | completos; el rediseño no los tocó |

**Lo siguiente** es comprobar esas doce a mano, en desarrollo y a 951 px de ancho, que es
como revisa el dueño del sitio. La verificación medida del rediseño está en
`docs/auditoria-ux-ui-verificacion.md`.

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

> **Usa mejor la receta del §11 de la guía** («Recrear la vista previa de producción»),
> que es más limpia que lo de abajo: con `env_file: !override [...]` el fichero de
> desarrollo se **sustituye** en vez de fusionarse, así que no hay que ir reponiendo
> variables una a una. Comprobado: con `!override`, `CELERY_BROKER_URL` desaparece del
> servicio y `settings.py` la calcula con la contraseña. Aplícalo a **web, worker y beat**:
> si se deja fuera al worker, este conserva el broker sin autenticar.
>
> Lo de abajo se conserva porque es lo que se usó de hecho durante §8 y §10, y describe
> qué variables acaban haciendo falta.

La configuración vive **fuera del repositorio** y hay que recrearla. Guárdala en
`~/.local/share/resenas-prodlocal/override.yml` (no en `/tmp`, que se limpia):

> **Los puertos NO van en el override.** Las listas `ports` se **suman** entre ficheros
> compose en vez de sustituirse, así que declarar `8090:80` deja también el `80:80` de
> `docker-compose.prod.yml` y el proxy no arranca («address already in use»). `prod.yml`
> ya los parametriza: pásalos como variables, `PROXY_HTTP_PORT=8090` y
> `PROXY_HTTPS_PORT=8443`.

```yaml
services:
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
       PROXY_HTTP_PORT=8090 PROXY_HTTPS_PORT=8443 \
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

## 4. Cómo se probaron los respaldos (§10)

Hecho el 2026-08-26. Se deja escrito porque es la parte más delicada del barrido y hay una
**decisión tomada y su porqué**, que sirve si hay que repetirla.

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

## 5. Cómo se comprobó §11, desarrollo y CI

Hecho el 2026-09-02. Tres casillas. Las dos primeras se corren solas:

```bash
docker compose exec web pytest                       # el orden se aleatoriza cada vez
docker compose exec web pytest -W error::DeprecationWarning
```

La tercera necesita mirar **Actions** en GitHub: cinco jobs (`test`, `build-prod`,
`security`, y los dos restantes). Instala `gh` si quieres hacerlo por consola.

---

## 6. Cabos sueltos, por si se cierran de camino

- **Las cuatro mejoras que quedaban** en `deferidos-y-decisiones.md` (el 404 en modo DEBUG,
  los rótulos a medias en inglés, `Article` sin `get_absolute_url` y el ZIP que pasaba por
  `.docx`) **están cerradas**; lo que queda abierto está en sus §2 a §4.
- **Siete PR de Dependabot abiertos** (#107 a #113), algunos de imágenes de Docker. Conviene
  revisarlos por tandas.
- **Decisiones que siguen siendo del dueño**: la licencia de TinyMCE, la identidad del sitio
  en la base de producción (en desarrollo ya está) y el `chown` del directorio de respaldos
  para que el sidecar no corra como root.
- **Resembrar pisa el estado editorial.** `seed_demo` usa `update_or_create` y reescribe
  el campo `status` directamente, sin pasar por el flujo: si resiembras, pierdes el
  recorrido de la bitácora y aparecen transiciones duplicadas. Y **no se corre sobre una
  base con la identidad aplicada**: el entorno de diseño se reconstruye con
  `tools/ux/preparar-entorno.sh`.
