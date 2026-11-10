# tools/ux — capturas y métricas de la interfaz

Nació como instrumento de la auditoría UX/UI de octubre de 2026 y de su backlog, que se
retiraron del árbol y siguen en git (`git show 38fdf03:docs/auditoria-ux-ui.md` y
`git show 38fdf03:docs/backlog-ux-ui.md`). Mide lo que se ve: cuánto del ancho usa el texto,
tamaños reales, imágenes deformadas, objetivos pulsables, scroll horizontal. No forma parte
del despliegue: `tools/` está fuera de la imagen de Docker.

## Preparación (una vez)

```bash
npm ci --prefix tools/ux             # playwright-core, axe-core y ESLint, del lockfile; usa el Chrome del sistema
```

Requiere Node 20.19 o superior (el CI usa el 24) y Chrome en `/usr/bin/google-chrome` (otra ruta: variable
`CHROME`). El sitio debe estar arriba en `http://localhost:8000` (otra base: `--base` o `UX_BASE`).
Los guiones de Node toman esa base, el Chrome y la lista de `pages.txt` de `common.js`, que también
lee la fuente de titulares del sitio (la primera familia de `--display`) en la página cargada: ninguna
herramienta nombra la fuente. `--base` lo aceptan `capture.js`, `browser-smoke.js` y `contraste.js`;
los demás leen `UX_BASE`.

## Uso

```bash
# 1. Capturar todas las páginas de pages.txt (1440, 390 y, en las marcadas, 1920)
node tools/ux/capture.js tools/ux/out/baseline

# 2. Solo algunas, o solo métricas
node tools/ux/capture.js tools/ux/out/prueba --only home,publicaciones
node tools/ux/capture.js tools/ux/out/prueba --sin-capturas

# 3. Leer las métricas
python3 tools/ux/metrics.py tabla tools/ux/out/baseline
python3 tools/ux/metrics.py comparar tools/ux/out/baseline tools/ux/out/prueba

# 4. Humo: todos los enlaces internos responden
python3 tools/ux/smoke.py
```

Cada página deja `<nombre>-<viewport>-view.png` (primer viewport), `-full.png` (página
entera) y `-metrics.json`. `tools/ux/out/` no se versiona. Lo que hay que conservar entre máquinas
está en `linea-base/` (ver más abajo).

`capture.js` solo mide una página que responde 200. Otra respuesta es un `FALLO` que nombra la ruta
y el código, no deja métricas ni capturas de esa página (borra las de una corrida anterior en el
mismo directorio) y la orden sale con 1; un nombre de `--only` que no está en `pages.txt` la para
con 2. Cada `-metrics.json` guarda con qué se midió, en `provenance`: el commit (y si había cambios
sin confirmar), la versión de Chrome y el sha256 de `backend/datos_de_desarrollo/datos.json`.
`metrics.py` lo muestra encima de la tabla, avisa al comparar si el navegador o los datos no son
los mismos, y no muestra ni compara una fila que no sea de un 200: la nombra con su ruta y su
código, y sale con 1.

## Qué mide

| Columna | Qué es | Referencia |
|---|---|---|
| `razon` | ancho del texto / ancho del viewport | la auditoría midió 0,54 a 1440; las referencias, 0,80 a 0,96 |
| `h1` | tamaño del primer `h1` visible | en un índice debe superar al título de las tarjetas |
| `cpl` | caracteres de la línea más larga del cuerpo de artículo | 45 a 75 (Bringhurst) |
| `img1` | imágenes en el primer viewport | |
| `desv` | imágenes cuya caja no respeta la proporción pedida | debe ser 0 |
| `mono%`, `MAY`, `<12` | elementos en monoespaciada, en mayúsculas, bajo 12 px | |
| `<24` | objetivos pulsables de menos de 24 px | WCAG 2.5.8 |
| `desb` | scroll horizontal (en móvil se prueba además a 320 px) | WCAG 1.4.10 |

Añadir una página: una línea en `pages.txt` (`nombre ruta [ancho]`). La prueba de humo también
la recorre. La ficha que nombra tiene que estar en los datos de desarrollo:
`backend/tests/test_measured_pages.py` lo comprueba.

