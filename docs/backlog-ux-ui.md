# Backlog UX/UI — Repitentes del Verso

> **Para el agente de IA que lo ejecute.** Documento autocontenido. Fuente de verdad de cada
> hallazgo: `docs/auditoria-ux-ui.md` (ids `ESP-n`, `TIP-n`, `COL-n`, `IMG-n`, `POR-n`, `NAV-n`,
> `CON-n`, `COM-n`). Este backlog agrupa esos 91 hallazgos en lotes ejecutables, en orden, con
> las decisiones ya tomadas. Fecha: 2026-10-08. Las líneas de `site.css` que se citan son las de
> ese día; comprueba antes de editar, porque cada lote las mueve.

---

## 0. Reglas de trabajo (léelas enteras antes del primer ticket)

**Flujo por ticket**, el mismo del proyecto (docs/plan-ui.md y el historial de git):
1. Rama desde `main` con el nombre del ticket en kebab-case (p. ej. `ux-1-1-imagenes-proporcion`).
2. Cambios acotados a lo que pide el ticket. Si descubres algo fuera de alcance, anótalo en
   `docs/deferidos-y-decisiones.md` §4 y sigue.
3. `docker compose run --rm --entrypoint ruff web check .` y `... ruff web format .`
4. `docker compose run --rm --entrypoint pytest web` en verde. Si un test fija una decisión que
   este backlog cambia a propósito (lista más abajo), actualízalo **en el mismo PR** y registra la
   decisión nueva en `docs/deferidos-y-decisiones.md` §1 con su porqué.
5. Capturas antes/después con la herramienta del ticket 0.1 (1440 y 390 como mínimo) en
   `tools/ux/out/<rama>/` y la tabla de métricas pegada en la descripción del PR (la CLI no adjunta imágenes).
6. PR real; con el CI del PR en verde, `gh pr merge --merge --delete-branch --subject "Merge <rama> — <efecto visible>"`
   (merge sin fast-forward hecho por GitHub, que además borra la rama remota); luego `git pull --ff-only`
   en `main` y se borra la rama local.
7. CI en verde en Actions antes de dar el ticket por cerrado: pip-audit y gitleaks **no** corren en local.

**Mensajes de commit** en español, como el historial: `<rama>: <qué cambia y por qué, en una línea>`.

**Restricciones no negociables** (romperlas falla tests o la CSP en producción):
- CSP estricta: sin `style=` en línea, sin `onclick`, scripts y fuentes solo propios con nonce
  donde aplique; nada de CDN ni Google Fonts. Un archivo `.svg` dentro de `backend/static/` rompe
  `tests/test_security_csp.py`: los glifos SVG van **en línea en la plantilla**; los íconos de
  pestaña, en `.png` o `.ico`.
- Todo funciona sin JavaScript (menú `<details>`, buscador con submit, click-to-play con `<noscript>`).
- Una sola paleta clara (`color-scheme:light`); los valores hex de `:root` no cambian; se pueden
  **añadir** tokens (`--paper-2`, `--riso-amarillo`, `--accent-on-ink`, `--line`, `--edge`).
- Click-to-play intacto: el iframe de YouTube/Vimeo solo se crea al pulsar (`static/js/embeds.js`).
- No ejecutar `seed_demo` después de que la identidad real esté aplicada: la pisa. Si en desarrollo
  necesitas resembrar, reaplica la identidad según `docs/tarea-identidad-del-sitio.md` §4.
- La base de desarrollo lleva material visual genérico generado por `seed_material_generico`
  (idempotente, nunca pisa material real; ver `docs/contenido-visual.md`). Sirve para diseñar con
  proporciones reales; el colectivo lo reemplaza desde el panel.
- Sin modelos ni migraciones nuevas. Lo único que toca `models.py` es un método (`Article.kicker()`).
- `.wrap{max-width:820px}` no cambia de valor: deja de ser el único contenedor, no deja de existir.
- Textos de interfaz en español de Chile; tipografía como la del sitio (sin mayúsculas nuevas).

**Tests que fijan decisiones anteriores y que este backlog cambia a propósito** (actualizar, no
borrar; cada uno en el ticket que lo rompe):
`tests/test_ia.py` (`NAV_PRINCIPAL` de 4 a 5), `tests/test_catalog.py::test_home_shows_catalog_but_not_press_or_partners`
(prensa y aliados vuelven como línea de respaldo), `tests/test_cinta_integrantes.py` (control de pausa y
copia oculta en táctil), `tests/test_ui_identity.py` (cifras acotadas a la portada, nav intacta),
`tests/test_ui_ux.py` (`.wrap` en `<main>`), `tests/test_home_ui.py::test_home_hero_has_manifesto_and_stats`,
`tests/test_contraste_paleta.py` (`PARES` crece), `tests/test_nav_css.py` (nav en una fila).

**Definition of Done de cada ticket:** ruff y pytest verdes; CI verde; las 40 rutas públicas de
`docs/guia-pruebas-manuales.md` §1 responden 200 (smoke con `curl`); sin scroll horizontal a 320,
390, 1440 y 1920; skip link, foco visible y landmarks intactos; capturas antes/después en el PR; la
guía de pruebas manuales actualizada si cambió algo que describe; los criterios de aceptación del
ticket medidos con la herramienta, no estimados.

**Orden:** épicas 0 → 6 en secuencia. Dentro de una épica, los tickets marcados `[paralelo]` pueden ir
en ramas simultáneas; los demás, en el orden listado (todos tocan `site.css` y se pisan).

---

## 1. Decisiones tomadas (delegadas por el dueño del sitio el 2026-10-08)

No vuelvas a preguntar por estas; están resueltas con criterio profesional y aquí consta el porqué.

| # | Tema | Resolución | Criterio |
|---|---|---|---|
| D1 | Cinta sin botón de pausa frente a WCAG 2.2.2 | Se corrige la pausa por hover y foco (no funcionaba), la animación corre **solo** en dispositivos con puntero (`hover:hover`) y sin `prefers-reduced-motion`, y en táctil la cinta es una fila con `scroll-snap`. **Sin control de pausa**: se propuso un icono discreto y el dueño del sitio lo descartó al verlo (2026-10-08), como antes había descartado el rótulo de texto (`dc2ffb3`). | Decisión del dueño. Lo que protege: en táctil y con «menos movimiento» no se mueve; con puntero se detiene al señalarla o al llevar el foco dentro. No hay pausa persistente, así que el cumplimiento de 2.2.2 (nivel A) es discutible. No volver a proponer el control salvo que él lo pida. |
| D2 | Buscador siempre visible | Se colapsa en un `<details>` con lupa dentro de la cabecera de una fila; la búsqueda en vivo con htmx sigue dentro del panel; `/buscar/` pasa a usar el sistema; la cobertura se amplía a integrantes, registros, publicaciones y eventos. | Sitio pequeño; el espacio de cabecera va al CTA de gestores; WCAG 2.4.5 no exige campo abierto. |
| D3 | La mono en nav, botones, pie y cifras | La mono queda en dos papeles: cejilla (12 px, mayúsculas, `+.1em`) y meta (13 px, caja baja). Nav en Syne 500 a 15 px, botones a 14 px en caja de frase, pie en serif 15 px, cifras en Syne. Se mantiene la pila mono de sistema; no se autoaloja otra. | La voz dominante debe ser la de lectura; las siete referencias racionan la familia «de sabor». |
| D4 | Serif de lectura autoalojada | Sí: **Source Serif 4** (OFL) variable, romana + cursiva, subconjunto latino, con fallback métrico; presupuesto de fuentes ≤ 200 KB sumando Syne. | Misma voz en Linux, macOS, Windows y Android; OFL permite empaquetar; `font-src 'self'` lo admite. |
| D5 | Amarillo del cartel como fondo | Sí, solo como superficie (`--riso-amarillo:#fce43c`) con tinta o magenta encima, un plano por viewport; sus pares entran en la prueba de contraste. | 13,81:1 con tinta y 4,96:1 con magenta; es la tinta del cartel que faltaba. |
| D6 | Bandas de tinta dentro de «una sola paleta clara» | Sí, máximo dos por página (destacado o cierre, y pie), texto en `--paper`, enlaces en `--accent-on-ink:#f77cc3`; `color-scheme:light` no cambia. | Una banda no es un modo oscuro; da el peso que hoy no tiene ninguna superficie. |
| D7 | «No cambiar .wrap» | `.wrap` conserva 820 px y pasa a ser el carril de lectura; `<main>` deja de llevarlo y monta una retícula de tres carriles (lectura / ancho 1320 / sangre); cabecera, nav y pie usan `.wrap-wide`. | Respeta la decisión de plan-ui.md y resuelve la queja principal sin alargar una línea de lectura. |
| D8 | Lema como titular con el nombre en `sr-only` | El nombre pasa a ser el h1 visible (Syne 800); el lema «Colectivo de poesía» es la cejilla; el h1 oculto se retira. Volver al lema como titular solo cuando exista una afirmación propia de seis palabras o menos. | Hoy el lema es una categoría genérica y el manifiesto es provisional: el nombre es lo único distintivo. |
| D9 | Barra fijada en cuatro enlaces; prensa y aliados fuera de la portada | Barra de cinco enlaces más CTA: Poemas · Textos · Registros · Publicaciones · Colectivo · [Dossier]. «Colectivo» es `/integrantes/`, cuya cabecera lleva una sub-fila (Trayectoria · Agenda · Galería · Prensa · Aliados). En la portada vuelve una **línea de respaldo** compacta (última cita de prensa + «Con el apoyo de»), no las dos franjas. Se actualizan `test_ia.py` y `test_catalog.py`. | Un tercio del encargo (textos y todo lo de gestores) vivía solo en el pie. |
| D10 | Placa azul del reproductor | El azul `--caratula` se queda como superficie de la placa, pero nunca vacía: póster en duotono si existe; si no, carátula tipográfica (título en Syne y meta en mono, en papel sobre azul). El azul es además la segunda tinta del duotono. | Figura-fondo dentro de la banda de tinta; el azul del cartel gana un sentido que hoy no tiene. |
| D11 | Cifras del dossier a 20 px «a propósito» | Syne 36–56 px acotado a `.dossier-doc`, con integrantes y festivales, también al imprimir. | Es lo primero que busca un jurado. |
| D12 | Cinta a partir de 12 integrantes | Se mantiene; el título lleva la cifra; retratos 4:5 de 160×200; cinco visibles en el carril ancho; en táctil, fila con scroll-snap. | La cinta no era el problema; sí lo eran sus tarjetas y su recorte. |
| D13 | Títulos de sección `.subhead` a 11 px (plan-ui.md) | Pasan a fila cejilla (12 px mono) + h2 en Syne `clamp(28px,3vw,40px)` en portada e índices; el dossier conserva su versión hasta el ticket 5.1. | Un encabezado no puede medir menos que el cuerpo que encabeza. |
| D14 | Hover por opacidad, bordes de 1 px y radios variados | Hover por color sólido o inversión; tokens de radio (`--r-1:3px` para campos, 0 para imágenes y tarjetas), filetes `--line` (decorativo) y `--edge` (funcional, ≥ 3:1). | Acabado consistente; WCAG 1.4.11 cuando el borde identifica un control. |

