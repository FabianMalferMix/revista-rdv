# Guía de pruebas manuales

Recorrido paso a paso de **todo lo que se puede ejercitar a mano** en «Reseñas». Cada
bloque dice qué probar, cómo hacerlo y **qué debe ocurrir**. Marca la casilla cuando el
resultado coincida; si no coincide, eso es un hallazgo.

El mapa de funcionalidades del que sale esta guía se levantó recorriendo los `urls.py`,
los `admin.py`, los comandos de gestión, las tareas de Celery, la infraestructura y el CI.

---

## 0. Preparación

### Los dos entornos

|           | Desarrollo                        | Vista previa de producción                   |
| --------- | --------------------------------- | -------------------------------------------- |
| URL       | <http://127.0.0.1:8000>           | <http://127.0.0.1:8090>                      |
| Servidor  | `runserver`, `DEBUG=1`            | gunicorn `gthread` tras **Caddy**, `DEBUG=0` |
| Estáticos | WhiteNoise (dentro de Django)     | **Caddy**, con caché inmutable               |
| Correo    | **a la consola** (log del worker) | SMTP real → fallará (no hay servidor)        |
| Datos     | tu base de siempre                | base propia y desechable                     |

**Regla práctica:** usa **desarrollo** para probar funcionalidad (sobre todo el boletín,
porque ahí puedes leer el correo) y **producción** para probar los controles de seguridad
(cabeceras, Caddy, CSP).

```bash
# Desarrollo
docker compose up -d
docker compose logs -f web worker      # deja esto abierto en otra terminal

# Vista previa de producción (crea su propio .env de prueba; NO toca el tuyo)
#   ver §11 para recrearla desde cero
```

### Credenciales

**Desarrollo** — `admin` (tu contraseña de siempre) · `editora` / `demo12345` ·
`autor1` / `demo12345`.

**Vista previa de producción** — `admin` / `bx0JqJp1po715yZq` ·
`editora` / `FTSUIgr79m9AJpKz` · `autor1` / `fdYrUkFqw7LZ8gOz`.

> Las de producción las generó `seed_demo --force` **al azar** y las imprimió una sola
> vez. Las de desarrollo conservan `demo12345` porque se crearon antes de ese cambio.

### Volver a empezar

```bash
docker compose exec web python manage.py seed_demo   # idempotente: se puede repetir
```

---

## 1. Sitio público — 40 rutas

Todas en español. Ábrelas en **desarrollo**; deben responder 200 y mostrar contenido real,
no una plantilla vacía.

### 1.1 Portada y archivo

- [x] **`/`** — Portada. Debe traer: un destacado grande (registro o poema), artículos
  
      recientes, integrantes, publicaciones, prensa y aliados.
- [x] **`/textos/`** — Archivo de textos, con paginación. Prueba `?page=2` y `?page=999`
  
      (este último **no debe reventar**).
- [ ] **`/poemas/`** — Índice de poemas.

### 1.2 Fichas de contenido

- [ ] **`/articulo/<slug>/`** — Entra desde la portada. Debe mostrar cuerpo, autoría,
  
      tiempo de lectura y datos estructurados JSON-LD.
- [ ] **`/poema/<slug>/`** — Ojo a la tipografía: los saltos y sangrías del poema se
  
      respetan (`pre-wrap`).
- [ ] **`/seccion/<slug>/`** — p. ej. `/seccion/resenas/`.
- [ ] **`/etiqueta/<slug>/`**
- [ ] **`/colaborador/<slug>/`** — Perfil con su obra.
- [ ] **`/colecciones/`** y **`/coleccion/<slug>/`** — Colección mixta (artículos y poemas).
- [ ] **`/pagina/privacidad/`**, **`/pagina/cookies/`**, **`/pagina/terminos/`** — Las tres
  
      páginas legales. La de privacidad debe citar la **Ley 21.719**.

### 1.3 El colectivo

- [ ] **`/integrantes/`** y **`/integrante/<slug>/`**
- [ ] **`/publicaciones/`** y **`/publicacion/<slug>/`** — Catálogo. **No hay pagos**: los
  
      enlaces llevan a puntos de venta externos.
- [ ] **`/prensa/`** — Menciones de prensa.
- [ ] **`/aliados/`** — Aliados y espacios.
- [ ] **`/dossier/`** — Kit de prensa. **Pulsa «Imprimir»** o `Ctrl+P`: la vista de
  
      impresión debe quedar limpia (sin nav ni pie).

