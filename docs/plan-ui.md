# Plan UI/UX — jerarquía, identidad y pulido

> Aborda los puntos 1–4 de la revisión visual. **Principio rector:** la sobriedad es
> intencional (calza con un colectivo de poesía); no se redecora — se añade **jerarquía**
> a la portada y **un** gesto de identidad, y se pulen detalles de UX/accesibilidad. El
> punto 5 (fotos reales) es contenido, no código: va como checklist al final.

Se ejecuta con el flujo del proyecto: rama desde `main` → PR real → merge `--no-ff` → push →
borrar rama. Cada lote deja el sitio funcionando, con `ruff` + `pytest` verdes y smoke de rutas.

Mapa: **UI-1** = punto 1 · **UI-2** = puntos 2 + 4 · **UI-3** = punto 3.

---

## Lote UI-1 — Portada: jerarquía y ritmo  ·  (punto 1)

**Problema.** Hoy la portada apila ~10 bloques con el mismo peso visual (hero → números →
evento → poema → registro → 6 artículos → publicaciones → prensa → integrantes → aliados):
un pasillo largo sin jerarquía, con los integrantes —clave para gestores— al fondo.

**Objetivo.** Convertirla en una jerarquía curada con la audiencia (§6.1 del plan de contenidos).

**Cambios concretos**
1. **Hero enriquecido:** tagline + **manifiesto corto** (`site_profile.manifesto|truncatewords`,
   con enlace a `/dossier/`) + CTAs + **números integrados** en el hero (mover `stats-strip`
   adentro; eliminar la franja suelta).
2. **Un solo destacado grande** en vez de dos apilados (poema **y** registro). Regla:
   `featured_recording` si existe, si no `featured_poem`. (Opcional: campo
   `SiteProfile.hero_choice` = poema/registro/auto para que el editor elija — migración trivial.)
3. **Reordenar** a: hero → destacado único → próxima actividad (compacta, 1 línea) →
   **Integrantes (subidos)** → Textos recientes → Publicaciones → Prensa → Aliados.
4. **Adelgazar textos:** la portada muestra **4–5 artículos**, no 12, con «Ver todos los textos →».
   Esto exige un **archivo dedicado**: nueva ruta `content:text_archive` en `/textos/`
   (vista + template reusando `_article_list.html`, paginado). La home deja de ser el archivo.
5. **Ritmo visual — bandas alternadas:** clase `.band` / `.band-alt` (fondo `--surface`/`--paper`
   a ancho completo con `.wrap` interno) para seccionar sin recargar. El destacado recibe más
   peso visual; las franjas secundarias mantienen `.subhead` mono.

**Archivos:** `apps/content/views.py` (home: recortar a 5 + contexto; nueva `text_archive`),
`apps/content/urls.py` (+`/textos/`), `templates/content/home.html` (reorden + bandas),
`templates/content/text_archive.html` (nuevo), `templates/base.html` (nav/pie → enlace a
`/textos/`), `static/css/site.css` (`.band`, hero con números, destacado grande).

**Pruebas:** home 200 con ≤5 artículos y enlace a `/textos/`; `/textos/` 200 + pagina (15→12+3);
un solo bloque destacado (no ambos); integrantes presentes antes que artículos. Ajustar los
asserts de portada existentes (siguen mostrando integrantes/publicaciones/prensa/aliados).

**Riesgos:** las `.band` a ancho completo requieren romper el `max-width` del `.wrap` — usar el
patrón «banda full-bleed + wrap interno», no cambiar `.wrap`. Es el lote más grande.

---

## Lote UI-2 — Identidad tipográfica + navegación responsive  ·  (puntos 2 + 4)

**Objetivo.** Darle **un** rasgo memorable (una display serif propia) y arreglar la nav en móvil.
Ambos viven en el «marco» del sitio (masthead + CSS), por eso van juntos.