---

## 2. Épicas y tickets

Formato de cada ticket: objetivo · hallazgos · archivos · pasos · aceptación · verificación · tests.

### Épica 0 — Preparación

#### 0.1 Herramienta de capturas y métricas dentro del repo
- **Objetivo:** que cada ticket pueda medir lo que promete, con el mismo instrumento de la auditoría.
- **Estado:** hecho. `tools/ux/` contiene `capture.js` (Playwright-core + Chrome del sistema; un solo
  navegador para todas las páginas de `pages.txt`, en 1440, 390 y, en las marcadas, 1920),
  `metrics.py` (`tabla <dir>` y `comparar <antes> <despues>`, solo biblioteca estándar), `smoke.py`
  (recorre los enlaces internos y falla si alguno responde 400 o más) y su `README.md`.
- **Uso en cada ticket:**
  `node tools/ux/capture.js tools/ux/out/<rama> --only <páginas>` y luego
  `python3 tools/ux/metrics.py comparar tools/ux/out/baseline tools/ux/out/<rama>`.
- **Qué mide:** razón texto/viewport (con recorte por `overflow`), tamaño y familia de h1, h2, h3 y
  párrafo, caracteres por línea del cuerpo de artículo, imágenes en el primer viewport, imágenes cuya
  caja no respeta la proporción pedida (`desv`), porcentaje de elementos en monoespaciada, elementos
  en mayúsculas y bajo 12 px, objetivos pulsables bajo 24 y 44 px, scroll horizontal (también a 320 px)
  y alto de página.

#### 0.2 Línea base
- **Objetivo:** capturar el estado actual antes de tocar nada para comparar al final (ticket 6.2).
- **Pasos:** con el sitio en `http://localhost:8000`, capturar las 21 páginas de la auditoría en
  `tools/ux/out/baseline/` y guardar la tabla en `tools/ux/out/baseline/tabla.txt`.
- **Estado:** hecho el 2026-10-08, con el material genérico ya cargado. La carpeta no se versiona.
- **Aceptación:** la tabla reproduce las cifras de la auditoría: ratio 0,54 a 1440 en índices,
  h1 de índices a 12 px y cubiertas deformadas (180 px de ancho por la altura del atributo HTML:
  780 con las cubiertas de la siembra, 1400 con las del material genérico).

#### 0.3 Pedido de material al colectivo `[paralelo]`
- **Objetivo:** que el contenido real pueda llegar mientras se implementa (hallazgo IMG-11).
- **Archivos:** nuevo `docs/contenido-visual.md`.
- **Pasos:** redactar el checklist de la sección 3 de este backlog como documento para personas,
  con formatos, tamaños mínimos, dónde se usa cada pieza y a qué campo del panel va (Medios → Recursos,
  luego el campo). Enlazar desde `README.md`.
- **Aceptación:** el documento existe; ningún cambio de código.
- **Estado:** hecho el 2026-10-08, junto con el comando `seed_material_generico`, que deja cargado
  material genérico con las proporciones de esa lista (retratos 4:5, afiches, seis fotos por evento,
  cubiertas 5:7, carátulas 16:9, logos, foto de grupo).

### Épica 1 — Quick wins de CSS y plantillas (sin contenido nuevo)

Cada ticket es un PR pequeño. Secuenciales, porque todos editan `site.css`.

#### 1.1 Imágenes con su proporción real
- **Hallazgos:** ESP-2, IMG-1, POR-4, CON-1 (defecto más visible y más barato del sitio).
- **Archivos:** `backend/static/css/site.css` (junto al reset de la línea 40, y reglas 205, 222, 276-277, 282).
- **Pasos:** añadir `img, video{max-width:100%; height:auto; display:block}`; en las reglas que fijan
  `aspect-ratio` (`.pub-card img`, `.pub-cover-fallback`, `.photo-grid img`, `.album-grid img`,
  `.pub-cover`, `.event-poster`) añadir `height:auto` explícito. Los `.avatar` y `.partner-logo`
  conservan su alto porque lo fijan en CSS con mayor especificidad; comprobarlo.
- **Aceptación:** en `/`, `/publicaciones/`, `/publicacion/<slug>/`, `/galeria/` y `/evento/<slug>/`
  toda `<img>` renderiza con proporción intrínseca ± 2 % (`metrics.py` columna de proporción = 0
  desvíos); las cubiertas miden ≈ 180×252 en la rejilla y la banda «Publicaciones» de la portada baja
  de 1006 px a ≈ 480 px.
- **Tests:** nuevo `tests/test_css_imagenes.py` al estilo de `test_nav_css.py`: la hoja contiene la
  regla global y ninguna regla con `aspect-ratio` carece de `height:auto`.
- **Estado:** hecho (paso 3 del plan). Sin `display:block` global: cambiaba las imágenes en línea del
  cuerpo de los textos sin necesidad. El afiche del evento queda topado en 420 px, porque a todo el
  ancho de la columna medía más de una pantalla. Las pruebas viven en `tests/test_css_sistema.py`.

#### 1.2 Cabecera de índice en los once índices
- **Hallazgos:** TIP-1, CON-2, COM-3, ESP-11.
- **Archivos:** nuevo `templates/content/partials/_index_head.html`; `poem_index.html`,
  `text_archive.html`, `people/member_index.html`, `media/recording_index.html`,
  `showcase/publication_index.html`, `agenda/agenda.html`, `agenda/trayectoria.html`,
  `agenda/gallery.html`, `showcase/press_index.html`, `showcase/partner_index.html`,
  `collection_index.html`, `content/search.html`; `site.css` 124-127.
- **Pasos:** el parcial recibe `titulo`, `cejilla` (dato vivo: «12 poemas · 7 voces», «4 registros»,
  usando `paginator.count` o `|length`, sin consultas nuevas), `dek` (una frase de contexto para
  gestores, p. ej. «Poemas publicados desde 2023 por las integrantes del colectivo.») y un bloque
  opcional `subnav`. Reutiliza `.index-head` existente; el h1 pasa a `clamp(36px,5vw,56px)`.
  `.page-title` desaparece del CSS y de las plantillas.
- **Aceptación:** `metrics.py` da h1 ≥ 36 px en los once índices y h1 ≥ 1,3 × el h3 de tarjeta;
  cada índice muestra cejilla, h1 y dek.
- **Tests:** ampliar `tests/test_views.py` (o nuevo `test_indices.py`): cada índice responde 200 y
  su `<h1>` no lleva `page-title`; `grep -c "page-title" templates static` = 0.
- **Estado:** hecho (paso 4 del plan). El parcial recibe `cuenta`, `singular` y `plural` en vez de una
  cejilla ya armada, para concordar en número («1 texto», «2 textos») y omitirse con cero. El tamaño
  del h1 (`clamp(34px,4.6vw,56px)`) se aplica también a las fichas, que comparten `.index-head`.

#### 1.3 Medida de lectura, interlíneas y mínimos tipográficos
- **Hallazgos:** TIP-4, TIP-9, TIP-11, CON-3 (paso 1), CON-7 (parte: nueve reglas a 11 px).
- **Archivos:** `site.css` 41-42, 142, 178-179, 383-386 y las nueve reglas con `font-size:11px`.
- **Pasos:** `.article .body, .dek, .rec-sumario, .member-about, .dossier-section p{max-width:66ch}`;
  `.article .body{font-size:19px; line-height:1.55}`; `.dek{font-size:20px}`;
  `h1,h2,h3{line-height:1.1; text-wrap:balance}` después de `body` (y `.brand{line-height:1.2}`);
  `p{text-wrap:pretty}`; `@media (max-width:600px){.article .body, .dek{hyphens:auto}}` nunca en
  `.poem-body`; subir las nueve reglas de 11 px a 12 px.
- **Aceptación:** primera línea del cuerpo de `/articulo/<slug>/` entre 60 y 75 caracteres a 1440
  (medir con el `textExtent` y la fuente actual); `grep -c "font-size:11px" site.css` = 0; títulos
  de dos líneas con interlínea ≤ 1.1.
- **Tests:** `tests/test_css_sistema.py`: ningún texto bajo 12 px, títulos con interlínea propia, medida
  en `ch` y sin guionado en poemas.
- **Estado:** hecho (paso 3 del plan). La medida quedó en el token `--medida:58ch`, no en 66ch:
  medido en la página, 66ch daban 82 letras por línea con la serif de reserva (Liberation Serif) y
  58ch dan 74; con una serif de ancho normal serán unas 65. La bajada a 20 px se acotó al artículo
  (`.article .dek`) para no agrandar las de las tarjetas.

