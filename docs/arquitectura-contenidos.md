# Arquitectura de contenidos — Colectivo de Poesía

> Plan para reorientar la plataforma desde «revista/blog para lectores» hacia el **dossier vivo de un
> colectivo de poesía**, dirigido a **pares y gestores culturales**. La tienda es **solo vitrina**
> (catálogo, sin pasarela de pago). Este documento define el modelo de datos objetivo, cómo se apoya
> en lo ya construido y un plan de ejecución por lotes.

## 1. Objetivo y audiencia

Un gestor cultural, un jurado de fondo o un par que entra al sitio está evaluando **«¿vale la pena
programarlos / reseñarlos / financiarlos?»**. Necesita, rápido: proyecto claro (poética), recorrido
(qué han hecho), prueba (registros de lecturas) y un **PDF que pueda reenviar**. Toda la arquitectura
empuja hacia eso.

**Prioridades derivadas** (de mayor a menor): dossier/kit de prensa · manifiesto/poética · trayectoria
(archivo de actividad) · registros (audio/video) · perfiles de integrantes · prensa · publicaciones
(catálogo) · aliados/financiamiento · contacto de gestión. El blog de reseñas se mantiene, pero pasa a
ser **evidencia de actividad**, no el motor del sitio.

## 2. Principios de diseño

1. **Aditivo y sobre lo construido.** Reutilizar `Contributor`, `Publisher`, `MediaAsset`, `Section`,
   el flujo editorial y las migraciones existentes. Nada se reescribe desde cero.
2. **3NF y consistencia.** Mismos patrones que ya rigen el esquema (slugs, `position`, tablas
   intermedias explícitas, `TextChoices`).
3. **Un solo flujo editorial reutilizado.** Piezas con curaduría (artículos, poemas) comparten el
   estado editorial de 8 estados; el resto usa visibilidad simple (`published` + `published_at`).
4. **Una sola fuente de verdad.** El dossier PDF se **genera** desde el contenido del sitio; no se
   mantiene un documento paralelo a mano.
5. **Ejecución por lotes**, igual que `docs/plan-mejoras.md`: rama desde `main` → PR → merge `--no-ff`.

## 3. Inventario actual (punto de partida)

| App | Modelos | Rol hoy |
|-----|---------|---------|
| `people` | `Contributor`, `SocialLink` | Personas + redes |
| `content` | `Section`, `Tag`, `Article`(+`ArticleContributor`,`ReviewedWork`), `Dossier`(+`DossierArticle`), `Page`, `EditorialTransition`, `EditorialNote` | Piezas editoriales + flujo |
| `reviews` | `Publisher`, `BookAuthor`, `Work` | Obras **externas** reseñadas |
| `media` | `MediaAsset` (solo imágenes) | Imágenes |
| `community` | `Comment`, `NewsletterSubscriber` | Comentarios / newsletter |
| `submissions` | `Call`, `Submission` | Convocatorias / envíos |

## 4. Modelo objetivo

Leyenda: **REUSE** (sin cambios) · **EXT** (extender) · **RENAME** · **NEW** · **NEW APP**.

### 4.1 Identidad y personas

**`people.Contributor` — EXT** (pasa a ser también «Integrante»)
- Añadir: `is_member` (bool), `short_bio` (bio corta para tarjetas/dossier), `poetics` (poética
  personal), `member_since` (año), `active` (activo vs histórico), `position`, `role` (opcional:
  «fundador/a», «gestión»).
- Ya cubierto: `display_name`, `bio` (→ bio larga), `photo` (FK `MediaAsset`), `website`, `user`,
  redes vía `SocialLink`.
- Nota: se evita una tabla `MemberProfile` O2O aparte; los campos son pocos y el patrón del repo es
  enriquecer el modelo. (Alternativa O2O documentada en §9, decisión 2.)

**`showcase.SiteProfile` — NEW** (singleton, una sola fila)
- `name`, `tagline` (poética corta), `manifesto` (texto) **o** `manifesto_page` (FK `content.Page`).
- `founded_year`, `location`, `general_email`, `booking_email` (contacto de **gestión**), `phone`.
- Destacados de portada: `featured_recording` (FK `media.Recording`), `featured_poem` (FK `content.Poem`).
- `dossier_pdf` (FileField, override manual opcional del kit generado).
- Redes del colectivo (mismo patrón que `SocialLink`).

### 4.2 Obra literaria

**`content.Poem` — NEW**
- `slug`, `title`, `epigraph` (opcional), `body` (se **renderiza preservando saltos y sangrías** —
  `white-space: pre-wrap`; ver §8).