### 1.4 Agenda y registros

- [ ] **`/agenda/`** — Solo eventos **futuros**.
- [ ] **`/trayectoria/`** — Eventos **pasados** + hitos + publicaciones, con números.
- [ ] **`/galeria/`** — Fotos por evento. **Pulsa una foto**: se amplía sin JavaScript
  
      (CSS `:target`). Pulsa fuera para cerrar.
- [ ] **`/evento/<slug>/`** — Ficha con fotos y registros del evento.
- [ ] **`/registros/`** y **`/registro/<slug>/`** — Ver §6.3 para el reproductor.

### 1.5 Catálogo bibliográfico

- [ ] **`/obra/<slug>/`** — Libro reseñado, con sus reseñas publicadas.
- [ ] **`/editorial/<slug>/`** y **`/autor/<slug>/`**

---

## 2. Buscador

- [ ] **Con JavaScript:** escribe «poesia» en la caja de la cabecera. Los resultados
  
      aparecen **en vivo** en un overlay, sin recargar (htmx, 300 ms de rebote).
- [ ] **Sin acentos:** busca `poesia` y luego `poesía`. **Ambas deben encontrar lo mismo**
  
      (extensión `unaccent`).
- [ ] **Sin JavaScript:** ve directo a **`/buscar/?q=umbral`**. Debe salir la **página
  
      completa** con cabecera y pie, no un fragmento suelto.
- [ ] **Busca en poemas y artículos a la vez:** un término que solo esté en un poema debe
  
      encontrarlo.
- [ ] **Borradores excluidos:** un texto no publicado **no** debe aparecer.
- [ ] **Entrada hostil:** `/buscar/?q=%00` debe responder **200**, no un error 500.
- [ ] **Consulta larga:** pega 5.000 caracteres. Debe responder 200 (se trunca a 120).
- [ ] **Rate limit:** recarga `/buscar/?q=a` más de 60 veces en un minuto. Debe aparecer
  
      «Demasiadas búsquedas seguidas», **no** un error.

---

## 3. Boletín — doble opt-in completo

> Hazlo en **desarrollo**: el correo se imprime en el log, así que puedes seguir el flujo
> entero. Ten abierto `docker compose logs -f worker`.

- [ ] **3.1 Alta.** En el pie del sitio, escribe un correo y envía. Debe redirigir con el
  
      mensaje **«Si la dirección es válida, te enviamos un correo…»**.
- [ ] **3.2 El correo.** En el log del worker aparece el mensaje completo. Comprueba que
  
      trae **dos enlaces** (confirmar y baja) y las cabeceras `List-Unsubscribe` y
      `List-Unsubscribe-Post`.
- [ ] **3.3 Un GET no confirma.** Abre el enlace de **confirmar**: debe mostrar una página
  
      con un **botón**, y el suscriptor sigue en `pending`. *(Esto impide que un escáner
      antivirus de correo confirme la suscripción por su cuenta.)*
- [ ] **3.4 Confirmar.** Pulsa el botón → «Suscripción confirmada».
- [ ] **3.5 Un solo uso.** Recarga ese mismo enlace y vuelve a pulsar: ahora da **404**.
- [ ] **3.6 Sin oráculo.** Da de alta **el mismo correo** otra vez y luego uno nuevo. El
  
      mensaje debe ser **idéntico** en ambos casos: no debe revelar quién ya estaba.
- [ ] **3.7 Baja.** Abre el enlace de baja → página con botón → pulsa → «Te diste de baja».
- [ ] **3.8 Honeypot.** Con las herramientas del navegador, rellena el campo oculto
  
      `apodo` y envía. Responde igual, pero **no se crea** el suscriptor.
- [ ] **3.9 Rate limit.** Más de 5 altas en un minuto → «Demasiados intentos».
- [ ] **3.10 Correo largo.** Un correo válido de 260 caracteres → error de validación
  
      limpio, **no** un 500.

Comprobar el estado en la base:

```bash
docker compose exec web python manage.py shell -c \
 "from apps.community.models import NewsletterSubscriber as N; print(list(N.objects.values('email','status')))"
```

---

## 4. Envío de propuestas

- [ ] **4.1** Abre **`/enviar/`**. Debe verse el formulario y la nota de consentimiento
  
      con enlace a la política de privacidad.
- [ ] **4.2 Envío válido.** Rellena y adjunta un **PDF** real → redirige a
  
      `/enviar/gracias/`.