#### 1.4 Pausa real de la cinta, control sin JS y fila en táctil (D1, D12)
- **Hallazgos:** COM-1, CON-6 (parte), POR-11 (parte).
- **Archivos:** `site.css` 433-502; `templates/content/home.html` (bloque `cinta-caja`);
  `templates/people/partials/_member_card_cinta.html`.
- **Pasos:** (1) envolver la animación en `@media (hover:hover) and (prefers-reduced-motion:no-preference)`;
  fuera de ella `.cinta{overflow-x:auto; scroll-snap-type:x mandatory}`, `.cinta-card{scroll-snap-align:start}`
  y `.cinta-card[aria-hidden="true"]{display:none}` (la copia solo sirve a la animación).
  (2) Pausa: `.cinta-caja:hover .cinta-pista, .cinta-caja:focus-within .cinta-pista{animation-play-state:paused}`
  en lugar de `.cinta:hover` (línea 483), que nunca se cumple porque el enlace extendido de la línea
  490 cubre la pista. (3) El enlace extendido (`.cinta-pie a::after{inset:0}`) solo existe dentro de
  la media query de animación: en modo fila taparía la pista y el dedo no podría desplazarla.
  (4) Control discreto, sin `:has()`: `<input type="checkbox" id="cinta-pausa" class="cinta-toggle">`
  como primer hijo de `.cinta-caja` (antes de `.cinta`, así los selectores de hermanos lo alcanzan) con
  `aria-label="Pausar el movimiento de la cinta"`, oculto a la vista pero enfocable; y en `.cinta-pie`
  un `<label for="cinta-pausa" class="cinta-pausa">` que es solo un icono (dos barras dibujadas en
  CSS que pasan a triángulo al marcar), de 32 px, a la izquierda de la fila de «Conoce al colectivo».
  CSS: `#cinta-pausa:checked ~ .cinta .cinta-pista{animation-play-state:paused}` y
  `#cinta-pausa:focus-visible ~ .cinta-pie .cinta-pausa{outline:…}`. El icono se eleva sobre el enlace
  extendido (`position:relative; z-index:1`) y solo se muestra cuando hay animación. Sin `style=` ni JS.
- **Aceptación:** con el puntero encima, `getComputedStyle(pista).animationPlayState === "paused"`;
  al tabular al control, también; con el control marcado, también; a 390 px no hay animación, la fila
  se desplaza con el dedo y muestra dos tarjetas enteras; con `prefers-reduced-motion` igual que en táctil.
- **Tests:** actualizar `tests/test_cinta_integrantes.py`: el enlace sigue siendo uno (el label no es
  enlace), la copia lleva `aria-hidden`, y nueva prueba de que el CSS contiene el selector de pausa
  sobre `.cinta-caja` y el selector de hermanos del control; `test_la_cinta_se_detiene_con_prefers_reduced_motion`
  pasa a comprobar la media query de `hover`.
- **Estado:** hecho en dos tiempos. El paso 5 del plan corrigió la pausa, dejó la cinta quieta en táctil y
  añadió un icono de pausa. El dueño del sitio retiró el icono al verlo (2026-10-08): lo descrito arriba
  en el punto (4) ya no existe. Sin casilla que retenga el foco, la pausa por `:focus-within` volvió:
  es lo que alcanza quien navega con teclado. Verificado en navegador: en marcha con el puntero fuera,
  en pausa con el puntero encima y con el foco en «Conoce al colectivo», y ningún control en la caja.

#### 1.5 Buscador: overlay dentro del viewport y cierre al perder el foco
- **Hallazgos:** NAV-3, COM-5 (la colapsación en `<details>` va en 4.1).
- **Archivos:** `site.css` 66-71, 115-121; `templates/base.html` 52-62;
  `templates/content/partials/_search_results.html`; `templates/content/search.html`.
- **Pasos:** `.masthead .top{position:relative}` y `@media (max-width:719px){#search-results{left:0; right:auto; width:100%}}`;
  `.search:not(:focus-within):not(:hover) #search-results{display:none}`; en el parcial, cuando hay
  resultados, última fila «Ver todos los resultados →» a `/buscar/?q=…`; `minlength="2"` en el campo;
  `/buscar/` con `.index-head` del ticket 1.2, campo y botón `.btn`.
- **Aceptación:** a 390 px el overlay tiene `x ≥ 0` y `right ≤ 390`; tras `Tab` fuera del formulario
  el overlay no es visible; `/buscar/?q=casa` muestra cabecera de índice y resultados.
- **Tests:** `tests/test_ui_ux.py::test_search_results_is_live_overlay` sigue; añadir comprobación de
  la fila «Ver todos» en `tests/test_search.py`.
- **Estado:** hecho (paso 6 del plan). En móvil el campo ocupa la línea entera y el panel lo mismo que
  el campo, sin unidades `vw`. El enlace del panel dice «Abrir estos resultados en una página» y va
  fuera de la lista: «ver todos» prometía más de los diez que la página también muestra.

#### 1.6 Tokens de motion, radio y filete; hover por color; foco sobre la placa (D14)
- **Hallazgos:** COM-2 (parte), COM-4 (foco), COM-6, COL-11.
- **Archivos:** `site.css` `:root`, 70, 106, 111-113, 191-194, 256-259, 308-309, 415-417, 451, 491.
- **Pasos:** tokens `--r-1:3px; --dur-fast:140ms; --dur-base:220ms; --ease:cubic-bezier(.22,.61,.36,1); --line:#9fbfe0; --edge:#5e7ea7`;
  regla única `a, button, .btn, summary, .tag{transition:color var(--dur-fast) var(--ease), background-color var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease), text-decoration-color var(--dur-fast) var(--ease)}`;
  sustituir los tres hovers por opacidad por color sólido (`.btn-primary:hover{background:#96055a}`,
  8,5:1 con blanco) o inversión; enlaces: `text-decoration-thickness:1px` → `2px` al hover;
  foco sobre la placa azul en blanco (`.player-consent :focus-visible{outline-color:#fff}`, 4,84:1);
  bloque global `@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:.01ms!important; animation-duration:.01ms!important; animation-iteration-count:1!important}}`.
- **Aceptación:** `grep -c "opacity:.9\|opacity:.88\|opacity:.92" site.css` = 0; una sola regla
  `transition` global más la de la cinta; foco visible ≥ 3:1 sobre la placa.
- **Tests:** `test_css_sistema.py`: tokens presentes, sin hover por opacidad.
- **Estado:** hecho (paso 6 del plan). `--line` no se añadió: ningún componente lo usa todavía.

#### 1.7 Componentes `.rotulo` y `.btn` unificados (D3 parcial, D14)
- **Hallazgos:** TIP-10, COM-2, COM-9 (botón del formulario).
- **Archivos:** `site.css` (las quince reglas de rótulo: 75-77, 83-84, 124, 127, 132, 143, 152, 163,
  200, 350, 354, 360-361, 365, 391-392, 407, 488-489; y los cinco botones: 191-194, 256-259, 308-309,
  338-339, 415-417); plantillas que emiten `.btn`, `.kicker`, `.meta`, `.subhead`, `.muted`.
- **Pasos:** `.rotulo{font-family:var(--mono); font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted)}`
  y `.rotulo--acento{color:var(--accent)}`; `.meta{font-family:var(--mono); font-size:13px; text-transform:none; letter-spacing:0}`;
  `.kicker` pasa a ser alias de `.rotulo--acento` (mantener la clase en plantillas, cambiar la regla);
  `.btn{font-family:var(--display); font-weight:600; font-size:14px; text-transform:none; letter-spacing:0; min-height:44px; display:inline-flex; align-items:center; padding:0 18px; border-radius:var(--r-1)}`
  con `.btn--primary` (tinta sobre papel; hover papel sobre tinta) y `.btn--ghost` (borde 1 px tinta;
  hover inversión); `.btn-primary` existente se mantiene como alias de `.btn--primary` hasta 4.2;
  el botón de `.form` usa `.btn .btn--primary`.
- **Aceptación:** una sola receta de botón en el CSS; todos los botones miden ≥ 44 px de alto;
  `metrics.py` muestra ≤ 20 elementos en mayúsculas en la portada (≤ 15 tras 2.3, cuando la nav sale de la mono).
- **Tests:** `tests/test_ui_identity.py::test_titulo_de_tarjeta_usa_la_tipografia_de_titular` sigue;
  `test_css_sistema.py`: existe `.rotulo`, no quedan `text-transform:uppercase` fuera de `.rotulo` y `.nav-disclosure summary`.
- **Estado:** hecho (paso 6 del plan). El botón primario ya va en tinta (lo pedía 1.9) para no dejar el
  componente a medias. Quedan dos mayúsculas fuera de la receta, con fecha: `.nav a` (2.3) y
  `.form label` (1.11); la prueba las lista y falla si aparece una tercera.

#### 1.8 Preload de Syne, fallback métrico y peso 800
- **Hallazgos:** TIP-8, COM-10.
- **Archivos:** `templates/base.html` 36-41; `site.css` 23, 32-38, 59, 303.
- **Pasos:** `<link rel="preload" href="{% static 'fonts/syne.woff2' %}" as="font" type="font/woff2" crossorigin>`
  antes del CSS; `@font-face{font-family:"Syne Fallback"; src:local("Arial"); size-adjust:…; ascent-override:…; descent-override:…}`
  con valores calculados (fontaine o capsize con el woff2; el 114 % de la auditoría es orientativo:
  calcúlalo y anótalo en el CSS); `--display:"Syne","Syne Fallback",sans-serif`;
  `.brand, .hero-tagline{font-weight:800}`.
- **Aceptación:** con la woff2 bloqueada en DevTools, `.brand` y el titular de la portada miden lo
  mismo que con Syne ± 2 %; sin salto visible al cargar.
- **Tests:** `tests/test_ui_identity.py::test_css_declares_self_hosted_display_font` sigue;
  añadir: `base.html` contiene el preload de la fuente que el CSS declara.