## Prueba de humo en navegador

`browser-smoke.js` carga el sitio a 951 px (la ventana del dueño) y a 375 px (un teléfono) con los
guiones ejecutándose de verdad. Comprueba que:

- las páginas de `pages.txt` no desbordan a lo ancho;
- los controles de la cabecera miden 44 px o más;
- «Menú» abre y cierra, también al salir el foco, sin moverlo ni dejar lo enfocado tapado;
- la lupa busca en vivo, no busca con una letra y anuncia una sola vez el recuento, sin leer los
  resultados;
- un correo que el sitio no acepta vuelve a su campo, con lo escrito, el error al lado y el foco, y
  los campos trampa de los formularios no se ven;
- la cabecera pasa a cápsula al bajar, y la portada se reconoce por su marca: arriba no tiene
  cabecera, y la cápsula le llega sin transición de vista;
- arriba de la portada, la cápsula que se abre con el teclado busca con el mismo ancho que al bajar;
- sin cada guion de la portada, sin un nodo que necesita o si falla al montarse, la página sigue
  usable: la cabecera clásica, la tirada en fila y el estante con sus enlaces;
- el estante y la tirada responden al teclado (la tirada, también al dedo, y solo anuncia lo que
  no mueve el foco);
- el reproductor externo solo se carga al pulsar;
- en las tarjetas, pulsar la fecha, la miniatura o la marca ▶ lleva a la pieza, y los enlaces
  secundarios (la sección, la firma, el evento de un registro) llevan a lo suyo;
- el dossier imprime;
- «Las voces» van en una fila; el relevo no cambia el árbol de accesibilidad de la lista, trae a
  la que más esperaba al lugar de la que se va, y el tabulador recorre la fila en el orden en que
  se ve;
- lo que lleva `hidden` no se ve, con los guiones y sin ellos.

Cada comprobación falla también ante un error de página o de consola, ante un recurso propio que
no carga y ante una petición a un tercero que nadie pidió. La corre el job `navegador` del CI, sobre
el stack de desarrollo poblado con `datos_de_desarrollo cargar`, el mismo comando que en local.

```bash
node tools/ux/browser-smoke.js                              # contra http://localhost:8000
node tools/ux/browser-smoke.js --base http://127.0.0.1:8096 # otra base
```

Sale con 1 si falla alguna. Si una falla después de un cambio de diseño, antes de ajustarla hay
que preguntarse qué vigilaba.

## Contraste en el navegador (axe)

`contraste.js` pasa axe-core, solo con su regla de contraste de color (WCAG 1.4.3, AA), por cada
página de `pages.txt` a 951 y a 375 px, con «reducir movimiento». La prueba de paleta
(`backend/tests/test_contraste_paleta.py`) calcula los pares desde el CSS; esto mide lo que queda
pintado, con los fondos heredados y el tamaño real de cada letra. Sale con 1 si encuentra algún
texto bajo el mínimo, si una página no responde 200 o si no le da nada que medir; lo que axe deja
«por revisar» (texto sobre imágenes o degradados) no cuenta. Lo corre el job `navegador` del CI.

```bash
node tools/ux/contraste.js --base http://127.0.0.1:8000
```

## ESLint de los guiones

`eslint.config.mjs` fija el dialecto de `backend/static/js/`: ES2020, en guiones clásicos sin
módulos. Desde la raíz del repositorio:

```bash
tools/ux/node_modules/.bin/eslint -c tools/ux/eslint.config.mjs backend/static/js
```

## Lo demás que hay en esta carpeta

Ayudantes que nacieron como guiones sueltos durante el rediseño (su plan sigue en git:
`git show 38fdf03:docs/plan-ejecucion-ux.md`); están aquí para poder rehacer ese trabajo desde
cualquier máquina.

