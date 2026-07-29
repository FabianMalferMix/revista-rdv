"""Las librerías JS vendorizadas coinciden con lo declarado (hallazgo S-31).

htmx y TinyMCE se sirven auto-hospedados para que la CSP pueda limitar `script-src` a
`'self'`. El precio es que quedan fuera del radar de todo el utillaje de seguridad: ni
Dependabot, ni pip-audit, ni trivy las ven. `backend/static/vendor/VERSIONS.md` es el
registro que sustituye a ese radar — y solo sirve de algo si algo comprueba que dice la
verdad. Estos tests son ese algo: si alguien re-vendoriza sin actualizar el registro, o
actualiza el registro sin cambiar el archivo, fallan.
"""

import hashlib
import re
from pathlib import Path

import pytest

VENDOR = Path(__file__).resolve().parent.parent / "static" / "vendor"
REGISTRO = VENDOR / "VERSIONS.md"


def _fila(nombre):
    """Extrae (versión, sha256) de la fila del inventario para esa librería."""
    texto = REGISTRO.read_text(encoding="utf-8")
    patron = rf"^\|\s*{nombre}\s*\|\s*([^|]+?)\s*\|[^|]*\|\s*`([0-9a-f]{{64}})`\s*\|"
    match = re.search(patron, texto, re.MULTILINE)
    assert match, f"{nombre} no aparece en el inventario de VERSIONS.md"
    return match.group(1), match.group(2)


def _sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_el_registro_de_versiones_existe():
    assert REGISTRO.exists(), "falta el registro de lo vendorizado"


def test_htmx_coincide_con_lo_declarado():
    version, sha = _fila("htmx")
    bundle = VENDOR / "htmx" / "htmx.min.js"
    assert _sha256(bundle) == sha, "el archivo de htmx no es el declarado en VERSIONS.md"
    # La versión también va dentro del bundle: se comprueba que las tres coincidan.
    incrustada = re.search(rb'"(\d+\.\d+\.\d+)"', bundle.read_bytes())
    assert incrustada, "no se encontró la cadena de versión dentro de htmx.min.js"
    assert incrustada.group(1).decode() == version


def test_tinymce_coincide_con_lo_declarado():
    version, sha = _fila("TinyMCE")
    bundle = VENDOR / "tinymce" / "tinymce.min.js"
    assert _sha256(bundle) == sha, "el archivo de TinyMCE no es el declarado en VERSIONS.md"
    incrustada = re.search(rb'majorVersion:"(\d+)",minorVersion:"([\d.]+)"', bundle.read_bytes())
    assert incrustada, "no se encontró la versión dentro de tinymce.min.js"
    encontrada = f"{incrustada.group(1).decode()}.{incrustada.group(2).decode()}"
    assert encontrada == version


def test_htmx_esta_al_dia_en_su_linea_2_0():
    """htmx 2.0.3 acumulaba ~21 meses y 7 releases de parche de retraso (S-32). No se
    consulta la red: se fija el suelo conocido para que un downgrade cante."""
    version, _ = _fila("htmx")
    mayor, menor, parche = (int(p) for p in version.split("."))
    assert (mayor, menor) == (2, 0)
    assert parche >= 10, "htmx quedó por detrás de la 2.0.10 ya verificada"


@pytest.mark.parametrize(
    "relativa",
    [
        "htmx/htmx.min.js",
        "tinymce/tinymce.min.js",
        "tinymce/themes/silver/theme.min.js",
        "tinymce/models/dom/model.min.js",
    ],
)
def test_los_bundles_declarados_estan_presentes(relativa):
    assert (VENDOR / relativa).is_file(), f"falta el bundle vendorizado {relativa}"