- [ ] **4.3 Formato prohibido.** Adjunta un `.exe` o un `.jpg` → **rechazado**.
- [ ] **4.4 Contenido que no cuadra.** Renombra un `.png` a `.pdf` y adjúntalo → rechazado
  
      («el contenido no coincide con su extensión»): se validan los **bytes mágicos**.
- [ ] **4.5 Tamaño.** Un archivo de más de 10 MB → rechazado.
- [ ] **4.6 Rate limit.** Más de 10 envíos en una hora → aviso, **y no se pierde el texto
  
      escrito**.
- [ ] **4.7 El adjunto es privado.** Comprueba que **no** es accesible por URL pública:
  
      vive fuera de `MEDIA_ROOT`.

```bash
docker compose exec web ls -R /app/private_media | head
```

---

## 5. Panel editorial

### 5.1 Los tres roles

Entra en **`/admin/`** con cada cuenta y compara lo que ve cada una.

- [ ] **`autor1`** — Solo debe ver **sus propios** artículos. Puede crear y editar
  
      **borradores**; no puede borrar; no toca la fecha de publicación ni el dueño.

- [ ] **`editora`** — Ve **todo** el contenido, y las apps de envíos, boletín, medios y
  
      personas. No ve la configuración del sitio (app *showcase*).

- [ ] **`admin`** — Lo ve todo, incluida la identidad del sitio y los usuarios.

- [ ] **El desplegable «estado» es de solo lectura para todos**, incluido el admin: el
  
      estado solo cambia por las acciones del flujo.

### 5.2 Flujo editorial de principio a fin

Con `autor1`, crea un artículo. Después, en el listado, selecciona la fila y usa el menú
**Acciones**:

- [ ] **Enviar a revisión** (`autor1`) — borrador → en revisión.
- [ ] **Pedir cambios** (`editora`) — en revisión → cambios solicitados.
- [ ] **Enviar a revisión** otra vez (`autor1`).
- [ ] **Aceptar** (`editora`) — en revisión → aprobado.
- [ ] **Programar** (`editora`) — pon una fecha de publicación **futura** y programa.
  
      Con fecha pasada o vacía **debe negarse**.
- [ ] **Publicar** (`editora`) — aprobado o programado → publicado. Compruébalo en el sitio.
- [ ] **Despublicar**, **Archivar**, **Restaurar**.
- [ ] **Guardas de rol:** intenta *Aceptar* con `autor1` → debe rechazarlo.
- [ ] **Bitácora:** en la ficha del artículo, el historial de transiciones debe listar cada
  
      movimiento con actor y fecha, y **no ser editable**.

### 5.3 Publicación programada (automática)

- [ ] Programa un artículo para **dentro de 2 minutos** y espera. La tarea de Celery corre
  
      **cada minuto** y debe publicarlo solo. Verás la traza en `docker compose logs worker`.

### 5.4 Adjunto de un envío

- [ ] Con `editora`, entra en un envío y descarga el adjunto (`/envios/<pk>/archivo/`).
- [ ] **Cierra sesión** y abre esa misma URL → debe **denegarte** el acceso.

---

## 6. Medios

### 6.1 Subida de imágenes

- [ ] Sube un JPG grande (>1440 px) en **Recursos**. Debe rellenar solo el alto y el ancho.
- [ ] **Derivadas:** se generan copias de 480, 960 y 1440 px (solo las menores al original).

```bash
docker compose exec web ls /app/mediafiles/assets/$(date +%Y)/$(date +%m)/
```

- [ ] **Metadatos:** sube una foto **con GPS** (una de tu móvil sirve). El original
  
      publicado **no debe conservar el EXIF**.

```bash
docker compose exec web python -c "
from PIL import Image; print(dict(Image.open('/app/mediafiles/assets/AAAA/MM/tu-foto.jpg').getexif()))"
```

### 6.2 Validación de subidas *(este era el hallazgo ALTO de la auditoría)*

- [ ] En **Registros**, intenta subir un **`.html`** como archivo → **rechazado**.
- [ ] Prueba también `.svg` → rechazado. Un `.mp3` o `.mp4` → aceptado.
- [ ] En **Publicaciones**, el PDF solo admite `.pdf`.

### 6.3 Reproductores y click-to-play

- [ ] En `/registro/<slug>/` de un registro **con embed** (YouTube/Vimeo): **no debe haber
  
      iframe** al cargar. Verás un botón **«▶ Reproducir»** y el aviso de a qué proveedor
      te conecta.