**Cambios concretos**
1. **Display serif auto-hospedada** (p. ej. **Fraunces**, licencia OFL → se puede empaquetar).
   - Descargar y commitear `static/fonts/fraunces-*.woff2` (subset latino; 1 archivo variable o
     2 pesos). Fetch desde el repositorio OFL en la implementación.
   - `@font-face` con `font-display: swap`; definir var `--display`.
   - Aplicar **selectivamente**: marca, `h1` de índices/detalle y `.hero-tagline`. El **cuerpo de
     los poemas y artículos NO cambia** (sigue en la serif de lectura).
   - **Ojo técnico:** en `site.css` la fuente se referencia con `url('../fonts/…woff2')` **relativo**
     (no `{% static %}`; el CSS no es plantilla). `CompressedManifestStaticFilesStorage` reescribe
     esa `url()` a la versión con hash en `collectstatic` — funciona con WhiteNoise.
2. **Nav responsive sin JS** con `<details><summary>Menú</summary>…</details>`:
   - En móvil: colapsada tras «Menú ▾» (disclosure nativo, accesible, degrada sin JS).
   - En `≥720px`: `summary` oculto y `.nav` en línea (media query). Los 9 enlaces siguen en el DOM.

**Archivos:** `static/fonts/` (nuevo asset), `static/css/site.css` (`@font-face`, `--display`,
media query de nav), `templates/base.html` (envolver nav en `<details>`).

**Pruebas:** los 9 enlaces de nav siguen presentes en el DOM (el `<details>` no los elimina);
`site.css` referencia `fraunces`/`--display`; el archivo de fuente existe en `static/fonts/`.
(El render tipográfico no es testeable en unidad → se valida por smoke visual.)

**Riesgos:** peso del woff2 (usar subset latino, `font-display: swap` evita FOIT). Verificar que
`collectstatic` reescribe la `url()` (correr el paso de estáticos de prod aislado, como en Lote 3).

---

## Lote UI-3 — UX y accesibilidad  ·  (punto 3)

**Objetivo.** Quick wins de bajo costo y alto retorno; todo sin JS nuevo salvo lo mínimo.

**Cambios concretos**
1. **Dropdown de búsqueda como overlay** (hoy empuja el layout): `#search-results` pasa a
   `position:absolute` bajo el buscador (contenedor `position:relative`, `z-index`, `max-height`
   con scroll). Al tipear ya no salta la página.
2. **Skip link:** `<a class="skip" href="#main">Saltar al contenido</a>` como primer elemento del
   `<body>`, visible solo en `:focus`; añadir `id="main"` a `<main>`.
3. **`aria-live="polite"`** en el contenedor de resultados de búsqueda (un lector de pantalla
   anuncia los resultados htmx).
4. **`:focus-visible` global:** una regla para `a, button, [tabindex], input` con `outline` de
   acento (hoy solo lo tiene el buscador).
5. **Lightbox de galería sin JS** (técnica CSS `:target`): cada foto enlaza a `#foto-N`; un overlay
   `:target` muestra la imagen a tamaño completo con cierre por enlace. En
   `agenda/event_detail.html` (grilla `photo-grid`).

**Archivos:** `templates/base.html` (skip link, `id=main`, `aria-live`, mover/anclar
`#search-results`), `static/css/site.css` (overlay, `.skip`, `:focus-visible`, lightbox `:target`),
`templates/agenda/event_detail.html` (markup del lightbox).

**Pruebas:** skip link presente con `href="#main"` y `<main id="main">`; contenedor de resultados
con `aria-live`; `site.css` contiene la regla `:focus-visible`; el overlay del lightbox se renderiza
cuando el evento tiene fotos.

**Riesgos:** el overlay de búsqueda no debe tapar contenido en móvil (probar con teclado virtual).
La técnica `:target` cambia el hash de la URL — aceptable para una galería.

---

## Orden y tamaño

1. **UI-1** (medio-grande) — máxima visibilidad; arregla el problema #1.
2. **UI-2** (medio) — el gesto de identidad levanta todo el sitio; bajo riesgo.
3. **UI-3** (medio) — pulido transversal.

Sin dependencias fuertes entre lotes; este orden prioriza impacto visible.

## Punto 5 — Fotos reales (contenido, no código)

La mayor mejora visual no se programa: retratos de integrantes y fotos de recitales reemplazando
avatares de iniciales y portadas de color plano. Entregable: un checklist en `docs/` con formatos
y proporciones esperadas (integrante 1:1 ≥600px; afiche/portada; foto de evento 8:5) para que el
colectivo suba material y el mismo diseño «suba dos categorías».
