# Auditoría UX/UI — Repitentes del Verso

Documento final. Fecha: 8 de octubre de 2026. Alcance: las 21 páginas del sitio local (escritorio 1440×900, móvil 390×844, siete páginas también a 1920×1080), el CSS único `backend/static/css/site.css` (502 líneas), las plantillas Django y siete sitios de referencia que te gustan. Los hallazgos pasaron por dos verificaciones independientes (evidencia y fundamento); las cifras que siguen son las corregidas. Las diez dimensiones del plan volvieron agrupadas en ocho bloques de hallazgos: espacio (ESP), tipografía (TIP), color e identidad (COL), imagen (IMG), portada (POR), navegación (NAV), páginas de contenido e índices con móvil (CON) y componentes, estados, motion y accesibilidad (COM). Ningún hallazgo fue descartado en la verificación; varios fueron ajustados en cifra o severidad y así se reproducen aquí.

**Método y material.** Capturas con Playwright sobre el Chrome del sistema de las 21 páginas del sitio local con datos de demostración (escritorio 1440×900, móvil 390×844 a 2x, siete páginas también a 1920×1080) y de las siete referencias con los avisos de cookies y boletines cerrados, más métricas computadas con `getComputedStyle` (familias reales, tamaños, ancho de texto frente al viewport, medios en el primer viewport). El análisis lo hicieron 26 agentes en cuatro fases: siete analistas de referencias, ocho auditores por dimensión, un verificador escéptico por dimensión (dos en color y portada) que comprobó evidencia y fundamento de cada hallazgo, y una síntesis revisada después a mano. Todo el material (capturas, métricas, resultados de cada agente y el script de captura) está en `~/.claude/projects/-home-fabian-User-repos-Rese-as/auditoria-ux-ui-material/`; las capturas que se citan más abajo viven en su carpeta `shots/`. Los datos auditados son los sembrados por `seed_demo` (avatares ilustrados, textos de prueba): lo que solo mejora con contenido real está marcado como dependiente de material nuevo en la hoja de ruta.

## 1. Resumen ejecutivo

El sitio está bien construido y mal terminado: la semántica, la seguridad, la accesibilidad de base y la arquitectura de rutas son mejores que las de cinco de las siete referencias, pero todo lo que se ve ocupa una franja de 780 px centrada, sin imagen, sin jerarquía y sin acabado, y eso es exactamente lo que se lee como «genérico y simplón».

Las causas raíz son cuatro. Primera: un solo contenedor de 820 px para cabecera, pie, índices, rejillas y lectura, de modo que el texto cubre el 54 % del viewport a 1440 px y el 41 % a 1920 px en las 20 páginas, y nada escala entre 1156 y 1920 px. Segunda: la jerarquía tipográfica está invertida y la voz dominante es la monoespaciada del sistema: el h1 de los once índices mide 12 px (el texto más pequeño de la página), los h2 de sección 11 px, y en la portada 113 de 163 elementos con texto van en mono, 49 de ellos en mayúsculas; la serif de lectura es la de una página sin estilos y cambia según el sistema operativo. Tercera: no hay imagen ni dirección de arte: cero imágenes en el primer viewport de la portada, un «registro destacado» que es un rectángulo azul de 780×439 px, y cinco campos de imagen del modelo (Recording.poster, Article.cover_image, Event.poster, Work.cover_image, Partner.logo) que nunca llegan a pantalla; donde sí hay foto, un defecto de CSS la deforma (portadas a 180×780 px). Cuarta: la paleta risográfica se usa como paleta de interfaz, no de identidad: el magenta es «el color de los links» (27 reglas de color de texto), no existe glifo, favicon ni og:image, y la portada alterna celeste y blanco al 50/50 sin ninguna superficie de peso.

Qué cambiar primero, en este orden: (1) una línea de CSS, `img{max-width:100%; height:auto}`, que arregla portadas, galería y fichas en cinco plantillas; (2) la cabecera de índice que ya existe (`.index-head`) aplicada a los once índices con h1 en Syne a 36-56 px; (3) la retícula de tres carriles (lectura 820 / ancho 1320 / sangre) que resuelve la queja del espacio sin alargar una sola línea de lectura; (4) un objeto real en el hero y el póster o una carátula tipográfica en el reproductor; (5) corregir el selector de pausa de la cinta, porque hoy no se detiene ni con hover ni con foco.

## 2. Diagnóstico: por qué hoy se ve genérico, simplón y no usa el espacio

### 2.1 Un solo carril para todo

`.wrap{max-width:820px; padding:0 20px}` (site.css:43) es el único contenedor del sitio y lo comparten cabecera, navegación, `<main>` y pie (base.html:46, 68, 87, 92). Resultado medido: 780 px de texto en todas las páginas, 54 % del viewport a 1440 px y 41 % a 1920 px; la portada da 1140 px solo porque la pista oculta de la cinta desborda. A 1920 px la rejilla de integrantes mide 767 px con 570 px de celeste vacío a cada lado, y las páginas miden exactamente lo mismo que a 1440 (artículo 1089 px, integrantes 1245, poema 1086, publicaciones 1383, textos 1579, portada 4077): 480 px más de monitor no mueven un píxel. La única media query de ancho es `min-width:720px` para la nav.

La proporción de píxeles de tinta en el primer viewport, con el mismo método para todos, es demoledora: portada 33 %, poemas 4,8 %, textos a 1920 3,7 %, integrantes a 1920 5,9 %; en las referencias, Explora 67 %, Politico 75 %, Tack Shop 70 %, IME 33 %, LEDUP 24 %, sinedogma 16 %, Shape of Intelligence 10 %. Sinedogma y Shape son más escasos que tú y aun así se ven diseñados, porque reparten esa tinta en el 87-92 % del ancho. Lo sobrio es la paleta y el ornamento, no dejar el 59 % de un monitor en blanco (Müller-Brockmann: la columna de texto es una subdivisión del formato, no el formato; Bringhurst §2.1.2: la medida de 45-75 caracteres rige la línea, no la página).

### 2.2 Las imágenes se dibujan con la altura del atributo HTML

`_responsive_img.html` emite `width` y `height` del asset (correcto contra el CLS), pero ninguna regla de site.css declara `height:auto` (grep: 0 coincidencias). Con ambas dimensiones no-auto, `aspect-ratio` no actúa (CSS Box Sizing L4 §5) y gana el `height="780"`. Medido: `.pub-card img` 180×780 (debería ser 180×252), `.pub-cover` 240×780 (las estelas circulares de «Cuadernos del ruido» salen como elipses), `.photo-grid img` 249×750 (fotos apaisadas 8:5 como tiras verticales). La banda «Publicaciones» de la portada mide 1006 px por culpa de esto; con 5:7 mediría unos 480. Es el defecto más visible del sitio y el más barato.

### 2.3 Tres familias, con la mono dominante y una serif que cambia según el sistema

Inventario de la portada a 1440: ui-monospace 113 elementos, Syne 38, serif 12 (con otro conteo: mono 137 / serif 56 / Syne 41). 68 de 163 elementos miden 12 px o menos; 49 van en mayúsculas, todos en mono. Hay 15 reglas `text-transform:uppercase` y 30 usos de `var(--mono)` con ocho trackings distintos (.04 a .14em). La pila serif se resuelve en Liberation Serif (Times) en Chrome/Linux, Noto Serif en Android, Iowan Old Style en macOS y Palatino Linotype en Windows: cuatro dibujos para el mismo cuerpo de 18-19 px. Syne se carga sin preload y con la serif como reserva: el lema a 104 px pasa de 676 a 780 px de ancho al llegar la fuente (FOUT horizontal, no CLS).

### 2.4 Índices con h1 de 12 px y encabezados invertidos

`.page-title` (12 px mono gris, site.css:124) es el `<h1>` de Poemas, Textos, Integrantes, Registros, Publicaciones, Agenda, Trayectoria, Galería, Prensa, Aliados y Colecciones. Es más chico que la nav (13 px) y que el h3 de tarjeta (26 px): ratio h1:h3 de 0,46. Los 28 `<h2 class="subhead">` miden 11 px, menos que el cuerpo que encabezan. Existe `.index-head h1{clamp(28px,5vw,42px)}` (site.css:125-126), pero lo usan 16 plantillas de detalle y ningún índice. El artículo corre a 102 caracteres por línea (18 px en 780 px), un 36 % sobre el máximo de Bringhurst. Hay 24 valores distintos de `font-size`, 10 de `line-height`, 8 de `letter-spacing` y ningún token en `:root`.

### 2.5 Componentes sin acabado y color sin reparto

Cinco vestimentas de botón de 12-13 px, cuatro `transition` para treinta reglas `:hover`, hover por opacidad (`.btn-primary:hover{opacity:.9}`), 19 bordes de 1 px a 1,17:1 sobre papel, 29 radios con cinco valores distintos. El magenta aparece 45 veces en el CSS (27 como color de texto, 6 como fondo, 7 como borde, 4 como outline): en el primer viewport de la portada hay nueve piezas magenta, dos de ellas planos (el sello de 292×52 y el CTA de 165×38) con la misma receta. La mayor superficie de color del sitio, la carátula #1f73c7 del reproductor, es un color huérfano que ningún otro elemento usa. No hay `filter`, `mix-blend-mode`, `background-image` ni `<svg>` en todo el sitio: la risografía está en los valores hex y ausente del lenguaje gráfico.

### 2.6 Sitio actual frente a referencias (1440 px)

| Sitio | Texto/viewport | Contenedor | Familias | Cuerpo | Medios en 1.er viewport |
|---|---|---|---|---|---|
| Repitentes del Verso | 0,54 (0,41 a 1920) | 820 px (780 útiles), único | 3: Syne autoalojada; serif y mono de sistema; mono domina (137 elementos) | 16 px (artículo 18, poema 19) | 0 |
| Explora Journal | 0,96 | 1440; listado 1248; dos columnas 499/624 | 3 autoalojadas (Monarch Nova 1 elemento, SangBleu 32, Shapiro 755) | 15 px | 1 foto grande visible (la métrica de 25 incluye miniaturas ocultas del megamenú) |
| POLITICO Europe | 0,94 | 1440 fondos / 1018 módulos / 640 entradas / 500 cuerpo | 2 autoalojadas con fallback métrico | 18 px | 6 ilustraciones en mosaico (CSS, 0 `<img>`) |
| sinedogma | 0,87 | 1080 shell / 680 lectura | 1 (EB Garamond variable, autoalojada) | 17 px | 2 portadas |
| LEDUP | 0,80 | 1440 con 80 px de margen (1280 útiles); párrafos 70-80ch | 1 (Poppins, 9 cortes) | 16 px | 0 visibles sin vídeo |
| Shape of Intelligence | 0,92 | fluido por márgenes; prosa 64ch (653 px) | 1 + mono (Diatype), con fallbacks size-adjust | 19 px | 1 (escultura) |
| The Tack Shop | 0,91 | 1320 útiles; medidas de lectura 650-920 | 3 (Americana BT, Fraunces, Roboto) | 15 px | 5 (hero + stickers) |
| IME Chile | 0,86 | 980 (Wix), extensión 1245 | 5 (Playfair, DIN, Avenir, Poppins, Lucida) | 14 px | 2 (logo + foto duotono) |

Lo que salta: ninguna referencia baja de 0,80 y todas mantienen la lectura corta dentro de ese ancho. Tu medida de lectura ya está bien; lo que falta es todo lo demás alrededor.

## 3. Qué tienen en común las referencias que te gustan

Son siete sitios muy distintos (revista de lujo, longform patrocinado, editorial turca, fabricante de LED, exposición interactiva, tienda ecuestre, gremio chileno) y comparten seis mecanismos. Ninguno depende de dinero: dependen de decisiones.

**a) Lienzo ancho con columna de lectura corta.** Politico: cuerpo de 500 px dentro de 1440 con módulos de 1018. Shape: prosa a 64ch con márgenes del 8 %. sinedogma: shell de 1080 y `--reading` de 680. LEDUP: 1280 útiles con párrafos a 70ch. Es el patrón que responde a tu queja literal.

**b) Racionamiento tipográfico.** Explora usa su fuente caligráfica en un elemento, la serif en 32 y la grotesca en 755. Shape lleva la mono a 46 elementos frente a 518 de la sans. sinedogma, una sola familia de 12 a 78 px a peso 400: la jerarquía nace del tamaño y del tracking, no de multiplicar voces. En todos, el h1 de sección mide entre 36 y 219 px.

**c) Seccionar con superficies, no con cajas.** Explora: tres neutros (papel, arena, oliva) y ni un borde, radio o sombra en 9.209 px. Politico: paneles celestes a sangre alternando con blanco y pie negro. Shape: bandas papel/carbon/azul dentro de una paleta única. Tack Shop: página «encuadernada» entre cabecera crema y pie burdeos.

**d) Un acento, un trabajo.** Explora: bronce solo en rótulos de 12 px, navy solo en dos botones. LEDUP: el cobre aparece una vez por pantalla y nunca como texto. Shape: azul solo para énfasis, estado activo y progreso. Tack Shop: naranja solo en una marquesina y un sticker.

**e) Imagen unificada por tratamiento.** IME: duotono azul que comparte tono con los títulos. Politico: toda la fotografía a blanco y negro en una sola geometría. Explora: gama cálida y un cuadrado en B/N como contrapunto. sinedogma: la portada como objeto, 248×352 centrada con aire.

**f) Firmas repetibles.** Rótulo «CATEGORÍA • N MIN READ» idéntico en hero, tarjetas y móvil (Explora); píldora de sección (Politico); «01 / 08 · 1936 — 1956» en las esquinas (Shape); emblema que sobrevive solo en la cabecera compacta (Explora); stickers troquelados en las costuras (Tack Shop); colofón con año, ciudad, ISSN (sinedogma).