- [ ] Pulsa el botón → aparece el reproductor. *(Comprueba en la pestaña **Red** que la
  
      conexión al tercero ocurre **solo entonces**.)*
- [ ] Un registro **con archivo** de audio muestra el reproductor nativo.
- [ ] **Grabación inédita:** enlaza a un poema publicado un registro **sin publicar**. En
  
      `/poema/<slug>/` **no debe aparecer** ni el audio ni el enlace.

### 6.4 Comando de derivadas

```bash
docker compose exec web python manage.py generate_image_derivatives
```

- [ ] Debe generar las derivadas que falten y reparar dimensiones nulas, sin duplicar.

---

## 7. Sindicación y SEO

- [ ] **`/feed/`** — RSS de textos.
- [ ] **`/feed/registros/`** — Podcast. El `<enclosure>` debe llevar **URL absoluta**
  
      (`http://…`), no relativa, y el feed declarar el namespace **iTunes**.
- [ ] **`/sitemap.xml`** — Debe incluir la portada, los 12 índices y las fichas publicadas;
  
      **no** borradores.
- [ ] **`/robots.txt`** — Debe hacer `Disallow: /admin/` y apuntar al sitemap.
- [ ] **Canonical:** en cualquier ficha, `<link rel="canonical">` no debe arrastrar la
  
      query string, salvo `?page=`.
- [ ] **Open Graph y JSON-LD:** ver el código fuente de la portada y de un artículo.

```bash
curl -s http://127.0.0.1:8000/feed/registros/ | grep -o '<enclosure[^>]*>'
```

---

## 8. Controles de seguridad

> Estos van en la **vista previa de producción** (`:8090`), que es donde están Caddy y
> `DEBUG=0`.

### 8.1 Cabeceras

```bash
curl -sS -D - -o /dev/null http://127.0.0.1:8090/ | grep -iE 'content-security|x-frame|nosniff|referrer|permissions'
```

- [ ] Deben aparecer CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` y
  
      `Permissions-Policy`. **No** debe aparecer la cabecera `Server`.
- [ ] **CSP más estricta en público:** `style-src 'self'` en `/`, pero
  
      `style-src 'self' 'unsafe-inline'` en `/admin/login/`.

### 8.2 Archivos subidos *(la otra mitad del hallazgo ALTO)*

```bash
curl -sS -D - -o /dev/null http://127.0.0.1:8090/media/<algun-archivo>
```

- [ ] Debe traer `X-Content-Type-Options: nosniff` y
  
      `Content-Security-Policy: default-src 'none'; sandbox`.

### 8.3 Estáticos desde el borde

```bash
curl -sS -D - -o /dev/null http://127.0.0.1:8090/static/css/site.<hash>.css
```

- [ ] `Cache-Control: public, max-age=31536000, immutable`.
- [ ] **Prueba decisiva:** para el contenedor `web`. Los estáticos deben **seguir
  
      respondiendo 200** mientras `/` da 502 → no pasan por gunicorn.

### 8.4 Anti-fuerza-bruta

- [ ] En `/admin/login/`, falla la contraseña **6 veces**. A partir del quinto intento
  
      debe bloquearte (django-axes, bloqueo por IP durante 1 hora).

```bash
docker compose exec web python manage.py axes_reset      # para desbloquearte
```

### 8.5 Guard de arranque

- [ ] Intenta levantar producción con la clave de ejemplo: **debe negarse a arrancar** con
  
      un mensaje que nombre las variables mal puestas.

### 8.6 Redacción de secretos en los logs

- [ ] Abre `/novedades/baja/UN-TOKEN-CUALQUIERA/` en `:8090` y luego mira el log del proxy:
  
      la ruta debe salir como `/novedades/baja/<redactado>/`.

### 8.7 Salud

- [ ] **`/healthz/`** → `ok` (no toca la base).
- [ ] **`/readyz/`** → JSON con el estado de base y broker. **Para Redis** y debe pasar a
  
      **503**.

---

## 9. Comandos y tareas

```bash
docker compose exec web python manage.py setup_groups              # idempotente
docker compose exec web python manage.py purge_stale_data --dry-run --days 180
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py generate_image_derivatives
```

- [ ] **`setup_groups`** — Correrlo dos veces no cambia nada. **Si le quitas un permiso a
  
      mano a un grupo, no debe restaurarlo.** Con `--reset` sí lo reemplaza.
- [ ] **`purge_stale_data`** — Con `--dry-run` solo informa. Purga suscriptores nunca
  
      confirmados, **los dados de baja**, envíos resueltos (con su adjunto) y los intentos
      de acceso de más de 90 días.
- [ ] **`seed_demo`** — En producción (`DEBUG=0`) **debe negarse** sin `--force`, y las
  
      contraseñas que genera son **aleatorias**.
- [ ] **Tareas automáticas:** `publish_due_items` cada minuto y `purge_stale_pii` los lunes
  
      a las 04:30 (`docker compose logs beat`).

---

## 10. Respaldos

```bash
docker compose --profile backup run --rm --entrypoint sh backup /scripts/backup.sh
ls -la ./backups/           # o tu BACKUP_DIR
```

- [ ] Se crea una carpeta con `db.dump`, `media.tar.gz` y `private_media.tar.gz`.
- [ ] **Permisos:** el directorio debe ser `700` y los archivos `600` — contienen la base
  
      completa y los manuscritos.
- [ ] **Restauración sin confirmar** → **debe negarse**:

```bash
docker compose --profile backup run --rm --entrypoint sh backup /scripts/restore.sh latest
```

- [ ] **Restauración confirmada** (⚠️ destructiva, hazla solo en la vista previa):

```bash
docker compose --profile backup run --rm --entrypoint sh \
  -e RESTORE_CONFIRM=SI-DESTRUIR-resenas backup /scripts/restore.sh latest
