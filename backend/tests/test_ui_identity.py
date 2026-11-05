"""Identidad tipográfica y nav responsive (Lote UI-2)."""

import re

import pytest
from django.conf import settings
from django.urls import reverse

from tests import css

pytestmark = pytest.mark.django_db

NAV_URLS = [
    "content:poem_index",
    "people:member_index",
    "agenda:agenda",
    "agenda:trayectoria",
    "agenda:gallery",
    "media:recording_index",
    "showcase:publication_index",
    "showcase:press_index",
    "showcase:dossier",
]


def test_nav_links_intact_in_disclosure(client):
    content = client.get(reverse("site:home")).content
    assert b"nav-disclosure" in content
    assert b"<summary>Men\xc3\xba</summary>" in content
    # El disclosure no quita enlaces del DOM: los 9 siguen presentes.
    for name in NAV_URLS:
        assert reverse(name).encode() in content


FUENTES = ["bricolage-grotesque.woff2", "rdv-serif.woff2", "rdv-serif-italic.woff2"]


@pytest.mark.parametrize("archivo", FUENTES)
def test_font_file_is_bundled(archivo):
    font = settings.BASE_DIR / "static" / "fonts" / archivo
    assert font.exists()
    assert font.read_bytes()[:4] == b"wOF2"  # firma woff2 válida


def test_las_fuentes_caben_en_su_presupuesto():
    """Decisión D4: la serif de lectura entra si el total de fuentes no pasa de 200 KB. Con
    los dos ejes completos la serif sola pesaba 302 KB."""
    total = sum((settings.BASE_DIR / "static" / "fonts" / f).stat().st_size for f in FUENTES)
    assert total <= 200 * 1024, f"las fuentes pesan {total / 1024:.0f} KB"