| Sitio | Qué aporta a Repitentes | Qué no copiar |
|---|---|---|
| Explora Journal | Superficies en vez de bordes; tarjeta sin cromo; rótulo-firma de 12 px; hero con leyenda en panel sólido; dos columnas desiguales 4:5 que alternan; aire de 64-140 px entre secciones | Vídeo autoplay; cabecera de 10 elementos con megamenú; barra de filtros sticky que tapa el pie; bronce 350 a 12 px (4,4:1, falla AA); cuerpo de 15 px; 192 px de cromo fijo en móvil |
| POLITICO Europe | Columna de 500 px en lienzo de 1440; cambio de registro entrada 24 px → cuerpo 18 px; fallbacks métricos; hero partido 58/42; medallón de retrato B/N; cifras gigantes; aparato editorial (notas, nombre y cargo) | 187 px de cromo fijo en móvil; titular cortado por el mosaico en móvil; 28 chips de etiquetas; pie de 70 enlaces; scroll-driven motion con orbes 3D; cinco geometrías de tarjeta |
| sinedogma | Shell 1080 + lectura 680; kicker 12 px + h2 54 px; listados tipográficos sobre reglas; portada como objeto; cabecera sticky de 56 px en una fila; énfasis por inversión; tokens de motion 160/220/300 ms; cinta con pausa y fallback reduced-motion; colofón institucional | Contenido vaciado sin JS; toast fijo que tapa el hero; minúsculas forzadas que aplastan siglas; texto de 11 px en móvil; información solo al hover; insignia de Awwwards fija |
| LEDUP | Contenedor 1280 con párrafos a 70ch; kicker + titular 36 px + párrafo; bento de 12 columnas con `align-self:end`; tarjeta-cifra; un glifo de acción repetido; paleta de una tinta en 10 pasos; scroll-snap en móvil | Hero de vídeo a 100vh (vacío sin JS); preloader; radios de 50 px y vidrio esmerilado (lenguaje «tech»); contraste 3,5:1 en kickers; descripciones solo en hover; 12 px en móvil |
| Shape of Intelligence | Layout fluido por márgenes + `max-width:64ch`; sala de lectura 33 % / 54 %; metadatos en esquinas; filas `.eventRow` con filete; enlaces-puerta de ancho completo; cabecera fija de 64 px; fallback con `size-adjust`; pie-colofón «REVIEWED» | Esculturas WebGL y deslizadores; página única de 18.643 px; dos barras fijas (112 px); texto de 10-11 px; body oscuro por defecto; cabecera que cambia de color con JS |
| The Tack Shop | 1320 útiles alternando bandas a sangre con rejillas; serif de display grande (60-70 px); stickers troquelados en costuras; declaración de 70 px con pictogramas; página «encuadernada»; dos variantes de botón; carrusel con «peek» en móvil | Pop-up de boletín; rótulos de 11 px; cabecera de 174 px que se oculta; 10 ítems de nav; simetría total (lo más «plantilla»); animaciones infinitas sin pausa ni reduced-motion; Google Fonts |
| IME Chile | Duotono de una tinta sobre un papel; dispositivo de título (regla + antetítulo + 71 px); cambio de papel por bloque; hero con imagen al 60 % del ancho; fichas de personas con retrato a tope; subrayado del ítem activo | Cinco familias; cuerpo de 14 px ExtraLight; sin pie, sin mailto, sin botones; cabecera no fija con 7 ítems; tarjetas desalineadas de 1000 px; tercer acento huérfano; alt que son nombres de archivo |

## 4. Dirección de diseño propuesta

Una propuesta, no tres: **un impreso risográfico puesto en pantalla**. Papel celeste como base, tinta y magenta como las dos tintas de la máquina, el amarillo del cartel recuperado como superficie, Syne como voz de titulares, una serif de lectura elegida y autoalojada, la mono reducida a rótulo, y las fotografías tratadas como si hubieran pasado por la misma máquina. Todo en CSS plano, sin JS, sin CDN, dentro de la CSP, y dentro de la sobriedad que decidiste: lo que se añade es estructura, no decoración.

### 4.1 Sistema espacial

Retícula de tres carriles con líneas con nombre, en `<main>` (hay que quitarle la clase `.wrap` en base.html:87 o anular su `max-width`, si no la rejilla queda topada a 820):

```
main{display:grid; grid-template-columns:
  [full-start] minmax(var(--gutter),1fr)
  [wide-start] minmax(0, calc((var(--wide) - var(--measure)) / 2))
  [content-start] min(var(--measure), 100% - 2*var(--gutter)) [content-end]
  minmax(0, calc((var(--wide) - var(--measure)) / 2)) [wide-end]
  minmax(var(--gutter),1fr) [full-end]}
main > *{grid-column:content}
:root{--measure:51.25rem; --wide:82.5rem; --gutter:clamp(20px,4vw,64px)}
@media (min-width:1600px){:root{--wide:90rem}}
```

- **Carril de lectura (content, 820 px):** poema, cuerpo de artículo, dossier, formulario. `.wrap` se conserva con su valor; lo que pedía docs/plan-ui.md:48-49 («no cambiar .wrap») se respeta: no cambia, deja de ser el único.
- **Carril ancho (wide, 1320 px):** cabecera, nav, pie, cabeceras de índice, rejillas (integrantes, publicaciones, galería, registros), hero, destacado, fichas de detalle.
- **Carril a sangre (full):** bandas de color, cinta de integrantes, pie en tinta. `.band` deja el truco `box-shadow:0 0 0 100vmax` + `clip-path` (site.css:324) y pasa a `grid-column:full; display:grid; grid-template-columns:subgrid`, sin `100vw` (el CSS evita esa unidad a propósito por la barra de scroll, y hay que seguir evitándola).

Dentro del carril ancho, 12 columnas con medianil de 24 px para bento y composiciones asimétricas (7/5 para el hero, 8/4 para el destacado, 4fr/5fr alternando para textos con imagen). Escala raíz fluida `html{font-size:clamp(100%, 0.875rem + 0.25vw, 118.75%)}`: 16 px a 800, 17,6 a 1440, 18,8 a 1920, con `--measure` y `--wide` en rem para que la columna de lectura siga midiendo unos 75 caracteres y crezca a 964 px en un monitor grande.

Ritmo vertical con tokens: `--s1:8px; --s2:16px; --s3:24px; --s4:40px; --s5:64px; --s6:96px; --s7:144px`. Secciones de portada con `padding-block:clamp(56px,7vw,112px)`; 20-24 px dentro de las rejillas, 32-40 entre filas, 64 px bajo la cabecera, pie con `margin-top:var(--s6)`. Hoy el aire está dentro de los bloques (bandas de 1000 px) y no entre ellos (32-52 px): la ley de proximidad de Wertheimer pide lo contrario, y Explora (64/76/130-140 px) y LEDUP (150 px de padding de sección) lo ejemplifican.

### 4.2 Sistema tipográfico

**Conservar de Syne:** la marca, los h1 de índice y de detalle, los h2 de sección y de destacado, las cifras. Subir el gesto: `.brand` y `.hero-tagline` a peso 800 (el eje variable ya lo sirve), h1 y h3 a 700, `letter-spacing:-.015em` a partir de 26 px. Precargar con `<link rel="preload" as="font" crossorigin>` y declarar «Syne Fallback» con `size-adjust` calculado con fontaine o capsize (el 114 % sale de 1121/977 medidos en Arial; verificar), reserva `sans-serif`, nunca la serif.

**Serif de lectura autoalojada.** Hoy tu voz de lectura es Times en Linux, Noto Serif en Android, Palatino en Windows e Iowan en macOS: dos personas del mismo jurado ven sitios distintos y ninguna ve una tipografía elegida. Las siete referencias autoalojan la suya. Recomiendo **Source Serif 4** o **Literata** (ambas OFL, con eje óptico, cursiva real y buen rendimiento en pantalla a 18-19 px); **Fraunces** (la de Tack Shop) y **EB Garamond** (la de sinedogma) son alternativas con más carácter pero más «de revista» que «de lectura». Tres cortes (regular, cursiva, negrita) en woff2 con subconjunto latino: unos 150 KB cacheables en un sitio que ya autoaloja Syne; `font-src 'self'` lo permite. Si mantienes la pila de sistema, al menos añade `"Noto Serif","DejaVu Serif"` antes de Times y `font-size-adjust:0.47` para que las cuatro alturas de x se acerquen.

**La mono se queda en dos papeles.** Cejilla de 12 px en mayúsculas con `+.1em` (POEMA, RESEÑA · 4 MIN, REGISTRO DESTACADO) y meta de 13 px en caja baja (autor · fecha). Sale de la nav (Syne 500 a 15 px o la serif a 16), de los botones (14 px, caja de frase), del pie (serif 15 px, solo los h2 de grupo en mono) y de las etiquetas de cifras. Objetivo en portada: 30 % o menos de elementos en mono, 15 o menos en mayúsculas. Si quieres que la mono tenga sabor risográfico, autoaloja una OFL (Space Mono, IBM Plex Mono, JetBrains Mono; 20-35 KB) en vez de la del sistema, que es DejaVu Sans Mono en Linux/Android.

**Escala de 8 pasos** en `:root`: `--t-1:12px` (cejillas, meta en mayúsculas), `--t0:14px` (meta en caja baja, legal), `--t1:16px` (UI, formularios), `--t2:19px` (lectura: cuerpo, poema, manifiesto), `--t3:22px` (títulos de evento y registro), `--t4:26px` (h3 de tarjeta), `--t5:32px` (h2 de sección y destacado), `--t6:clamp(34px,4.6vw,56px)` (h1 de índices y detalles), `--t7:clamp(44px,7.5vw,148px)` (lema o nombre en el hero). Interlíneas por rol: `.92` display, `1.08` títulos de 26-56, `1.35` UI, `1.55` cuerpo, `1.5` verso. Tres trackings: `.1em` versales, `.02em` UI, `-.015em` títulos. Regla de sistema: ningún encabezado más pequeño que el cuerpo que encabeza; mínimo absoluto 12 px. Medida: `.article .body{max-width:66ch}`, `.poem-body{max-width:40ch; width:fit-content}` con sangría francesa para versos partidos; `text-wrap:pretty` en párrafos, `balance` en títulos, `hyphens:auto` en móvil (nunca en el poema).

### 4.3 Color

Cuatro superficies, con reparto escrito en el comentario de `:root` y custodiado por `test_contraste_paleta.py`:

- `--paper #d9e8f7`: base y hero.
- `--paper-2 #eef4fb`: listados y rejillas (1,13:1 frente al papel; «una hoja más clara»).
- `--ink #121823`: banda de peso, una o dos por página (registro destacado, cierre «Para programadores y jurados», pie). Texto en `--paper` (14,26:1). No es modo oscuro: `color-scheme:light` sigue, el body sigue claro; es una banda, como la carbon de Shape o el pie burdeos de Tack Shop.
- `--surface #fff`: solo objetos (portadas, campos de formulario), nunca bandas.

El magenta queda reservado a tres funciones: el glifo de marca, la cejilla de 12 px y los estados activo/foco. Enlaces de cuerpo en tinta con `text-decoration-color:var(--accent)`; CTA primario en tinta sobre papel (14,26:1) con hover invertido; `.nav a`, `.member-role`, `.year-mark`, bordes de 3 px de `.poetics` y `.press-quote` pasan a tinta o muted. Es un cambio de unas 15 reglas, sin tocar plantillas.

**El amarillo vuelve como fondo.** `#fce43c` con tinta encima da 13,81:1 y con magenta 4,96:1: supera AAA y AA respectivamente; solo falla como texto (1,03:1 sobre papel), que es el uso que nadie propone (WCAG 1.4.3 evalúa pares, no colores aislados; Albers: un plano cálido pequeño activa toda una paleta fría). Usos permitidos, un plano por viewport: la franja de cifras del hero, un sticker estático («Convocatoria abierta», «Próxima lectura · 28 abr»), segunda tinta del duotono. Añadir los pares (ink, amarillo) y (accent, amarillo) a la prueba.

**El azul #1f73c7 entra a la familia o se va.** Hoy es huérfano (3 ocurrencias). Como segunda tinta del duotono y del glifo, y como regla de 3 px del territorio «El colectivo», deja de ser el azul de un framework y pasa a ser el azul del cartel que dice el comentario de site.css:18-21.

**Pares prohibidos escritos:** magenta sobre tinta (2,78:1), azul como texto sobre papel (3,88:1; solo a partir de 24 px), muted sobre cualquier banda de color. Para acento sobre tinta, token `--accent-on-ink:#f77cc3` (7,31:1), inutilizable sobre papel (1,95:1).

### 4.4 Imagen y dirección de arte

- **Duotono risográfico en CSS** para fotos propias (retratos, fotos de lectura, pósteres de registro, galería): `.riso-duo{display:block; background:var(--accent); isolation:isolate} .riso-duo img{filter:grayscale(1) contrast(1.15) brightness(1.05); mix-blend-mode:multiply}`; variante `--azul` con `--caratula`. Da magenta/tinta o azul/tinta, una tinta por pantalla. Para revelar el original al pasar o enfocar hay que anular las dos propiedades: `filter:none; mix-blend-mode:normal` (con solo `filter:none` la foto a color sigue multiplicándose sobre el magenta). Grano opcional: pseudo-elemento con un SVG `feTurbulence` como `data:` URI al 5-8 % sobre bandas de tinta y hero (la CSP admite `img-src data:`). Exclusión: cubiertas de libros, afiches de terceros y logos de aliados se muestran sin tratamiento (obra ajena); la ficha del integrante y el detalle del evento conservan el original.
- **Portadas como objetos:** 5:7 a 240-260 px en rejilla y 360 en detalle, borde de 1 px, sombra plana `8px 8px 0 var(--border)` (tinta plana, sin blur), la destacada con `rotate(-2deg)`. Es lo que hace sinedogma con 248×352 y 140 px de aire.
- **Carátulas tipográficas** para todo lo que no tenga imagen: registro sin póster (título en Syne 28-44 px en papel sobre tinta o azul, más «Video · Recital · 2026» en mono), publicación sin cubierta (5:7 en papel con filete superior magenta de 6 px y título Syne 20 px; nunca la palabra «LIBRO»), integrante sin retrato (monograma de dos letras en Syne 700 a 56 px, o el primer verso de su poema más reciente). Son fallbacks que leen como espécimen tipográfico, no como avatar de chat.
- **Retratos 4:5** a tope de tarjeta (245-287 px en rejilla, 160×200 en cinta, 240×300 en ficha), nunca el círculo de 72 px con inicial.
- **Un objeto real por pantalla**, siempre del colectivo, sin stock, sin velos oscuros ni vídeo: en el hero la última cubierta, el póster del próximo evento o una foto de lectura en duotono; en el destacado el póster del registro; entre poemas y agenda, una foto a sangre 2:1 con rótulo mono de lugar y fecha.
- **Pedido de material** (docs/contenido-visual.md, previsto en plan-ui.md y nunca escrito): retrato por integrante 1200×1500, seis fotos por lectura a 3:2 y 2400 px con nombre del fotógrafo, afiches a 300 dpi, cubiertas 1000×1400 más una foto del objeto en mano, fotograma 1920×1080 por registro, logos en SVG, una foto de grupo 2400×1260 para hero y og_image.