```

---

## 11. Desarrollo y CI

```bash
docker compose exec web python -m pytest -q                 # 385 tests
docker compose exec web python -m pytest -m integration     # solo los de concurrencia
docker compose exec web sh -c "cd /app && ruff check . && ruff format --check ."
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py check --deploy
```

- [ ] La suite pasa entera. El orden se **aleatoriza** en cada corrida.
- [ ] Los warnings son errores: si aparece una deprecación, la suite se pone roja.
- [ ] **CI:** cinco jobs en GitHub Actions — `test`, `build-prod`, `security`,
  
      `prod-runtime` y `backup-restore`.

### Recrear la vista previa de producción

```bash
# 1. un .env de prueba (NO uses el tuyo)
cat > /tmp/prod.env <<'EOF'
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<50+ caracteres variados>
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_HSTS_SECONDS=0
POSTGRES_DB=resenas
POSTGRES_USER=resenas
POSTGRES_PASSWORD=<contraseña>
REDIS_PASSWORD=<contraseña>
SITE_ADDRESS=:80
PROXY_HTTP_PORT=8090
EOF

# 2. un override que sustituya el env_file de desarrollo
cat > /tmp/prod.override.yml <<'EOF'
services:
  web:    { env_file: !override [/tmp/prod.env] }
  worker: { env_file: !override [/tmp/prod.env] }
  beat:   { env_file: !override [/tmp/prod.env] }
EOF

# 3. levantar, migrar y sembrar
C="docker compose --env-file /tmp/prod.env -p resenasprod -f docker-compose.yml -f docker-compose.prod.yml -f /tmp/prod.override.yml"
$C up -d --build
$C run --rm --entrypoint python web manage.py migrate
$C run --rm --entrypoint python web manage.py setup_groups
$C run --rm --entrypoint python web manage.py seed_demo --force   # anota las contraseñas

# bajar y borrar sus datos
$C down -v
```

---

## 12. Lo que NO se puede probar en local

No es que falle: **necesita infraestructura que aún no existe**.

| Funcionalidad                                         | Qué falta                                      |
| ----------------------------------------------------- | ---------------------------------------------- |
| Recibir el correo de confirmación en una bandeja real | Servidor SMTP + SPF/DKIM/DMARC en el DNS       |
| Certificado TLS automático y HSTS de verdad           | Un dominio real apuntando al host              |
| Respaldo off-site cifrado (restic) y alerta de fallo  | Repositorio restic + `BACKUP_PING_URL`         |
| Errores en Sentry                                     | Un `SENTRY_DSN`                                |
| Despliegue continuo con rollback                      | Registro de contenedores + destino             |
| Publicar el podcast en Apple/Spotify                  | Portada cuadrada ≥1400 px y un dominio público |

Y una que **existe pero está latente por decisión de producto**: no hay forma de **enviar**
un boletín. El sistema capta y confirma suscriptores, pero el camino de envío no se
construyó a propósito (minimización de datos, mientras no haya campaña).
