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
entera) y `-metrics.json`. `tools/ux/out/` no se versiona.

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