### 4.5 Componentes

- **Botón:** un componente `.btn` de 14 px mono en caja de frase, `min-height:44px`, `padding:0 18px`, radio `--r-1`, con variantes `--primary` (tinta sobre papel; hover papel sobre tinta) y `--ghost` (borde 1 px tinta; hover inversión). Sin opacidad en hover. Una acción primaria por pantalla.
- **Tarjeta sin cromo:** imagen + cejilla + título + extracto sobre el fondo, sin borde ni sombra; la tarjeta entera es el enlace (enlace extendido con `::after`), con los enlaces secundarios por encima (`z-index:1; padding:6px 0; margin:-6px 0`). Estado de fila al hover y al `:focus-within`.
- **Fila tipográfica** para Poemas, Textos, Trayectoria y Prensa: `grid-template-columns:12ch minmax(0,1fr) auto`, paso de 64 px, filete de tinta al 20-25 % de alfa (visible para baja visión), fecha en mono a la izquierda, título Syne 24-28 px, «autor · 3 min» a la derecha.
- **Enlaces:** tinta con subrayado magenta de 1 px, `text-underline-offset:3px`; hover: 2 px. Vocabulario de flechas: → para fichas internas, ↗ solo para destinos externos.
- **Estados:** `aria-current="page"` en la nav con subrayado de 2 px; foco visible propio sobre la placa azul (anillo blanco, 4,84:1; el magenta actual da 1,32:1).
- **Motion mesurado:** `--dur-fast:140ms; --dur-base:220ms; --ease:cubic-bezier(.22,.61,.36,1)`; transiciones solo de color, borde, fondo y `text-decoration-color`; bloque global `prefers-reduced-motion:reduce`; nada de revelado al scroll. Es el sistema de sinedogma (160/220/300 ms, una curva).
- **Rótulo:** un componente `.rotulo` (12 px mono, `.1em`, mayúsculas, muted) con modificador `--acento`, que sustituye a las quince reglas actuales.

### 4.6 Wireframe textual de la nueva portada (1440 px, carril ancho 1320)

```
[cabecera 64 px, sticky, carril ancho]
 glifo + Repitentes del Verso (Syne 22)  Poemas · Textos · Registros · Publicaciones · Colectivo   ⌕  [Dossier]
[hero, carril ancho, min-height 78vh, grid 7/5, align-items:end]
 ┌───────────────────────────────┬────────────────────┐
 │ COLECTIVO DE POESÍA · CHILE · │                    │
 │ DESDE 2023 (mono 12)          │  objeto real 5:7   │
 │ Repitentes del Verso          │  (última cubierta, │
 │ (Syne 800, 112-148 px, 2 lín.)│  póster o foto en  │
 │ manifiesto serif 20 px, 54ch  │  duotono), 420 px, │
 │ [Ver el dossier] [Escríbenos] │  rotate(-2deg)     │
 │ franja amarilla: 12 integr. · │                    │
 │ 4 eventos · 1 festival · 3 pub│                    │
 └───────────────────────────────┴────────────────────┘
 línea de respaldo: cita de prensa en cursiva · «Con el apoyo de» Fondo del Libro · Casa del Libro · Overol
[banda de tinta a sangre: REGISTRO DESTACADO, grid 8/4]
 ┌──────────────────────────────┬──────────────┐
 │ reproductor 16:9 con póster  │ 01 / 05      │
 │ en duotono o carátula tipo-  │ Recital      │
 │ gráfica; botón ▶ de 64 px    │ «Nuevas      │
 │ en panel sólido abajo-izq.   │ voces»       │
 │                              │ ficha + resu-│
 │                              │ men + Todos →│
 └──────────────────────────────┴──────────────┘
[papel: POEMAS, 3 filas tipográficas con 3 versos cada una, «Leer →»]
[paper-2: INTEGRANTES · 12 voces · Conoce al colectivo →, cinta a sangre de retratos 4:5 160×200, 5 visibles]
[papel: TEXTOS · reseñas, ensayos y entrevistas, 3 filas; la más reciente con miniatura 3:4 a la derecha]
[paper-2: PUBLICACIONES, 4-5 cubiertas 5:7 a 240 px como objetos]
[tinta: PARA PROGRAMADORES Y JURADOS: cuatro puertas (Dossier · Prensa · Aliados · Contacto) + última actividad + «Actualizado el …»]
[pie en tinta: glifo + ficha (Chile · desde 2023 · correo · Instagram) | El colectivo | La obra | Prensa y gestión | verso corto en cursiva]
```

### 4.7 Wireframe textual de un índice (Poemas)

```
[cabecera sticky]
[index-head, carril ancho, grid 1fr / minmax(260px,420px), filete inferior]
 POEMAS · 12 PIEZAS · 7 VOCES (cejilla mono 12)   │  «Poemas publicados desde 2023 por las
 Poemas (Syne 700, clamp 36-56 px)                 │  integrantes del colectivo.» (serif 18, 60ch)
                                                   │  filtros GET: todos · con registro · por voz
[listado, carril ancho, filas de 64 px sobre filete de tinta al 20 %]
 24 JUL 2026 │ Umbral (Syne 26)               │ Fernanda Soto · ♫ con registro →
             │ primer verso en serif cursiva   │
 02 JUL 2026 │ Oficio de la lluvia             │ Tomás Vergara →
 …
[paginación: «1-12 de 38 poemas», números con elipsis, cajas de 44 px, aria-current]
[pie]
```

## 5. Hallazgos y recomendaciones por dimensión

Severidad: alta / media / baja. Esfuerzo: S (horas), M (días). Evidencia abreviada; el detalle de cada ítem está en los hallazgos verificados.

### 5.1 ESP · Uso del espacio y retícula

Diagnóstico: una sola medida para todo. La columna de lectura está bien; el marco, las rejillas y el cromo no tienen dónde vivir. El ritmo vertical está invertido y nada escala con el monitor.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| ESP-1 | Un solo carril de 820 px: 54 % a 1440, 41 % a 1920; tinta en 1.er viewport 33 % (home), 4,8 % (poemas) | alta | site.css:43; base.html:46,68,87,92; textExtent 780 en 20 páginas | Retícula: la columna es subdivisión del formato (Müller-Brockmann; Bringhurst §2.1.2) | Retícula de tres carriles con líneas con nombre; quitar `.wrap` de `<main>`; `.band` a `grid-column:full` con subgrid | Shape (64ch en 92 %), sinedogma (1080/680), Politico (1440/1018/640/500) | M |
| ESP-2 | Imágenes dibujadas con la altura del atributo HTML: 180×780, 249×750, 240×780 | alta | _responsive_img.html:1; site.css:276-277, 222, 282, 205; home-d1440-metrics | `aspect-ratio` solo actúa con una dimensión auto (CSS Box Sizing L4 §5) | `img,video{max-width:100%; height:auto}` + `height:auto` en las reglas con aspect-ratio; prueba Playwright de proporción | sinedogma (248×352 fija) | S |
| ESP-3 | Portada deja de escalar a 1156 px: lema topado en 104 px/512 px, hero de 532 px fijos, 0 imágenes | alta | site.css:302-305; home-d1440/w1920-view; mediaInFirstViewport 0 | Fold Manifesto (NN/g 2015); Marcotte 2011; figura-fondo | Hero en carril ancho, grid 7/5, `min-height:min(78vh,760px)`, lema `clamp(44px,7.5vw,148px)`, objeto real a la derecha | Politico 58/42, sinedogma 1.35/.65, IME foto al 60 % | M |
| ESP-4 | Índices apilan tarjetas de 780 px: Poemas enseña 2 y aparece el pie; Registros 2 placas de 780×438 | alta | site.css:130-131, 263, 195-196; poemas-d1440-view pageHeight 900 | Patrón F (Pernice 2017): primera palabra de cada fila | Poemas/Textos como filas tipográficas (12ch / 1fr / auto, paso 64 px); Registros en rejilla `minmax(380px,1fr)`; Agenda a 2 columnas | sinedogma, Shape `.eventRow`, Explora 499/624 | M |
| ESP-5 | Rejillas auto-fill encerradas en 780: integrantes 3×245, publicaciones 4×180, idéntico a 1920 | media | site.css:158-159, 273-274, 358-359, 220-221; _publication_card.html:4 (sizes 240px) | Intrinsic web design (Simmons 2018) | Rejillas al carril ancho con `minmax(220px,1fr)`: 5 columnas a 1440, cubiertas de 240-260 | Tack Shop 4×315, sinedogma 528, IME 4×287 | S |
| ESP-6 | La cinta corre en 746 px con máscaras que evidencian el recorte: 3 de 12 visibles | media | site.css:471-474, 456-458; home-d1440-s01 | Continuidad y cierre (Wertheimer 1923) | `.cinta-caja{grid-column:full}` con la retícula de ESP-1, máscaras de 96 px; sin `50vw` | sinedogma (cinta 0→1440), Tack Shop | S |
| ESP-7 | Ritmo invertido: bandas de 1000 px con 32-52 px entre secciones; portada 4077 px en ambos anchos | media | site.css:322, 127, 130, 420; bandas medidas por píxel | Proximidad (Wertheimer); Bringhurst §2.2 | Tokens `--s1..--s7`; `.home-block{padding-block:clamp(56px,7vw,112px)}`; pie con `--s6` | Explora 64/76/130, LEDUP 150, sinedogma regla+70-100 | S |
| ESP-8 | Cabecera y pie en 820: marca en x=330 (1440) y x=570 (1920); pie de 4 columnas de 180 | media | base.html:46,68,92; site.css:57-58, 358-359 | Logotipo a la izquierda (Whitenton, NN/g 2016); cromo alineado al formato (Müller-Brockmann) | Cabecera, nav y pie al carril ancho con `--gutter`; pie `minmax(220px,1fr)` | Explora x=40, LEDUP 40/75, Tack Shop pie a sangre | S |
| ESP-9 | Detalles en una columna: poema a 216 px de ancho (11 % a 1920), artículo a 85 cpl | media | site.css:177-179, 383-385; poema-w1920-view ratio 0,41 | Medida + marginalia (Bringhurst §2.1.2, cap. 8) | `.detail{grid 2fr/3fr}` con columna-ancla sticky (kicker, h1, autor, audio, medio) y cuerpo a 66ch; poema a 40ch | Shape 33/54, Politico 500, sinedogma 680 | M |
| ESP-10 | Destacado: placa azul 780×438 sin póster, ficha apilada encima | media | site.css:242-255; _player.html:10-16; home.html:32-48 | Figura-fondo (Rubin/Koffka) | `.featured{grid 8fr/4fr}` en carril ancho; póster en la placa o carátula tipográfica (hoy ningún registro tiene cartel) | Explora panel sólido, LEDUP, Politico audio | M |
| ESP-11 | Cabeceras de índice sin estructura: h1 de 12 px y el listado debajo | baja | site.css:124; once plantillas de índice | Jerarquía visual (Gordon, NN/g 2020) | Parcial `_index_head.html` a dos columnas (título / contexto + contador + filtros GET); reutiliza `.index-head h1` | sinedogma split-heading, LEDUP, Shape | S |
| ESP-12 | Nada crece con el monitor: única @media de ancho `min-width:720px`; Agenda vacía deja el 75 % en blanco | baja | site.css:91-101, 41-43, 16-24; pageHeight idénticos 1440/1920; agenda.html:12 | Responsive = escalar con el formato (Marcotte); Material «Empty states» | Raíz fluida con `clamp`, `--wide` en rem, breakpoint a 1600; Agenda vacía con «última actividad» y dossier | sinedogma clamp, Shape 6vw, LEDUP rem | S |

Precisión de la verificación: fuera del hero hay cinco titulares con `clamp(…vw…)` (site.css:126, 177, 327, 341, 384) que topan entre 840 y 941 px de viewport; a partir de ahí, nada escala.

### 5.2 TIP · Sistema tipográfico y jerarquía

