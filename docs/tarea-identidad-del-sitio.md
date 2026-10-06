# Tarea: completar la identidad del sitio

> **Para el agente que ejecute esto.** Documento autocontenido: no supone conocimiento de
> conversaciones anteriores. Todos los datos de aquí se verificaron contra el código el
> 2026-09-02. Antes de dar nada por hecho, vuelve a comprobarlo — el proyecto cambia.

---

## 1. Qué hay que conseguir

El sitio funciona pero **se presenta con datos de marcador**. El nombre es «Reseñas», que
era el del proyecto anterior (una revista de reseñas); ahora es el sitio de un **colectivo
de poesía** cuya audiencia son pares y gestores culturales. Las redes sociales apuntan a
las portadas genéricas de Instagram y YouTube.

La tarea es sustituir eso por la identidad real. **Es una tarea de contenido, no de
código**: no hay que tocar modelos, plantillas ni migraciones.

### Lo que NO puedes decidir tú

El nombre real, el lema, el manifiesto y las URLs de las redes **son del usuario**. Si no
te los ha dado, pídeselos antes de empezar; no inventes valores ni pongas nada
provisional. Un marcador nuevo no es mejor que el viejo.

---

## 2. Dónde se edita

Todo vive en un único registro **singleton** (`pk=1`) del modelo
`apps.showcase.models.SiteProfile`.

```
http://127.0.0.1:8000/admin/showcase/siteprofile/1/change/
```

**Hace falta la cuenta `admin`** (superusuario). Comprobado: `editora` **no** tiene
`showcase.change_siteprofile`, así que con esa cuenta la sección ni siquiera aparece.

Las redes sociales **no tienen entrada propia en el panel**: `SiteSocialLink` se edita como
*inline* dentro de ese mismo formulario, al final.

---

## 3. Estado de los campos

**Aplicado en el entorno de desarrollo el 2026-10-06**, con valores dados por el usuario.
Verificado con `SiteProfile.load()` y con los cuatro comandos del §5.

| Campo | Valor | |
|---|---|---|
| `name` | `Repitentes del Verso` | ✅ |
| `tagline` | `Colectivo de poesía` | ✅ |
| `founded_year` | `2023` | ✅ el dossier calcula los años de trabajo desde aquí |
| `general_email` | `repitentesdelverso@gmail.com` | ✅ |
| `location` | `Chile` | ✅ |
| Instagram | `https://www.instagram.com/repitentesdelverso` | ✅ única red configurada |

### Lo que falta

| Campo | Estado | Qué hacer |
|---|---|---|
| `manifesto` | **provisional** | Hay un texto escueto de 21 palabras que no afirma nada que no se sepa. Sale **recortado a 28 palabras en la portada** y completo en `/dossier/`, así que debe leerse bien de las dos formas. El usuario lo escribirá. |
| `og_image` | vacío | Imagen al compartir en redes. Es clave foránea a `media.MediaAsset`: **sube la imagen primero** en Medios → Recursos y luego selecciónala. |
| `booking_email` | **vaciado a propósito** | Tenía `gestion@resenas.cl`, un dominio que no es del colectivo. Publicar una dirección en un dominio ajeno es peor que no publicar ninguna. Ponlo solo si existe de verdad. |
| YouTube | **eliminado** | Apuntaba a `https://youtube.com/` a secas. Si hay canal, añádelo como `SiteSocialLink`. |
| `phone` | vacío | Opcional. |
| `featured_recording` / `featured_poem` | apuntan a piezas sembradas | Revisar cuando haya contenido real. |
| `dossier_pdf` | vacío | Kit de prensa, si existe. |

> **Esto está SOLO en el entorno de desarrollo.** La vista previa de `:8090` tiene su
> propia base de datos y conserva los datos antiguos. El despliegue real tendrá la suya.

> **`seed_demo` lo borra todo.** Usa `update_or_create` y reescribe el perfil. No lo
> ejecutes después de aplicar esto.

## 4. Cómo aplicarlo

**Prefiere el panel** si el usuario está delante: es la vía normal y deja constancia en el
historial de administración de Django.