- `authors` (M2M `Contributor`, patrón de `Article` para coautoría).
- `status` + `owner` + `published_at` (flujo editorial reutilizado, ver §7).
- `recording` (FK `media.Recording`, audio del autor leyéndolo), `featured`, campos SEO.

**`content.Collection` — RENAME de `content.Dossier`**
- Renombrar para **liberar la palabra «dossier»** (que pasa a significar *kit de prensa*). «Colección /
  Serie / Antología».
- Extender su M2M para agrupar **poemas además de artículos** (`poems` M2M, junto al `articles` actual).

**`reviews.Work` / `BookAuthor` / `Publisher` — REUSE**
- Se mantienen para reseñas de **obras externas**. `Publisher` se reutiliza también en el catálogo
  propio (§4.5).

### 4.3 Registros y medios

**`media.MediaAsset` — REUSE** (imágenes).

**`media.Recording` — NEW** (registro de audio/video de lecturas)
- `title`, `slug`, `kind` (AUDIO/VIDEO).
- Fuente: `file` (FileField subido) **o** `embed_url` (YouTube/Vimeo/SoundCloud/Bandcamp) — uno u otro.
- `poster` (FK `MediaAsset`), `recorded_on`, `event` (FK `agenda.Event`), `participants` (M2M `Contributor`),
  `description`, `featured` (para portada), `published` + `published_at`, `position`.
- Alimenta la página de registros y el **feed podcast RSS** (§8).

> Los PDF (plaquettes descargables, dossier) se guardan con `FileField` directo en `Publication.pdf` y
> `SiteProfile.dossier_pdf`; no se crea un modelo `Document` salvo que se necesite compartir (§9).

### 4.4 Vida del colectivo — `agenda` (NEW APP)

**`agenda.Event` — NEW**
- `slug`, `title`, `type` (RECITAL/LANZAMIENTO/TALLER/FESTIVAL/FERIA/OTRO).
- `starts_at`, `ends_at` (opc), lugar: `venue_name`, `city`, `address`, `lat`/`lng` (opc).
- `description`, `poster` (FK `MediaAsset`, afiche), `participants` (M2M `Contributor`).
- `is_external` (invitados a un evento de terceros), `host` (organizador externo), `registration_url`.
- `published`, `featured`.
- **Deriva dos vistas:** `starts_at ≥ hoy` → **Agenda**; `starts_at < hoy` → **Trayectoria** (el «CV»).

**`agenda.EventPhoto` — NEW** (galería ligada a eventos)
- `event` (FK), `asset` (FK `MediaAsset`), `position`, `caption` (override opc).
- La **Galería** pública = eventos que tienen fotos.

**`agenda.Milestone` — NEW (opcional)** — hitos de la línea de tiempo que no son eventos (fundación,
primer libro): `year`, `title`, `description`. Si no, la trayectoria se deriva de `Event` + `Publication`.

### 4.5 Catálogo, prensa y aliados — `showcase` (NEW APP)

**`showcase.Publication` — NEW** (catálogo vitrina — **sin pago**)
- `slug`, `title`, `kind` (LIBRO/PLAQUETTE/FANZINE/ANTOLOGIA/REVISTA/DISCO).
- `publisher` (FK `reviews.Publisher`, opc), `year`, `isbn` (opc), `cover` (FK `MediaAsset`), `synopsis`.
- `participants` (M2M `Contributor`), `is_own` (editada por el colectivo vs participación).
- `pdf` (FileField, descarga gratis si es digital), `featured`, `position`, `published`.

**`showcase.WhereToBuy` — NEW** (dónde conseguirlo)
- `publication` (FK), `label` (editorial/feria/tienda), `url`, `position`. (Solo enlaces externos.)

**`showcase.PressMention` — NEW** (prensa)
- `title`, `outlet` (medio), `author` (periodista, opc), `published_on`, `kind`
  (ENTREVISTA/RESEÑA/NOTA/PERFIL/MENCION), `url`, `quote` (cita destacada), `logo` (FK `MediaAsset`),
  `featured`, `position`.

**`showcase.Partner` — NEW** (aliados / financiamiento)
- `name`, `kind` (FINANCIAMIENTO/INSTITUCION/EDITORIAL/MEDIA/ESPACIO/OTRO), `logo` (FK `MediaAsset`),
  `url`, `description`, `active`, `position`.

## 5. Relación con lo construido (matriz)