Diagnóstico: jerarquía invertida, mono dominante, serif sin elegir, sin escala ni tokens. Los contrastes de rótulo sí cumplen AA (muted 5,02:1, magenta 5,12:1): el problema es de jerarquía y voz, no de legibilidad cromática.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| TIP-1 | h1 de once índices a 12 px mono gris, menor que la nav (13) y el h3 (26) | alta | site.css:124-126; once plantillas; poemas-d1440-metrics | Jerarquía visual; heurística 1 de Nielsen | `.index-head` en todos los índices, h1 `clamp(34px,4.6vw,54px)`, cejilla con `paginator.count`, línea de contexto | sinedogma 12+54, Shape .label + h1, LEDUP 14+36 | S |
| TIP-2 | Mono dominante: 113 de 163 elementos, 49 en mayúsculas (6 de 12 cadenas mono del 1.er viewport) | alta | measure_tip.out.txt; 15 reglas uppercase, 30 usos de `--mono` | Versales se leen ~13 % más lento (Tinker 1963); Bringhurst §2.1.6 | Mono solo en cejilla 12 px y meta 13 px caja baja; nav, botones, pie y cifras a Syne/serif; ≤30 % mono en portada | Explora (1/32/755), Shape (46/518), sinedogma | M |
| TIP-3 | Serif de sistema: Liberation Serif en Linux, Noto en Android, Iowan en macOS, Palatino en Windows | media | CDP getPlatformFontsForNode; site.css:22-24; plan-ui.md:55-64 | La voz de lectura debe ser la misma en todos los sistemas (Bringhurst cap. 1; CSS Fonts L4/L5) | Autoalojar serif OFL con fallback métrico; opción conforme: Noto/DejaVu antes de Times + `font-size-adjust` | sinedogma, Politico, Shape (size-adjust) | M |
| TIP-4 | Artículo a 102 cpl (18 px en 780); dek y sumarios 113-120 | alta | measure_tip (cpl); site.css:43, 385-386; articulo-d1440-view (731 px de tinta) | Medida 45-75, 66 ideal (Bringhurst §2.1.2) | `.article .body, .dek, .rec-sumario{max-width:62-66ch}`, cuerpo 19 px/1.55, dek 20 px | Politico 500, Shape 64ch, LEDUP 70ch | S |
| TIP-5 | Sin escala: 24 font-size, 10 line-height, 8 letter-spacing; cifras en serif 20 (dossier) y Syne 42 (portada) | media | grep de site.css; :208 vs :316-317; h2 de listado a 22 o 24 sin regla | Escala modular (Brown 2011; Bringhurst §3.1); Nielsen 4 | Tokens `--t-1..--t7`, 5 interlíneas, 3 trackings; cifras siempre en Syne tabular | Explora, sinedogma (tokens), Politico | M |
| TIP-6 | 28 h2 a 11 px: h2 < cuerpo < h3; rótulos no-encabezado idénticos a encabezados | media | site.css:127, 132, 360-361, 388; dossier-d1440-view | Similitud (Wertheimer); WCAG 2.4.6 pide descriptivos, la práctica pide peso | `.subhead` a Syne 600 22-26 px en caja de frase; cejilla mono separada; `.foot-group h2` a 12 | Politico píldora + entrada, Shape cejilla→tesis, IME | M |
| TIP-7 | Poema a 213 px de 780, sin sangría de continuación; salto entre estrofas de 68 px (dos interlíneas de 34,2) | media | site.css:178-179; poem_detail.html:26; poema-d1440/m390-view | Composición de poesía (Chicago Manual); Bringhurst §2.2 | `width:fit-content; margin-inline:auto`, filtro `versos` con sangría francesa, 20 px/1.5 (salto 60 px) | Shape, sinedogma (medida) | M |
| TIP-8 | Syne sin preload y con reserva serif 24 % más estrecha: el lema brinca | media | site.css:23, 32-38; base.html:36-41; shift 1121/849/977 px | Estabilidad visual; CSS Fonts L5 overrides | `<link rel=preload as=font crossorigin>`; «Syne Fallback» con `size-adjust≈114%` calculado; `--display:"Syne","Syne Fallback",sans-serif`; peso 800 en marca y lema | Shape, sinedogma, LEDUP | S |
| TIP-9 | Nueve títulos heredan 1.6: dossier h1 44/70,4 px | baja | dossier-d1440-metrics; site.css:41-42, 59, 153… | Interlínea según tamaño (Bringhurst §2.2.1) | `h1,h2,h3{line-height:1.1; text-wrap:balance}` tras body; `.brand` 1.2 | sinedogma .94/1.0/1.05, Shape | S |
| TIP-10 | Quince reglas de rótulo con seis trackings (.04-.14em) y color sin regla | baja | site.css:75-77…488-489; textos/integrantes-d1440-view | Nielsen 4; Bringhurst §2.1.6 (5-10 % uniforme) | Componente `.rotulo` + `.rotulo--acento`; un tracking para versales | Explora rótulo-firma, sinedogma tokens | S |
| TIP-11 | Sin `text-wrap:pretty` ni guionado: huérfanas y rag irregular a 45 cpl en móvil | baja | grep site.css; base.html:3 (`lang="es"`) | Rag, viudas y huérfanas (Bringhurst §2.4); CSS Text L4 | `pretty` en párrafos, `balance` en títulos, `hyphens:auto` ≤600 px salvo poema | Explora, Politico (ilustrativas) | S |

### 5.3 COL · Color, marca e identidad visual

Diagnóstico: paleta bien elegida y custodiada (prueba de contraste en CI), desplegada como paleta de interfaz. No hay símbolo, superficie de peso, tratamiento de imagen ni gesto risográfico.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| COL-1 | Magenta como color de interfaz: 45 usos (27 texto, 6 fondo, 7 borde, 4 outline); nueve piezas magenta en el 1.er viewport, dos planos (sello y CTA) | alta | site.css:44, 83-84, 132, 163, 191-194…; censo HTML (6 kicker, 22 member-role, 4 nav) | Un color, un significado (Nielsen 4); reparto 60-30-10 (convención) | Acento solo en glifo, cejilla y estados; enlaces en tinta con subrayado magenta; CTA en tinta (concilia con COL-2); ~15 reglas | Explora, LEDUP, Shape, Tack Shop | S |
| COL-2 | Sello = rectángulo magenta con la receta del botón; sin glifo, favicon, theme-color ni og:image | alta | site.css:59-65, 191-194, 308; base.html:1-42; models.py:40-47; static/ sin img | Significantes (Norman 2013); Nielsen 4 | Glifo SVG en línea de dos tintas (sin `style=`; sobreimpresión por clase), nombre en Syne sin fondo; favicon .ico/.png (un .svg en static/ rompe test_security_csp.py:49-63) o vista Django; theme-color; og_image 1200×630 | Explora emblema, Shape glifo, Tack Shop, sinedogma, IME | M |
| COL-3 | Carátula azul #1f73c7: mayor superficie de color y color huérfano (3 ocurrencias); 48-49 % del viewport en /registros/ | alta | site.css:18-21, 253-255; _player.html:10-16; contrastes 4,84 / 3,88 / 1,29 | Semejanza (Gestalt); «Photos as Web Content» (Nielsen 2010) | Póster con duotono, placa tipográfica sin póster (caso por defecto hoy), azul como segunda tinta de la familia | Explora, IME, Politico audio | M |
| COL-4 | Bandas blancas al 50/50 (2015 px papel / 2056 blanco) a 1,25:1; cajas blancas con borde a 1,17:1 sobre papel; ninguna superficie de tinta | alta | site.css:319-324; muestreo x=6 de home-d1440-full; home.html:32,74,127 | Región común y figura-fondo (Palmer 1992); bandas (Explora, Politico, Shape) | Cuatro superficies (paper, paper-2, ink, white solo objetos); orden de portada con dos bandas de tinta; quitar fondo blanco y borde a `.next-event`, `.milestone`, `.event-date`, `.dossier-contact`, `.reviewed` (`.featured-poem` es CSS muerto) | Explora, Politico, Shape, Tack Shop, LEDUP | M |
| COL-5 | Gramática de app: 19 bordes de 1 px, 29 radios, avatares circulares con inicial (9 de 12 en la demo, de relleno) | media | site.css:165-168, 197, 205, 219, 222…; integrantes-d1440-view | Tarjeta sin cromo; consistencia con el medio citado | `--r:0` salvo campos; sin borde en imágenes; avatares 4:5 o cuadrados; etiquetas sin píldora; filetes de tinta al 20-25 % | Explora, sinedogma radio 0, Shape, Politico medallón | S |
| COL-6 | El amarillo #fce43c excluido por contraste, pero como superficie con tinta da 13,81:1 | media | site.css:12-13; contrastes; test_contraste_paleta.py:75 | 1.4.3 evalúa pares; contraste simultáneo (Albers) | `--riso-amarillo` solo como fondo (cifras, sticker, duotono); añadir pares a la prueba | Tack Shop, Politico, Explora | S |
| COL-7 | Sin tratamiento de casa: 0 filter, 0 mix-blend-mode; avatares lila, portadas grises, fotos de evento (además deformadas por ESP-2) | media | site.css completo; _member_card.html:4-8; csp.py:37-38 | Semejanza; dirección de arte por sistema | `.riso-duo` con `isolation:isolate`; hover revela con `filter:none; mix-blend-mode:normal`; excluir obra ajena | IME, Politico, Explora | S |
| COL-8 | 21 páginas con cuerpo celeste sin firma de sección ni cierre; `.band` solo en home | media | metrics bodyBg; site.css:420-421, 124, 127, 302, 314, 340; base.html:110-154 (cuatro grupos) | Nielsen 1 y 4; cabecera de sección + cierre (Explora, Politico, Shape) | Firma por territorio (La obra: magenta; El colectivo: azul; Prensa y gestión: tinta); pie en tinta con enlaces papel; verso de cierre; «Seguir» a muted | Explora, Politico, Shape, Tack Shop, IME | M |
| COL-9 | Ningún rasgo material de la risografía (sobreimpresión, desregistro, grano, troquel) | baja | site.css:6-9; 0 svg; csp.py:37 | Identidad por dispositivos repetibles (Wheeler) | Multiply en solapes, un desregistro por página, grano al 5-8 %, 2-3 stickers SVG en línea sin animación | Tack Shop stickers, Politico adornos, Shape multiply | M |
| COL-10 | Nueve pares custodiados, ninguno prohibido: magenta/tinta 2,78, azul/papel 3,88, muted/azul 1,29 | baja | test_contraste_paleta.py:59-84; site.css:401 (paginación 1,17) | WCAG 1.4.3 y 1.4.11 por par; tokens con matriz | Matriz de pares permitidos y prohibidos en `:root` y en la prueba; `--accent-on-ink`; paginación inactiva a muted | Explora (error a evitar), LEDUP, sinedogma | S |
| COL-11 | 15 hovers cuyo único cambio es «→ magenta», 3 por opacidad; sin `aria-current` | baja | site.css:81,141,145,155…492; 259, 309, 417 | Nielsen 1; microinteracciones como marca (Saffer 2013) | Gramática: subrayado 1→2 px y tinta en enlaces, inversión en botones, fondo paper-2 en filas; `aria-current` desde base.html | sinedogma (CSS real), IME | S |

### 5.4 IMG · Imagen, medios y dirección de arte

Diagnóstico: la capa de imagen no es sobria, está vacía, y donde hay foto está rota. El modelo guarda más imagen de la que las plantillas muestran.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| IMG-1 | `height` HTML anula `aspect-ratio`: 180×780, 249×750, 240×780 deformada | alta | _responsive_img.html:1; site.css:276-277, 222, 282, 205; cinco plantillas | width/height exigen `height:auto` (Pollard 2020); Box Sizing L4 | `img{max-width:100%; height:auto}` + prueba Playwright | sinedogma 1:1,42 | S |
| IMG-2 | Carátula click-to-play azul plano 780×439; `Recording.poster` solo en `<video>` y OG | alta | _player.html:10-16; site.css:245-255; embeds.js:25-27 (vacía el contenedor) | Nielsen 1 y 6; «Photos as Web Content» | Póster en la placa (lazy=False, velo para 4,5:1), fallback foto del evento, luego carátula tipográfica; nunca img.youtube.com (CSP y privacidad); audio con póster 1:1 | Explora póster, Politico audio, Tack Shop | M |
| IMG-3 | Cero imágenes en el 1.er viewport; la primera a 1437 px | alta | home-d1440-metrics; home.html:4-29; site.css:302-305; plan-ui.md «Fotos reales» | Primera impresión en 50 ms (Lindgaard 2006); figura-fondo | Hero 3fr/2fr con un objeto real elegido en la vista (cubierta > póster > foto duotono), LCP con width/height; móvil: lema primero | Politico 58/42, IME, sinedogma, Shape | M |
| IMG-4 | Avatares de 72 px con inicial (demo de relleno) y retrato al 15 % de su asset de 480 | media | site.css:165, 168, 480, 158-159; _member_card.html | Similitud; atención a rostros (Djamasbi 2010); avatar con inicial = «cuenta anónima» (Material) | Retrato 4:5 a tope, nombre Syne 20-24, duotono, fallback monograma o primer verso; pedir retratos | IME, Politico, sinedogma | M |
| IMG-5 | Sin dirección de arte: cuatro lenguajes visuales en cuatro pantallas | media | capturas home s01/s03, evento, integrante; site.css sin filter | Similitud y continuidad; Nielsen 4 | Duotono, trama, gesto (rotate + sombra plana), sticker por sección; exclusión de obra ajena; una tinta por pantalla | IME, Politico, Explora, Tack Shop | M |
| IMG-6 | Cubiertas a 150-180 px con filete, no como objetos; detalle a 240 sola sobre la sinopsis | media | site.css:273-277, 282; publication_detail.html:27-29 | Figura-fondo; producto grande y nítido | `.pub-grid minmax(220px,1fr)`, tarjeta-objeto con sombra plana, detalle a dos columnas con cubierta de 360 | sinedogma, Politico 4:5 | S |
| IMG-7 | `Article.cover_image` y `Work.cover_image` solo en og:image, nunca en pantalla | media | article_detail.html:10-28; _article_card.html; reviews/models.py:64; mediaCount 0 | Nielsen 4 (la vista previa promete lo que la página no entrega); convención de reseña | `<figure>` 3:2 entre meta y cuerpo; `.reviewed` como ficha con cubierta 5:7 a 140; miniatura 3:4 a la derecha en listados cuando exista | sinedogma (caveat literal), Explora | M |
| IMG-8 | `Event.poster` ausente en agenda, «Próxima actividad» y trayectoria | media | _event_card.html; home.html:61-71; event_detail.html:54-56; seed sin póster | Nielsen 6; proximidad | Tarjeta 64px/128px/1fr con póster 4:5; miniatura en trayectoria; detalle como objeto con pie y crédito | Tack Shop, LEDUP, Explora | M |
| IMG-9 | Galería: miniatura de 249 px, pies a 12 px, `MediaAsset.credit` nunca se muestra (17,79:1 en el lightbox) | media | site.css:220-239; gallery.html:15; grep credit = 0 | 1.1.1 cumplido por el alt; crédito es convención editorial; 1.4.3 para el pie | Hoja de contactos 2fr/1fr, filas 3:2, crédito en pie y lightbox, figcaption 13-14 px, contador | Explora, sinedogma, Shape | M |
| IMG-10 | Estados vacíos genéricos: una línea en Agenda, «LIBRO» en caja 5:7, inicial en círculo | media | agenda-d1440 pageHeight 900; site.css:146, 278-279, 166-167; gallery.html:22; partner_index.html:20 | Estado vacío que explica y ofrece acción (NN/g; Nielsen 1 y 10) | Agenda: última lectura + póster + «Avísame» + Instagram + 3 pasados; sobrecubierta tipográfica; galería/aliados con enlace | sinedogma, Explora | S |
| IMG-11 | No existe el checklist de fotos reales de plan-ui.md | media | plan-ui.md «Punto 5»; docs/ sin el archivo; media/models.py listo; seed sin póster/cover/logo | Diseño con contenido real (McGrane 2012) | `docs/contenido-visual.md` con pedido por pieza y formatos | Explora, sinedogma, IME | S |
| IMG-12 | Aliados sin logo: `.partner-logo` a 64 px; sin franja en portada | baja | aliados-d1440 mediaCount 0; models.py:206-208; site.css:294-295; §6.1 ítem 7 | Credibilidad por afiliación (Fogg 2002); Nielsen 6 | Logos 160×80 en gris con hover a color, agrupados por tipo; franja «Con el apoyo de»; fallback tipográfico | sinedogma, Explora | S |

