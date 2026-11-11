"""Los guiones del sitio, leídos como texto: lo que cada uno toma de common.js y lo que common.js
comparte. Lo usan las pruebas que miran que lo común no se copie."""

import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "static" / "js"
COMMON = JS / "common.js"
SCRIPTS = sorted(JS.glob("*.js"))


def taken_from_common(source):
    """Los nombres que un guion toma de common.js (`const { … } = common;`)."""
    return {
        name.strip()
        for names in re.findall(r"const \{([^}]*)\} = common;", source)
        for name in names.split(",")
    }


def shared_by_common():
    """Lo que common.js deja en `window.common`: los ayudantes (`quieto,`) y las curvas de la
    hoja (`get CURVA()`), cada una con la propiedad de la hoja que lee."""
    shared = re.search(
        r"window\.common = Object\.freeze\(\{(.*?)\n  \}\);", COMMON.read_text(), re.S
    )
    body = shared.group(1)
    helpers = set(re.findall(r"^\s+(\w+),$", body, re.M))
    curves = dict(
        re.findall(r"get (\w+)\(\) \{\s*return [^;]*getPropertyValue\('(--[\w-]+)'\)", body)
    )
    return helpers, curves