| Elemento existente | Acción | Detalle |
|--------------------|--------|---------|
| `people.Contributor`, `SocialLink` | **EXT** | Base de «Integrante»; añade campos de membresía |
| `content.Article` + flujo (`Section`,`Tag`,`EditorialTransition`,`EditorialNote`) | **REUSE / refactor** | Se extrae base editorial para compartir con `Poem` (§7) |
| `content.Dossier`(+`DossierArticle`) | **RENAME → `Collection`** | Libera «dossier» para el kit de prensa; agrupa también poemas |
| `content.Page` | **REUSE** | Manifiesto, historia, textos estáticos |
| `reviews.*` | **REUSE** | Reseñas de obras externas; `Publisher` se reutiliza en catálogo |
| `media.MediaAsset` | **REUSE** | Imágenes; audio/video/PDF van en `Recording`/FileField |
| `community.Comment` | **Deprioriza** | Se **oculta del público** (audiencia = pares/gestores); modelo intacto |
| `community.NewsletterSubscriber` | **Reencuadra** | Deriva a «lista de prensa/gestores» o queda latente |
| `submissions.*` | **Opcional** | Convocatorias solo si reciben obra externa; si no, latente |

## 6. Arquitectura pública (IA → entidades)

| Ruta | Contenido | Entidades |
|------|-----------|-----------|
| `/` | Portada orientada a gestores (ver §6.1) | `SiteProfile` + destacados |
| `/colectivo/` | Manifiesto/poética + historia/línea de tiempo | `Page`/`SiteProfile`, `Milestone`/`Event` |
| `/integrantes/`, `/integrantes/<slug>/` | Grilla + perfil (agrega su obra) | `Contributor`(member), `SocialLink`, `Poem`, `Article`, `Publication`, `Recording` |
| `/poemas/`, `/poemas/<slug>/` | Obra propia, tipografía cuidada + audio | `Poem`, `Recording` |
| `/colecciones/`, `/colecciones/<slug>/` | Antologías/series | `Collection` |
| `/resenas/`, `/resenas/<slug>/` | Blog de crítica (existente) | `Article` |
| `/agenda/` | Próximos eventos | `Event` (futuros) |
| `/trayectoria/` | Archivo de actividad (el «CV») | `Event` (pasados) + `Publication` + `Milestone` |
| `/eventos/<slug>/` | Detalle + galería + registros | `Event`, `EventPhoto`, `Recording` |
| `/galeria/` | Álbumes por evento | `Event` con `EventPhoto` |
| `/registros/` | Audio/video (+ podcast RSS) | `Recording` |
| `/publicaciones/`, `/publicaciones/<slug>/` | Catálogo + «dónde conseguirlo» | `Publication`, `WhereToBuy` |
| `/prensa/` | Menciones | `PressMention` |
| `/aliados/` | Aliados/financiamiento (o franja en home/footer) | `Partner` |
| `/dossier/` | **Kit de prensa** (HTML imprimible / PDF) | agrega todo (§8) |
| `/contacto/` | Contacto general + **gestión** | `SiteProfile` |
| Se mantienen | `/feed/`, `/buscar/`, `/robots.txt`, `/sitemap.xml`, `/healthz/`, (`/enviar/` opc) | — |

### 6.1 Jerarquía de la portada
1. Nombre + una línea de poética + **[Descargar dossier]** y **[Contacto gestión]**.
2. Manifiesto corto (link al completo).
3. Trayectoria en números / hitos (años · recitales · publicaciones · festivales).
4. **Registro destacado** (video o audio de una lectura).
5. Integrantes (grilla).
6. Publicaciones (catálogo).
7. Prensa + aliados.
8. Footer: contacto de gestión, redes, ubicación.

## 7. Flujo editorial y visibilidad por entidad

- **Flujo completo (8 estados + transiciones + notas):** `Article` (existente), `Poem` (nuevo).
  - **Refactor clave:** extraer una base editorial reutilizable. Recomendación: modelo abstracto
    `content.EditorialItem` (status, owner, published_at + hooks de `workflow.py`) del que hereden
    `Article` y `Poem`; y generalizar `EditorialTransition`/`EditorialNote` con **relación genérica**
    (`content_type` + `object_id`) para que sirvan a ambos. Es el trabajo estructural del lote de obra.
- **Visibilidad simple (`published` + `published_at`, gestionado en el admin):** `Event`, `Publication`,
  `PressMention`, `Partner`, `Recording`, `Collection`, perfil de integrante (`active`).
- **Config (solo admin):** `SiteProfile`.

## 8. El dossier / kit de prensa (pieza clave)

Objetivo: que un gestor descargue **un PDF reenviable** con bio del colectivo, integrantes, trayectoria,
publicaciones, prensa, aliados y contacto de gestión.

- **MVP (recomendado, cero dependencias nuevas):** ruta `/dossier/` como **HTML optimizado para
  impresión** (CSS `@media print`) que agrega el contenido en vivo; el usuario «imprime a PDF». Más un
  `SiteProfile.dossier_pdf` subido como override si se quiere una versión maquetada a mano.