### 5.5 POR · Portada: narrativa, jerarquía y conversión

Diagnóstico: sigue el orden de §6.1 pero no cuenta la historia que cada audiencia necesita; el titular es una categoría, no hay un verso, el bloque fotográfico sale deformado y las llamadas no forman sistema.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| POR-1 | 1.er viewport sin lugar, año ni contacto; el hero no cae a `general_email` como sí hace el pie; correo a ≈4.015 px (a un clic en el dossier) | media | home.html:15-20; base.html:137-141; models.py:16-18; tarea-identidad §3 | Fogg 2002 directrices 2 y 5; Nielsen & Tahir 2001 | Línea mono «Chile · desde 2023 · 12 integrantes · @instagram» (count en la vista, no `members\|length` acotado a 16); `elif general_email`; pedir ciudad para `location` | sinedogma colofón, Shape esquinas, IME y LEDUP (a evitar) | S |
| POR-2 | Titular de 104 px = categoría; nombre a 24 px en el sello; 260 px vacíos dentro de la columna y 0 imágenes | alta | home-d1440-metrics; site.css:298-304; home.html:9-13; tarea-identidad §3 (manifiesto provisional) | Nielsen & Tahir directrices 1-3; jerarquía por peso visual (Lidwell; Arnheim) | Vía A: h1 visible «Repitentes del Verso» 56-112 px con el lema como cejilla; vía B: lema como titular solo cuando sea una afirmación propia; en ambas, hero 1.35fr/.65fr con objeto | Shape, sinedogma, LEDUP, Politico, Explora (advertencia) | M |
| POR-3 | Ningún verso en 4077 px; «Textos recientes» (3 reseñas, 1 ensayo, 1 entrevista, libros de integrantes) ocupa el 22,6 %; registro manda sobre poema (decisión plan-ui UI-1) | media | home.html:118-124, 31-59; views.py:71-76, 83; home-d1440-full | Priorizar lo que ofrece valor (Nielsen & Tahir, directrices 3-4) | Bloque «Poemas» (3 filas tipográficas con 3 versos, +1 consulta, 16→17 de techo 24); Textos a 3 con kicker descriptivo; opción bento registro + poema del mes | sinedogma, Shape, LEDUP, Politico | M |
| POR-4 | Cubiertas a 180×780 (1:4,3): +528 px en escritorio, ≈1.100 en móvil | alta | home-d1440-metrics; site.css:276-277, 282; home-d1440-s03/s04; publicaciones-d1440-view | Fogg 6 y 10 (aspecto profesional, sin errores); Box Sizing L4; HTML presentational hints | `img{max-width:100%; height:auto}`; `.avatar` conserva su alto por especificidad; prueba manual 5:7 | sinedogma, Explora, Politico | S |
| POR-5 | Tres CTA con tres estilos, dos a /dossier/, «Descargar» entrega HTML; cinco «ver todos» con cuatro estilos | media | home.html:13, 16, 26, 48, 105, 122, 134; site.css:44, 143, 191-194, 206-207, 308, 488 | Nielsen 2 y 4; information scent (Pirolli & Card 1999) | Etiqueta por estado («Ver el dossier» sin PDF); «Conócenos» a /integrantes/; un primario por pantalla + enlace-fila único; CTA de contorno «Enviar un texto» | sinedogma, LEDUP, Shape, Tack Shop | S |
| POR-6 | Títulos de sección a 11 px (`.subhead`, decisión plan-ui.md:36-37; usada en 11 plantillas, 8 en el dossier) | media | site.css:127, 132, 83; home.html:75, 120, 128; home-d1440-s01 | Patrón F (Pernice 2017); similitud; escala modular (Brown) | Fila kicker 12 px + h2 Syne `clamp(28px,3vw,40px)` + «Ver todos ↗»; acotar a `.home-block > .subhead` para no tocar el dossier | sinedogma, IME, LEDUP, Tack Shop (a evitar) | S |
| POR-7 | Mayor elemento visual = placa azul vacía en una columna; el destacado sembrado no tiene póster | media | home-d1440-view/s01; _player.html:10-16; media/models.py:219; site.css:245-260 | «Photos as Web Content»; Fogg 6; 1.4.3 para texto sobre carátula | Póster + panel sólido abajo-izquierda para botón y aviso (no velo del 35 %); carátula tipográfica sin póster; `.featured{grid 1fr/1.6fr}` | Explora panel sólido, Politico, LEDUP, IME | M |
| POR-8 | Prensa y aliados retirados de la portada (240921a, razones técnicas; test_catalog lo fija) aunque §6.1 ítem 7 los pide; el contenido existe | media | commit 240921a; arquitectura-contenidos.md:177; prensa/aliados-d1440-view; site.css:288-296 (`.home-quote cite` y `.partners-strip .meta` huérfanas) | Fogg 1 y 3; prueba social (Cialdini) | Línea de respaldo compacta bajo las cifras: cita más reciente + «Con el apoyo de»; 2 consultas (16→18); invertir la aserción | sinedogma, Shape, Politico, LEDUP | S |
| POR-9 | Cifras 3·4·3 omiten integrantes y festival, no enlazan a su prueba | media | home.html:21-27; services.py:14-26; dossier.html:44; site.css:314-317 | Fogg 1 | «12 integrantes · 4 actividades · 1 festival · 3 publicaciones · desde 2023», cada `<strong>` enlazado; < 3 → nombres; etiqueta desde `Event.type`, no «lecturas» | LEDUP, Politico, sinedogma, Shape | S |
| POR-10 | Nada dice si el colectivo está activo: sin próximo evento no hay bloque; último evento pasado («Recital de invierno», 10 sep 2026) no aparece | media | home.html:61-71; views.py:87; agenda/models.py:46, 68-70; site.css:210-213 | Fogg 8 (contenido actualizado) | `last_event = Event.past().first()` en el mismo bloque; «Actualizado el 24 jul 2026 · …» calculado en la vista de portada (no en base) | Shape REVIEWED, sinedogma | S |
| POR-11 | Cinta: 3 de 12 visibles, nombres cortados en móvil (1,2 tarjetas), sin cifra; 72 s por vuelta | media | home-d1440-s01; home-m390-s01; site.css:456-480, 440-447; integrantes-d1440-view (los 12 caben en 900 px) | Continuidad y cierre; carruseles automáticos (Nielsen 2013); WCAG 2.2.2 | Título con cifra; ≤720 px fila con scroll-snap sin máscara (el fallback ya existe para reduced-motion); retratos 4:5 160×200; 5 visibles con carril ancho | sinedogma, IME, Politico, Tack Shop peek | M |
| POR-12 | Kickers redundantes «RESEÑAS · RESEÑA»; todos «1 min» | baja | _article_card.html:3; home-d1440-s01/s02 | Nielsen 8 | `Article.kicker()` en el modelo; «RESEÑA · 4 MIN» o «RESEÑA · obra reseñada» con prefetch | Explora, Shape | S |
| POR-13 | Ritmo sin alternar (dos blancos seguidos), franja celeste vacía de ≈42 px antes del pie, fila de cubiertas al 74 % de la columna | baja | home.html:32,74,119,127; site.css:322-324, 420; home-d1440-s03/s04 | Región común (Palmer 1992); proximidad | Alternancia estricta; `main > .band:last-child{margin-bottom:-40px; padding-bottom:72px}` (`.band + .site-foot` no casa: no son hermanos); mostrar las 4 cubiertas o `auto-fit` | Explora, Politico, LEDUP, sinedogma | S |

### 5.6 NAV · Navegación y arquitectura de información

Diagnóstico: arquitectura sólida (21 rutas, mapa del pie en cuatro grupos, skip link, landmarks, sin JS) que la cabecera no representa; sin señal de ubicación; detalles sin salida; overlay de búsqueda fuera de pantalla en móvil.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| NAV-1 | «Textos» y nueve rutas de gestores solo en el pie (a 3774 px de 4077); barra fijada en cuatro por test_ia.py | alta | base.html:70-75, 110-154; test_ia.py:24-54; commit bb70bb9 | Information scent; Nielsen 6; pie como red de seguridad («Footers 101») | Cinco enlaces + CTA «Dossier»: Poemas · Textos · Registros · Publicaciones · Colectivo (con sub-fila mono); actualizar NAV_PRINCIPAL manteniendo la aserción exacta | Explora 6+2, sinedogma 4+CTA, LEDUP, Shape | S |
| NAV-2 | Sin acción para gestores en la cabecera; hero sin fallback de correo; mailto del pie sin affordance (sin subrayado) | alta | base.html:45-77, 137-141; home.html:17-19; dossier.html:106-114 sin id; arquitectura:167 (/contacto/ no existe) | Fitts (1954); Nielsen 7 | `<a class="btn btn-primary" href="/dossier/#contacto">`; `id="contacto"`; fallback en el hero | Explora, sinedogma, LEDUP, IME, Politico | S |
| NAV-3 | Overlay de búsqueda en móvil desde x=-111 (títulos cortados); /buscar con dos campos y controles nativos | alta | site.css:116-117, 66-68; home-m390-search-overlay.png; search.html:7-12 | WCAG 1.4.10 Reflow; Nielsen 4 | `@media (max-width:719px){#search-results{left:0; right:auto; width:100%}}`; fila «Ver todos»; /buscar con `.index-head` y `.btn`; ocultar el campo de cabecera en esa ruta | Explora, sinedogma | S |
| NAV-4 | Buscador siempre visible, segundo elemento del cromo, solo indexa Article y Poem; placeholder «Buscar textos…» | media | views.py:218-231; base.html:52-62; site.css:66-68 | Nielsen 8; «Search Is Not Enough» (Budiu 2014); 2.4.5 no exige campo abierto | Opción A: `<details>` con lupa + cobertura de Contributor, Recording, Publication, Event; opción B: campo de 180 px en la fila de nav tras el CTA | Explora, Politico, LEDUP, Tack Shop, sinedogma | M |
| NAV-5 | Sin «estás aquí»: 0 `aria-current`, sin migas, detalles sin enlace al índice; cuatro estilos de h1 | media | grep aria-current; site.css:83-85, 124; poem/article/member/event_detail; dossier.html:14-28 | Nielsen 1; migas (Laubheimer 2018); 2.4.6, 2.4.8; aria-current | Context processor + `.nav a[aria-current]`; kicker como miga de 1-2 niveles; dossier con kicker «Dossier · kit de prensa» y la barra de impresión tras la cabecera | Shape, IME, LEDUP, Tack Shop | S |
| NAV-6 | Cabecera estática de dos filas: 120 px escritorio, 164 móvil (19 %), 223 con menú abierto; desaparece al desplazar | media | site.css:57-58, 82, 100; headerPosition static; home-m390-view; base.html:103-108 | Cabeceras sticky compactas (Laubheimer 2020); región común (Palmer 1992) | Una fila sticky de 64 px (sello 36 px + nav + lupa + CTA); ≤720 px fila de 56 con `<details>` en capa absoluta | sinedogma 56, Shape 64, Explora 95→62; IME y Politico (a evitar) | M |
| NAV-7 | Menú móvil: summary de 12 px gris, cuatro enlaces de 21 px como texto corrido (en el límite de 2.5.8 por la excepción inline) | media | site.css:75-77, 82-90; home-m390-menu-open.png | 2.5.8 con excepciones; HIG 44 pt; Material 48 dp; navegación oculta (Pernice & Budiu 2016) | Enlaces en bloque de 16 px con `padding:12px 0` y filete; summary de 44 px en tinta; parcial `_mapa.html` dentro del `<details>` | Explora, LEDUP, sinedogma (a evitar) | S |
| NAV-8 | Pie empieza por el formulario, sin identidad, rótulos distintos de los títulos de destino, paso de 21 px | media | base.html:91-161; site.css:420-421, 363, 365; submit.html:8-9; partner_index.html:8 | Nielsen 4; 2.4.4 Link Purpose; 2.5.8; «Footers 101» | Identidad primero (sello + ficha + correo como enlace), grupos, newsletter en una línea, legal; `.foot-group a{padding:4px 0; font-size:15px}`; rótulos unificados | Shape, Tack Shop, sinedogma, LEDUP (a evitar) | S |
| NAV-9 | Detalles sin salida: poema enlaza a YouTube (↗, _blank) en vez de la ficha del registro; integrante sin eventos; evento sin agenda | media | poem_detail.html:28-39; member/event/publication/recording_detail; enlaces en `<main>`: poema 2, dossier 1, agenda 1 | Forrajeo; navegación persistente (Krug); 2.4.4 (↗ promete externo) | `rec.get_absolute_url`; parcial `_pie_de_entidad.html` con dos puertas; «Actividades» en integrante, «Reseñas sobre…» en publicación, «Poema registrado» en registro | sinedogma flechas, Shape puertas, Explora | M |
| NAV-10 | Lenguaje: kickers duplicados, «Registros» ambiguo, «Textos» vs «Publicaciones» sin frontera, tres nombres para /enviar/ | media | _article_card.html:3; base.html:72, 120-128, 136, 53; submit.html:8-9 | Nielsen 2; 2.4.6; information scent | Kicker solo si difiere; descriptores («Audio y video», «Reseñas y ensayos», «Libros y plaquettes»); «Enviar una propuesta» en los tres sitios; frase de apoyo bajo cada h1 | Explora, sinedogma, Tack Shop (a evitar) | S |
| NAV-11 | Portada sin enlace a agenda, prensa, aliados, galería ni convocatorias; dos rótulos al dossier | media | home.html; commit 240921a; test_catalog.py:62-68; arquitectura §6.1 | Etiqueta describe el destino (NN/g 2015); Nielsen & Tahir | Banda de cierre «Para programadores y prensa»: cuatro puertas + cita; CTA condicional; «Agenda →» junto a trayectoria | Shape, Explora, LEDUP, IME | S |
| NAV-12 | Diez plantillas titulan la pestaña con el sufijo «Reseñas» | baja | article/contributor/section/tag/page_detail, submit, submit_thanks, reviews/publisher/bookauthor/work_detail (:3) | Nielsen 4 | `{{ site_profile.name\|default:"Reseñas" }}` + prueba que recorra rutas públicas | Shape | S |

### 5.7 CON · Páginas de contenido, índices y móvil