- **Estado:** hecho (paso 6 del plan), salvo el peso 800, que NO se aplica. Medido: el 800 de Syne es un
  corte extendido, un 44 % más ancho que el 700; el nombre del sitio pasaría de 292 a 420 px y no cabría
  en un móvil. Se decide en 4.2, con el titular nuevo a la vista. La reserva son tres caras de Arial
  escaladas al 102, 103 y 114,1 %; con el archivo bloqueado, marca, titular y títulos varían menos de un 2 %.

#### 1.9 Reasignación del magenta y matriz de pares de contraste (D5 parcial)
- **Hallazgos:** COL-1, COL-10, COL-6 (pares), COM-8 (paginación inactiva).
- **Archivos:** `site.css` 44, 83-85, 132-134, 163, 171, 191-194, 215, 288, 308, 399-402;
  `tests/test_contraste_paleta.py` (`PARES`, línea 59).
- **Pasos:** `a{color:var(--ink); text-decoration-color:var(--accent); text-underline-offset:3px}`;
  `.nav a`, `.member-role`, `.year-mark`, bordes de `.poetics` y `.press-quote` a tinta o muted;
  `--accent` queda en: marca/glifo, `.rotulo--acento`, estados activo y foco; `.btn--primary` en tinta;
  `--accent-on-ink:#f77cc3` y `--riso-amarillo:#fce43c` en `:root` (todavía sin uso de superficie:
  eso es 3.2); paginación inactiva en `--muted`, no en `--border`.
  En la prueba: añadir pares permitidos (ink/riso-amarillo ≥ 4,5; accent/riso-amarillo ≥ 4,5;
  paper/ink ≥ 4,5; accent-on-ink/ink ≥ 4,5; edge/paper ≥ 3) y una prueba de **pares prohibidos**
  (accent/ink, caratula/paper como texto normal, muted/caratula) que falle si alguno aparece como
  par frente/fondo en el CSS.
- **Aceptación:** `grep -c "color:var(--accent)" site.css` ≤ 6; todos los pares en verde; el
  comentario de `:root` documenta el reparto.
- **Tests:** `test_contraste_paleta.py` ampliado como se indica.
- **Estado:** hecho (paso 7 del plan). El criterio «≤ 6 usos de `color:var(--accent)`» era irreal: los
  estados (`:hover`, foco, marcado) también lo usan y son legítimos. La regla que se prueba es otra y
  más útil: el magenta solo es color de texto EN REPOSO en la cejilla y en el asterisco de campo
  obligatorio. Los «pares prohibidos» se prueban de dos formas: una tabla con su número, y una
  comprobación de toda regla que declare texto y fondo a la vez. Diez reglas `:hover` de títulos pasan
  a una sola (subrayado magenta). Se retiran doce reglas de seis clases que ninguna plantilla emite.

#### 1.10 Paginación con contador, números y objetivos de 44 px
- **Hallazgos:** CON-10, COM-8.
- **Archivos:** nuevo `templates/content/partials/_pagination.html`; `_poem_list.html`,
  `_article_list.html`, `media/recording_index.html`; `site.css` 395-402.
- **Pasos:** un parcial que recibe `page_obj` y usa `paginator.get_elided_page_range(number, on_each_side=1, on_ends=1)`;
  «1-12 de 38 poemas» (`start_index`/`end_index`/`count`), `aria-current="page"`, `rel="prev"`/`rel="next"`,
  cajas de 44 px, inactivo con `aria-disabled="true"` en muted.
- **Aceptación:** con 13 ítems sembrados en una fixture, aparece «1-12 de 13», dos páginas y
  `aria-current`; cada objetivo mide ≥ 44 × 44.
- **Tests:** `tests/test_home_ui.py::test_text_archive_paginates_full_list` sigue; añadir prueba del
  parcial (contador y `rel`).
- **Estado:** hecho (paso 8 del plan). El rango con elipsis lo da una etiqueta de plantilla,
  `rango_paginas`, porque una plantilla no puede pasar argumentos a `get_elided_page_range`.

#### 1.11 Formulario de envío
- **Hallazgos:** COM-9.
- **Archivos:** `templates/submissions/submit.html`; `apps/submissions/forms.py`; `site.css` 404-417.
- **Pasos:** etiquetas 14 px en caja de frase y tinta; leyenda «* obligatorio» antes del primer
  campo; `autocomplete="name"` y `"email"` en los widgets del formulario; `aria-describedby` que
  enlace ayuda y error de cada campo (Django 5.2 ofrece `as_field_group` y `field.id_for_label`);
  textarea `min-height:220px`; botón `.btn .btn--primary`; mantener `novalidate` solo si los errores
  del servidor se muestran enlazados.
- **Aceptación:** HTML servido con `autocomplete` en nombre y correo; cada campo con ayuda o error
  lleva `aria-describedby` resuelto; `tests/test_ui_ux.py::test_submit_file_help_aria_reference_resolves` sigue.
- **Tests:** ampliar `tests/test_submissions.py` con los atributos.
- **Estado:** hecho (paso 8 del plan). El hallazgo era más grave de lo que decía la auditoría: Django
  5.2 marca cada campo inválido con `aria-describedby="<id>_error"` y la plantilla pintaba los errores
  sin ese id, así que TODA referencia apuntaba a nada. Ahora cada error vive en un contenedor con su id.

#### 1.12 Lenguaje, cejillas y títulos de pestaña
- **Hallazgos:** POR-12, NAV-10, NAV-12, POR-5 (etiquetas).
- **Archivos:** `apps/content/models.py` (`Article.kicker()`), `_article_card.html`,
  `article_detail.html`, `base.html` (72, 120-136), `submissions/submit.html`,
  `submit_thanks.html`, y las diez plantillas con sufijo «Reseñas» en `<title>`
  (`article_detail`, `contributor_detail`, `section_detail`, `tag_detail`, `page_detail`, `submit`,
  `submit_thanks`, `reviews/publisher_detail`, `bookauthor_detail`, `work_detail`).
- **Pasos:** `Article.kicker()` devuelve «Reseña · 4 min» (tipo + tiempo) o «Sección · Tipo» solo
  si difieren; títulos de pestaña con `{{ site_profile.name|default:"Reseñas" }}`; «Enviar una
  propuesta» en pie, cejilla y h1; descriptores bajo cada h1 de índice (ya previstos en 1.2);
  «Conócenos →» del hero a `/integrantes/`; etiqueta del CTA de dossier según estado («Ver el
  dossier» si no hay PDF; «Descargar dossier (PDF)» si lo hay).
- **Aceptación:** ninguna cejilla repite palabra («RESEÑAS · RESEÑA» desaparece); `<title>` de
  todas las rutas públicas termina en el nombre del sitio.
- **Tests:** `tests/test_indices.py`: ninguna plantilla cierra su `<title>` con el nombre fijo, y la
  cejilla de la tarjeta según sección y tipo. `tests/test_dossier.py`: el rótulo del botón por estado.
- **Estado:** hecho (paso 4 del plan). En vez de `Article.kicker()` hay una propiedad
  `Article.seccion_aporta`: la plantilla necesita el enlace a la sección, no una cadena. Cuando la
  sección repite al tipo, el tipo enlaza a la sección. La cejilla de `/enviar/` («Colaboraciones») se
  conserva: lo que se unificó es el rótulo del enlace del pie con el h1 de la página.

#### 1.13 Estados vacíos y fallbacks tipográficos
- **Hallazgos:** CON-9, IMG-10, ESP-12 (parte).
- **Archivos:** `apps/agenda/views.py`, `templates/agenda/agenda.html`, `gallery.html`,
  `showcase/partner_index.html`, `_publication_card.html`; `site.css` 146, 166-167, 278-279.
- **Pasos:** agenda sin futuros: `recientes = Event.past()[:3]` + texto «Sin fechas anunciadas.
  La última lectura fue …» + botones «Escríbenos» (mailto con fallback a `general_email`) y
  «Ver el dossier»; galería y aliados vacíos con una frase y un enlace; cubierta sin imagen como
  sobrecubierta tipográfica (5:7, papel, filete superior magenta de 6 px, título en Syne 20 px),
  nunca la palabra «LIBRO»; avatar sin foto como monograma de dos letras en Syne 700 (sin círculo:
  cuadrado o 4:5), preparando 3.6.
- **Aceptación:** `/agenda/` sin eventos futuros mide > 900 px y muestra tres pasados y dos
  botones; el fallback de cubierta no contiene el nombre del tipo.
- **Tests:** `tests/test_agenda.py`: agenda vacía muestra pasados; presupuesto de consultas de
  `test_performance.py` intacto.
- **Estado:** hecho (paso 8 del plan). El monograma conserva por ahora el círculo del avatar; la forma
  4:5 llega con los retratos en 3.6. Una actividad ya realizada deja de ofrecer «Inscripción / entradas».

### Épica 2 — Retícula y tipografía (D3, D4, D7)

Secuencial. Es el lote que resuelve «no usa el espacio».

#### 2.1 Retícula de tres carriles y escala raíz fluida
- **Hallazgos:** ESP-1, ESP-5, ESP-6, ESP-7, ESP-8, ESP-12.
- **Archivos:** `templates/base.html` 46, 68, 87, 92; `site.css` 40-43, 57-58, 91-101, 302-324,
  356-359, 449-474; `tests/test_ui_ux.py`, `tests/test_nav_css.py`.
