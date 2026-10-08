# tools/ux — capturas y métricas de la interfaz

Instrumento de la auditoría UX/UI (`docs/auditoria-ux-ui.md`) y de su backlog
(`docs/backlog-ux-ui.md`). Mide lo que cada ticket promete: cuánto del ancho usa el texto,
tamaños reales, imágenes deformadas, objetivos pulsables, scroll horizontal. No forma parte
del despliegue: `tools/` está fuera de la imagen de Docker.

## Preparación (una vez)

```bash
npm --prefix tools/ux install        # playwright-core; usa el Chrome del sistema
```

Requiere Node 20 o superior y Chrome en `/usr/bin/google-chrome` (otra ruta: variable
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

Añadir una página: una línea en `pages.txt` (`nombre ruta [ancho]`).

## Lo demás que hay en esta carpeta

Ayudantes del plan de ejecución (`docs/plan-ejecucion-ux.md`). Nacieron como guiones sueltos
durante los primeros pasos; están aquí para que el plan se pueda seguir desde cualquier máquina.

| Archivo | Para qué | Uso |
|---|---|---|
| `preparar-entorno.sh` | Reconstruye el entorno de diseño en una máquina nueva: demostración, identidad real, 12 integrantes y material genérico. Idempotente. | `bash tools/ux/preparar-entorno.sh` |
| `ver.js` | Capturas sueltas a cualquier ancho y de cualquier ruta, con aviso de scroll horizontal. | `node tools/ux/ver.js tools/ux/out/prueba 768 900 poemas=/poemas/` |
| `hoja.js` | Hoja de contactos: varias capturas en una sola imagen. | `node tools/ux/hoja.js tools/ux/out/prueba tools/ux/out/prueba/hoja.png -d1440-full.png 620 3 home poemas` |
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
