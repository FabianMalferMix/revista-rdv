#!/usr/bin/env python3
"""Tabla y comparación de las métricas que escribe capture.js.

    python3 tools/ux/metrics.py tabla <dir>
    python3 tools/ux/metrics.py comparar <dirAntes> <dirDespues>

Solo biblioteca estándar. Solo se muestran y se comparan las páginas que respondieron 200: una
fila con otro código, o sin él, se nombra al final con su ruta y su código, y la orden sale con 1.
Encima de la tabla va con qué se midió cada directorio (el commit, el navegador y la huella de
los datos de desarrollo, si capture.js los guardó); al comparar, avisa si el navegador o los datos
no son los mismos, porque entonces una diferencia puede no venir del diseño. Columnas:
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
# Los campos de `provenance` que se muestran, con su nombre en la cabecera.
PROVENANCE = (("commit", "commit"), ("browser", "navegador"), ("devDataSha256", "datos"))


def cargar(directorio):
    datos = {}
    for archivo in sorted(Path(directorio).glob("*-metrics.json")):
        clave = archivo.name[: -len("-metrics.json")]
        datos[clave] = json.loads(archivo.read_text(encoding="utf-8"))
    if not datos:
        sys.exit(f"sin archivos *-metrics.json en {directorio}")
    return datos


def split_by_status(datos):
    """Las filas de las páginas que respondieron 200 y, aparte, las demás, con su ruta y su código."""
    measured, refused = {}, []
    for clave, m in datos.items():
        if m.get("estado") == 200:
            measured[clave] = m
        else:
            refused.append((clave, m.get("ruta") or "sin ruta", m.get("estado") or "sin código"))
    return measured, refused


def report_refused(refused, directorio):
    for clave, ruta, estado in refused:
        print(f"sin medir en {directorio}: {clave} ({ruta}) respondió {estado}", file=sys.stderr)


def provenance(datos):
    """Los valores de cada campo de procedencia que hay en un directorio, y si alguna medición se
    hizo con cambios sin confirmar."""
    found = {campo: set() for campo, _ in PROVENANCE}
    uncommitted = False
    for m in datos.values():
        origen = m.get("provenance") or {}
        for campo in found:
            if origen.get(campo):
                found[campo].add(origen[campo])
        uncommitted = uncommitted or bool(origen.get("uncommittedChanges"))
    return found, uncommitted


def describe(datos):
    found, uncommitted = provenance(datos)
    if not any(found.values()):
        return "sin procedencia (medido antes de que capture.js la guardara)"
    partes = []
    for campo, nombre in PROVENANCE:
        valores = sorted(v if campo == "browser" else v[:12] for v in found[campo])
        partes.append(f"{nombre} {', '.join(valores) or '?'}")
    return " · ".join(partes) + (" (con cambios sin confirmar)" if uncommitted else "")


def warn_if_provenance_differs(a, d):
    (pa, _), (pd, _) = provenance(a), provenance(d)
    avisos = (
        ("browser", "el navegador no es el mismo"),
        ("devDataSha256", "los datos de desarrollo no son los mismos"),
    )
    for campo, aviso in avisos:
        if pa[campo] and pd[campo] and pa[campo] != pd[campo]:
            print(
                f"aviso: {aviso} en las dos mediciones: una diferencia puede venir de ahí y no "
                "del diseño",
                file=sys.stderr,
            )


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
    datos, refused = split_by_status(cargar(directorio))
    print(f"medido con: {describe(datos)}\n")
    print(f"{'página-viewport':26}" + "".join(f"{c:>8}" for c in COLUMNAS))
    for clave, m in datos.items():
        f = fila(m)
        print(f"{clave:26}" + "".join(f"{celda(f[c]):>8}" for c in COLUMNAS))
    report_refused(refused, directorio)
    return 1 if refused else 0


def comparar(antes, despues):
    a, refused_a = split_by_status(cargar(antes))
    d, refused_d = split_by_status(cargar(despues))
    print(f"antes:   {describe(a)}\ndespués: {describe(d)}\n")
    warn_if_provenance_differs(a, d)
    print(f"{'página-viewport':26}" + "".join(f"{c:>14}" for c in COLUMNAS))
    for clave in sorted(set(a) & set(d)):
        fa, fd = fila(a[clave]), fila(d[clave])
        celdas = []
        for c in COLUMNAS:
            va, vd = celda(fa[c]), celda(fd[c])
            celdas.append(f"{va if va == vd else va + '→' + vd:>14}")
        print(f"{clave:26}" + "".join(celdas))
    # Las que no respondieron 200 en un lado tampoco se comparan con el otro.
    sin_medir = {clave for clave, _, _ in refused_a + refused_d}
    solo = sorted((set(a) ^ set(d)) - sin_medir)
    if solo:
        print("\nsolo en uno de los dos directorios:", ", ".join(solo))
    report_refused(refused_a, antes)
    report_refused(refused_d, despues)
    return 1 if refused_a or refused_d else 0


def main(argv):
    if len(argv) == 3 and argv[1] == "tabla":
        sys.exit(tabla(argv[2]))
    elif len(argv) == 4 and argv[1] == "comparar":
        sys.exit(comparar(argv[2], argv[3]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