- **Pasos:** en `:root`: `--measure:51.25rem; --wide:82.5rem; --gutter:clamp(20px,4vw,64px)` y
  `@media (min-width:1600px){:root{--wide:90rem}}`; `html{font-size:clamp(100%, .875rem + .25vw, 118.75%)}`;
  `<main id="main">` sin `.wrap` y con la rejilla de líneas con nombre de la auditoría §4.1
  (`[full-start] … [wide-start] … [content-start] … [content-end] … [wide-end] … [full-end]`),
  `main > *{grid-column:content}`; utilidades `.ancho{grid-column:wide}` y `.sangre{grid-column:full}`;
  `.band` pasa a `grid-column:full; display:grid; grid-template-columns:subgrid` y pierde el truco de
  `box-shadow:0 0 0 100vmax` + `clip-path`; nueva `.wrap-wide{max-width:var(--wide); margin-inline:auto; padding-inline:var(--gutter)}`
  para cabecera, nav y pie; tokens de espacio `--s1:8px … --s7:144px`;
  `.home-block{padding-block:clamp(56px,7vw,112px)}`; `.site-foot{margin-top:var(--s6)}`;
  la cinta a `.sangre` con máscaras de 96 px. Nunca `100vw`.
- **Aceptación:** `metrics.py` a 1440: ratio ≥ 0,85 en portada e índices, ≥ 0,80 en fichas,
  lectura (`.poem-body`, `.article .body`) entre 780 y 964 px; a 1920: ≥ 0,65 en índices; sin scroll
  horizontal a 320; la cinta muestra 5 tarjetas a 1440.
- **Tests:** `tests/test_ui_ux.py` (si afirma `.wrap` en `<main>`, pasa a afirmar `id="main"` y la
  rejilla); `test_nav_css.py` sigue; `test_css_sistema.py`: existe `grid-template-columns:[full-start]`
  y no existe `100vw`.

#### 2.2 Índices como filas tipográficas y rejillas en el carril ancho
- **Hallazgos:** ESP-4, ESP-5, IMG-6, CON-5, IMG-9 (parte), COM-7 (filas de poemas y textos).
- **Archivos:** `_article_card.html`, `_poem_card.html`, `_event_card.html`, `media/recording_index.html`,
  `people/member_index.html`, `showcase/publication_index.html`, `agenda/gallery.html`;
  `site.css` 129-131, 157-159, 195-198, 220-223, 263-266, 273-277.
- **Pasos:** Poemas, Textos, Trayectoria y Prensa: `.fila{display:grid; grid-template-columns:12ch minmax(0,1fr) auto; column-gap:24px; min-height:64px; align-items:baseline; border-top:1px solid color-mix(in srgb, var(--ink) 22%, transparent)}`
  con fecha en `.meta` a la izquierda, título en Syne 26 px, autor y «♫ con registro» a la derecha;
  en Poemas el primer verso en serif cursiva bajo el título (usa `poem.body|truncatechars` de la
  primera línea; sin consultas nuevas). Toda la fila es enlace (enlace extendido con `::after`
  sobre el título; autor y sección por encima con `z-index:1; padding:6px 0; margin:-6px 0`) y
  cambia de fondo a `--paper-2` al hover y al `:focus-within`. Integrantes: `.member-grid{grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}`
  en `.ancho` (4-5 columnas a 1440). Publicaciones: `minmax(220px,1fr)`, cubierta-objeto con sombra
  plana `8px 8px 0 var(--line)`. Registros: rejilla `minmax(380px,1fr)` de tarjetas con miniatura
  16:9 (póster o carátula tipográfica del ticket 3.4) + título + meta; el reproductor solo en el
  detalle. Agenda: dos columnas. Galería: hoja de contactos `2fr 1fr` con filas 3:2.
- **Aceptación:** `/poemas/` con 12 poemas sembrados muestra ≥ 10 por pantalla a 1440; `/registros/`
  con 2 registros cabe en una pantalla; cubiertas ≥ 240 px; `metrics.py` ratio ≥ 0,85 en los cuatro índices.
- **Tests:** `tests/test_ui_ux.py::test_article_card_title_is_h3` sigue; `tests/test_recordings.py`:
  el índice no emite `player-consent` (sí el detalle); `tests/test_embed_consent.py` sigue.

#### 2.3 Serif autoalojada, escala tipográfica con tokens y mono reducida (D3, D4)
- **Hallazgos:** TIP-2, TIP-3, TIP-5, TIP-6, TIP-7 (medida), D3, D4.
- **Archivos:** `backend/static/fonts/` (+ `SourceSerif4-Roman-latin.woff2`, `SourceSerif4-Italic-latin.woff2`,
  `NOTICE.txt`), `site.css` 16-38, 46-54, 82-84, 127, 143, 162-163, 177-179, 188-189, 206-208,
  314-317, 360-365, 420-421; `templates/base.html` (preload); `NOTICE.md` del repo.
- **Pasos:** (1) Obtener Source Serif 4 variable (OFL 1.1) de la release oficial de Adobe Fonts
  en GitHub; subconjunto latino con `pyftsubset` (fonttools + brotli en un entorno local, **no** en
  requirements): `--unicodes="U+0000-00FF,U+0100-017F,U+2000-206F,U+20AC,U+2190-2199,U+2600-26FF"`
  `--layout-features="kern,liga,onum,pnum,tnum"` `--flavor=woff2`. Anotar comando, versión y licencia
  en `fonts/NOTICE.txt`. (2) `@font-face` romana e itálica con `font-display:swap`, eje `wght 200 900`
  y `opsz`, y «Source Serif Fallback» con `size-adjust`/overrides calculados sobre Georgia;
  `--serif:"Source Serif 4","Source Serif Fallback",Georgia,serif`. (3) Escala en `:root`:
  `--t-1:12px; --t0:14px; --t1:16px; --t2:19px; --t3:22px; --t4:26px; --t5:32px; --t6:clamp(34px,4.6vw,56px); --t7:clamp(44px,7.5vw,148px)`;
  interlíneas `.92/1.08/1.35/1.55/1.5`; trackings `.1em/.02em/-.015em`; sustituir los 24 `font-size`
  sueltos por tokens. (4) Mono solo en `.rotulo` y `.meta`: `.nav a{font-family:var(--display); font-weight:500; font-size:15px; text-transform:none}`;
  pie en serif 15 px con `.foot-group h2` como `.rotulo`; cifras en Syne con `font-variant-numeric:tabular-nums`;
  `.subhead` → fila `.rotulo` + h2 Syne `clamp(28px,3vw,40px)` **acotado** a `.home-block` e índices
  (el dossier espera a 5.1). (5) Poema: `.poem-body{font-size:20px; line-height:1.5; max-width:40ch; width:fit-content; margin-inline:auto}`;
  salto entre estrofas de 60 px.
- **Aceptación:** `metrics.py`: la familia del párrafo es «Source Serif 4» en todas las páginas;
  portada ≤ 30 % de elementos en mono y ≤ 15 en mayúsculas; peso total de `static/fonts/*.woff2`
  ≤ 200 KB (si Syne lo impide, subconjuntar Syne también); h2 de sección ≥ cuerpo; sin `font-size`
  fuera de tokens salvo `.rotulo`/`.meta`.
- **Tests:** `tests/test_ui_identity.py::test_no_hay_fuentes_huerfanas` y
  `test_font_file_is_bundled` actualizados a los tres archivos; `tests/test_vendored_assets.py`
  (licencias) con la entrada nueva; `test_css_sistema.py`: existe `--t2` y `"Source Serif 4"`.

#### 2.4 Sala de lectura y fichas a dos columnas
- **Hallazgos:** ESP-9, CON-3 (paso 2), TIP-7 (sangría), CON-4, IMG-7, NAV-9 (pie de entidad).
- **Archivos:** `poem_detail.html`, `article_detail.html`, `people/member_detail.html`,
  `showcase/publication_detail.html`, `agenda/event_detail.html`, `media/recording_detail.html`;
  nuevo `templates/content/partials/_pie_de_entidad.html`; nuevo filtro `versos` en
  `apps/content/templatetags/`; `site.css`.
- **Pasos:** `.lectura{display:grid; grid-template-columns:minmax(240px,1fr) minmax(0,66ch); column-gap:var(--s5)}`
  en `.ancho`, con columna-ancla `position:sticky; top:80px` (cejilla como miga «Poemas», h1,
  epígrafe, autora con avatar de 56 px, fecha, «Escuchar en el registro →» interno con `<audio>`
  nativo cuando `rec.file`, etiquetas) y cuerpo a 66ch; el poema con sangría francesa: filtro
  `versos` que escapa cada línea y la envuelve en `<span class="verso">` (`display:block; text-indent:-1.5em; padding-left:1.5em`),
  devolviendo `mark_safe` solo tras escapar. Artículo: `<figure>` 3:2 con `cover_image` entre meta y
  cuerpo cuando exista; `.reviewed` como ficha con `Work.cover_image` a 140 px. Fichas de integrante,
  publicación y evento: `.ficha-head{display:grid; grid-template-columns:minmax(200px,320px) 1fr}`
  con el medio a la izquierda (retrato 4:5, cubierta 5:7 a 360, afiche) y cabecera al lado.
  `_pie_de_entidad.html`: «← Todos los poemas» y «Más de {autora}» (o equivalentes por entidad).
  Poema: el enlace al registro apunta a `rec.get_absolute_url` (interno), no a YouTube.
- **Aceptación:** a 1920, ratio ≥ 0,60 en poema y artículo; cuerpo del artículo 60-75 cpl; cada
  detalle con ≥ 4 enlaces internos en `<main>`; el poema conserva versos, sangrías y espacios
  (comparar `innerText` del cuerpo antes/después).
- **Tests:** `tests/test_poems.py`: el filtro `versos` escapa HTML (`<script>` no se renderiza) y
  conserva saltos; `tests/test_poem_recording_visibility.py` sigue; `test_article_detail_query_budget`
  (≤ 12) intacto con `select_related("cover_image")`.

### Épica 3 — Color, imagen y dirección de arte (D5, D6, D10)

#### 3.1 Cuatro superficies, bandas de tinta y firma por territorio (D6)
- **Hallazgos:** COL-4, COL-8, POR-13, ESP-10 (parte).
- **Archivos:** `site.css` `:root`, 183-189 (`.featured-poem` es CSS muerto: borrar), 197-198, 210,
  219, 346, 367-368, 387, 419-421; `home.html`; `base.html` (pie).