| Archivo | Para qué | Uso |
|---|---|---|
| `preparar-entorno.sh` | Reconstruye el entorno de diseño en una máquina nueva: levanta el stack, lo puebla con `datos_de_desarrollo cargar` (el único camino; ver el README), instala estas herramientas y pasa la prueba de humo. Se puede repetir: en una base de desarrollo ya poblada, `cargar` no hace nada. | `bash tools/ux/preparar-entorno.sh` |
| `ver.js` | Capturas sueltas a cualquier ancho y de cualquier ruta, con aviso de scroll horizontal. | `node tools/ux/ver.js tools/ux/out/prueba 768 900 poemas=/poemas/` |
| `hoja.js` | Hoja de contactos: varias capturas en una sola imagen. | `node tools/ux/hoja.js tools/ux/out/prueba tools/ux/out/prueba/hoja.png -d1440-full.png 620 3 home poemas` |
| `superficies.js` | Bandas de tinta, planos de amarillo por pantalla, cajas blancas con borde y textos bajo AA contra el fondo que tienen debajo, página a página (pasos 13 y siguientes). Sale con 1 si una página no cumple. | `node tools/ux/superficies.js 951 900` (todas) o `… 390 800 home dossier` |
| `variantes.js` | Alternativas de una pieza sobre la página real: CSS (y JS) inyectado en el navegador de captura, una imagen por variante, recortada a la pieza. Para que el dueño elija viendo. | `node tools/ux/variantes.js tools/ux/out/cifras 951 900 / .hero hoy=- marcador=marcador.css` |
| `iconos.js` | El icono de la pestaña (32 px y `.ico`), el del teléfono (180 px) y la tarjeta para compartir (1200 × 630), dibujados con la fuente de titulares del sitio (la de `--display`); se detiene si no carga. Necesita el sitio arriba y Pillow en python3. | `node tools/ux/iconos.js` |
| `mutar.sh` | Comprueba que una prueba nueva pasa y que **falla** cuando se rompe lo que vigila. Trabaja en un worktree temporal con los cambios sin confirmar (no toca el árbol de trabajo) y recrea su propia base de pruebas, así que también vale para mutar una migración. Necesita la imagen `resenas-app:dev` y la base del stack arriba; no usa el contenedor `web`. Sale con 0 si detecta, 1 si no y 2 si no llegó a correr o ya fallaba sin mutar. | `bash tools/ux/mutar.sh static/css/site.css '<actual>' '<roto>' 'tests/…::test_…'` |
| `fusionar.sh` | Fusiona el PR de un paso solo si su CI está verde, con el asunto del proyecto. | `bash tools/ux/fusionar.sh 105 <rama> "<efecto visible>"` |

Cada uno explica sus argumentos en su cabecera. Los de Node usan el mismo Chrome (variable `CHROME`)
y la misma base (`UX_BASE`), de `common.js`.

## Línea base versionada

`linea-base/` guarda las métricas del sitio **antes** del backlog (49 archivos, capturados el
2026-10-08 sobre `main` en `e6873fe`) y ocho capturas del primer viewport: portada, índice de
poemas, un poema y una ficha de integrante, a 1440 y a 390. `out/` no se versiona y esas
capturas no se pueden regenerar: el código que las produjo ya cambió.

```bash
python3 tools/ux/metrics.py tabla tools/ux/linea-base
python3 tools/ux/metrics.py comparar tools/ux/linea-base tools/ux/out/<rama>
```

El ticket 6.2 del backlog (métricas finales) compara contra esta carpeta. Al comparar, ten en
cuenta que la base de datos de entonces no tenía fechas de agenda por venir: en un entorno recién
sembrado la portada y `/agenda/` miden distinto por los datos, no por el diseño.

## Medida final versionada

`final/` guarda lo mismo **después** del backlog: las métricas de las 21 páginas (capturadas el
2026-10-14, al cerrar el paso 25) y las ocho capturas equivalentes en `final/capturas/`. La tabla
de §10 de la auditoría, criterio a criterio, sigue en git:
`git show 38fdf03:docs/auditoria-ux-ui-verificacion.md`.
Para ver si algo empeora desde entonces:

```bash
node tools/ux/capture.js tools/ux/out/<rama>
python3 tools/ux/metrics.py comparar tools/ux/final tools/ux/out/<rama>
```
