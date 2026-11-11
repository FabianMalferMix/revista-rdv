"""Lo que comparten los guiones del sitio vive en static/js/common.js: la consulta de «reducir
movimiento», si se puede animar, las curvas de la hoja, el gesto de deslizar y el montaje de cada
componente. Ningún otro guion lo copia, y common.js llega antes que los guiones que lo usan. Que
montar dos veces no duplique escuchas, que lo que llega con htmx se monte, que el gesto sea solo
del dedo, que con «reducir movimiento» nada se anime y que sin common.js la página siga usable lo
mira la prueba de humo (tools/ux/browser-smoke.js)."""

import re

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from apps.people.models import Contributor
from tests.factories import make_publication, make_recording
from tests.scripts import COMMON, SCRIPTS, shared_by_common, taken_from_common

# Lo que delata, en otro guion, una copia de lo que hace common.js.
COPIES = {
    "la consulta de «reducir movimiento»": r"prefers-reduced-motion:\s*reduce",
    "la comprobación de la API de animaciones": r"Element\.prototype\.animate",
    "el gesto de deslizar": r"""['"]pointer(?:up|cancel)['"]""",
}


def test_no_script_copies_what_common_js_shares():
    """Ni su código, ni sus nombres, ni las propiedades de la hoja que lee: un guion que lo
    necesita lo toma de `window.common`, y solo toma lo que common.js tiene."""
    helpers, curves = shared_by_common()
    common = COMMON.read_text()
    assert all(re.search(pattern, common) for pattern in COPIES.values()), "control: common.js"
    assert {"--ease-tirada", "--ease"} <= set(curves.values()), "control: las curvas de la hoja"
    copied, unknown = [], []
    for script in SCRIPTS:
        if script == COMMON:
            continue
        source = script.read_text()
        copied += [f"{script.name}: {what}" for what, p in COPIES.items() if re.search(p, source)]
        copied += [
            f"{script.name}: define {name}"
            for name in helpers
            if re.search(rf"\b(?:function|const|let|var)\s+{name}\b", source)
        ]
        copied += [
            f"{script.name}: lee {prop}"
            for prop in re.findall(r"getPropertyValue\('(--[\w-]+)'\)", source)
            if prop in curves.values()
        ]
        unknown += [
            f"{script.name}: {name}" for name in taken_from_common(source) - {*helpers, *curves}
        ]
    assert not copied, f"lo común, copiado: {copied}"
    assert not unknown, f"toman de common.js lo que no tiene: {unknown}"


def test_what_moves_asks_common_js_first():
    """Quien pidió menos movimiento no ve nada animarse: cada guion que anima pregunta antes a
    common.js, que responde que no si el sistema pide reducir el movimiento."""
    common = COMMON.read_text()
    quieto = re.search(r"const quieto = window\.matchMedia\('([^']+)'\);", common).group(1)
    assert quieto == "(prefers-reduced-motion: reduce)"
    assert "!quieto.matches" in re.search(r"const canAnimate = \(\) => ([^;]+);", common).group(1)
    animate = [s for s in SCRIPTS if s != COMMON and ".animate(" in s.read_text()]
    names = {s.name for s in animate}
    assert {"registros.js", "estante.js", "integrantes.js"} <= names, "control: los que animan"
    assert not [s.name for s in animate if "canAnimate" not in taken_from_common(s.read_text())]


@pytest.fixture
def every_component(db):
    """Lo que hace que la portada pida sus tres guiones: dos registros destacados (la tirada),
    más integrantes de las que caben en el teléfono (el relevo) y dos publicaciones (el estante)."""
    for n in range(5):
        Contributor.objects.create(
            slug=f"voz-{n}", display_name=f"Voz {n}", is_member=True, active=True, position=n
        )
    for n in range(2):
        make_recording(featured=True, position=n)
        make_publication()


@pytest.mark.parametrize("route", ["site:home", "showcase:dossier", "site:search"])
def test_common_js_comes_with_defer_before_the_scripts_that_use_it(client, every_component, route):
    """Con defer, los guiones corren en el orden de la página cuando esta terminó de leerse:
    common.js va antes que cada guion con defer que toma algo de él."""
    page = BeautifulSoup(client.get(reverse(route)).content, "html.parser")
    scripts = [s for s in page.select("script[src]") if "/static/js/" in s["src"]]
    names = [re.search(r"/js/([a-z_]+)\.js", s["src"]).group(1) + ".js" for s in scripts]
    assert "common.js" in names, f"{route} no carga common.js"
    first = names.index("common.js")
    assert scripts[first].has_attr("defer")
    users = [
        n
        for n, s in zip(names, scripts, strict=True)
        if s.has_attr("defer") and taken_from_common((COMMON.parent / n).read_text())
    ]
    if route == "site:home":
        assert {"registros.js", "integrantes.js", "estante.js"} <= set(users), "control: la portada"
    assert not [n for n in users if names.index(n) < first], names