- **Pasos:** `--paper-2:#eef4fb`; clases `.band--papel2` y `.band--tinta` (fondo `--ink`, color
  `--paper`, enlaces `--accent-on-ink`, foco en papel); quitar fondo blanco y borde de `.next-event`,
  `.milestone`, `.event-date`, `.dossier-contact`, `.reviewed` (pasan a `--paper-2` sin borde);
  `--surface` solo en campos y objetos; alternancia estricta papel / papel-2 / tinta en la portada
  (el orden definitivo lo fija 4.3); pie en tinta; firma por territorio: regla de 3 px bajo el h1 de
  índice (`La obra` magenta, `El colectivo` azul, `Prensa y gestión` tinta).
- **Aceptación:** ≤ 2 bandas de tinta por página; ningún texto sobre tinta por debajo de 4,5:1;
  no quedan cajas blancas con borde de 1 px sobre papel; la franja celeste vacía de ≈ 42 px antes
  del pie desaparece.
- **Tests:** pares (paper/ink, accent-on-ink/ink) ya en `test_contraste_paleta.py` desde 1.9.

#### 3.2 Amarillo como superficie (D5)
- **Hallazgos:** COL-6, POR-9 (parte).
- **Archivos:** `site.css` 310-317; `home.html` (cifras); `submissions` (sticker de convocatoria).
- **Pasos:** `.hero-stats{background:var(--riso-amarillo); color:var(--ink); padding:var(--s3) var(--s4)}`
  (un plano por viewport); sticker estático «Convocatoria abierta hasta el …» (SVG en línea con
  `rotate(-3deg)`, sin animación) en el hero cuando exista un `Call` abierto; nada de amarillo como texto.
- **Aceptación:** el amarillo aparece como fondo en un solo plano por pantalla; los pares están en
  la prueba (1.9).

#### 3.3 Duotono risográfico y tratamiento de casa
- **Hallazgos:** COL-7, IMG-5, COL-9 (parte).
- **Archivos:** `site.css`; `_member_card.html`, `_member_card_cinta.html`, `_event_card.html`,
  `gallery.html`, `_player.html`; `config/csp.py` (solo para **comprobar** `img-src data:`; no relajar).
- **Pasos:** `.riso-duo{display:block; background:var(--accent); isolation:isolate; overflow:hidden}`
  `.riso-duo img{filter:grayscale(1) contrast(1.15) brightness(1.05); mix-blend-mode:multiply}`,
  variante `.riso-duo--azul{background:var(--caratula)}`; al pasar o enfocar, `filter:none; mix-blend-mode:normal`
  (ambas, o el color se multiplica sobre el magenta); aplicar a retratos en listados y cinta, fotos
  de evento en listados, póster del reproductor; **excluir** cubiertas, afiches de terceros, logos
  de aliados, y la ficha de integrante y el detalle de evento (original). Grano opcional con
  `feTurbulence` en un `data:` URI solo si `img-src` lo admite; si no, omitir.
- **Aceptación:** una tinta por pantalla (magenta o azul); hover revela el original; las cubiertas
  no llevan tratamiento.
- **Tests:** `test_css_sistema.py`: `.riso-duo` existe; `tests/test_security_csp.py` sigue.

#### 3.4 Reproductor: póster o carátula tipográfica, botón y foco (D10)
- **Hallazgos:** IMG-2, COL-3, COM-4, POR-7, CON-5.
- **Archivos:** `templates/media/partials/_player.html`; `site.css` 241-262; `static/js/embeds.js`
  (solo leerlo: al pulsar vacía el contenedor, así que el póster desaparece solo).
- **Pasos:** dentro de `.player-consent`, `{% if r.poster %}{% responsive_img r.poster css_class="player-poster riso-duo--azul" sizes="(max-width:800px) 100vw, 880px" lazy=False alt="" %}{% endif %}`
  en posición absoluta cubriendo la placa; si no hay póster, carátula tipográfica: título en Syne
  `clamp(24px,3vw,44px)` en papel sobre azul + meta «Video · Recital · 2026» en `.rotulo`; botón
  `.embed-play` circular de 64 px blanco con «▶», en panel sólido abajo-izquierda junto al aviso de
  privacidad (sin velo del 35 %); foco en blanco; audio con póster 1:1 cuando exista; variante
  miniatura para índices (sin botón, enlaza al detalle).
- **Aceptación:** ninguna placa azul vacía en todo el sitio; texto sobre la placa ≥ 4,5:1; foco
  ≥ 3:1; al pulsar «Reproducir» el iframe reemplaza la placa (click-to-play intacto);
  `tests/test_embed_consent.py` en verde.

#### 3.5 Las imágenes del modelo llegan a pantalla
- **Hallazgos:** IMG-7, IMG-8, IMG-9, IMG-12.
- **Archivos:** `_article_card.html`, `article_detail.html`, `_event_card.html`, `home.html`
  («Próxima actividad»), `agenda/trayectoria.html`, `event_detail.html`, `gallery.html`,
  `showcase/partner_index.html`, vistas correspondientes (`select_related`/`prefetch_related`).
- **Pasos:** miniatura 3:4 a la derecha en la fila de Textos cuando `cover_image`; `Event.poster`
  en tarjetas de agenda (64px / 128px / 1fr), en «Próxima actividad» y como miniatura en trayectoria;
  galería y lightbox con `MediaAsset.credit` y `caption` en `figcaption` (13-14 px, ≥ 4,5:1) y
  contador «3 / 12»; aliados con logo 160×80 en gris que pasa a color al hover, agrupados por tipo,
  y franja «Con el apoyo de» reutilizable (la usa 4.2).
- **Aceptación:** con la demo sembrada con `cover_image`, `poster` y `logo` (ampliar `seed_demo`
  solo en lo que haga falta y sin tocar la identidad), cada pieza aparece donde se indica;
  presupuestos de `test_performance.py` intactos (`content:home` ≤ 24).
- **Tests:** `tests/test_seed_photos.py` y `tests/test_images.py` ampliados; nuevo test de que el
  crédito se muestra cuando existe.

#### 3.6 Retratos 4:5 y monograma
- **Hallazgos:** IMG-4, COL-5.
- **Archivos:** `_member_card.html`, `_member_card_cinta.html`, `member_detail.html`,
  `dossier.html` (avatar 96); `site.css` 157-169, 474-480.
- **Pasos:** `.member-card img{width:100%; aspect-ratio:4/5; object-fit:cover; border-radius:0}`
  (≈ 245-287 px en rejilla), cinta 160×200, ficha 240×300; nombre Syne 20-24 px; rol `.rotulo`;
  toda la tarjeta es enlace (enlace extendido con `::after`, secundarios con `z-index:1`); fallback
  monograma de dos letras en Syne 700 a 56 px sobre `--paper-2`, 4:5, nunca círculo.
- **Aceptación:** en `/integrantes/` el rostro ocupa ≥ 60 % de la tarjeta; sin `border-radius:50%`
  en el CSS; `tests/test_cinta_integrantes.py` sigue (la cinta no añade enlaces por tarjeta).

#### 3.7 Glifo, favicon, theme-color y og_image
- **Hallazgos:** COL-2.
- **Archivos:** `base.html` (`<head>` y `.brand`); `static/img/favicon-32.png`, `favicon-180.png`,
  `favicon.ico`; nuevo `tools/ux/make_icons.py` (Pillow, ya instalado por `ImageField`).
- **Pasos:** glifo de dos tintas como `<svg>` **en línea** en `.brand` (28-32 px): dos formas simples
  solapadas en `--accent` y `--caratula` con `mix-blend-mode:multiply` y 1-2 px de desregistro, con
  `aria-hidden="true"` y el nombre en Syne sin fondo (el sello magenta desaparece; `.btn--primary` ya
  no comparte receta con la marca); `make_icons.py` dibuja el mismo glifo a 32/180/48 px en PNG/ICO
  (sin `.svg` en `static/`); `<link rel="icon">` × 2 y `<meta name="theme-color" content="#d9e8f7">`;
  `make_icons.py --og` genera una tarjeta tipográfica 1200×630 para subir como `og_image` desde el
  panel (tarea de contenido; el ticket deja el archivo en `tools/ux/out/og-card.png` y lo documenta).
- **Aceptación:** `tests/test_security_csp.py` en verde (no hay `.svg` en `static/`); la pestaña
  muestra el icono; `grep -c "<svg" templates/base.html` ≥ 1; el nombre en la cabecera no lleva fondo.
- **Tests:** `tests/test_ui_identity.py::test_css_declares_self_hosted_display_font` sigue;
  `test_contraste_del_sello_de_la_cabecera` se adapta (ya no hay sello: afirmar tinta sobre papel).

### Épica 4 — Cabecera, portada y navegación (D2, D8, D9)

#### 4.1 Cabecera de una fila, sticky, con CTA, buscador colapsado y `aria-current`
- **Hallazgos:** NAV-1, NAV-2, NAV-4, NAV-5, NAV-6, NAV-7, D2, D9.
- **Archivos:** `base.html` 45-77; nuevo `templates/partials/_mapa.html` (los cuatro grupos del pie,
  reutilizado en el menú móvil); `site.css` 56-101, 115-121; `config/` (context processor que ya
  inyecta `site_profile`: añadir `nav_actual` a partir de `request.resolver_match.namespace`);
  `tests/test_ia.py`, `tests/test_nav_css.py`, `tests/test_ui_identity.py::test_nav_links_intact_in_disclosure`.
