"""Lo vendorizado es exactamente lo que dice su manifiesto (hallazgo S-31).

htmx y TinyMCE se sirven auto-hospedados para que la CSP pueda limitar `script-src` a `'self'`,
y quedan fuera del radar de pip-audit y trivy. `static/vendor/manifest.json` dice qué hay: el
paquete de npm, la versión, la integridad del paquete y el sha256 de cada archivo
(`tools/vendor/update.py` lo escribe y lo comprueba contra npm). Estas pruebas atan el árbol al
manifiesto, la versión que llevan dentro las librerías a la declarada, los plugins que pide el
editor a sus archivos, la URL de TinyMCE a su versión y `package.json`, que vigila Dependabot, a
las mismas versiones.
"""

import hashlib
import json
import re
from pathlib import Path

from apps.content.admin import RichTextWidget
from config.staticfiles import TINYMCE_DIR

STATIC = Path(__file__).resolve().parent.parent / "static"
VENDOR = STATIC / "vendor"
MANIFEST = json.loads((VENDOR / "manifest.json").read_text("utf-8"))
NOT_VENDORED = {"VERSIONS.md", "manifest.json", "package.json"}


def _target(lib):
    return lib["target"].format(version=lib["version"])


def test_the_tree_is_exactly_the_manifest():
    declared = {
        _target(lib) + relative: sha
        for lib in MANIFEST.values()
        for relative, sha in lib["files"].items()
    }
    present = {
        str(path.relative_to(VENDOR)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in VENDOR.rglob("*")
        if path.is_file() and path.name not in NOT_VENDORED
    }
    assert sorted(present) == sorted(declared), "sobra o falta un archivo en static/vendor"
    assert [p for p, sha in present.items() if declared[p] != sha] == []


def test_the_declared_versions_are_the_ones_inside_the_bundles():
    htmx = (VENDOR / _target(MANIFEST["htmx"]) / "htmx.min.js").read_bytes()
    assert re.search(rb'"(\d+\.\d+\.\d+)"', htmx).group(1).decode() == MANIFEST["htmx"]["version"]
    tinymce = (VENDOR / _target(MANIFEST["tinymce"]) / "tinymce.min.js").read_bytes()
    found = re.search(rb'majorVersion:"(\d+)",minorVersion:"([\d.]+)"', tinymce)
    assert f"{found.group(1).decode()}.{found.group(2).decode()}" == MANIFEST["tinymce"]["version"]


def test_htmx_esta_al_dia_en_su_linea_2_0():
    """htmx 2.0.3 acumulaba ~21 meses y 7 releases de parche de retraso (S-32). No se
    consulta la red: se fija el suelo conocido para que un downgrade cante."""
    mayor, menor, parche = (int(p) for p in MANIFEST["htmx"]["version"].split("."))
    assert (mayor, menor) == (2, 0)
    assert parche >= 11, "htmx quedó por detrás de la 2.0.11 ya verificada"


def test_dependabot_watches_the_vendored_versions():
    package = json.loads((VENDOR / "package.json").read_text("utf-8"))
    assert package["dependencies"] == {lib["package"]: lib["version"] for lib in MANIFEST.values()}


def test_the_tinymce_url_carries_its_version():
    assert TINYMCE_DIR == f"vendor/tinymce-{MANIFEST['tinymce']['version']}/"
    assert f"{TINYMCE_DIR}tinymce.min.js" in str(RichTextWidget().media)


def test_every_plugin_the_editor_asks_for_is_vendored():
    init = (STATIC / "admin" / "richtext_init.js").read_text("utf-8")
    plugins = re.search(r'plugins:\s*"([^"]+)"', init).group(1).split()
    assert plugins
    files = MANIFEST["tinymce"]["files"]
    assert [p for p in plugins if f"plugins/{p}/plugin.min.js" not in files] == []
    assert {"themes/silver/theme.min.js", "models/dom/model.min.js"} <= set(files)