Si te pide que lo hagas tú, hazlo por consola con los valores que **él** te dé:

```bash
docker compose exec -T web python - <<'PY'
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from apps.showcase.models import SiteProfile, SiteSocialLink

p = SiteProfile.load()
p.name = "..."          # <- valores del usuario, no inventados
p.tagline = "..."
p.save()

SiteSocialLink.objects.filter(profile=p).delete()
SiteSocialLink.objects.create(profile=p, platform="Instagram", url="https://...", position=0)
print(f"perfil: {p.name} — {p.tagline}")
PY
```

> **`SiteProfile` no se crea con `objects.create()`.** Usa siempre `SiteProfile.load()`,
> que garantiza la fila singleton; el admin además impide añadir una segunda.

---

## 5. Cómo verificar que quedó bien

El perfil lo consumen **28 plantillas** más los dos feeds, así que el cambio se propaga
solo. Comprueba al menos estos cuatro puntos, que son los que fallan de formas distintas:

```bash
# 1. La portada: nombre y lema en el título y en Open Graph
curl -s http://127.0.0.1:8000/ | grep -oE "<title>[^<]*|og:site_name\" content=\"[^\"]*"

# 2. El RSS de textos: el canal lo construye desde SiteProfile (nombre — lema)
curl -s http://127.0.0.1:8000/feed/ | grep -oE "<title>[^<]*" | head -1

# 3. Las redes: se leen del array `sameAs` del JSON-LD, que contiene EXACTAMENTE los
#    SiteSocialLink. No uses un grep de href sobre la portada: capturaría también el
#    enlace del vídeo del registro destacado y parecería que hay redes de más.
curl -s http://127.0.0.1:8000/ | python3 -c "
import sys, re, json
for m in re.findall(r'<script type=\"application/ld\+json\"[^>]*>(.*?)</script>', sys.stdin.read(), re.S):
    d = json.loads(m)
    if 'sameAs' in d: print(d['sameAs'])"

# 4. Que no quede ningún marcador suelto (debe dar 0)
curl -s http://127.0.0.1:8000/ | grep -cE 'resenas\.cl|https://instagram\.com/"|https://youtube\.com/"'
```

Salida esperada del punto 3 tras lo aplicado el 2026-10-06:
`['https://www.instagram.com/repitentesdelverso']`

El punto 2 importa más de lo que parece: hasta hace poco el feed llevaba el título escrito
a fuego y **no leía `SiteProfile`**, así que configurar la identidad no lo cambiaba. Se
arregló en el lote `feed-identidad-del-sitio`. Si el feed no refleja el nombre nuevo, es
una regresión de eso, no un despiste de configuración.

---

## 6. Advertencias

**No hace falta ningún commit de código.** Esto son datos en la base de datos. Si te ves
editando `.py` o `.html`, algo se ha torcido: para.

**Resembrar pisa esto.** `seed_demo` usa `update_or_create` y reescribe el perfil. Si
alguien corre `python manage.py seed_demo` después, la identidad real se pierde. No lo
ejecutes tras aplicar los cambios.

**Cuidado con `og_image`.** Es una clave foránea a `media.MediaAsset`: hay que subir la
imagen primero en **Medios → Recursos** y luego seleccionarla. No acepta una ruta.

**Los correos son públicos.** `general_email` y `booking_email` se muestran en el sitio.
Confirma con el usuario que quiere publicarlos tal cual.

---

## 7. Contexto que quizá te haga falta

- El barrido de pruebas manuales (`docs/guia-pruebas-manuales.md`) está **completo, 104 de
  104**, y el CI en verde. Si algo falla tras tus cambios, es de tus cambios.
- `docs/deferidos-y-decisiones.md` recoge lo que se dejó abierto a propósito y por qué.
- **Sigue pendiente y es independiente de esta tarea:** el texto de la política de
  privacidad (Ley 21.719) es un **borrador redactado por una IA** y debe revisarlo un
  abogado antes de publicar el sitio. No lo des por bueno ni lo edites para «mejorarlo».