- **Pasos:** `.masthead{position:sticky; top:0; z-index:100; background:var(--paper); min-height:64px}`
  con `.wrap-wide` y una fila: glifo + nombre (Syne 22) · nav de cinco (`NAV_PRINCIPAL` =
  `content:poem_index, content:text_archive, media:recording_index, showcase:publication_index, people:member_index`,
  rótulos «Poemas · Textos · Registros · Publicaciones · Colectivo») · `<details class="busqueda">` con
  `<summary>` de lupa (SVG en línea, 44 px, nombre accesible «Buscar») que despliega el formulario
  htmx actual · `.btn .btn--primary` «Dossier» a `/dossier/#contacto`. ≤ 720 px: fila de 56 px con
  `<details>` «Menú» (summary de 44 px en tinta) que contiene `_mapa.html` con enlaces en bloque de
  16 px y `padding:12px 0`. `aria-current="page"` en el enlace del namespace activo con subrayado de
  2 px. En `/integrantes/`, sub-fila del territorio (Trayectoria · Agenda · Galería · Prensa · Aliados)
  dentro de `_index_head.html` (slot `subnav`).
- **Aceptación:** cromo ≤ 64 px en escritorio y ≤ 56 px en móvil cerrado; `/textos/` y el dossier
  a un clic desde cualquier página; `aria-current` presente en cada página; con JS apagado, la lupa
  abre el campo y el submit lleva a `/buscar/`; el overlay htmx sigue funcionando dentro del panel.
- **Tests:** `test_ia.py`: `NAV_PRINCIPAL` con cinco y la aserción exacta de conteo intacta; los
  nueve que «salieron de la barra» siguen alcanzables (dossier ahora por el CTA); `test_nav_css.py`:
  reglas de `::details-content` conservadas para el menú móvil y la búsqueda; `test_ui_identity.py`:
  nav intacta dentro del `<details>` móvil; nuevo test de `aria-current`.

#### 4.2 Hero con el nombre, objeto real, ficha, cifras y línea de respaldo (D8, D9)
- **Hallazgos:** POR-1, POR-2, POR-5, POR-8, POR-9, ESP-3, IMG-3, NAV-2.
- **Archivos:** `home.html` 4-29; `apps/content/views.py::home`; `site.css` 298-317;
  `tests/test_home_ui.py::test_home_hero_has_manifesto_and_stats`,
  `tests/test_ui_identity.py` (cifras), `tests/test_catalog.py::test_home_shows_catalog_but_not_press_or_partners`,
  `tests/test_ui_ux.py::test_home_has_an_h1`.
- **Pasos:** `.hero{grid-column:wide; display:grid; grid-template-columns:minmax(0,7fr) minmax(0,5fr); column-gap:clamp(32px,6vw,96px); align-items:end; min-height:min(78vh,760px)}`.
  Columna izquierda: cejilla `.rotulo` «Colectivo de poesía · Chile · desde 2023 · 12 integrantes ·
  @repitentesdelverso» (datos de `site_profile` y un `members_count` calculado en la vista con
  `Contributor.members().count()`, no `members|length` que está acotado a 16); h1 visible
  «Repitentes del Verso» en Syne 800 `var(--t7)` (se retira el `h1.sr-only`); manifiesto a 54ch;
  CTAs: `.btn--primary` «Ver el dossier» / «Descargar dossier (PDF)» según `dossier_pdf`, y
  `.btn--ghost` «Escríbenos» con `booking_email` y fallback `general_email` (el mismo que usa el pie).
  Cifras sobre amarillo (3.2): «12 integrantes · 4 actividades · 1 festival · 3 publicaciones», cada
  `<strong>` enlazado a su prueba (`/integrantes/`, `/trayectoria/`, `/publicaciones/`), etiqueta por
  tipo de evento; si una cifra es < 3, mostrar nombres en vez de número. Columna derecha: un objeto
  real elegido en la vista (`hero_object`, prioridad: póster del registro destacado > última cubierta
  publicada > afiche del próximo evento > `og_image` > nada), 5:7 o 16:9 según el objeto, con
  `rotate(-2deg)` y sombra plana, `lazy=False` y `width/height` (LCP); sin objeto, la columna se
  colapsa y el titular ocupa todo. Debajo: línea de respaldo (última `PressMention` con `quote` en
  cursiva + «Con el apoyo de» con los nombres o logos de `Partner`), dos consultas.
  En móvil, el orden es titular → manifiesto → CTAs → objeto → cifras.
- **Aceptación:** `mediaInFirstViewport ≥ 1` a 1440, 1920 y 390 con la demo; h1 ≥ 112 px a 1920;
  un solo `.btn--primary` en el primer viewport; `content:home` ≤ 24 consultas; el correo del hero
  coincide con el del pie.
- **Tests:** `test_home_hero_has_manifesto_and_stats` adaptado (manifiesto, cifras, nombre como h1);
  `test_home_shows_catalog_but_not_press_or_partners` **invertido**: la portada muestra la cita y el
  aliado en la línea de respaldo (renombrar la prueba y documentar D9); `test_ui_identity.py`: la
  cifra grande sigue acotada a `.hero-stats` y `.dossier-doc` (5.1); `test_home_has_an_h1` sigue.

#### 4.3 Orden y bloques de la portada
- **Hallazgos:** POR-3, POR-6, POR-10, POR-11, POR-13, NAV-11, ESP-10, COL-8.
- **Archivos:** `home.html` 31-137; `apps/content/views.py::home` (+ `poems`, `last_event`,
  `updated_at`); `site.css` 319-335; `tests/test_home_ui.py::test_home_members_appear_before_texts`.
- **Pasos:** orden: hero (papel) → destacado (`.band--tinta`, grid 8/4: reproductor con póster o
  carátula a la izquierda, ficha «01 / 05 · Recital «Nuevas voces» · fecha · ciudad · participantes ·
  resumen · Todos los registros →» a la derecha) → **Poemas** (papel: 3 poemas publicados más
  recientes como filas tipográficas con cejilla, título Syne 32 y los tres primeros versos vía filtro
  `primeros_versos`, +1 consulta) → Integrantes (`.band--papel2`: h2 con cifra «12 voces», cinta a
  sangre de retratos 4:5, 5 visibles) → Textos (papel: 3 ítems con `Article.kicker()`; miniatura 3:4
  cuando hay `cover_image`) → Publicaciones (`.band--papel2`: 4 cubiertas-objeto) → cierre
  «Para programadores y jurados» (`.band--tinta`: cuatro puertas Dossier · Prensa · Aliados ·
  Escríbenos, última actividad `Event.past().first()` y «Actualizado el {fecha}» calculado en la
  vista como el máximo `published_at`/`updated_at` entre poemas, textos y registros) → pie en tinta.
  `.subhead` de portada → fila `.rotulo` + h2 Syne (D13). Alternancia estricta de superficies; sin
  franja vacía antes del pie.
- **Aceptación:** la portada mide ≤ 3300 px a 1440 con la demo; ≥ 3 versos visibles; integrantes
  antes que textos (test existente); `content:home` ≤ 24 consultas (medido hoy 16; añade ≤ 5);
  alternancia papel / tinta / papel / papel-2 / papel / papel-2 / tinta.
- **Tests:** `test_home_members_appear_before_texts` sigue; `test_home_caps_articles_and_links_to_archive`
  adaptado a 3 textos; nuevo test de que la portada emite tres poemas y la fecha de actualización;
  `test_performance.py` intacto.

#### 4.4 Pie en tinta con identidad y mapa
- **Hallazgos:** NAV-8, COL-8.
- **Archivos:** `base.html` 91-161; `_mapa.html` (4.1); `site.css` 348-369, 419-421.
- **Pasos:** orden: identidad (glifo + nombre + «Chile · desde 2023» + correo **como enlace**
  subrayado + Instagram) → cuatro grupos (`_mapa.html`, rótulos iguales a los h1 de destino) →
  newsletter en una línea (etiqueta, campo, botón `.btn--ghost`, consentimiento debajo) → legal.
  `.foot-group a{font-size:15px; padding:4px 0; display:inline-block}` (paso ≥ 28 px); fondo
  `--ink`, texto `--paper`, enlaces `--accent-on-ink` al hover. El verso de cierre queda como bloque
  opcional que solo se renderiza si `site_profile.manifesto` tiene contenido y se decide usar su
  primera frase; si no, se omite (depende de contenido).
- **Aceptación:** objetivos del pie ≥ 28 px de paso vertical; contraste de todos los textos del
  pie ≥ 4,5:1; `tests/test_newsletter*.py` siguen (el formulario no cambia de campos ni de honeypot).

#### 4.5 Enlaces cruzados entre entidades
- **Hallazgos:** NAV-9 (lo que no cubrió 2.4).
- **Archivos:** `member_detail.html` (+ «Actividades» con `Event.participants` reverse),
  `publication_detail.html` (+ «Reseñas sobre esta publicación» solo si existe una relación en el
  modelo; si no existe, omitir y anotar en deferidos), `recording_detail.html` (+ «Poema registrado»
  por la FK inversa de `Poem.recording`, «Ver el evento»), `event_detail.html` (puertas
  «← Trayectoria {año}» y «Agenda»).
- **Aceptación:** cada detalle con ≥ 4 enlaces internos en `<main>`; presupuestos de consultas intactos.

### Épica 5 — Dossier, agenda, galería, aliados y búsqueda

#### 5.1 Dossier como kit de prensa (D11)
- **Hallazgos:** CON-8, NAV-2 (ancla), D11.
- **Archivos:** `showcase/dossier.html`; `apps/showcase/views.py` (cronología única);
  `site.css` 336-347, 206-208, 310-313, 371-380 (print); `tests/test_dossier.py`,
  `tests/test_ui_identity.py::test_la_cifra_grande_esta_acotada_a_la_portada` y
  `test_solo_la_portada_usa_la_tira_de_cifras_de_portada` (pasan a permitir `.dossier-doc`).
- **Pasos:** cejilla «Dossier · kit de prensa», barra de impresión después de la cabecera, bloque
  «Ficha» (fundado, ciudad, integrantes, contacto, Instagram, «Actualizado el …»), cifras en Syne
  36-56 px acotadas a `.dossier-doc` con integrantes y festivales, una cronología única ordenada
  descendente que fusione hitos, eventos y publicaciones en la vista, integrantes en rejilla con
  retrato 96 px, publicaciones con cubierta 120 px, cita de prensa y aliados con logo,
  `id="contacto"` en el bloque de contacto; `@media print` conserva las imágenes y las cifras.
