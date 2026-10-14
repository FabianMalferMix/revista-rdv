# Plan de ejecución del backlog UX/UI

> Este documento es el punto de entrada para **retomar el trabajo desde cualquier entorno**:
> dice en qué punto está el proyecto, qué se hace a continuación, con qué criterios se da por
> cerrado cada paso y cómo se trabaja. No depende de nada que no esté en el repositorio.
>
> Fuentes: los tickets están en `docs/backlog-ux-ui.md`, los hallazgos y la dirección de diseño
> en `docs/auditoria-ux-ui.md`, el material que debe aportar el colectivo en
> `docs/contenido-visual.md`.
>
> **Actualizado el 2026-10-14: el plan está cerrado, con la aprobación final del dueño.** Lo
> que venga después ya no son pasos de este plan (ver sección 2).

## 1. Dónde estamos

**El plan está cerrado.** Los 25 pasos están hechos y el dueño del sitio aprobó el punto de
control final el 2026-10-14 («Quedó bien, doy mi aprobación final»), después de probar las
páginas de lectura con los textos largos de prueba (#136). `main` está en verde, con 893
pruebas. No hay ninguna rama abierta.
Los PR abiertos de Dependabot (#107 a #113, actualizaciones de dependencias) no son del plan.

**Siguiente: nada de este plan.** Lo que pida el dueño a partir de ahora va en su propia rama,
con el mismo método, y se mide contra `tools/ux/final/` (sección 2). Lee «Lo que espera
respuesta del dueño», más abajo: son tareas suyas, no pasos.

Para comprobar que el repositorio está donde dice este documento:

```bash
git fetch origin && git status -sb               # en main, al día con origin/main
git log --oneline --merges -3                    # debe aparecer «Merge plan-ux-cerrado …»
gh pr list --state open --author "@me"           # ninguno: los de Dependabot no cuentan
gh run list --branch main --limit 1              # completed · success
grep -n '^- \[ \]' docs/plan-ejecucion-ux.md | head -1   # ninguno: los 25 están marcados
```

Si algo no coincide (una rama de paso a medias, un PR abierto), termina eso antes de abrir nada
nuevo: mira su descripción y la sección 4.

### Lo hecho

| Paso | Rama | PR | Qué dejó |
|---|---|---|---|
| 0 | (sin rama) | entra en #94 | Material visual genérico: comando `seed_material_generico` |
| 1 | `docs-auditoria-y-backlog` | #94 | Auditoría, backlog, este plan y el comando, en el repo |
| 2 | `ux-0-herramienta-y-linea-base` | #95 | `tools/ux` y la línea base de métricas |
| 3 | `ux-1a-imagenes-y-lectura` | #96 | Imágenes con su proporción, medida de lectura, mínimo de 12 px |
| 4 | `ux-1b-indices-y-lenguaje` | #97 | Cabecera común en los once índices, cejillas sin repetir |
| 5 | `ux-1c-cinta` | #98 | La cinta de integrantes se detiene de verdad; fila en táctil |
| 6 | `ux-1d-componentes` | #100 | Un botón, un rótulo, tokens de movimiento, buscador que no se sale |
| 7 | `ux-1e-color` | #101 | El magenta deja de ser el color de los enlaces; matriz de pares |
| 8 | `ux-1f-paginacion-formulario-vacios` | #102 | Paginación, errores de formulario, estados vacíos |
| — | `cinta-sin-icono` | #103 | Fuera el icono de pausa, por decisión del dueño |
| 9 | `ux-2-1-reticula` | #104 | Tres carriles: lectura, ancho y sangre |
| 10 | `ux-2-2-indices-y-rejillas` | #105 | Índices como filas, registros en miniaturas, cubiertas como objetos |
| — | `plan-retomable` | #106 | Este plan, autocontenido; `tools/ux/preparar-entorno.sh` y ayudantes |
| 11 | `ux-2-3-tipografia` | #114 | Serif propia, escala de diez tamaños, monoespaciada solo en rótulos y datos |
| 12 | `ux-2-4-lectura-y-fichas` | #115 | Sala de lectura, poema verso a verso, fichas a dos columnas, salidas al pie |
| — | `sala-ancla-sin-solape` | #116 | La columna fija del artículo y del poema ya no se monta sobre las salidas |
| 13 | `ux-3a-superficies-y-amarillo` | #117 | Hoja clara y tinta, pie en tinta, firma por territorio, cifras en amarillo, sello de convocatoria |
| — | `cifras-destacado-y-pie` | #118 | Lo que eligió el dueño: cifras con trazo de marcador, destacado sobre el papel a dos columnas, pie compacto y siempre abajo |
| 14 | `ux-3b-duotono-y-retratos` | #119 | Retratos 4:5 a todo el ancho de la tarjeta, duotono azul en listados y galería, monograma |
| 15 | `ux-3c-reproductor` | #120 | La placa del reproductor con su póster a una tinta o su carátula, y el mando en un panel sólido |
| 16 | `ux-3d-imagenes-del-modelo` | #121 | Imágenes de textos y afiches en los listados, crédito y contador en el álbum, aliados por tipo |
| 17 | `ux-3e-marca` | #122 | El sello con el monograma RV, el icono «RdV», `theme-color` y la tarjeta para compartir |
| 18 | `ux-4-1-cabecera` | #123 | Cabecera de una fila y fija: cinco enlaces con la página actual marcada, lupa, «Dossier»; «Menú» con el mapa en el teléfono |
| — | `dev-conexiones-runserver` | #124 | El servidor de desarrollo ya no agota las conexiones de Postgres al medir |
| 19 | `ux-4-2-hero` | #125 | El nombre como titular junto a la cubierta del catálogo; cifras con su página y línea de respaldo de prensa y aliados |
| 20 | `ux-4-3-portada` | #126 | La portada completa: integrantes, poemas con sus versos junto a los textos, publicaciones y un cierre para programadores y jurados |
| — | `portada-obra-antes` | #127 | La obra antes que las integrantes, como en el tablero: lo pidió el dueño |
| — | `portada-sin-cifras-ni-aliados` | #128 | Fuera de la portada, por ahora, las cifras y «Con el apoyo de»: lo pidió el dueño |
| — | `portada-sin-cita` | #129 | Fuera de la portada la cita de prensa: lo pidió el dueño |
| 21 | `ux-4-4-pie-y-enlaces` | #130 | El pie abre con la identidad del colectivo; actividades en la ficha de cada integrante; «Aliados» se titula así |
| — | `publicaciones-y-resenas` | #131 | Cada publicación enseña sus reseñas: una obra reseñada puede ser un libro del colectivo (con migración) |
| 22 | `ux-5-1-dossier` | #132 | El dossier como kit de prensa: ficha, cifras grandes, retratos, una sola trayectoria por años, cubiertas, prensa, logos; se imprime con sus imágenes |
| 23 | `ux-5-2-agenda-galeria-aliados` | #133 | Ficha de evento con el afiche a 420 px y su pie, «Participan» y «Registros» a su lado, fotos en mosaico con «Ver las N fotos»; la vista ampliada cubre la pantalla; logo tipográfico para el aliado sin logo |
| 24 | `ux-5-4-busqueda` | #134 | La búsqueda encuentra personas, registros, publicaciones y actividades además de textos y poemas, por grupos; cinco por grupo en la lupa y diez en la página; una consulta menos |
| 25 | `ux-6-cierre` | #135 | La verificación de §10 criterio a criterio, con capturas de antes y después (`docs/auditoria-ux-ui-verificacion.md`); la pasada de accesibilidad; los enlaces de la barra a 45 px; D1 a D14 y lo diferido documentados |
| — | `textos-largos-de-prueba` | #136 | Lo pidió el dueño antes del cierre: `seed_textos_largos` siembra seis textos y cinco poemas largos; arreglados el bloque preformateado que desbordaba la página, la columna ancla más alta que la pantalla, los títulos larguísimos y el adelanto de los poemas en la portada |
| — | `plan-ux-cerrado` | #137 | La aprobación final del dueño, anotada; el plan, cerrado |

El PR #99 se cerró sin fusionar (mensaje de commit equivocado) y se reabrió como #100. Cada
ticket cerrado lleva en el backlog una nota **Estado** con lo que de verdad se construyó.

### Lo que ha cambiado, medido

Con `tools/ux` a 1440 px, sobre la base de desarrollo original. «Antes» es
`tools/ux/linea-base/`.

| Medida | Antes | Tras el paso 13 |
|---|---|---|
| Ancho que ocupa el texto en la portada | 53 % | 97 % |
| Lo mismo a 1920 px | 40 % | 100 % |
| Lo mismo en Poemas, Textos y Trayectoria | 47 a 51 % | 92 % |
| Lo mismo en Integrantes | 53 % | 91 % |
| Título de un índice | 12 px | 56 px |
| Letras por línea en un artículo | 102 | 62 |
| Textos de menos de 12 px en la portada | 29 | 0 |
| Imágenes deformadas en la portada | 3 | 0 |
| Cubierta en Publicaciones | 180 px, deformada | 421 px |
| Alto de la portada en un teléfono | 6512 px | 4297 px |
| Elementos de la portada en monoespaciada | 72 % | 39 % |
| Elementos de la portada en mayúsculas | 30 | 18 (12 tras el paso 11; el rol de cada integrante pasó a rótulo en el 14) |
| Tamaños de letra distintos en la hoja | 25 | 10, en una escala |
| Ancho que ocupa el texto en un artículo a 1920 px | 38 % | 73 % |
| Enlaces internos en la ficha de un poema | 1 | 5 |
| Cajas blancas con borde sobre el papel (21 páginas) | 5 | 0 |
| Superficies de tinta | 0 | 1 por página: el pie |
| Alto del pie a 951 px, y desde 1100 | 435 tras el paso 13 | 320 y 236, siempre abajo |
| Área del retrato sobre la tarjeta en `/integrantes/` | 10 % a 951, 12 % a 1440 | 76 % y 73 % (63 % de media a 390) |
| Placas del reproductor vacías | 2 | 0 |
| Imágenes del modelo en los listados | ninguna | las de los textos y los afiches (a una tinta), créditos en el álbum, logos de aliados |
| Icono de la pestaña | ninguno (`/favicon.ico` daba 404) | «RdV» a 32 px, `.ico` y 180 px para el teléfono |
| Alto de la cabecera en escritorio, y en un teléfono | 111 y 156 px | 64 y 56 px, fija al bajar |
| `/textos/` y el dossier en la cabecera | no | sí: un enlace y un botón |
| Páginas que marcan su sección en la cabecera | 0 | las de las cinco secciones y el dossier; no las que no son de ninguna (portada, búsqueda, colecciones, envío) |
| Consultas por página para las redes del colectivo | 3 | 1 |
| Titular de la portada | el lema, con el nombre oculto | el nombre: 124 px a 1440 y 125 a 1920 |
| Imágenes en la primera pantalla de la portada (1440, 1920 y 390) | 1, 1 y 0 | 1, 1 y 1 |
| Botones principales en la primera pantalla de la portada | 2 desde 900 px | 1 |
| Alto de la portada a 1440 | 4459 px tras el paso 19 | 4092 px, con poemas y el cierre y sin cifras, aliados ni cita; la meta de 3300 no cabía (decisión del dueño, paso 20) |
| Versos que se leen en la portada | 0 | 6: tres por poema |
| Consultas de la portada (prueba, en frío; desarrollo) | 17; 21 | 16; 15, con un techo de 24 |
| Identidad del colectivo en el pie | no | sí, sin subir el alto: 320 px a 951 y 236 desde 1100 |
| Enlaces internos en la ficha de una integrante | 10 | 13: con sus actividades |
| Textos por debajo de AA contra su fondo real (21 páginas, 5 anchos) | sin medir | 0 |
| Años de la trayectoria del dossier | 2022, 2019, 2026, 2026, 2026, 2025 | en orden: 2026, 2025, 2024, 2023, 2022, 2019 |
| Imágenes del dossier al imprimir desde el navegador | ninguna | 12 retratos, 3 cubiertas y 3 logos; A4 en cuatro hojas |
| Fotos a una tinta al imprimir cualquier página | salían en blanco | tal cual |
| Consultas del dossier (prueba, en frío) | 17 | 15, con retratos, cubiertas, logos y la fecha |
| Afiche en la ficha de un evento (951 y 1440) | 320 px, sin pie | 420 px, con «Afiche · …» |
| Fotos en la ficha de un evento (951) | seis iguales de 207 × 129, con su pie debajo | mosaico: la primera de 581 × 390, las demás de 288 × 192; «Ver las N fotos» si hay más de seis |
| Vista ampliada de una foto | no cubría la pantalla y recortaba la foto a 8:5 | pantalla entera, la foto entera |
| Aliado sin logo en `/aliados/` y en el dossier | caja vacía o nada | su nombre en la caja del logo |
| Consultas de la ficha de un evento (prueba, en frío) | 13 | 12 |
| «Fernanda» y «recital» en el buscador | sin resultados | la integrante; el registro y dos actividades |
| Tipos que encuentra el buscador | 2: textos y poemas, en una lista | 6, por grupos |
| Consultas de la búsqueda (prueba, en frío) | 9 | 8 |
| Alto de los enlaces de la barra y de la sub-fila del colectivo | 23 y 43 px | 45 px |
| Objetivos que fallan WCAG 2.5.8, con sus excepciones (21 páginas, 1440 y 390) | sin medir | 0 de 821 y 822 |
| LCP y CLS de la portada en un teléfono (4G lento, CPU ×4, desarrollo) | sin medir | 2,1 s y 0 |

### Lo que todavía se ve a medias, a propósito

Cada cosa de esta lista tiene su paso. No son defectos por arreglar fuera de orden.

| Lo que se ve hoy | Lo resuelve |
|---|---|
| Nada pendiente de un paso: lo que la verificación deja sin cumplir está, con su causa, en `docs/deferidos-y-decisiones.md` §4 («Del rediseño UX/UI») | — |

### Lo que ha decidido el dueño del sitio

- **Delegó las catorce decisiones de diseño** (D1 a D14, tabla en §1 del backlog). No se le
  vuelven a preguntar.
- **Punto de control A (2026-10-08):** aprobó el reparto del magenta, las frases de los índices y
  el texto de la agenda vacía, y aceptó las recomendaciones para todo lo demás.
- **Sin control de pausa en la cinta.** Lo ha retirado dos veces (un rótulo y un icono). No se
  vuelve a proponer salvo que él lo pida.
- **Quiere ver cada paso al terminarlo.** Después de fusionar un paso hay que **parar** y decirle
  dónde mirar. No se encadenan pasos hasta el siguiente punto de control.
- **Revisión del paso 10 (2026-10-13):** sí a las cubiertas grandes con tres títulos, sí a la
  trayectoria sin cejillas magenta y sí a los registros sin reproductor en el índice. No quiso
  ajustar el umbral de dos columnas de la agenda y la galería («no es necesario»).
- **Revisión del paso 11 (2026-10-13):** pidió seguir con el paso 12 sin ajustes, así que las
  decisiones de ese paso quedan aceptadas: la familia «RdV Serif», la navegación en caja de
  frase, los títulos de sección grandes y la monoespaciada de la portada en el 39 %.
- **Punto de control B (2026-10-13):** aprobó la serif nueva, el poema verso a verso y las
  fichas a dos columnas. Señaló que en el artículo la columna de la izquierda se montaba sobre
  las salidas del final al desplazarse; se corrigió en `sala-ancla-sin-solape`.
- **Corrección del solape (2026-10-13):** la vio y dio paso al 13 («Se ve bien, pasa al paso
  13»). Con eso quedan aceptadas también las decisiones del paso 12 que no había contestado: las
  salidas «anterior» y «siguiente» en todas las fichas, el poema que enlaza a la ficha de su
  registro y la firma propia omitida en la ficha de quien firma.
- **Revisión del paso 13 (2026-10-13):** sí al sello magenta y al reparto de colores de la firma
  por territorio. Descartó dos decisiones delegadas al verlas: el plano amarillo de las cifras
  («invasivo», «demasiado cuadrado») y la banda de tinta del registro destacado («rompe la visual
  de la portada»). Pidió alternativas, se le enseñaron capturadas sobre la página real
  (`tools/ux/variantes.js`) y eligió el trazo de marcador para las cifras y el destacado sobre el
  papel a dos columnas. Del pie dijo que pesaba por alto y propuso usar más ancho; también señaló
  el papel que asomaba bajo el pie en una página corta. Todo quedó en `cifras-destacado-y-pie`.
  Quiere **conservar la convocatoria de prueba** en la base de desarrollo.
- **Ajustes del paso 13 (2026-10-13):** los vio y pidió seguir con el paso 14.
- **Marca (2026-10-13, paso 17):** después de dos rondas de alternativas sobre la cabecera real
  (https://claude.ai/artifact/Q9joypGzPw2ePFckQ7Dik7 y
  https://claude.ai/artifact/W9pBicg8tAa2URusJpYw2q), eligió:
  - **quedarse con el sello magenta**, con el monograma RV dentro (H1);
  - **«RdV» en blanco sobre el magenta** como icono (I6 con RdV);
  - **el sello a toda la tarjeta** para compartir (T2).
  Descartó un glifo de dos formas y el nombre sin sello.
- **Revisión del paso 16 (2026-10-13):** aprobó las decisiones, también los afiches de los
  listados a una tinta: «deja el azul que aprobé previamente».
- **Revisión del paso 15 (2026-10-13):** visto bueno, sin ajustes.
- **Revisión del paso 14 (2026-10-13):** aprobó todas las decisiones, también la tinta: «el azul
  del cartel fue la decisión correcta para ambos casos» (retratos y galería).
- **Punto de control C (2026-10-13):** visto bueno a los pasos 13 a 17 («Doy el visto bueno»).
- **D9 no necesitó aviso (2026-10-13):** no avisó al colectivo porque «todas las decisiones
  fueron delegadas a mí». Las decisiones de diseño las toma él; no hace falta preguntar si el
  colectivo está avisado.
- **Punto de control D (2026-10-14):** visto bueno a la portada completa («Doy el visto bueno
  para el control D»).
- **Reseñas de cada publicación (2026-10-14):** pidió enlazar cada publicación con sus reseñas,
  «correcto para futuras features», aunque el plan no lo incluía y pedía una migración. Eligió
  el diseño recomendado («hazlo como mejor encuentres»): la obra reseñada puede señalar su
  publicación del colectivo (`reviews.Work.publicacion`, #131).
- **Dossier (2026-10-14):** mantiene «En números», «Prensa» y «Con el apoyo de», aunque los
  quitó de la portada («Sí, mantén todo eso en el Dossier»).
- **Paso 22 (2026-10-14):** pidió empezarlo («Sigue con el paso 22») sin comentar el #131.
- **Punto de control final (2026-10-14):** aprobado («Quedó bien, doy mi aprobación final»).
  Antes de darlo pidió probar las páginas de lectura con textos largos y realistas (#136). No
  pidió nada distinto para el poema en prosa, así que se queda como está: cada párrafo se
  compone como un verso largo, con sangría francesa.
- **Revisión del paso 24 (2026-10-14):** dio paso al 25 («Sigue al paso 25») sin ajustes:
  quedan aceptados el orden de los grupos de la búsqueda, sus topes y quién sale como persona.
- **Revisión del paso 23 (2026-10-14):** dio paso al 24 («Sigue al paso 24») sin ajustes:
  quedan aceptados «Participan» y «Registros» junto al afiche.
- **Revisión del paso 22 (2026-10-14):** dio paso al 23 («Sigue al paso 23») sin ajustes, así
  que quedan aceptadas las decisiones de ese paso: los retratos del dossier en su color, sin
  duotono; el dossier en la columna de lectura; sin las reseñas del propio sitio.
- **Revisión del paso 20 (2026-10-14):** tras los tres ajustes de la portada (#127 a #129), dio
  paso al 21 («Adelante, sigue al paso 21»).
- **Cifras y aliados (2026-10-14, después del paso 20):** los quitó de la portada por ahora,
  «siendo que aún somos un grupo pequeño». Salieron las cifras del titular («12 integrantes ·
  4 actividades · 1 festival · 3 publicaciones») y «Con el apoyo de»; la cita de prensa se
  queda (#128). Al verlo, pidió quitar también la cita (#129). Para devolver cada pieza se
  revierte su commit: `30799d0` (cifras), `28b0de3` (aliados) y `7ee4e14` (cita). Sigue
  abierto si quiere quitar también el «12 integrantes» de la cejilla y el «12 voces» de la
  sección de integrantes: se le preguntó y aún no contesta.
- **Portada completa (2026-10-14, paso 20):** la meta de 3300 px a 1440 no cabía sin quitar
  algo. Vio dos maneras sobre la portada real
  (https://claude.ai/artifact/JtujcEMzZ1dEqgb46Nd62p) y eligió la A: conservar el bloque de
  publicaciones (4415 px a 1440) frente a quitarlo (3841). Antes, al ver el 19, dio paso al 20
  sin ajustes. Al construir, las integrantes quedaron antes que la obra, por la prueba de
  julio; al verlo, pidió el orden del tablero, con la obra primero (#127). La prueba se
  invirtió.
- **Titular de la portada (2026-10-14, paso 19):** vio tres disposiciones capturadas sobre la
  portada real (https://claude.ai/artifact/7iU76LZaaiuhyVPTazCvMv) y eligió la A: el nombre en
  dos líneas y, a su lado, la cubierta del catálogo. Descartó el nombre en una línea como
  cabecera de revista y el nombre como cartel gigante. Antes pidió la corrección del entorno
  de desarrollo (#124).
- **Cabecera (2026-10-13, paso 18):** a 951 px la fila entera no cabe con el nombre del sello en
  una línea. Se le enseñaron tres maneras sobre la cabecera real
  (https://claude.ai/artifact/SPdVbArnaZeDSm32H6UVi7) y eligió la A: por debajo de 1100 px el
  nombre va en dos líneas, «Repitentes / del Verso». Descartó los enlaces en una segunda fila y
  los enlaces escondidos en «Menú».
- **Revisa en una ventana de 951 px de ancho al 100 %.** A ese ancho el carril ancho mide 875 px.
  Cada paso se mide y se le describe también a 951 px (sección 4); lo que solo aparece en
  pantallas más anchas se le dice, con el zoom con que verlo (90 % ≈ 1057 px, 80 % ≈ 1189 px).
- El material visual es genérico y lo reemplazará él desde el panel (`docs/contenido-visual.md`).

### Lo que espera respuesta del dueño

1. **Los textos largos de prueba (#136) siguen sembrados** en desarrollo, con `zz-largo-` en la
   dirección: aparecen arriba en la portada y en los índices. Cuando ya no los quiera:
   `docker compose exec web python manage.py seed_textos_largos --borrar`.
2. **Doce casillas por comprobar** en `docs/guia-pruebas-manuales.md` (§1, §1.5 y §2): las que
   describen lo que cambió con el rediseño. `docs/retomar-barrido.md` dice cuáles.
3. **La relación entre publicaciones y reseñas (#131)**: no la comentó; con la aprobación final
   queda aceptada.
   Qué mirar, a 951 px:
   - http://localhost:8000/publicacion/cuadernos-del-ruido/: al final, la sección «Reseñas»;
   - http://localhost:8000/obra/zz-demo-cuadernos-del-ruido/: «Publicación del colectivo:
     Cuadernos del ruido»;
   - en el panel, al editar una obra reseñada, el campo «Publicación del colectivo».
   La reseña que se ve es **de prueba** («Reseña de prueba: Cuadernos del ruido»): se borra
   cuando la haya visto, con
   `docker compose exec web python manage.py shell -c "from apps.content.models import Article; from apps.reviews.models import Work; Article.objects.filter(slug='zz-demo-resena-cuadernos-del-ruido').delete(); Work.objects.filter(slug='zz-demo-cuadernos-del-ruido').delete()"`.
   Sigue abierto si quiere quitar el «12 integrantes» de la cejilla y el «12 voces»: no lo ha
   contestado, y se quedan.
4. **La convocatoria de prueba se queda**, porque lo pidió él: `convocatoria-primavera-2026`,
   abierta hasta el 30 de noviembre de 2026. Cuando quiera quitarla:
   `docker compose exec web python manage.py shell -c "from apps.submissions.models import Call; Call.objects.filter(slug='convocatoria-primavera-2026').delete()"`.
5. **La tarjeta para compartir** del paso 17 está en `tools/ux/out/tarjeta-para-compartir.png`:
   él decide si la sube desde el panel (Perfil del sitio → imagen para compartir).
6. Un dato de la base que se ve raro en el dossier: el hito «Fundación del colectivo» dice
   **2019** y la ficha dice «Fundado 2023»; se corrige en el panel (Agenda → Hitos, o Perfil
   del sitio).
7. Lo que solo él puede aportar: fotos, afiches, cubiertas y logos reales, la ciudad, un correo
   de gestión que exista, un manifiesto propio. Nada de eso bloquea ningún paso.

## 2. Después del plan

El plan está cerrado: los 25 pasos y el punto de control final, aprobado por el dueño del sitio
el 2026-10-14. Este documento queda como registro de cómo se hizo y de lo que él decidió por el
camino (sección 1).

**Si el dueño pide un cambio**, ya no es un paso de este plan, pero se trabaja igual:
- una rama y un PR por cambio, con el método de la sección 4 y las reglas de la sección 5;
- se le enseña antes de construir si choca con algo que él aprobó;
- se mide contra `tools/ux/final/`, la medida del cierre, que es ahora la línea base:
  `python3 tools/ux/metrics.py comparar tools/ux/final tools/ux/out/<rama>`.

**Lo que quedó sin cumplir de la auditoría** tiene su causa y su seguimiento en
`docs/deferidos-y-decisiones.md` §4, con lo que costaría cada punto. Lo que él decidió no se
«arregla» sin preguntarle: el alto de la portada, la pausa de la cinta, las cifras y la tinta
de la portada, y el poema en prosa compuesto como verso largo.

**Sus tareas** (sección 1, «Lo que espera respuesta del dueño»): borrar los textos de prueba y
la reseña de prueba del #131 cuando quiera, la convocatoria de prueba, la tarjeta para
compartir, el hito de 2019, las doce casillas de la guía y el material real del colectivo.

## 3. Los pasos

La casilla marcada significa fusionado en `main` con su CI en verde. «Cierra cuando» resume la
aceptación del ticket: los detalles y las pruebas están en el backlog. Los rombos son puntos de
control: además de enseñar el paso, ahí se pide una aprobación expresa de la dirección.

- [x] **0. Material genérico.** Comando `seed_material_generico` y `docs/contenido-visual.md`.
- [x] **1. `docs-auditoria-y-backlog`.** Auditoría, backlog, plan y comando, al repo.
- [x] **2. `ux-0-herramienta-y-linea-base`.** Tickets 0.1 y 0.2.
- [x] **3. `ux-1a-imagenes-y-lectura`.** Tickets 1.1 y 1.3.
- [x] **4. `ux-1b-indices-y-lenguaje`.** Tickets 1.2 y 1.12.
- [x] **5. `ux-1c-cinta`.** Ticket 1.4 (D1, D12). El icono de pausa se retiró después (#103).
- [x] **6. `ux-1d-componentes`.** Tickets 1.5, 1.6, 1.7 y 1.8.
- [x] **7. `ux-1e-color`.** Ticket 1.9.
- [x] **8. `ux-1f-paginacion-formulario-vacios`.** Tickets 1.10, 1.11 y 1.13.
- ◆ **Punto de control A.** Hecho el 2026-10-08 (ver sección 1).
- [x] **9. `ux-2-1-reticula`.** Ticket 2.1 (D7).
- [x] **10. `ux-2-2-indices-y-rejillas`.** Ticket 2.2.
- [x] **11. `ux-2-3-tipografia`.** Ticket 2.3 (D3, D4).
- [x] **12. `ux-2-4-lectura-y-fichas`.** Ticket 2.4: poema y artículo con columna ancla, fichas a
  dos columnas, pie de entidad.
  Cierra cuando: a 1920 el texto ocupa el 60 % o más en poema y artículo; el artículo queda entre
  60 y 75 letras por línea; cada ficha tiene cuatro enlaces internos o más; el poema conserva
  versos, sangrías y espacios (comparar el `innerText` del cuerpo antes y después).
- ◆ **Punto de control B.** Hecho el 2026-10-13: aprobado (ver sección 1).
  Preguntar: si la serif nueva se siente del colectivo; si el poema respira; si las fichas a dos
  columnas se leen mejor que apiladas.
- [x] **13. `ux-3a-superficies-y-amarillo`.** Tickets 3.1 y 3.2 (D5, D6): cuatro superficies,
  bandas de tinta, amarillo como fondo.
  Cierra cuando: dos bandas de tinta por página como mucho; ningún texto sobre tinta por debajo de
  4,5:1; no quedan cajas blancas con borde de 1 px sobre el papel; el amarillo aparece en un solo
  plano por pantalla.
- [x] **14. `ux-3b-duotono-y-retratos`.** Tickets 3.3 y 3.6: tratamiento a dos tintas, retratos
  4:5 y monograma.
  Cierra cuando: una tinta por pantalla; al señalar una imagen se ve el original; las cubiertas no
  llevan tratamiento; en `/integrantes/` el rostro ocupa el 60 % o más de la tarjeta; no queda
  `border-radius:50%` en la hoja.
- [x] **15. `ux-3c-reproductor`.** Ticket 3.4 (D10): póster o carátula tipográfica en la placa.
  Cierra cuando: ninguna placa azul vacía en el sitio; el texto sobre la placa da 4,5:1 o más y
  el foco 3:1; al pulsar «Reproducir» el iframe sustituye a la placa;
  `tests/test_embed_consent.py` sigue en verde.
- [x] **16. `ux-3d-imagenes-del-modelo`.** Ticket 3.5: imagen de texto, afiche, crédito y logos
  llegan a pantalla.
  Cierra cuando: cada imagen aparece donde dice el ticket; el crédito se muestra si existe; los
  presupuestos de consultas de `tests/test_performance.py` no suben.
- [x] **17. `ux-3e-marca`.** Ticket 3.7: glifo, icono de pestaña, `theme-color`, tarjeta para
  compartir. El dueño eligió conservar el sello, con el monograma dentro.
  Cierra cuando: `tests/test_security_csp.py` sigue en verde (ningún `.svg` en `static/`); la
  pestaña enseña el icono; el nombre de la cabecera ya no lleva fondo.
- ◆ **Punto de control C.** Hecho el 2026-10-13: aprobado (ver sección 1).
  Preguntar: si quiere el tratamiento a dos tintas y con cuál; si el glifo lo representa; si
  acepta el nombre sin sello magenta.
- [x] **18. `ux-4-1-cabecera`.** Ticket 4.1 (D2, D9): una fila, cinco enlaces, «Dossier»,
  buscador plegado. Cambia `tests/test_ia.py`. El dueño eligió el nombre del sello en dos
  líneas por debajo de 1100 px; por debajo de 900, la cabecera del teléfono.
  Cierra cuando: la cabecera mide 64 px o menos en escritorio y 56 o menos en un teléfono;
  `/textos/` y el dossier quedan a un clic desde cualquier página; cada página marca su enlace con
  `aria-current`; sin JavaScript la lupa abre el campo y el envío lleva a `/buscar/`.
- [x] **19. `ux-4-2-hero`.** Ticket 4.2 (D8, D9): el nombre como titular visible, un objeto real,
  cifras y línea de respaldo. Cambia `tests/test_catalog.py`. El dueño eligió, entre tres, el
  nombre en dos líneas con la cubierta al lado.
  Cierra cuando: hay una imagen en la primera pantalla a 1440, 1920 y 390; el titular mide 112 px
  o más a 1920; un solo botón primario en la primera pantalla; la portada no pasa de 24 consultas;
  el correo del titular es el mismo que el del pie.
- [x] **20. `ux-4-3-portada`.** Ticket 4.3: orden de los bloques, poemas en la portada. La
  meta de 3300 px no cabía: el dueño eligió conservar las publicaciones (4415 px a 1440).
  Cierra cuando: la portada mide 3300 px o menos a 1440 con la demo; se leen tres versos o más;
  los integrantes van antes que los textos; no pasa de 24 consultas. (El dueño decidió otra
  cosa en dos de ellos: conservar las publicaciones, con 4415 px, y la obra antes que las
  integrantes.)
- [x] **21. `ux-4-4-pie-y-enlaces`.** Tickets 4.4 y 4.5: pie en tinta, enlaces cruzados.
  Cierra cuando: los enlaces del pie tienen 28 px o más de paso vertical; todo el texto del pie da
  4,5:1 o más; cada ficha tiene cuatro enlaces internos o más.
- ◆ **Punto de control D.** Hecho el 2026-10-14: aprobado (ver sección 1). Portada completa a
  1440, 1920 y 390.
- [x] **22. `ux-5-1-dossier`.** Ticket 5.1 (D11): el dossier como kit de prensa. Sigue en la
  columna de lectura, como una hoja; de paso, las fotos a una tinta ya no salen en blanco al
  imprimir cualquier página.
  Cierra cuando: los años van en orden descendente estricto; el PDF impreso desde el navegador
  enseña retratos y cubiertas; `/dossier/#contacto` lleva al bloque de contacto.
- [x] **23. `ux-5-2-agenda-galeria-aliados`.** Tickets 5.2 y 5.3. «Participan» y «Registros»
  subieron junto al afiche; de paso, la vista ampliada de las fotos cubre la pantalla.
  Cierra cuando: un evento con afiche lo enseña en la agenda, en «Próxima actividad» y en su
  ficha; la ampliación de fotos sigue funcionando sin JavaScript; `/aliados/` usa el ancho.
- [x] **24. `ux-5-4-busqueda`.** Ticket 5.4: la búsqueda cubre integrantes, registros,
  publicaciones y eventos. Las personas incluyen a quien firma algo publicado; los cuatro
  tipos nuevos son una sola consulta.
  Cierra cuando: «Fernanda» devuelve a la integrante y «recital» al registro; la búsqueda no pasa
  de 10 consultas.
- [x] **25. `ux-6-cierre`.** Tickets 6.1, 6.2 y 6.3: accesibilidad, métricas finales contra
  `tools/ux/linea-base/`, documentación y decisiones.
  Cierra cuando: hay una tabla con cada criterio de §10 de la auditoría, cumplido o explicado;
  ningún documento describe un estado que ya no existe.
- ◆ **Punto de control final.** Hecho el 2026-10-14: aprobado (ver sección 1).

Tamaño de lo que queda, según §5 del backlog: los pasos 11, 12, 15, 16, 17, 18, 20 y 22 son
medianos; el 19 es el grande; el resto, pequeños.

## 4. Cómo se hace un paso

Es el flujo de §0 del backlog, con los comandos que se han usado en los diez primeros.

1. **Partir de `main` limpio y en verde.**

   ```bash
   git checkout main && git pull --ff-only
   gh run list --branch main --limit 1          # success
   git checkout -b <rama-del-paso>
   ```

2. **Leer.** El ticket entero, su Nota de entrada y los hallazgos que cita. Mirar cómo está hoy
   lo que se va a tocar: `node tools/ux/capture.js tools/ux/out/antes --only <páginas>`.
3. **Buscar qué pruebas fijan lo que vas a cambiar**, antes de escribir nada:
   `grep -rn "<clase o texto>" backend/tests/`. Muchas afirman cadenas literales del HTML.
4. **Construir y mirar.** El criterio es lo que se ve en el navegador, no que el código parezca
   correcto. Captura, mira la imagen, ajusta.

   ```bash
   node tools/ux/capture.js tools/ux/out/<rama> --only <páginas>
   node tools/ux/hoja.js tools/ux/out/<rama> tools/ux/out/<rama>/hoja.png -d1440-full.png 620 3 <páginas…>
   node tools/ux/ver.js tools/ux/out/<rama> 768 900 <nombre>=<ruta> …      # anchos intermedios
   node tools/ux/superficies.js 951 900                  # bandas, amarillo, cajas y texto bajo AA
   ```

   Los estados (puntero encima, foco de teclado) también se miran: un guion corto de Playwright
   que mueva el puntero, pulse Tab y capture.
5. **Escribir las pruebas** de lo nuevo y actualizar las que fijaban la decisión anterior.
   **Cada prueba nueva se comprueba rompiendo lo que vigila:**

   ```bash
   bash tools/ux/mutar.sh <archivo> '<texto actual>' '<texto roto>' 'tests/<archivo>.py::<prueba>'
   ```

   Debe decir «falla como debe». Si dice que no detecta la regresión, la prueba no vigila nada.
6. **Pasar las puertas locales.**

   ```bash
   docker compose run --rm --entrypoint ruff web check .
   docker compose run --rm --entrypoint ruff web format .
   docker compose run --rm --entrypoint pytest web -q -p no:cacheprovider
   # El SAST del CI, igual que allí (bloquea severidad media o más):
   docker run --rm -v "$PWD/backend:/src:ro" -w /src python:3.12-slim sh -c \
     'pip install -q "bandit==1.9.4" && bandit -r apps config -ll'
   ```

7. **Medir entero.**

   ```bash
   node tools/ux/capture.js tools/ux/out/<rama>                                  # las 21 páginas
   python3 tools/ux/metrics.py comparar tools/ux/out/<paso-anterior> tools/ux/out/<rama>
   for a in 320 768 951 1024 1920; do node tools/ux/ver.js tools/ux/out/<rama> $a 900 <rutas…>; done
   for a in 390 951 1440; do node tools/ux/superficies.js $a 900; done            # sale con 1 si algo falla
   python3 tools/ux/smoke.py                                                     # todas con 200
   ```

   Si no tienes las capturas del paso anterior, compara con `tools/ux/linea-base`.
8. **Documentar en el mismo PR.** La nota **Estado** del ticket en el backlog, con lo que se
   construyó y en qué difiere de lo escrito. La casilla y la sección 1 de este plan. La guía
   `docs/guia-pruebas-manuales.md` si cambió algo que describe.
9. **Commit, PR y CI.** Mensaje en español: `<rama>: <qué cambia y por qué, en una línea>`, cuerpo
   que explique el porqué, y la línea de atribución que indique tu sesión. La descripción del PR
   lleva la tabla de métricas, porque la consola no adjunta imágenes.

   ```bash
   git add <archivos concretos>                 # nunca `git add -A`: ver sección 5
   git commit -F <archivo con el mensaje>
   git push -u origin <rama>
   gh pr create --base main --title "<asunto del commit>" --body-file <descripción>
   gh pr checks <n> --watch                     # cinco comprobaciones
   ```

10. **Fusionar y comprobar `main`.**

    ```bash
    bash tools/ux/fusionar.sh <n> <rama> "<efecto visible, en minúscula>"
    gh run list --branch main --limit 1         # esperar a success
    docker compose restart web
    ```

11. **Parar y enseñar.** Dile al dueño qué páginas abrir, con la URL literal y las palabras que
    verá en pantalla, qué cambió, qué quedó a medias a propósito y qué decisiones tomaste por él.
    Descríbele lo que verá **a 951 px**, su ancho: si algo solo aparece en pantallas más anchas,
    díselo y dale el zoom con que verlo.
    Si rechaza algo visual, no lo rehagas a ciegas: prepárale alternativas sobre la página real
    con `tools/ux/variantes.js`, a 951 px, y publícalas en una página con las capturas lado a
    lado para que elija viéndolas. Así se eligieron las cifras y el destacado tras el paso 13.

**Hecho quiere decir:** `ruff` y la suite en verde; CI verde en el PR y en `main`; todas las
rutas con 200; sin scroll horizontal a 320, 390, 951, 1440 y 1920; enlace de salto, foco visible y
regiones intactos; los criterios del ticket medidos, no estimados; la documentación al día.

## 5. Reglas que no se rompen

Romperlas falla pruebas, la política de seguridad de contenido en producción, o una decisión del
dueño.

- **Sin `style=` en línea, sin `onclick`, sin CDN.** Fuentes y guiones propios. Un archivo `.svg`
  o `.html` dentro de `backend/static/` rompe `tests/test_security_csp.py`: los glifos SVG van en
  línea en la plantilla y los iconos en PNG o ICO.
- **Todo funciona sin JavaScript.**
- **Una sola paleta, clara.** Los valores de `:root` que ya existen no cambian; se pueden añadir.
- **El video de un tercero solo se carga al pulsar** (`static/js/embeds.js`).
- **Sin modelos ni migraciones nuevas**, salvo la que pidió el dueño el 2026-10-14:
  `reviews.Work.publicacion` (migración `reviews.0003`), que dice qué obra reseñada es un libro
  del colectivo. Otra excepción, solo si él la pide.
- **`.wrap{max-width:820px}` conserva su valor.**
- **Nunca `seed_demo` sobre una base con la identidad aplicada:** reescribe el perfil del sitio.
- **Nunca un push forzado ni borrar ramas remotas a mano.** La rama remota la borra GitHub al
  fusionar (`fusionar.sh`) o al cerrar el PR. Un commit ya subido con el mensaje mal no se
  enmienda: se cierra el PR con `gh pr close --delete-branch` y se abre otro.
- **`docs/Sesión 00 Bootcamp Odoo.md` no es de este proyecto.** Si aparece sin seguimiento en el
  árbol de trabajo, no se añade a ningún commit.
- **El repositorio es público.** Nada de credenciales ni datos personales en commits, PR o capturas.
- **Los comentarios de plantilla de más de una línea van con `{% comment %}`**, no con `{# #}`.
- **Textos de interfaz en español de Chile**, sin mayúsculas nuevas fuera de la receta `.rotulo`.

## 6. Preparar un entorno nuevo

La base de datos, los medios subidos y `tools/ux/out/` **no viajan con el repositorio**. Lo que
hace falta para seguir sí está en él.

**Requisitos de la máquina:** Docker con Compose, Node 20 o superior, Python 3, Chrome (por
defecto en `/usr/bin/google-chrome`; otra ruta, variable `CHROME`), `git` y `gh` con sesión
iniciada y permiso de escritura en `FabianMalferMix/revista-rdv`.

```bash
git clone https://github.com/FabianMalferMix/revista-rdv.git && cd revista-rdv
bash tools/ux/preparar-entorno.sh
```

El guion crea `.env` si falta, levanta los contenedores, siembra la demostración **solo si la
base está vacía**, aplica la identidad real del colectivo, completa los integrantes hasta doce,
dibuja el material genérico, instala `tools/ux` y comprueba que todas las rutas responden. Es
idempotente: en un entorno ya preparado no cambia nada. Está probado sobre una base vacía.

**Después de prepararlo, espera unos tres minutos.** La demostración deja una reseña programada,
`/articulo/resena-la-casa-vacia/`, que se publica sola. Es la página de artículo que captura
`tools/ux`: hasta entonces responde 404.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/articulo/resena-la-casa-vacia/   # 200
docker compose run --rm --entrypoint pytest web -q -p no:cacheprovider                          # 694 en verde
```

**En qué se diferencia un entorno recién preparado de la base original**, para no leer como
regresión lo que es un dato distinto:

| En la base original | En un entorno recién preparado |
|---|---|
| Los cuatro eventos de la demostración ya pasaron | Dos están por venir |
| `/agenda/` enseña «Sin fechas anunciadas por ahora» y tres actividades recientes | `/agenda/` enseña dos fechas |
| La portada no tiene bloque «Próxima actividad» | Lo tiene |
| `/trayectoria/` lista cuatro actividades | Lista dos |

Las fechas de la demostración son relativas al día en que se siembra. Para ver el estado vacío
de la agenda, despublica los dos eventos por venir desde el panel. Por esto mismo, al comparar
con `tools/ux/linea-base`, la portada, la agenda y la trayectoria miden distinto en alto.

**Lo que no viaja y no hace falta:** las capturas de los pasos ya hechos, las notas de la sesión
que ejecutó los diez primeros pasos y el material de trabajo de la auditoría (capturas de los
sitios de referencia). Lo que importa de todo eso está en este documento, en el backlog y en la
auditoría.

## 7. Lo aprendido en los diez primeros pasos

**Sobre las pruebas de la hoja de estilos** (`tests/test_css_sistema.py`,
`tests/test_contraste_paleta.py`, `tests/test_ui_identity.py`). Leen `site.css` con expresiones
regulares y fijan, entre otras cosas:

- ningún `font-size` por debajo de 12 px;
- ninguna regla `:hover` que declare `opacity`;
- toda `transition` usa los tokens `--dur-…`;
- una regla con `aspect-ratio` sobre un `img` declara también `height:auto`;
- ningún `100vw`;
- mayúsculas solo en la receta `.rotulo`;
- el magenta como color de texto en reposo, solo en la cejilla y el asterisco de obligatorio;
- toda regla que fija a la vez `color` y `background` con colores de la paleta da 4,5:1;
- un token de color nuevo entra con sus pares en `PARES`.

**Sobre las pruebas del HTML.** Varias cuentan cadenas literales: `class="event-card"` exacto en
la agenda, `article-card` cinco veces como mucho en la portada, la primera
`<span class="kicker">` del archivo de textos. Antes de añadir una clase a un elemento, busca su
clase en `backend/tests/`.

**Sobre editar con guiones.** Una sustitución por posición (`s.index(...)`) toma la primera
aparición del texto, que puede estar en otra parte del archivo. En el paso 14 eso borró siete
pruebas de un tirón, y solo lo delató `mutar.sh` (salida 2: la prueba no llegó a ejecutarse).
Ancla en un texto que no se repita y mira `git diff --stat` después de cada guion.

**Sobre medir.**
- El dueño revisa a **951 px**, no a 1440. Lo que se diseña para pantallas anchas hay que verlo
  también a ese ancho: en el paso 10 le describimos cosas que su pantalla no enseñaba.
- La columna `parrafo` de `capture.js` toma el primer `<p>` de `<main>`, que en casi todas las
  páginas es la cejilla. Para saber en qué letra se lee, mira los párrafos de lectura.
- La columna `razon` de `tools/ux` mide hasta dónde llega el **texto**. Una página de imágenes
  (galería, publicaciones, registros) puede ocupar todo el carril y marcar 0,75.
- Un `.py` cambiado y restaurado en segundos puede dejar al servidor de desarrollo con el código
  viejo. `mutar.sh` lo evita; si dudas, `docker compose restart web` antes de capturar.
- Las capturas de página entera recorren la página para cargar las imágenes perezosas; una
  captura propia que no lo haga las enseña vacías.
- **Una captura de página entera no enseña lo que pasa al desplazarse.** Un elemento
  `position:sticky` se comprueba bajando de verdad, con un guion que mida en cada tramo si
  pisa algo. El solape de la columna ancla del paso 12 solo lo vio el dueño, desplazándose.
- Datos de prueba temporales para medir un criterio (doce poemas, tres fechas de agenda) se crean
  con un prefijo reconocible y se borran en la misma orden. No se dejan en la base.
- **Un elemento girado engaña al rectángulo que lo envuelve.** `getBoundingClientRect`
  devuelve la caja del giro: la cubierta del titular (paso 19) salía como deformada.
  `capture.js` mide ya la caja propia (el `width` y el `height` calculados).
- **Mide también los anchos intermedios.** La fila de la cabecera del paso 18 cabía a 390, 951
  y 1440, pero a 768 y a 820 el botón «Dossier» se salía de la pantalla, y a 320 se salía
  «Menú». `node tools/ux/ver.js <dir> 768 900 …` sale con 1 si una página desborda.
- **El servidor de desarrollo se quedaba sin conexiones** con cientos de páginas seguidas:
  `runserver` abre un hilo por petición y, con `CONN_MAX_AGE=60`, cada hilo dejaba su conexión
  abierta hasta llenar las 100 de Postgres (500, «too many clients already»). Desde el PR #124,
  `docker-compose.override.yml` le pone `DJANGO_CONN_MAX_AGE=0`: con 357 páginas seguidas no
  pasa de 2 conexiones. Si vuelve a pasar en otro entorno, mira que el override esté cargado.

- **La prueba de contraste de la hoja solo ve las reglas que declaran a la vez `color` y
  `background`.** Un texto que hereda su color de una banda y está encima de otro fondo (el aviso
  de la placa azul dentro de la banda de tinta, en el paso 13) no lo ve nadie más que
  `tools/ux/superficies.js`, que mide cada texto contra el fondo que tiene debajo en la página
  pintada.

**Sobre el diseño ya construido.**
- **El lienzo.** `<main class="lienzo">` tiene tres carriles: lectura (780 px), ancho (1320 px,
  y 1440 desde 1600 de ventana) y sangre. Cada página elige con
  `{% block lienzo %}lienzo--ancho{% endblock %}`. Una banda a sangre lleva dentro un
  `<div class="band-in">` que vuelve al carril ancho.
- **Las filas.** `.filas` es un contenedor: la fila se dispone según el ancho de su lista, no el
  de la ventana. Sus piezas van en áreas con nombre (`fecha`, `cuerpo`, `pie`).
- **Un elemento fijo (`sticky`) se mueve por todo su contenedor.** No lo pongas en la misma
  rejilla que lo que viene después: la columna ancla vive en `.lectura-sala` y el pie, fuera.
- **Toda la tarjeta es enlace** con una capa `::after` del enlace del título; los enlaces
  secundarios van por encima con `z-index:1`. Nunca se envuelve la tarjeta en un `<a>`.
- **Estados por color**, nunca por opacidad ni por movimiento.
- **Superficies.** El papel; la hoja clara (`--paper-2`), que es la de `.band` y la de los avisos;
  la tinta, solo en el pie (el dueño descartó la banda de tinta del destacado: lista cerrada en
  `TINTA_PERMITIDA`); y el blanco, solo para campos y objetos (`BLANCO_PERMITIDO`). El amarillo
  es un trazo de marcador detrás de las cifras de la portada, nunca un plano ni un texto. Sobre
  la tinta, el texto va en papel, los datos en `--muted-on-ink` y el acento en `--accent-on-ink`.
- **Duotono.** Una envoltura `<span class="riso-duo">` por imagen (una `<img>` no admite
  `::after`): la tinta de fondo, la foto en gris con `screen` y el papel en una capa
  `multiply`. Una sola tinta en todo el sitio, el azul del cartel. Solo en los listados
  (`CON_DUOTONO`), y al señalar o enfocar, el original.
- **Un `include` hereda todo el contexto de la página.** Una parcial con un parámetro que se
  llama como una variable de la página (en el paso 20, `cejilla`, que la portada ya tenía
  como lista) la pinta cuando no se le pasa. Las parciales con parámetros se incluyen con
  `only`.
- **Un argumento de filtro que no se resuelve rompe la página entera.** Con `r.event` vacío,
  `{{ r.recorded_on|default:r.event.starts_at }}` lanza un error en vez de quedar en blanco.
  Usa `{% if %}…{% elif %}`. Pasó en los pasos 12 y 15.
- **El pie llega siempre abajo.** `body` es una columna flexible de al menos `100dvh` y el lienzo
  crece (`flex:1 0 auto`) sin separar sus filas (`align-content:start`). Un hijo de `body` con
  `margin-inline:auto` necesita `width:100%`, o en la columna flexible se encoge a su contenido.
- **Una regla de banda alcanza a todo lo que lleva dentro**, también a un componente con fondo
  propio. Las reglas de la banda van después de las del componente al que corrigen (con la misma
  especificidad gana la última: el título del destacado desapareció, tinta sobre tinta, porque
  `.featured h2 a` iba detrás), y el componente con fondo propio va después de la banda.
- **Añadir un atributo a una etiqueta rompe las pruebas que la buscan literal.** Pasó con
  `<header class="index-head">` al añadir `data-territorio`: búscala con `[^>]*`.
- **Una receta que va después en la hoja le gana a un `@media` anterior** con la misma
  especificidad. En el paso 18 la regla de `.btn` volvía a enseñar el botón «Dossier» en el
  teléfono, y la de los rótulos dejaba «Menú» en gris. Se arregla con la clase del contenedor
  delante: `.masthead .masthead-cta`.
- **La cabecera es fija y su alto es un token**, `--alto-cabecera`: 56 px por debajo de 900 de
  ventana y 64 desde ahí. Lo usan `scroll-padding-top`, la columna ancla y el año de la
  trayectoria. Un elemento fijo nuevo usa `top:calc(var(--alto-cabecera) + …)`, y una prueba
  lo vigila.
- **Pocos elementos.** `auto-fit` con un tope por tarjeta, o columnas según la cantidad con
  `:has()`, para que tres cosas no se arrinconen a la izquierda de cinco columnas.
- **Syne 800 es un corte extendido** y no se usa. **La cinta no lleva control de pausa.**
- `responsive_img` emite un texto alternativo vacío con `decorativa=True`, no con `alt=""`.
- **HTML armado en Python:** con `format_html` o `format_html_join`, nunca `mark_safe`. El SAST
  del CI (bandit) bloquea `mark_safe`, y con razón: es por donde se cuela un XSS. Le pasó al
  filtro `versos` en el paso 12.
- **Tamaños de letra:** solo pasos de la escala (`--t-2` a `--t7`); una prueba lo vigila. La
  monoespaciada, solo en las reglas que lista `MONO_PERMITIDA` en `tests/test_css_sistema.py`.
- **Fuentes de terceros:** mira si la licencia reserva un nombre. Source Serif 4 reserva
  «Source»: el subconjunto se llama «RdV Serif». Para trabajar con `fonttools` sin instalar nada
  en la máquina, un contenedor desechable de `python:3.12-slim` basta (ver `fonts/NOTICE.txt`).

## 8. Al cerrar cada paso, este documento se actualiza

En el mismo PR del paso:

1. Marca su casilla en la sección 3.
2. En la sección 1: el recuento, el último paso y su PR, el número de pruebas, la fila nueva de
   «Lo hecho», las medidas que hayan cambiado, y quita de «a medias» lo que el paso resolvió.
3. En «Lo que espera respuesta del dueño»: lo que ya contestó sale; lo que el paso deja pendiente
   de su visto bueno entra, con las páginas que debe mirar.
4. Reescribe la sección 2 para el paso siguiente: qué se hace, qué hace falta, la tabla de
   criterios con el valor de hoy, las pruebas que cambian y los cuidados.
5. Si el paso cambió algo de lo que depende un ticket posterior, deja una **Nota de entrada** en
   ese ticket del backlog.
6. La fecha de la cabecera.