Diagnóstico: un solo molde (columna de 780, kicker de 11, título y texto apilados) que sirve para leer un poema y no para presentar al colectivo; móvil con 19 % de cromo y 42 de 58 objetivos por debajo de 24 px.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| CON-1 | Portadas y galería a su altura intrínseca; publicaciones 2524 px en móvil | alta | _responsive_img.html; site.css sin `height:auto`; getBoundingClientRect | Pollard 2020; MDN responsive images | `img,video{max-width:100%; height:auto}` junto al reset (site.css:40) | sinedogma, Politico | S |
| CON-2 | Once índices con h1 de 12 px y sin introducción; `.index-head` existe y no se usa en índices | alta | site.css:124-126; metrics h1 12 px ×11; submit/member/publication/event_detail usan `.index-head` | Patrón F; Nielsen 1; escala monotónica | `.index-head` con cejilla de dato vivo, h1 `clamp(36px,5vw,56px)`, dek de 60ch para gestores; `padding:40px 0 16px` | sinedogma, LEDUP, Shape, IME | S |
| CON-3 | Artículo a 101-102 cpl; poema a 216 px (11 % a 1920) | alta | Range API; site.css:43, 385, 178, 305; poema-w1920 0,41 | Bringhurst §2.1.2; línea óptima (Baymard) | Paso 1: `max-width:66ch`; paso 2: `.lectura{grid minmax(240px,1fr)/minmax(0,66ch)}` con columna-ancla (kicker, h1, autor con avatar, audio, cover_image) | Shape 33/54, Politico 500, sinedogma 680, LEDUP 70ch | M |
| CON-4 | Fichas de integrante, publicación y evento: medio pequeño apilado (104 px, 240 px, póster tras la cabecera) | media | site.css:165, 168, 282, 158-159; member/publication/event_detail; integrante 1675 px | Proximidad y región común (Palmer 1992); «Photos as Web Content» | `.ficha-head{grid minmax(200px,320px)/1fr}` en los tres; rejilla de integrantes 4 por fila con retrato 4:5; cubiertas 260 | Politico, IME, sinedogma, Explora | M |
| CON-5 | Placa azul 780×439 sin póster, título ni duración; /registros/ es una pila de placas (2 = 1262 px) | media | site.css:245-255; _player.html; recording_index.html:11-13 | Significantes (Norman); Nielsen 6; «Video Usability» (Schade 2014) | Póster en la placa o placa tipográfica; en índice y móvil, tarjeta con miniatura 16:9 de 360 + título + meta; reproductor solo en detalle | Tack Shop, LEDUP, Politico | S |
| CON-6 | Móvil: cabecera de 164 px (19 %), sello igual al botón, cinta con 1,2 tarjetas y nombres cortados sin forma de pararla | media | getBoundingClientRect 390; site.css:59-65, 308, 474, 443-444, 499-502 | Contenido antes que cromo; carruseles automáticos (Nielsen 2013); Nielsen 4; 2.2.2 | Cabecera de una fila de 56-64 px; sello y botón diferenciados; ≤720 px cinta en fila con scroll-snap (misma regla que reduced-motion), sin añadir pausa | sinedogma, Tack Shop, LEDUP, Explora (a evitar) | M |
| CON-7 | 42 de 58 objetivos de la portada por debajo de 24 px (sin infringir 2.5.8 por excepciones); nueve reglas a 11 px sin media query | media | Playwright 390; site.css:83, 362-363, 391-392, 396-402, 127-488 | 2.5.8 (AA) y 2.5.5 (AAA); HIG 44; Material 48; Fitts | `.nav a{padding:10-12px 0}`, pie 15 px con padding, `.tag` 12 px/8×12, paginación 44 px; subir las nueve reglas a 12-13 px | Explora, Shape, Tack Shop (a evitar) | S |
| CON-8 | Dossier: cifras a 20 px (acotado «a propósito», site.css:310-313), trayectoria en desorden (2022, 2019, 2026…), sin fotos ni cubiertas | media | dossier-d1440-full; site.css:206-208; dossier.html:51-86; views.py:54-55 | Numerales (Nielsen 2007); continuidad; Nielsen 4 | Cifras Syne 36-56 solo en `.dossier-doc`; una cronología única ordenada en la vista; integrantes con avatar 96 px; cubiertas 120 px; bloque «Ficha» con fecha de actualización | Politico, LEDUP, sinedogma, Shape | M |
| CON-9 | Agenda vacía: 900 px con una frase; tarjetas sin póster | media | agenda.html:8-14; views.py:9-10; _event_card.html; site.css:196-204 | Estado vacío que orienta (Material; Nielsen 1) | `recent = Event.past()[:3]`, cabecera de índice con dek para gestores, botones de contacto y dossier, `.event-thumb` 4:5 a 120 px | Tack Shop, sinedogma, IME (a evitar) | S |
| CON-10 | Paginación de 12 px sin números ni total, inactivo a 1,17:1 | baja | site.css:396-402; _poem_list.html:9-23; Paginator 12 | Nielsen 1; paginación citable (Loranger 2014); 2.5.8 | Parcial `_pagination.html`: «1-12 de 38», `get_elided_page_range`, cajas de 44 px, `aria-current`, `rel`, inactivo en muted o omitido | Explora «1 - 12 of 38», Shape | S |

### 5.8 COM · Componentes, estados, motion y accesibilidad

Diagnóstico: bien resuelto en lo semántico (skip link, foco global, click-to-play con noscript, `<details>`, reduced-motion) y mal terminado en lo visible. Lo más grave: la pausa de la cinta, premisa de la decisión de no poner botón, no funciona.

