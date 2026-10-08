#!/usr/bin/env python3
"""Tabla y comparación de las métricas que escribe capture.js.

    python3 tools/ux/metrics.py tabla <dir>
    python3 tools/ux/metrics.py comparar <dirAntes> <dirDespues>

Solo biblioteca estándar. Columnas:
  razon   ancho del texto / ancho del viewport (cuánto del ancho se usa)
  h1      tamaño del primer h1 visible, en px
  cuerpo  tamaño de fuente de <body>, en px
  cpl     caracteres en la línea más larga del cuerpo de artículo (45–75 es lo legible)
  img1    imágenes en el primer viewport
  desv    imágenes cuya caja no respeta la proporción pedida (deformadas o mal recortadas)
  mono%   porcentaje de elementos con texto pintados en la monoespaciada
  MAY     elementos con texto en mayúsculas
  <12     elementos con texto por debajo de 12 px
  <24     objetivos pulsables de menos de 24 px (WCAG 2.5.8)
  desb    hay scroll horizontal (a este viewport, o a 320 px en la fila móvil)
  alto    alto total de la página, en px
"""

import json
import sys
from pathlib import Path

COLUMNAS = ["razon", "h1", "cuerpo", "cpl", "img1", "desv", "mono%", "MAY", "<12", "<24", "desb", "alto"]


def cargar(directorio):
    datos = {}
    for archivo in sorted(Path(directorio).glob("*-metrics.json")):
        clave = archivo.name[: -len("-metrics.json")]
        datos[clave] = json.loads(archivo.read_text(encoding="utf-8"))
    if not datos:
        sys.exit(f"sin archivos *-metrics.json en {directorio}")
    return datos


def fila(m):
    texto = m["texto"]
    total = max(1, texto["elementos"])
    desborde = m.get("desbordeHorizontal") or m.get("desborde320")
    return {
        "razon": texto["razon"],
        "h1": (m.get("h1") or {}).get("px"),
        "cuerpo": m.get("cuerpoPx"),
        "cpl": m["cpl"].get("articulo"),
        "img1": m["imagenes"]["enPrimerViewport"],
        "desv": m["imagenes"]["desviadas"],
        "mono%": round(100 * texto["porTipo"]["mono"] / total),
        "MAY": texto["mayusculas"],
        "<12": texto["bajo12"],
        "<24": m["objetivos"]["bajo24"],
        "desb": "SÍ" if desborde else "",
        "alto": m["altoPagina"],
    }


def celda(valor):
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:g}"
    return str(valor)


def tabla(directorio):
    datos = cargar(directorio)
    print(f"{'página-viewport':26}" + "".join(f"{c:>8}" for c in COLUMNAS))
    for clave, m in datos.items():
        f = fila(m)
        print(f"{clave:26}" + "".join(f"{celda(f[c]):>8}" for c in COLUMNAS))


def comparar(antes, despues):
    a, d = cargar(antes), cargar(despues)
    print(f"{'página-viewport':26}" + "".join(f"{c:>14}" for c in COLUMNAS))
    for clave in sorted(set(a) & set(d)):
        fa, fd = fila(a[clave]), fila(d[clave])
        celdas = []
        for c in COLUMNAS:
            va, vd = celda(fa[c]), celda(fd[c])
            celdas.append(f"{va if va == vd else va + '→' + vd:>14}")
        print(f"{clave:26}" + "".join(celdas))
    solo = sorted(set(a) ^ set(d))
    if solo:
        print("\nsolo en uno de los dos directorios:", ", ".join(solo))


def main(argv):
    if len(argv) == 3 and argv[1] == "tabla":
        tabla(argv[2])
    elif len(argv) == 4 and argv[1] == "comparar":
        comparar(argv[2], argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
