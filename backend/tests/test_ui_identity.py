"""Identidad tipográfica y nav responsive (Lote UI-2)."""

import re

import pytest
from django.conf import settings
from django.urls import reverse

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
    content = client.get(reverse("content:home")).content
    assert b"nav-disclosure" in content
    assert b"<summary>Men\xc3\xba</summary>" in content
    # El disclosure no quita enlaces del DOM: los 9 siguen presentes.
    for name in NAV_URLS:
        assert reverse(name).encode() in content


FUENTES = ["syne.woff2", "rdv-serif.woff2", "rdv-serif-italic.woff2"]


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


def test_css_declares_self_hosted_display_font():
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    assert "@font-face" in css
    assert "syne.woff2" in css  # url() relativa (la reescribe WhiteNoise)
    assert "rdv-serif.woff2" in css and "rdv-serif-italic.woff2" in css
    assert "--display" in css
    assert "font-display:swap" in css


def test_las_fuentes_de_la_primera_pantalla_se_precargan(client):
    """Syne y la redonda de la serif se piden sin esperar a que el navegador lea el CSS y
    descubra que las necesita. La cursiva no: rara vez está en la primera pantalla, y una
    precarga que no se usa compite con lo que sí.

    La URL de la precarga debe ser la MISMA que resuelve el url() de la hoja (sin
    parámetro de versión); si difieren, el archivo se descarga dos veces. `crossorigin`
    es obligatorio en una precarga de fuente, aunque sea del mismo origen: sin él el
    navegador la descarta y vuelve a pedirla.
    """
    html = client.get(reverse("content:home")).content.decode()
    precargas = re.findall(r'<link rel="preload"[^>]*>', html)
    assert len(precargas) == 2, f"se esperaban dos precargas, hay {len(precargas)}"
    archivos = sorted(re.search(r'href="[^"?]*fonts/([^"?/]+)"', p).group(1) for p in precargas)
    assert [re.sub(r"\.[0-9a-f]{12}\.", ".", a) for a in archivos] == [
        "rdv-serif.woff2",
        "syne.woff2",
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
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    huerfanas = [f.name for f in fuentes if f.name not in css]
    assert not huerfanas, f"fuentes que el CSS no referencia: {huerfanas}"


# Las dos parciales que producen una tarjeta de listado. El titular de la tarjeta
# es la superficie donde más se repite la tipografía de titular en todo el sitio.
TARJETAS = [
    "content/partials/_article_card.html",
    "content/partials/_poem_card.html",
]


def _selectores_de_titular(css):
    """Lista de selectores de la regla que fija font-family:var(--display)."""
    m = re.search(r"([^{}]+)\{[^{}]*font-family:var\(--display\)", css)
    assert m, "no se encontró la regla que fija la tipografía de titular"
    return m.group(1)


def test_titulo_de_tarjeta_usa_la_tipografia_de_titular():
    """El CSS debe nombrar la etiqueta que la plantilla emite de verdad.

    La regla apuntaba a `.article-card h2` mientras ambas parciales emiten
    `<h3>`, así que el selector estaba muerto y los títulos de todos los
    listados caían a `--serif`, la pila con Georgia. Con una serif de titular
    la diferencia era casi invisible; con cualquier otra familia, evidente.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    selectores = _selectores_de_titular(css)
    for parcial in TARJETAS:
        html = (settings.BASE_DIR / "templates" / parcial).read_text(encoding="utf-8")
        etiqueta = re.search(r"<(h[1-6])[\s>]", html)
        assert etiqueta, f"{parcial} ya no emite ningún titular"
        assert f".article-card {etiqueta.group(1)}" in selectores, (
            f"{parcial} emite <{etiqueta.group(1)}> pero la regla de titulares "
            f"no lo cubre; el título caerá a la serif del cuerpo"
        )


# `.stats-strip` es la tira de cifras del dossier y de la trayectoria: cifras de dato, no de
# cartel. La portada tuvo una con número grande (`.hero-stats`) hasta que el dueño la quitó.


def test_ninguna_tira_de_cifras_lleva_la_cifra_grande_fuera_de_la_portada():
    """Ninguna regla puede agrandar el <strong> de una tira de cifras sin acotarla a la
    portada. Si la regla del número grande pasara a `.stats-strip strong`, /dossier/ y
    /trayectoria/ mostrarían cifras de cartel sin que nadie lo hubiera pedido. Hoy no hay
    ninguna: la portada ya no lleva cifras.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    raiz = re.search(r":root\{(.*?)\n\}", css, re.S).group(1)
    escala = dict(re.findall(r"(--t-?\d):\s*([^;]+);", raiz))

    def maximo_px(valor):
        token = re.fullmatch(r"var\((--t-?\d)\)", valor.strip())
        valor = escala[token.group(1)] if token else valor
        return max(float(n) for n in re.findall(r"([\d.]+)px", valor))

    reglas = re.findall(r"([^{}]*strong[^{}]*)\{([^{}]*)\}", css)
    for selector, cuerpo in reglas:
        if "stats" not in selector:
            continue
        tam = re.search(r"font-size:\s*([^;]+)", cuerpo)
        if tam and maximo_px(tam.group(1)) > 24:
            assert ".hero-stats" in selector, (
                f"la cifra grande dejó de estar acotada a la portada: «{selector.strip()}»; "
                f"así se filtra a /dossier/ y /trayectoria/"
            )


def test_el_dossier_y_la_trayectoria_no_llevan_la_marca_de_portada():
    """`hero-stats` marcaba la tira con estilo de portada: las otras no la llevan."""
    tpl = settings.BASE_DIR / "templates"
    for otra in ("showcase/dossier.html", "agenda/trayectoria.html"):
        texto = (tpl / otra).read_text(encoding="utf-8")
        assert "stats-strip" in texto, f"{otra} ya no usa la tira de cifras"
        assert "hero-stats" not in texto, (
            f"{otra} adoptó la marca de portada y heredaría la cifra grande"
        )


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

    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    estilizadas = set(re.findall(r"\.article-card\s+(h[1-6])\b", css))
    muertas = estilizadas - emitidas
    assert not muertas, (
        f"el CSS estiliza .article-card {sorted(muertas)} pero las parciales emiten "
        f"{sorted(emitidas)}: esas reglas no se aplican a nada"
    )