- **Aceptación:** años en orden descendente estricto; el PDF impreso desde el navegador muestra
  retratos y cubiertas; `/dossier/#contacto` desplaza al bloque; `tests/test_dossier.py` en verde.

#### 5.2 Agenda y evento con afiche `[paralelo]`
- **Hallazgos:** IMG-8, CON-9 (resto), IMG-9 (parte).
- **Archivos:** `_event_card.html`, `agenda.html`, `event_detail.html`; `site.css` 195-205.
- **Pasos:** tarjeta `64px 128px 1fr` (fecha, afiche 4:5, texto); detalle con el afiche como
  objeto a 420 px y pie «Afiche · {caption} · {credit}»; mosaico de 6 fotos 3:2 con la primera a
  doble columna y «Ver las N fotos»; registros enlazados; puertas (4.5).
- **Aceptación:** con un evento sembrado con afiche, aparece en agenda, en «Próxima actividad» y
  en el detalle; el lightbox sigue sin JS (`tests/test_ui_ux.py::test_event_gallery_renders_lightbox`).

#### 5.3 Galería como hoja de contactos y aliados con logo `[paralelo]`
- **Hallazgos:** IMG-9, IMG-12 (lo que no cubrió 3.5).
- **Pasos:** `.album-grid` a `2fr 1fr` con filas 3:2, pie con crédito y contador; `.partner-list`
  agrupada por `kind` con logos 160×80; fallback tipográfico cuando no hay logo.
- **Aceptación:** `/galeria/` y `/aliados/` con ratio ≥ 0,85 a 1440 y sin imágenes deformadas.

#### 5.4 Búsqueda con cobertura completa (D2)
- **Hallazgos:** NAV-4 (resto).
- **Archivos:** `apps/content/views.py` 218-231 (búsqueda), `_search_results.html`.
- **Pasos:** añadir `Contributor` (nombre), `Recording` (título), `Publication` (título) y `Event`
  (título) a la búsqueda con `icontains` sin acentos (reutilizar `_strip_accents`), resultados
  agrupados por tipo con cejilla, límite por grupo; la limitación de tasa y el escape existentes se
  conservan.
- **Aceptación:** «Fernanda» devuelve a la integrante y «recital» al registro;
  `tests/test_search.py` y `tests/test_search_hardening.py` en verde; `test_search_query_budget` ≤ 10
  (si no cabe, consolidar en una consulta por tipo y anotar la medición).

### Épica 6 — Cierre: accesibilidad, métricas y documentación

#### 6.1 Pasada de accesibilidad completa
- **Pasos:** recorrer con teclado las 40 rutas (skip link, orden de foco, foco visible, menú y
  búsqueda en `<details>`, control de pausa, lightbox); comprobar con la herramienta
  `animationPlayState` en la cinta con hover, foco y control; contraste de todos los pares en la
  prueba; objetivos ≥ 44 px en nav, pie, paginación y botones; `aria-current`; títulos de pestaña;
  `prefers-reduced-motion` en todas las animaciones; `lang="es"` y guionado solo donde se indicó.
- **Aceptación:** una tabla en el PR con cada criterio de §10 de la auditoría marcado; cero
  incumplimientos de nivel A o AA en lo verificable sin herramientas externas.

#### 6.2 Métricas finales frente a la línea base
- **Pasos:** recapturar las 21 páginas en `tools/ux/out/final/` y correr
  `python3 tools/ux/metrics.py comparar tools/ux/out/baseline tools/ux/out/final`; volcar la tabla y
  los criterios de §10 de la auditoría en `docs/auditoria-ux-ui-verificacion.md` con las capturas
  antes/después de portada, un índice, un poema y una ficha a 1440 y 390.
- **Aceptación:** todos los criterios de §10 cumplidos o, si alguno no, explicado con su causa y
  su ticket de seguimiento en deferidos.

#### 6.3 Documentación y decisiones
- **Pasos:** `docs/deferidos-y-decisiones.md` §1 con D1-D14 y su porqué (copiar de la sección 1 de
  este backlog, con fecha); `docs/guia-pruebas-manuales.md` actualizada (cabecera de una fila,
  buscador en `<details>`, control de pausa, nav de cinco, índices con cabecera, portada nueva);
  `README.md` con `tools/ux/`; `docs/plan-ui.md` con una nota al inicio: «superado por
  docs/auditoria-ux-ui.md y docs/backlog-ux-ui.md (2026-10-08)»; este backlog con cada ticket
  marcado como cerrado y el número de PR.
- **Aceptación:** ningún documento describe un estado que ya no existe.

---

## 3. Pedido de material al colectivo (no lo hace el agente; va en `docs/contenido-visual.md`)

Nada de lo anterior se bloquea por esto: cada ticket tiene su fallback tipográfico. Con el material
real, el mismo diseño sube de categoría sin tocar código.

| Pieza | Formato | Dónde se usa | Campo del panel |
|---|---|---|---|
| Retrato por integrante | 1200×1500 (4:5), color, fondo neutro | rejilla, cinta, ficha, dossier | Integrante → foto |
| Seis fotos por lectura | 3:2, ≥ 2400 px, con nombre del fotógrafo | galería, evento, portada (duotono) | Evento → fotos (caption y credit) |
| Afiche de cada evento | 300 dpi, PDF o PNG | agenda, próxima actividad, detalle, hero | Evento → afiche |
| Cubierta de cada publicación + foto del objeto | 1000×1400 (5:7); foto 3:2 | catálogo, ficha, hero, dossier | Publicación → cubierta |
| Fotograma por registro | 1920×1080 | placa del reproductor, miniaturas, destacado | Registro → póster |
| Logos de aliados | SVG o PNG ≥ 600 px | aliados, línea de respaldo, dossier | Aliado → logo |
| Foto de grupo | 2400×1260 | hero (si no hay objeto) y `og_image` | Perfil del sitio → og_image |
| Ciudad | texto | cejilla del hero, ficha, dossier | Perfil → location |
| Correo de gestión real | texto | hero, pie, dossier | Perfil → booking_email |
| Manifiesto propio | 60-120 palabras | hero (recortado) y dossier (completo) | Perfil → manifesto |
| Lema propio (opcional) | ≤ 6 palabras | solo si se quiere volver al lema como titular (D8) | Perfil → tagline |
| Verso de cierre acreditado | 1-2 líneas | pie | pendiente de definir campo; hoy se omite |

---

## 4. Mapa hallazgo → ticket (cobertura completa de los 91)

| Dimensión | Hallazgo → ticket |
|---|---|
| ESP | 1→2.1 · 2→1.1 · 3→4.2 · 4→2.2 · 5→2.1/2.2 · 6→2.1 · 7→2.1 · 8→2.1 · 9→2.4 · 10→3.1/4.3 · 11→1.2 · 12→2.1/1.13 |
| TIP | 1→1.2 · 2→2.3 · 3→2.3 · 4→1.3 · 5→2.3 · 6→2.3 · 7→2.3/2.4 · 8→1.8 · 9→1.3 · 10→1.7 · 11→1.3 |
| COL | 1→1.9 · 2→3.7 · 3→3.4 · 4→3.1 · 5→3.6 · 6→1.9/3.2 · 7→3.3 · 8→3.1/4.4 · 9→3.3 · 10→1.9 · 11→1.6 |
| IMG | 1→1.1 · 2→3.4 · 3→4.2 · 4→3.6 · 5→3.3 · 6→2.2 · 7→2.4/3.5 · 8→3.5/5.2 · 9→3.5/5.3 · 10→1.13 · 11→0.3 · 12→3.5/5.3 |
| POR | 1→4.2 · 2→4.2 · 3→4.3 · 4→1.1 · 5→1.12/4.2 · 6→4.3 · 7→3.4 · 8→4.2 · 9→4.2/3.2 · 10→4.3 · 11→1.4/4.3 · 12→1.12 · 13→3.1/4.3 |
| NAV | 1→4.1 · 2→4.1/4.2 · 3→1.5 · 4→4.1/5.4 · 5→4.1 · 6→4.1 · 7→4.1 · 8→4.4 · 9→2.4/4.5 · 10→1.12 · 11→4.3 · 12→1.12 |
| CON | 1→1.1 · 2→1.2 · 3→1.3/2.4 · 4→2.4 · 5→2.2/3.4 · 6→1.4/4.1 · 7→1.3/1.7/4.1 · 8→5.1 · 9→1.13/5.2 · 10→1.10 |
| COM | 1→1.4 · 2→1.6/1.7 · 3→1.2 · 4→1.6/3.4 · 5→1.5 · 6→1.6 · 7→2.2/3.6 · 8→1.9/1.10 · 9→1.11 · 10→1.8 |

## 5. Estimación y secuencia

| Épica | Tickets | Tamaño | Depende de |
|---|---|---|---|
| 0 Preparación | 0.1, 0.2, 0.3 | S | — |
| 1 Quick wins | 1.1 … 1.13 | S cada uno (13 PR pequeños) | 0.1 |
| 2 Retícula y tipografía | 2.1 → 2.4 | M, M, M, M | 1.x |
| 3 Color e imagen | 3.1 → 3.7 | S, S, S, M, M, S, M | 2.1, 2.2 |
| 4 Cabecera y portada | 4.1 → 4.5 | M, L, M, S, S | 2.x, 3.1, 3.2, 3.4 |
| 5 Secundarias | 5.1 … 5.4 | M, S, S, S | 2.4, 3.5 |
| 6 Cierre | 6.1 … 6.3 | S, S, S | todo |

Cada «S» cabe en una sesión corta de agente; cada «M» en una sesión larga con pruebas; la «L» (4.2)
conviene partirla en dos PR (hero sin objeto; luego objeto, cifras y línea de respaldo) si el
contexto se alarga.
