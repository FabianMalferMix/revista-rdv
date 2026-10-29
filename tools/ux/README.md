# tools/ux — capturas y métricas de la interfaz

Nació como instrumento de la auditoría UX/UI de octubre de 2026 y de su backlog, que se
retiraron del árbol y siguen en git (`git show 38fdf03:docs/auditoria-ux-ui.md` y
`git show 38fdf03:docs/backlog-ux-ui.md`). Mide lo que se ve: cuánto del ancho usa el texto,
tamaños reales, imágenes deformadas, objetivos pulsables, scroll horizontal. No forma parte
del despliegue: `tools/` está fuera de la imagen de Docker.

## Preparación (una vez)

```bash
npm ci --prefix tools/ux             # playwright-core y ESLint, del lockfile; usa el Chrome del sistema
```

Requiere Node 20.19 o superior (el CI usa el 24) y Chrome en `/usr/bin/google-chrome` (otra ruta: variable
`CHROME`). El sitio debe estar arriba en `http://localhost:8000` (otra base: `--base` o `UX_BASE`).

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

## Qué mide

| Columna | Qué es | Referencia |
|---|---|---|
| `razon` | ancho del texto / ancho del viewport | la auditoría midió 0,54 a 1440; las referencias, 0,80 a 0,96 |
| `h1` | tamaño del primer `h1` visible | en un índice debe superar al `h3` de tarjeta |
| `cpl` | caracteres de la línea más larga del cuerpo de artículo | 45 a 75 (Bringhurst) |
| `img1` | imágenes en el primer viewport | |
| `desv` | imágenes cuya caja no respeta la proporción pedida | debe ser 0 |
| `mono%`, `MAY`, `<12` | elementos en monoespaciada, en mayúsculas, bajo 12 px | |
| `<24` | objetivos pulsables de menos de 24 px | WCAG 2.5.8 |
| `desb` | scroll horizontal (en móvil se prueba además a 320 px) | WCAG 1.4.10 |

Añadir una página: una línea en `pages.txt` (`nombre ruta [ancho]`). La prueba de humo también
la recorre.

## Prueba de humo en navegador

`browser-smoke.js` carga el sitio a 951 px (la ventana del dueño) y a 375 px (un teléfono) con los
guiones ejecutándose de verdad. Son 15 comprobaciones:

- las páginas de `pages.txt` no desbordan a lo ancho;
- los controles de la cabecera miden 44 px o más;
- «Menú» abre y cierra, y la lupa busca en vivo;
- la cabecera pasa a cápsula al bajar;
- el estante y la tirada responden al teclado;
- el reproductor externo solo se carga al pulsar;
- el dossier imprime.

Cada comprobación falla también ante un error de página o de consola, ante un recurso propio que
no carga y ante una petición a un tercero que nadie pidió. La corre el job `navegador` del CI, sobre
el stack de desarrollo con los datos de `backend/datos_de_desarrollo/`.

```bash
node tools/ux/browser-smoke.js                              # contra http://localhost:8000
node tools/ux/browser-smoke.js --base http://127.0.0.1:8096 # otra base
```

Sale con 1 si falla alguna. Si una falla después de un cambio de diseño, antes de ajustarla hay
que preguntarse qué vigilaba.

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
| `preparar-entorno.sh` | Reconstruye el entorno de diseño en una máquina nueva: demostración, identidad real, 12 integrantes y material genérico. Idempotente. | `bash tools/ux/preparar-entorno.sh` |
| `ver.js` | Capturas sueltas a cualquier ancho y de cualquier ruta, con aviso de scroll horizontal. | `node tools/ux/ver.js tools/ux/out/prueba 768 900 poemas=/poemas/` |
| `hoja.js` | Hoja de contactos: varias capturas en una sola imagen. | `node tools/ux/hoja.js tools/ux/out/prueba tools/ux/out/prueba/hoja.png -d1440-full.png 620 3 home poemas` |
| `superficies.js` | Bandas de tinta, planos de amarillo por pantalla, cajas blancas con borde y textos bajo AA contra el fondo que tienen debajo, página a página (pasos 13 y siguientes). Sale con 1 si una página no cumple. | `node tools/ux/superficies.js 951 900` (todas) o `… 390 800 home dossier` |
| `variantes.js` | Alternativas de una pieza sobre la página real: CSS (y JS) inyectado en el navegador de captura, una imagen por variante, recortada a la pieza. Para que el dueño elija viendo. | `node tools/ux/variantes.js tools/ux/out/cifras 951 900 / .hero hoy=- marcador=marcador.css` |
| `iconos.js` | El icono de la pestaña (32 px y `.ico`), el del teléfono (180 px) y la tarjeta para compartir (1200 × 630), dibujados con la Syne del sitio. Necesita el sitio arriba y Pillow en python3. | `node tools/ux/iconos.js` |
| `mutar.sh` | Comprueba que una prueba nueva **falla** cuando se rompe lo que vigila. | `bash tools/ux/mutar.sh static/css/site.css '<actual>' '<roto>' 'tests/…::test_…'` |
| `fusionar.sh` | Fusiona el PR de un paso solo si su CI está verde, con el asunto del proyecto. | `bash tools/ux/fusionar.sh 105 <rama> "<efecto visible>"` |

Cada uno explica sus argumentos en su cabecera. `ver.js` y `hoja.js` usan el mismo Chrome que
`capture.js` (variable `CHROME`) y la misma base (`UX_BASE`).

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