| Id | Hallazgo | Sev. | Evidencia | Principio (fuente) | Recomendación | Referencia | Esf. |
|---|---|---|---|---|---|---|---|
| COM-1 | La cinta no se detiene con hover ni foco: el enlace extendido de `.cinta-pie a::after` cubre la pista y `.cinta:hover` nunca se cumple; con reduced-motion no se desplaza con rueda ni dedo (overlay en la cadena) y hay 24 tarjetas (12 duplicadas) | alta | site.css:490, 483, 449, 440-447; verify.js A1-A3, B1-B5; com-cinta-hover.png | WCAG 2.2.2 (A), 2.1.1 (A); Nielsen 3 | (1) `.cinta-caja:hover .cinta-pista, .cinta-caja:focus-within .cinta-pista{animation-play-state:paused}`; (2) bajo reduced-motion, overlay solo en la fila del enlace, duplicados ocultos, scroll-snap; (3) checkbox + `:has()` como pausa sin JS, o carrusel por scroll-snap sin animación | sinedogma («durdur» + fallback), LEDUP, Tack Shop (a evitar) | S |
| COM-2 | Cinco botones, sin transición, hover por opacidad: el CTA baja de 5,12 a ≈4,7:1 (sigue en AA) y mide 37 px | media | site.css:191-194, 308-309, 415-417, 256-259; buscar botón Arial; 4 transition / 30 hover | Nielsen 4 y 1; 100-500 ms (NN/g 2020); 44 pt / 48 dp | Componente único con variantes, hover por color sólido (#96055a, 8,5:1 con blanco) o inversión, `min-height:44px`, 14 px | sinedogma, Tack Shop, LEDUP | M |
| COM-3 | Encabezados invertidos (h1 12 / h2 11 / h3 26); /buscar y /enviar con otros patrones | alta | site.css:124, 127, 360-361; metrics; search.html:7; submit.html:7-9 | Jerarquía visual y patrón F; similitud; Nielsen 4 (no 1.3.1 ni 2.4.6) | `.index-head` en los once índices; `.subhead` como fila kicker + h2 Syne; `.foot-group h2` a 12; search con `.index-head` | sinedogma, Shape, LEDUP, IME | M |
| COM-4 | Placa azul vacía y anillo de foco magenta a 1,32:1 sobre azul | media | _player.html:10-16; site.css:242-260, 111-113; com-focus-embed-play.png | 1.4.11 (3:1 en foco), 2.4.7; Nielsen 6 | Póster con velo multiply, botón circular de 64 px, foco blanco (4,84:1) con `outline-offset`, `aria-describedby` | Politico, LEDUP, IME | M |
| COM-5 | Overlay de búsqueda no se cierra al perder el foco y tapa la nav; sin «ver todos»; /buscar sin estilo | media | verify2.js E2; site.css:116-119; base.html:52-62; _search_results.html | Combobox APG (se cierra al perder foco); 2.4.11; Nielsen 1, 3, 4 | `.search:not(:focus-within):not(:hover) #search-results{display:none}` (el `:not(:hover)` evita que Safari cierre antes del clic); contador + «Ver todos»; `minlength=2`; trigger `input` | sinedogma, Explora | S |
| COM-6 | Sin tokens: 4 transiciones para 30 hovers, cinco radios, bordes a 1,17:1; reduced-motion solo apaga la cinta | media | site.css:70, 106, 451, 491; radios; :499-502 | Nielsen 1 y 4; Gestalt; 1.4.11 cuando el borde identifica; 2.3.3 (AAA) | `--r-1:3px; --r-2:5px; --dur-fast:140ms; --dur-base:220ms; --ease`; `--line:#9fbfe0` (1,53:1, solo decorativo) y `--edge:#5e7ea7` (3,35:1); regla única de transición; bloque global reduced-motion | sinedogma, Shape, LEDUP | S |
| COM-7 | En tarjetas solo el título es pulsable (`.kicker a` 56×13, `.meta a` 159×15, exentos por inline) | media | _article_card.html:2-9; _poem_card.html; site.css:131, 139-141 | Fitts; Nielsen 1; Inclusive Components «Cards» | Enlace extendido con `::after`, secundarios con z-index y padding, estado de fila y `:has(:focus-visible)` | Explora, Shape, sinedogma | S |
| COM-8 | Paginación: inactivo a 1,17:1 como `<span>`, enlaces de 12 px sin área; defecto latente (hoy nada pagina) | baja | site.css:396-402; parciales | 1.4.3 (span no es control), 2.5.8; Nielsen 1 | Cajas de 44 px, `visibility:hidden` o `aria-disabled` en muted, «Página 2 de 4 · 38 textos», `rel` | Explora, sinedogma (a evitar) | S |
| COM-9 | Formulario: etiquetas de 12 px en mayúsculas, asterisco sin leyenda, sin `autocomplete`, `aria-describedby` en 1 de 6, `novalidate` | baja | site.css:407-408, 415-417, 354; submit.html:17, 27-29; HTML servido | 3.3.2, 1.3.5, 3.3.1; Nielsen 5 | Etiquetas 14 px en caja de frase y tinta; leyenda; `autocomplete=name/email`; `as_field_group` si Django ≥5; botón `.btn`; textarea 220 px | sinedogma, Tack Shop (a evitar) | S |
| COM-10 | Syne sin preload y reserva serif: `.brand` 231→292 px, lema 676→780 (FOUT horizontal, CLS≈0) | baja | site.css:32-38, 23; base.html:36-40; verify2.js C1-C3 | Carga de fuentes (web.dev); Nielsen 4 | Preload, «Syne Fallback» con overrides calculados, subconjunto latino (34,6 → ≈18 KB); opcional mono y serif OFL (≈40 KB) | Shape, LEDUP, sinedogma | S |

## 6. Página por página

**Portada.** Hero en carril ancho 7/5 con nombre o lema (según la decisión de §9) y un objeto real; línea de ficha (Chile · desde 2023 · 12 integrantes · Instagram) y botón «Escríbenos» con fallback a `general_email`; cifras enlazadas con integrantes y festival, etiqueta por tipo de evento; línea de respaldo (cita + «Con el apoyo de»). Destacado en banda de tinta 8/4 con póster o carátula tipográfica, botón en panel sólido. Bloque Poemas (3 filas con versos). Integrantes con cifra en el título y cinta a sangre de retratos 4:5, en móvil fila con scroll-snap. Textos a 3 ítems con kicker descriptivo y sin «RESEÑAS · RESEÑA». Publicaciones con las 4 cubiertas 5:7 a 240 px. Cierre «Para programadores y jurados» con cuatro puertas y última actividad. Secciones con `padding-block:clamp(56px,7vw,112px)`, alternancia estricta de superficies, sin franja vacía antes del pie.

**Índices (poemas, textos, integrantes, registros, publicaciones, agenda, trayectoria, galería, prensa, aliados, colecciones).** `.index-head` en carril ancho a dos columnas: cejilla con dato vivo, h1 Syne 36-56 px, frase de contexto para gestores y, donde aplique, filtros GET. Poemas, Textos, Trayectoria y Prensa como filas tipográficas de 64 px; Textos alterna miniatura 3:4 cuando hay `cover_image`. Integrantes a 4-5 columnas con retrato 4:5 a tope y toda la tarjeta enlace. Registros en rejilla de miniaturas 16:9 con título y meta (reproductor solo en el detalle). Publicaciones con cubiertas-objeto de 240-260 px. Agenda con tarjetas 64px/128px/1fr con póster y, vacía, última lectura + contacto + dossier + tres pasados. Galería como hoja de contactos 2fr/1fr con crédito. Aliados con logos 160×80 agrupados. Paginación con contador, números y cajas de 44 px. `aria-current` en la nav.

**Poema.** Sala de lectura: columna-ancla (kicker como miga «Poemas», h1, epígrafe, autora con avatar de 56 px y enlace, fecha, «Escuchar en el registro →» interno con `<audio>` nativo cuando exista, etiquetas) y columna de versos a 20 px/1.5, `width:fit-content`, sangría francesa para versos partidos, salto entre estrofas de 60 px; sin guionado. Pie de entidad: «← Todos los poemas» y «Más de {autora}».

**Artículo / reseña.** Cuerpo a 66ch, 19 px/1.55, `text-wrap:pretty`, guionado en móvil; dek a 20 px; columna-ancla con `cover_image` 4:5 o, en su defecto, ficha «Obra reseñada» con la cubierta de `Work.cover_image` a 140 px, autor con medallón, fecha, tiempo de lectura; kicker «RESEÑA · 4 MIN»; miga «Textos › Reseñas»; título de pestaña con el nombre del colectivo; notas al pie reales cuando las haya; puertas de cierre.

**Integrante.** `.ficha-head` con retrato 4:5 a 240×300 (duotono en listados, original aquí) y, al lado, kicker-miga «Integrantes», nombre, rol, bio y enlaces; debajo poética, trayectoria, poemas, registros y una sección «Actividades» (`Event.participants`); rejilla de obra en carril ancho.

**Registro.** Placa con póster o carátula tipográfica, botón ▶ circular con foco blanco, nota de privacidad en panel sólido; ficha al lado (evento, fecha, ciudad, participantes, duración); «Poema registrado» y «Ver el evento»; audio con póster 1:1. Click-to-play intacto.

**Publicación.** Cubierta 5:7 a 360 px como objeto a la izquierda, kicker + h1 + sinopsis + «Dónde conseguirlo» a la derecha; «Reseñas sobre esta publicación» cuando exista relación; foto del objeto en mano si la hay; sin la palabra «LIBRO» como fallback.

**Evento.** Póster 4:5 a 420 px como objeto con pie «Afiche · diseño · risografía» desde `caption`/`credit`; cabecera al lado; mosaico de 6 fotos 3:2 con la primera a doble columna y «Ver las N fotos»; registros enlazados; puertas «← Trayectoria 2026» y «Agenda».

**Dossier.** Kicker «Dossier · kit de prensa», barra de impresión tras la cabecera, bloque «Ficha» (fundado, ciudad, integrantes, contacto, Instagram, actualizado), cifras Syne 36-56 px, cronología única descendente, integrantes en rejilla con avatar de 96 px, publicaciones con cubierta de 120 px, cita de prensa y aliados con logo; `id="contacto"`. Imprimible con las fotos.

**Buscar / enviar.** /buscar con `.index-head`, campo y botón del sistema, contador y campo de cabecera oculto en esa ruta; cobertura ampliada a integrantes, registros, publicaciones y eventos. /enviar con etiquetas de 14 px en tinta, leyenda del asterisco, `autocomplete`, errores vinculados, botón `.btn--primary`, título unificado «Enviar una propuesta» en pie, kicker y h1.

## 7. Hoja de ruta priorizada

Flujo del proyecto en todos los lotes: rama por lote, PR con capturas antes/después a 1440 y 390, pruebas verdes en local y en Actions (pip-audit y gitleaks no están en el bucle local), y la guía de pruebas manuales actualizada.

### Quick wins (horas; solo CSS y plantillas; no dependen de contenido nuevo)

| Ítem | Hallazgos | Archivos | Cómo comprobar |
|---|---|---|---|
| `img,video{max-width:100%; height:auto}` + `height:auto` en `.pub-card img`, `.pub-cover`, `.photo-grid img`, `.event-poster` | ESP-2, IMG-1, POR-4, CON-1 | site.css:40, 205, 222, 276, 282 | Playwright: `.pub-card img` alto ≈ ancho×1,4 en /, /publicaciones/, /publicacion/<slug>/, /galeria/, /evento/<slug>/ |
| `.index-head` en los once índices con h1 `clamp(36px,5vw,56px)`; `.page-title` como cejilla | TIP-1, CON-2, COM-3, ESP-11 | site.css:124-126; poem_index, text_archive, member_index, recording_index, publication_index, agenda, trayectoria, gallery, press_index, partner_index, collection_index | metrics h1 ≥ 36 px en los once; h1 ≥ 1,3× h3 |
| Medida de lectura `max-width:66ch` en cuerpo, dek, sumarios, dossier | TIP-4, CON-3 paso 1 | site.css:142, 385, dossier | Primera línea del cuerpo entre 60 y 75 caracteres a 1440 |
| Selector de pausa de la cinta y fallback reduced-motion sin overlay ni duplicados | COM-1 (1 y 2) | site.css:483, 490, 499-502 | verify.js: `animationPlayState` = paused con el ratón encima y al tabular; rueda desplaza bajo reduced-motion |
| Overlay de búsqueda en móvil + «Ver todos» + cierre al perder foco | NAV-3, COM-5 | site.css:116-119; _search_results.html | A 390 px, overlay con x ≥ 0; tras Tab fuera, overlay oculto |
| Tokens de motion, radio y filete; regla única de transición; bloque global reduced-motion | COM-6, COM-2 (hover por color) | site.css `:root`, 259, 309, 417 | grep `transition` ≥ 1 regla global; sin `opacity` en hover |
| Componente `.rotulo`; subir 11 px a 12; interlínea base de títulos; `text-wrap` y guionado | TIP-9, TIP-10, TIP-11, CON-7 | site.css:127, 132, 163, 200, 354, 360, 365, 391, 488 | grep `font-size:11px` = 0; títulos de dos líneas a ≤1.1 |
| Preload de Syne + «Syne Fallback» con `size-adjust` calculado; peso 800 en marca y lema | TIP-8, COM-10 | base.html:36; site.css:23, 32-38 | Con la woff2 bloqueada, `.brand` y `.hero-tagline` miden lo mismo que con Syne (±2 %) |
| Reasignar el magenta: enlaces en tinta con subrayado, CTA en tinta, nav/rol/año a tinta o muted; matriz de pares en la prueba | COL-1, COL-10, COL-11 | site.css:44, 83-84, 132, 163, 191-194, 308, 401; test_contraste_paleta.py | ≤3 funciones con `--accent`; prueba con los pares nuevos en verde |
| CTA «Dossier» en cabecera, `elif general_email` en el hero, `id="contacto"` | NAV-2, POR-1 | base.html:45-77; home.html:15-20; dossier.html:106 | Un `.btn-primary` visible en el 1.er viewport de todas las páginas |
| `aria-current` vía context processor; migas de 1-2 niveles en detalles | NAV-5 | base.html; poem/article/member/event_detail; config | grep `aria-current` ≥ 1 por página; el enlace activo subrayado |
| Nav de cinco + CTA; actualizar `NAV_PRINCIPAL` | NAV-1 | base.html:70-75; tests/test_ia.py | test_ia en verde con cinco; /textos/ alcanzable desde cualquier página |
| Etiqueta condicional del CTA, «Conócenos» a /integrantes/, un estilo de enlace-fila, CTA «Enviar un texto» | POR-5, NAV-11 | home.html:13, 16, 26, 48, 105, 122, 134 | Ningún par de enlaces con rótulos distintos al mismo destino |
| Kicker sin duplicar (`Article.kicker()`), nomenclatura con descriptor, «Enviar una propuesta» unificado, títulos de pestaña | POR-12, NAV-10, NAV-12 | reviews/models, _article_card.html, base.html, submit.html, diez plantillas | `<title>` termina en `site_profile.name` en todas las rutas públicas |
| Agenda vacía con última actividad, contacto y dossier; estados vacíos de galería y aliados | CON-9, IMG-10, ESP-12, POR-10 | agenda/views.py, agenda.html, gallery.html, partner_index.html, home.html:61-71 | /agenda/ sin eventos futuros muestra ≥3 pasados y dos botones |
| Paginación con contador, números y cajas de 44 px | CON-10, COM-8 | nuevo `_pagination.html`; _poem_list, _article_list, recording_index | Con 13 ítems sembrados, «1-12 de 13», `aria-current`, `rel` |
| Rejillas con `minmax(220px,1fr)`; cubiertas-objeto; `.partner-logo` 160×80 | ESP-5, IMG-6, IMG-12 | site.css:158-159, 273-277, 294-295 | Cubiertas ≥ 240 px a 1440 |
| Formulario: etiquetas 14 px, leyenda, `autocomplete`, botón `.btn` | COM-9 | site.css:407-417; submit.html; forms | HTML servido con `autocomplete` en nombre y correo |
| Amarillo como superficie en la franja de cifras y pares en la prueba | COL-6 | site.css `:root`, 314-317; test_contraste_paleta.py | (ink, amarillo) ≥ 4,5 en la prueba |
| Pie: identidad primero, enlaces 15 px con padding, newsletter en una línea, rótulos unificados | NAV-8 | base.html:91-161; site.css:363 | Paso vertical de enlaces ≥ 28 px |
| Tokens de espacio y padding de sección | ESP-7, POR-13 | site.css:16-24, 322-324, 420 | Portada ≤ 3300 px a 1440 tras los lotes de imagen |

### Medio (días; CSS + plantillas + vistas; algunos dependen de contenido)

| Ítem | Hallazgos | Archivos | Depende de contenido | Cómo comprobar |
|---|---|---|---|---|
| Retícula de tres carriles; `<main>` sin `.wrap`; `.band` con subgrid; cabecera, nav, pie y cinta al carril ancho/full; raíz fluida | ESP-1, ESP-6, ESP-8, ESP-12 | base.html:46, 68, 87, 92; site.css:43, 57-58, 319-324, 449-474 | No | textExtent de rejillas ≥ 0,85 a 1440 y ≥ 0,65 a 1920; lectura sigue en 780-964 px; sin scroll horizontal (sin `100vw`) |
| Hero 7/5 con objeto real elegido en la vista; nombre o lema según §9; ficha y respaldo | ESP-3, IMG-3, POR-2, POR-8, POR-9 | home.html:4-29; content/views.py; site.css:298-317 | Parcial: con la demo basta la cubierta; mejor con foto de grupo | mediaInFirstViewport ≥ 1 en 1440, 1920 y 390; lema ≥ 144 px a 1920 |
| Índices como filas tipográficas; registros en rejilla de miniaturas; agenda a dos columnas con póster | ESP-4, CON-5, IMG-8 | site.css:130-131, 195-196, 263; _article_card, _poem_card, _event_card, recording_index | Póster para que luzca; funciona sin él | ≥ 10 ítems por pantalla en /poemas/ con datos suficientes; /registros/ ≤ 1 pantalla para 2 ítems |
| Sala de lectura en poema y artículo; `cover_image` y obra reseñada en pantalla; versos con sangría | ESP-9, CON-3, TIP-7, IMG-7 | poem_detail, article_detail, site.css:177-179, 383-386; filtro `versos` | `cover_image` sembrado para QA | ratio a 1920 ≥ 0,6 en poema; cpl 60-75 en artículo |
| Fichas de integrante, publicación y evento a dos columnas; rejilla de integrantes con retrato 4:5 | CON-4, IMG-4 | member_detail, publication_detail, event_detail, _member_card; site.css:158-168, 282 | Retratos reales | Ficha completa (rostro, rol, obra) en un viewport de 900 px |
| Destacado 8/4 en banda de tinta con póster o carátula tipográfica; foco blanco; botón circular | ESP-10, IMG-2, POR-7, COM-4, COL-3 | _player.html; home.html:32-48; site.css:242-260 | Carátula 1920×1080 por registro; sin ella, carátula tipográfica | Placa sin azul plano vacío; foco ≥ 3:1 sobre la placa |
| Cuatro superficies, firma de sección por territorio, pie en tinta con verso de cierre | COL-4, COL-8 | site.css `:root`, 319-324, 420-421; base.html pie; home.html | Verso corto acreditado | ≤ 2 bandas de tinta por página; todos los pares en la prueba |
| Glifo SVG en línea, favicon .ico/.png, theme-color, og_image | COL-2 | base.html `<head>` y `.brand`; static/img; SiteProfile desde admin | Dibujo del glifo; og_image 1200×630 | test_security_csp en verde; vista previa del enlace con imagen |
| Duotono `.riso-duo`, trama y gesto; exclusión de obra ajena | COL-7, IMG-5 | site.css; _member_card, _member_card_cinta, _player, gallery | Fotos propias | Hover revela el original (filter y blend anulados) |
| Cabecera sticky de una fila de 64 px; menú móvil con el mapa completo; cinta móvil con scroll-snap | NAV-6, NAV-7, CON-6, POR-11 | base.html:45-77; site.css:57-100, 440-502 | No | Cromo ≤ 64 px escritorio, ≤ 64 móvil cerrado; dos tarjetas enteras a 390 |
| Bloque Poemas en portada; Textos a 3 | POR-3 | content/views.py:83; home.html:118-124 | No | Consultas de portada ≤ 24 (test_performance) |
| Búsqueda colapsada a `<details>` y cobertura de cuatro modelos más; /buscar con el sistema | NAV-4 | content/views.py:218-231; base.html:52-62; search.html | No | «Fernanda» devuelve a la integrante; «recital» al registro |
| Enlaces cruzados y pie de entidad | NAV-9 | poem/member/publication/recording/event_detail; nuevo `_pie_de_entidad.html` | No | ≥ 4 enlaces internos en `<main>` de cada detalle |
| Dossier: cifras grandes, cronología única, fotos y cubiertas, ficha | CON-8 | showcase/views.py:54-55; dossier.html; site.css:206-208 | Retratos y cubiertas | Años en orden descendente; impresión con imágenes |
| Mono reducida a cejilla y meta; nav, botones y pie fuera de mayúsculas; escala de tokens | TIP-2, TIP-5, TIP-6 | site.css (30 usos de `--mono`, 15 uppercase) | No | Portada ≤ 30 % de elementos en mono, ≤ 15 en mayúsculas |
| Serif OFL autoalojada con fallback métrico (o la opción conforme) | TIP-3 | site.css:22-24, 32-38; static/fonts; base.html preload | No (decisión en §9) | CDP devuelve la misma familia en Linux, macOS, Windows, Android |

### Grande (rediseño por lotes, con el flujo del proyecto)

Lote A «Retícula y tipografía» (ESP-1/5/6/7/8/12, TIP-1/2/4/5/6/8/9/10/11, CON-2/3, COM-3/6): una rama, un PR, pruebas de layout en Playwright (ratio, cpl, h1). Lote B «Imagen y color» (ESP-2/10, IMG-1 a 12, COL-1 a 11, COM-4): depende del pedido de material de IMG-11; se puede mergear con la demo y volver a sembrar cuando llegue el material. Lote C «Portada y navegación» (POR-1 a 13, NAV-1 a 12): toca tests de IA y de catálogo; cada cambio de decisión (cinco enlaces, prensa y aliados) se documenta en docs/deferidos-y-decisiones.md. Lote D «Componentes y accesibilidad» (COM-1/2/5/7/8/9, CON-6/7/9/10): cierra con una pasada de teclado completa y verificación de 2.2.2 en la portada.

Depende de contenido nuevo: fotos de lectura y retratos (IMG-4, IMG-5, IMG-9, IMG-11, CON-4, POR-11), afiches (IMG-8), carátulas de registro (IMG-2, COM-4, POR-7), cubiertas y foto del objeto (IMG-6), logos (IMG-12), lema o manifiesto propio (POR-2 vía B), ciudad en `location` (POR-1), og_image y glifo (COL-2), verso de cierre (COL-8). No depende de nada: todo lo demás.

## 8. Lo que no conviene copiar de las referencias

- **Pop-ups y cookie walls** (Tack Shop, Explora, sinedogma toast): tapan el hero en todas nuestras capturas; son anti-patrones de conversión y de accesibilidad, y tu política de privacidad ya resuelve lo que un banner de cookies intentaría.
- **Vídeo hero autoplay** (LEDUP, Explora): choca con click-to-play, con la CSP y con «funciona sin JS»; en headless LEDUP es un vacío de 900 px. Un objeto estático del colectivo vale más.
- **Preloader y transiciones de página** (LEDUP): retrasan el primer contenido en un sitio de lectura.
- **Cabeceras enormes o dobles** (Tack Shop 174 px, Politico 187 px fijos en móvil, Shape dos barras de 112 px, Explora 192 px de cromo móvil): tu cabecera ya consume el 19 % del móvil; el objetivo es 56-64 px en una fila.
- **Menús de 7-10 ítems con megamenú** (Tack Shop, Explora, IME): cinco entradas más un CTA cubren tus 21 rutas.
- **Texto diminuto** (Shape 10-11 px, Tack Shop y LEDUP 11 px, Explora bronce 350 a 12 px con 4,4:1): tu mínimo es 12 px en tinta o acento con peso 500 o más.
- **Dependencia de JS para mostrar contenido** (sinedogma vacía sus listados sin JS, LEDUP esconde todo tras reveal, Tack Shop carga sus stickers con `data-src`): tu requisito de que todo funcione sin JS es una ventaja frente a ellos; no la pierdas.
- **Scroll-driven motion, parallax, cursor personalizado, capa «goo», esculturas WebGL** (Politico, LEDUP, Shape): JS pesado, no descubrible en táctil ni por teclado.
- **Animaciones infinitas sin pausa ni reduced-motion** (Tack Shop marquesina y stickers, Explora vídeo): es justo el problema que tienes en la cinta.
- **Radios de 50 px, vidrio esmerilado, sombras difusas** (LEDUP): lenguaje «tech premium» que borra la identidad risográfica de tintas planas.
- **Lógica de tienda y catálogo** (sinedogma precios y stock, Tack Shop carrito, Explora «Sort by» y conmutadores de vista para 38 piezas): tu catálogo necesita paginación simple.
- **Minúsculas forzadas y monolingüismo con `translate="no"`** (sinedogma): decisiones de voz ajenas; en castellano basta con no abusar de mayúsculas.
- **Fuentes comerciales o de Google Fonts** (todas salvo sinedogma): el patrón se traslada, las fuentes no; autoaloja OFL.
- **Pies sin contacto o con acordeones cerrados** (IME sin pie, LEDUP con el correo tras un «+»): el contacto para gestores siempre visible.

## 9. Decisiones que debes validar tú

1. **Cinta sin botón de pausa frente a WCAG 2.2.2.** La decisión se apoyaba en que hover y foco la detienen; verificado: no la detienen (el enlace extendido cubre la pista) y bajo reduced-motion no se puede desplazar con el puntero. Recomendación: corregir el selector y el fallback (respeta la decisión) y, además, añadir un checkbox con `:has()` como pausa sin JS, porque es nivel A en la portada y sinedogma, que te gusta, lo hace. Alternativa: carrusel por scroll-snap sin animación automática, que elimina el problema de raíz.
2. **Buscador siempre visible.** Hoy es el segundo elemento del cromo y solo indexa poemas y artículos. Recomendación: colapsar a `<details>` con lupa y ampliar cobertura. Alternativa: campo visible de 180 px en la fila de nav, tras el CTA, con placeholder honesto.
3. **La mono en nav, botones y pie.** Decidida como voz de rótulo, medida como voz dominante (69 %). Recomendación: mono solo en cejilla y meta; nav y botones a Syne o serif. Alternativa: conservar la mono en nav pero en caja de frase y autoalojar una OFL con carácter.
4. **Serif de lectura autoalojada y su peso.** Recomendación: Source Serif 4 o Literata, tres cortes, ≈150 KB cacheables, con fallback métrico. Alternativa conforme a la decisión: pila de sistema con Noto/DejaVu antes de Times y `font-size-adjust`.
5. **Amarillo como fondo.** Recomendación: sí, solo como superficie con tinta encima, un plano por viewport, custodiado por la prueba. Alternativa: dejarlo fuera y usar `--paper-2` como única segunda superficie clara.
6. **Banda de tinta frente a «una sola paleta clara».** Recomendación: una o dos bandas por página (destacado, cierre, pie) con `color-scheme:light`; no es un modo oscuro. Alternativa: solo papel y paper-2, aceptando que el pie y el destacado tendrán menos peso.
7. **«No cambiar .wrap».** Recomendación: no cambiarlo, sumar carriles; `<main>` deja de llevar la clase. Alternativa: mantener `.wrap` en `<main>` y usar el truco de `.band` solo para fondos, aceptando que las rejillas sigan en 780 px.
8. **Lema como titular con el nombre en `sr-only`.** Recomendación: nombre visible mientras el lema sea «Colectivo de poesía» y el manifiesto provisional; volver al lema cuando exista una afirmación propia de seis palabras o menos. Alternativa: lema actual como titular, pero a 144 px a 1920 y con el nombre a 36 px encima.
9. **Barra de exactamente cuatro enlaces y prensa/aliados fuera de la portada** (fijados en tests). Recomendación: cinco más CTA, y una línea de respaldo compacta en vez de las dos franjas; cambiar las aserciones y documentar. Alternativa: cuatro enlaces y CTA, con «Textos» como sub-entrada de Poemas, y las cuatro puertas de cierre como único acceso desde la portada.
10. **Placa azul plana del reproductor.** Recomendación: conservar el azul solo como estado sin póster y como segunda tinta del duotono; carátula tipográfica mientras no haya carteles. Alternativa: retirar `--caratula` y usar tinta para la placa.
11. **Cifras del dossier a 20 px «a propósito».** Recomendación: 36-56 px solo en `.dossier-doc`, porque es lo primero que busca un jurado. Alternativa: 20 px pero en Syne y con la cifra de integrantes.
12. **Cinta a partir de 12 integrantes.** Se respeta; solo se pide cifra en el título, fila con scroll-snap en móvil y retratos 4:5. Alternativa: rejilla de 5×2 con «y N más» cuando haya más de 10.

## 10. Criterios de aceptación y métricas de éxito

- **Ratio texto/viewport a 1440:** portada e índices ≥ 0,85; fichas de detalle ≥ 0,80; poema y artículo ≥ 0,60 (lienzo ancho con columna corta). A 1920: ≥ 0,65 en índices. Medido con el mismo `textExtent` de los metrics.
- **Tinta en el primer viewport** (muestreo 1/4, tolerancia 12): portada ≥ 50 %; índices ≥ 20 % (hoy 33 % y 4,8 %).
- **Medida de línea:** cuerpo de artículo, dek, dossier y sumarios entre 60 y 75 caracteres en escritorio; poema con `width:fit-content` y sangría de continuación.
- **Jerarquía:** h1 de índice ≥ 36 px y ≥ 1,3× el h3 de tarjeta; ningún encabezado menor que el cuerpo que encabeza; mínimo de texto 12 px; 8 tamaños, 5 interlíneas, 3 trackings en `:root`.
- **Voz:** ≤ 30 % de elementos en mono en la portada, ≤ 15 en mayúsculas; la familia de lectura idéntica en Linux, macOS, Windows y Android (CDP `getPlatformFontsForNode`).
- **Contraste:** todo texto ≥ 4,5:1 y todo indicador de foco y borde funcional ≥ 3:1, incluido sobre la placa y sobre las bandas de tinta; la prueba de paleta cubre pares permitidos y prohibidos.
- **Objetivos:** todo enlace de nav, pie, paginación y botón ≥ 44 px de alto (24 px es el mínimo legal y no la meta); formulario con `autocomplete` y errores vinculados.
- **Imágenes:** ≥ 1 en el primer viewport de la portada en 1440, 1920 y 390; proporción renderizada = proporción intrínseca (±2 %) en todas las `<img>`; póster o carátula tipográfica en el 100 % de las placas click-to-play; cobertura de fotos reales: 100 % de integrantes con retrato, 100 % de eventos con afiche o foto, 100 % de registros con carátula, og_image definido.
- **Rendimiento:** LCP ≤ 2,5 s en móvil con la imagen del hero precargada y con `width/height`; CLS < 0,1 (ya ≈0; mantenerlo con el fallback métrico de Syne); peso de fuentes autoalojadas ≤ 200 KB; consultas de portada ≤ 24.
- **Accesibilidad:** 2.2.2 cumplido en la portada (pausa funcional por hover, foco y control); overlay de búsqueda dentro del viewport a 320 px; `aria-current` en todas las páginas; títulos de pestaña con el nombre del colectivo en el 100 % de las rutas.
- **Navegación:** desde cualquier página, Dossier, Textos y contacto a un clic; cada detalle con ≥ 4 enlaces internos en `<main>`; agenda vacía con ≥ 3 actividades pasadas y dos acciones.
- **Portada:** ≤ 3300 px a 1440 tras los lotes; alternancia estricta de superficies; ≥ 3 versos visibles; cifras enlazadas a su prueba; fecha de última actualización visible.

## Anexo A. Mediciones actuales (brief.md, Playwright + Chrome)

| Medida | Valor |
|---|---|
| Contenedor | `.wrap{max-width:820px; padding:0 20px}` → 780 px de texto |
| Ratio texto/viewport | 0,54 a 1440; 0,41 a 1920 (todas las páginas; home 1140 solo por la cinta desbordada); móvil 390: 0,82-0,90 |
| Fuentes por elementos (portada) | mono 137, serif 56, Syne 41 (inventario de texto directo: 113 / 12 / 38) |
| Titulares | lema 104 px Syne 700 (clamp 44-104, 13ch); h2 destacado 32; h3 tarjeta 26; h1 detalle 42-46; h1 de los once índices 12 px mono mayúsculas gris |
| Cuerpo | 16 px/1.6; artículo 18 (102 cpl); poema 19/1.8 pre-wrap; botones 12 px mono; nav 13 px mono |
| Pila serif resuelta | Linux Chrome: Liberation Serif; Android: Noto Serif; macOS: Iowan Old Style; Windows: Palatino Linotype |
| Pila mono resuelta | Safari ui-monospace; macOS SF Mono/Menlo; Windows Consolas; Linux/Android DejaVu / Droid Sans Mono |
| Medios | 0 en el primer viewport de la portada (1440, 1920, 390); primera imagen a 1437 px; ninguna foto salvo cubiertas, avatares y fotos de evento |
| Alturas de página (1440 = 1920) | home 4077, textos 1579, publicaciones 1383, integrantes 1245, artículo 1089, poema 1086, agenda 900 |
| Imágenes renderizadas | cubiertas 180×780 (debería 180×252); detalle 240×780; galería y evento 249×750 |
| Cabecera | 120 px escritorio (estática); 164 px móvil cerrado, 223 abierto |
| Cinta | 746 px visibles, 3 de 12, 230 px por tarjeta, 72 s por vuelta; hover/foco no la detienen |
| Contrastes | tinta/papel 14,26; muted/papel 5,02; magenta/papel 5,12; blanco/azul 4,84; magenta/tinta 2,78; azul/papel 3,88; borde/papel 1,17; CTA en hover ≈4,7 |
| Referencias (ratio a 1440) | Explora 0,96; Politico 0,94; Shape 0,92; Tack Shop 0,91; sinedogma 0,87; IME 0,86; LEDUP 0,80 |

## Anexo B. Capturas que respaldan los hallazgos principales

Carpeta base: `~/.claude/projects/-home-fabian-User-repos-Rese-as/auditoria-ux-ui-material/`. Sitio local: `shots/pw-local/`; referencias: `shots/pw-refs/`; extras generados por los auditores: `shots/com/`, `shots/nav-extra/`, `crops/`.

- Espacio: `home-d1440-view.png`, `home-w1920-view.png`, `home-d1440-full.png`, `home-w1920-full.png`, `integrantes-w1920-view.png`, `textos-w1920-view.png`, `poemas-d1440-view.png`, `poema-w1920-view.png`, `articulo-w1920-view.png`, `registros-d1440-full.png`, `agenda-d1440-view.png`.
- Imagen rota: `publicaciones-d1440-view.png`, `publicaciones-w1920-view.png`, `publicaciones-m390-view.png`, `publicacion-d1440-view.png`, `galeria-d1440-view.png`, `evento-d1440-full.png`, `home-d1440-s03.png`, `home-m390-s04.png`.
- Tipografía: `poemas-d1440-view.png`, `textos-d1440-view.png`, `integrantes-d1440-view.png`, `articulo-d1440-view.png`, `poema-d1440-view.png`, `poema-m390-view.png`, `dossier-d1440-view.png`, `buscar-d1440-view.png`, `enviar-d1440-view.png`.
- Color e identidad: `home-d1440-view.png` (nueve piezas magenta), `home-d1440-s01.png` (placa azul, avatares lila), `home-d1440-s04.png` (franja vacía, correo), `registro-d1440-view.png`, `registros-d1440-view.png`, `integrantes-d1440-view.png` (iniciales).
- Portada y navegación: `home-d1440-s01.png` (cinta cortada, INTEGRANTES 11 px), `home-d1440-s02.png` (kickers duplicados), `home-m390-view.png` (cabecera 164 px), `home-m390-s01.png` (nombres cortados), `nav-extra/home-m390-search-overlay.png`, `nav-extra/home-m390-menu-open.png`, `dossier-d1440-s02.png`, `prensa-d1440-view.png`, `aliados-d1440-view.png`.
- Componentes: `com/com-cinta-hover.png` (la pista corre con el ratón encima), `com/com-hover-btn-primary.png`, `com/com-focus-embed-play.png`, `textos-m390-view.png`.
- Referencias citadas: `explora-d1440-view.png`, `explora-d1440-s01/s02/s06/s09/s10.png`, `politico-d1440-view.png`, `politico-d1440-s02/s04/s08/s09/s10.png`, `sinedogma-d1440-view.png`, `sinedogma-d1440-s01/s03/s05/s06.png`, `sinedogma-m390-view.png`, `ledup-d1440-view.png`, `ledup-d1440-s01/s04/s05.png`, `ledup-m390-s05.png`, `shapeofintelligence-d1440-view.png`, `shapeofintelligence-d1440-s02/s03/s04/s11.png`, `tackshop-d1440-s01/s02/s03/s05.png`, `crops/ts-d-hero-clean.png`, `crops/ts-d-slice5-4480-5128.png`, `crops/ts-m-slice2-1688-2532.png`, `imechile-d1440-view.png`, `imechile-d1440-s01/s02.png`.