- **Evolución:** generación automática de PDF con **WeasyPrint** (añade dependencia + libs del sistema)
  desde la misma plantilla, cacheado y regenerado al publicar cambios.

Otras notas técnicas:
- **Tipografía de poemas:** `body` en `white-space: pre-wrap` o markup mínimo saneado (ya hay `nh3`);
  respeta versos, sangrías y espacios.
- **Podcast RSS:** un feed adicional (patrón del `/feed/` existente) que expone `Recording` de audio.
- **Media en producción:** el audio/video/PDF subido usa el volumen `/media/` que **Caddy ya sirve**
  (no requiere infra nueva); los envíos privados siguen en `private_media`.
- **SEO/OG:** cada entidad nueva con `get_absolute_url`, título/descr. y `og_image` (portada/afiche).

## 9. Plan de ejecución por lotes

Cada lote: migraciones aditivas → admin → plantillas/vistas → **pruebas** → actualización del `seed_demo`
→ PR contra `main` → merge. Orden pensado para que cada lote deje el sitio funcionando.

### Lote A — Cimientos y renombres
- **RENAME** `Dossier → Collection` (data migration; actualizar admin, vistas, seed, plantillas).
- **NEW** `showcase.SiteProfile` (singleton) + cableado en header/footer (contacto gestión, redes).
- **NEW** `media.Recording` (substrato para registros; audio/video file-o-embed).
- Pruebas de migración de datos y del singleton. *Desbloquea todo lo demás.*

### Lote B — Identidad e integrantes
- **EXT** `Contributor` (campos de membresía) + admin.
- Público: `/integrantes/`, `/integrantes/<slug>/` (agrega poemas/reseñas/publicaciones/registros).
- Home: grilla de integrantes. Seed con integrantes realistas. Pruebas de vistas.

### Lote C — Obra: poemas y colecciones
- **Refactor** base editorial (`EditorialItem` abstracto + relación genérica en transiciones/notas).
- **NEW** `content.Poem` (reusa flujo) con render tipográfico; extender `Collection` con `poems`.
- Público: `/poemas/`, `/poemas/<slug>/`, `/colecciones/`. Pruebas de flujo y de render.

### Lote D — Vida del colectivo: eventos, agenda, galería, trayectoria
- **NEW APP** `agenda`: `Event`, `EventPhoto`, (`Milestone` opc).
- Público: `/agenda/`, `/trayectoria/`, `/eventos/<slug>/`, `/galeria/`.
- Home: trayectoria en números + evento destacado. Seed + pruebas.

### Lote E — Registros (audio/video) + podcast
- Exponer `Recording` en público: `/registros/`, embeds, relación con eventos/poemas/integrantes.
- **Feed podcast RSS**; «registro destacado» en portada. Pruebas de feed.

### Lote F — Catálogo, prensa y aliados
- **NEW** `showcase.Publication` (+`WhereToBuy`, reusa `Publisher`), `PressMention`, `Partner`.
- Público: `/publicaciones/`, `/prensa/`, `/aliados/` (+ franjas en home). Seed + pruebas.

### Lote G — Dossier / kit de prensa
- Ruta `/dossier/` HTML imprimible que agrega todo; override `SiteProfile.dossier_pdf`.
- CTAs de portada **[Descargar dossier]** / **[Contacto gestión]**. Pruebas de agregación.
- (Opcional posterior) autogeneración con WeasyPrint.

### Lote H — Limpieza según audiencia (opcional)
- Ocultar comentarios del público; decidir newsletter → «lista de prensa» o retirar; revisar
  convocatorias; ajustar navegación, SEO/OG y `sitemap` a la nueva IA.

## 10. Decisiones a confirmar (con mi recomendación)

1. **Renombrar `Dossier`(editorial) → `Collection`** para reservar «dossier» = kit de prensa. → *Recomiendo sí.*
2. **Integrante:** enriquecer `Contributor` (simple) vs `MemberProfile` O2O (más aislado). → *Recomiendo enriquecer.*
3. **Publicaciones:** modelo nuevo `Publication` vs generalizar `Work`. → *Recomiendo `Publication` (semántica clara).*
4. **Dossier PDF:** HTML imprimible + PDF subido (MVP) vs WeasyPrint desde ya. → *Recomiendo MVP primero.*
5. **Poemas:** flujo editorial completo reutilizado vs visibilidad simple. → *Recomiendo reutilizar el flujo.*
6. **Comentarios / newsletter / convocatorias:** ¿retirar, reencuadrar o dejar latentes? → *Recomiendo ocultar comentarios, reencuadrar newsletter como lista de prensa, dejar convocatorias latentes.*