def test_la_licencia_de_la_serif_viaja_con_ella():
    """La OFL exige que cada copia lleve el aviso de copyright y la licencia, y prohíbe que
    una versión modificada use el nombre reservado. Las dos cosas quedan escritas junto a
    los archivos."""
    carpeta = settings.BASE_DIR / "static" / "fonts"
    licencia = (carpeta / "OFL-source-serif-4.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in licencia
    assert "Reserved Font Name" in licencia and "Adobe" in licencia
    aviso = (carpeta / "NOTICE.txt").read_text(encoding="utf-8")
    for clave in (
        "rdv-serif.woff2",
        "rdv-serif-italic.woff2",
        "Source Serif 4",
        "OFL-source-serif-4.txt",
    ):
        assert clave in aviso, f"fonts/NOTICE.txt no menciona «{clave}»"


def _requested_fonts():
    """Cada archivo de fuente que pide una @font-face de la hoja, con su @font-face. La url()
    es relativa: la reescribe WhiteNoise."""
    return {
        archivo: cara
        for cara in css.at_rules("font-face")
        for archivo in re.findall(r'url\("\.\./fonts/([^"]+)"\)', cara.get("src", ""))
    }


def test_css_declares_self_hosted_display_font():
    pedidas = _requested_fonts()
    assert set(FUENTES) <= set(pedidas), sorted(pedidas)
    assert all(cara["font-display"] == "swap" for cara in pedidas.values())
    assert pedidas["bricolage-grotesque.woff2"]["font-family"] == '"Bricolage Grotesque"'
    assert css.split_commas(css.tokens()["--display"])[0] == '"Bricolage Grotesque"'


def test_las_fuentes_de_la_primera_pantalla_se_precargan(client):
    """La fuente de titulares y la redonda de la serif se piden sin esperar a que el navegador lea el CSS y
    descubra que las necesita. La cursiva no: rara vez está en la primera pantalla, y una
    precarga que no se usa compite con lo que sí.

    La URL de la precarga debe ser la MISMA que resuelve el url() de la hoja (sin
    parámetro de versión); si difieren, el archivo se descarga dos veces. `crossorigin`
    es obligatorio en una precarga de fuente, aunque sea del mismo origen: sin él el
    navegador la descarta y vuelve a pedirla.
    """
    html = client.get(reverse("site:home")).content.decode()
    precargas = re.findall(r'<link rel="preload"[^>]*>', html)
    assert len(precargas) == 2, f"se esperaban dos precargas, hay {len(precargas)}"
    archivos = sorted(re.search(r'href="[^"?]*fonts/([^"?/]+)"', p).group(1) for p in precargas)
    assert [re.sub(r"\.[0-9a-f]{12}\.", ".", a) for a in archivos] == [
        "bricolage-grotesque.woff2",
        "rdv-serif.woff2",
    ]
    for etiqueta in precargas:
        assert 'as="font"' in etiqueta and 'type="font/woff2"' in etiqueta
        assert "crossorigin" in etiqueta


def test_no_hay_fuentes_huerfanas():
    """Toda fuente empaquetada debe estar referenciada por el CSS.

    Un .woff2 que ya nadie pide no rompe nada visible: simplemente viaja en la
    imagen y en el manifiesto de estáticos. Fraunces pesaba 67 KB y se quedó
    sin empleo al cambiar la tipografía de titular; esta prueba evita que la
    próxima sustitución deje otro archivo muerto detrás.
    """
    fuentes = sorted((settings.BASE_DIR / "static" / "fonts").glob("*.woff2"))
    assert fuentes, "no hay ninguna fuente empaquetada"
    pedidas = _requested_fonts()
    huerfanas = [f.name for f in fuentes if f.name not in pedidas]
    assert not huerfanas, f"fuentes que el CSS no referencia: {huerfanas}"


# Las dos parciales que producen una tarjeta de listado. El titular de la tarjeta
# es la superficie donde más se repite la tipografía de titular en todo el sitio.
TARJETAS = [
    "partials/_article_card.html",
    "partials/_poem_card.html",
]


def _selectores_de_titular():
    """Los selectores de las reglas que fijan font-family:var(--display)."""
    selectores = {
        selector
        for regla in css.rules()
        if regla.context == () and regla.get("font-family") == "var(--display)"
        for selector in regla.selectors
    }
    assert selectores, "no se encontró la regla que fija la tipografía de titular"
    return selectores


def test_titulo_de_tarjeta_usa_la_tipografia_de_titular():
    """El CSS debe nombrar la etiqueta que la plantilla emite de verdad.

    La regla apuntaba a `.article-card h2` mientras ambas parciales emiten
    `<h3>`, así que el selector estaba muerto y los títulos de todos los
    listados caían a `--serif`, la pila con Georgia. Con una serif de titular
    la diferencia era casi invisible; con cualquier otra familia, evidente.
    """
    selectores = _selectores_de_titular()
    for parcial in TARJETAS:
        html = (settings.BASE_DIR / "templates" / parcial).read_text(encoding="utf-8")
        etiqueta = re.search(r"<(h[1-6])[\s>]", html)
        assert etiqueta, f"{parcial} ya no emite ningún titular"
        assert f".article-card {etiqueta.group(1)}" in selectores, (
            f"{parcial} emite <{etiqueta.group(1)}> pero la regla de titulares "
            f"no lo cubre; el título caerá a la serif del cuerpo"
        )


# `.stats-strip` es la tira de cifras de la trayectoria: cifras de dato, no de cartel. La
# cifra grande es la del dossier (`.dossier-cifras`, ticket 5.1): la portada tuvo una
# (`.hero-stats`) hasta que el dueño la quitó, el 2026-10-14.


def test_la_cifra_grande_solo_esta_en_el_dossier():
    """Ninguna regla puede agrandar el <strong> de una tira de cifras fuera del dossier. Si
    la regla del número grande pasara a `.stats-strip strong`, /trayectoria/ mostraría
    cifras de cartel sin que nadie lo hubiera pedido. En el dossier sí: es lo primero que
    busca un jurado (D11).
    """
    grandes = [
        regla.selector
        for regla in css.rules()
        if "strong" in regla.selector
        and ("stats" in regla.selector or "cifras" in regla.selector)
        and any(css.px_range(tam)[1] > 24 for tam in regla.values("font-size"))
    ]
    assert grandes == [".dossier-cifras strong"], (
        f"la cifra grande tiene que estar en el dossier y solo ahí: {grandes}"
    )


def test_la_trayectoria_conserva_su_tira_y_el_dossier_tiene_sus_cifras():
    """La trayectoria rotula sus cifras como dato; el dossier, con número grande. Ninguna de
    las dos lleva la marca de portada, que heredaría su estilo."""
    tpl = settings.BASE_DIR / "templates"
    trayectoria = (tpl / "agenda/trayectoria.html").read_text(encoding="utf-8")
    dossier = (tpl / "showcase/dossier.html").read_text(encoding="utf-8")
    assert "stats-strip" in trayectoria, "la trayectoria ya no usa la tira de cifras"
    assert "dossier-cifras" in dossier and "stats-strip" not in dossier
    for texto in (trayectoria, dossier):
        assert "hero-stats" not in texto


def test_ninguna_regla_estiliza_un_titular_que_las_tarjetas_no_emiten():
    """Caza TODAS las reglas con el selector muerto, no solo una.

    `test_titulo_de_tarjeta_usa_la_tipografia_de_titular` solo vigilaba la
    regla de la familia tipográfica. Otras tres —tamaño, color y subrayado—
    siguieron apuntando a `.article-card h2`, que ninguna plantilla emite, así
    que el título del listado caía al estilo global de enlace (magenta y
    subrayado) y al cuerpo por defecto del navegador para un h3: 18,7px frente
    a los 26 previstos, apenas un 17% por encima del resumen.

    Una regla con selector muerto no da error: simplemente no se aplica. Por
    eso hace falta comprobarlo, y comprobarlo entero.
    """
    tpl = settings.BASE_DIR / "templates"
    emitidas = set()
    for parcial in TARJETAS:
        html = (tpl / parcial).read_text(encoding="utf-8")
        emitidas.update(re.findall(r"<(h[1-6])[\s>]", html))
    assert emitidas, "las parciales de tarjeta ya no emiten ningún titular"

    estilizadas = {
        titular
        for regla in css.rules()
        for selector in regla.selectors
        for titular in re.findall(r"\.article-card (h[1-6])\b", selector)
    }
    assert estilizadas, "la hoja ya no estiliza el titular de las tarjetas"
    muertas = estilizadas - emitidas
    assert not muertas, (
        f"el CSS estiliza .article-card {sorted(muertas)} pero las parciales emiten "
        f"{sorted(emitidas)}: esas reglas no se aplican a nada"
    )
