"""La hoja de la portada: la cejilla (el lema, el lugar, desde cuándo, cuántas integrantes y el
Instagram), el manifiesto hasta su primera pausa, los botones y, mientras haya una convocatoria
abierta, su sello. Desde 900 px es una lámina a dos tintas. Sin la franja de cifras, sin aliados
ni cita de prensa, y sin cubierta. El nombre es el logo, al pie de la obra: ver test_mancheta.py.
"""

import re
from datetime import date, timedelta
from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.agenda.models import Event
from apps.media.models import MediaAsset
from apps.people.models import Contributor
from apps.showcase.models import Partner, PressMention, SiteProfile, SiteSocialLink
from apps.submissions.models import Call
from tests import css
from tests.factories import make_event, make_publication, soup

pytestmark = pytest.mark.django_db


def _imagen(nombre, tamano=(50, 70)):
    buffer = BytesIO()
    Image.new("RGB", tamano, (10, 20, 30)).save(buffer, format="JPEG")
    recurso = MediaAsset(alt_text=nombre)
    recurso.file.save(f"{nombre}.jpg", ContentFile(buffer.getvalue()))
    return recurso


def _portada(client):
    return soup(client, reverse("site:home"))


def _texto(nodo):
    return " ".join(nodo.get_text().split())


def test_el_nombre_es_el_logo_y_el_lema_baja_a_la_cejilla(client):
    perfil = SiteProfile.load()
    perfil.name = "Repitentes del Verso"
    perfil.tagline = "Colectivo de poesía"
    perfil.location = "Chile"
    perfil.founded_year = 2023
    perfil.save()
    SiteSocialLink.objects.create(
        profile=perfil, platform="Instagram", url="https://www.instagram.com/repitentesdelverso/"
    )
    for i in range(2):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    sopa = _portada(client)
    assert [_texto(h1) for h1 in sopa.select("h1")] == ["Repitentes del Verso"]
    # De la marca de la página cuelgan la cápsula de la cabecera y cabecera.js.
    assert sopa.body["data-pagina"] == "portada"
    # Se ve el logo, un dibujo; el nombre va en texto para lectores y buscadores.
    assert sopa.h1.select_one(".sr-only").get_text() == "Repitentes del Verso"
    logos = sopa.h1.select("svg")
    assert [svg["class"] for svg in logos] == [["logo-horizontal"], ["logo-apilado"]]
    assert all(svg["aria-hidden"] == "true" for svg in logos)
    cejilla = sopa.select_one(".hero-cejilla")
    assert cejilla.get_text() == (
        "Colectivo de poesía · Chile · desde 2023 · 2 integrantes · @repitentesdelverso"
    )
    assert cejilla.a["href"] == "https://www.instagram.com/repitentesdelverso/"


@pytest.mark.parametrize(("cuantas", "cuenta"), [(1, "1 integrante"), (2, "2 integrantes")])
def test_the_cejilla_counts_them_in_singular_or_plural(client, cuantas, cuenta):
    """La cuenta de la cejilla concuerda con el número: una integrante, dos integrantes."""
    perfil = SiteProfile.load()
    perfil.tagline, perfil.location, perfil.founded_year = "Colectivo de poesía", "", None
    perfil.save()
    for i in range(cuantas):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    cejilla = _portada(client).select_one(".hero-cejilla").get_text()
    assert cejilla == f"Colectivo de poesía · {cuenta}"


def test_la_cejilla_cuenta_a_todas(client):
    """Las cuenta todas, también las que esperan su turno en el relevo de «Las voces»."""
    for i in range(17):
        Contributor.objects.create(slug=f"m{i}", display_name=f"Integrante {i}", is_member=True)
    assert "17 integrantes" in _portada(client).select_one(".hero-cejilla").get_text()


def test_el_manifiesto_termina_en_su_primera_pausa(client):
    """La portada cita el manifiesto hasta su primera pausa, no a media frase."""
    perfil = SiteProfile.load()
    perfil.manifesto = (
        "Somos un colectivo que lee en voz alta y lleva los poemas a donde no suelen llegar: "
        "salas de clases, ferias y plazas. Lo demás vuelve al taller."
    )
    perfil.save()
    manifiesto = soup(client, reverse("site:home"))
    texto = " ".join(manifiesto.select_one(".hero-manifesto").get_text().split())
    assert texto == (
        "Somos un colectivo que lee en voz alta y lleva los poemas a donde no suelen llegar. "
        "Conócenos →"
    )


def test_the_hoja_has_no_cover_and_the_book_is_on_the_estante(client):
    """La hoja no lleva cubierta: el libro va en el bloque de publicaciones."""
    make_publication(slug="primera", title="Cuadernos del ruido", cover=_imagen("cubierta-1"))
    sopa = _portada(client)
    assert sopa.select_one(".hero-objeto, .hero-cubierta") is None
    assert "hero--con-objeto" not in sopa.select_one("section.hero")["class"]
    assert [t.get_text() for t in sopa.select(".home-publicaciones .estante-titulo")] == [
        "Cuadernos del ruido"
    ]


def test_un_solo_boton_principal_y_el_mismo_correo_que_el_pie(client):
    """El botón principal de la hoja es el dossier, que la hoja oculta desde donde lo lleva
    la cabecera. «Escríbenos» usa el correo de gestión o, si falta, el general: el del pie."""
    perfil = SiteProfile.load()
    perfil.general_email = "hola@example.com"
    perfil.save()
    sopa = _portada(client)
    principales = sopa.select("section.hero .btn--primary")
    assert len(principales) == 1 and "hero-dossier" in principales[0]["class"]
    assert sopa.select_one("section.hero").find("a", string="Escríbenos")["href"] == (
        "mailto:hola@example.com"
    )
    assert sopa.select_one('footer.site-foot a[href="mailto:hola@example.com"]') is not None


def test_la_portada_no_lleva_cifras(client):
    """Sin la franja de cifras (integrantes, actividades, publicaciones): el colectivo aún es
    pequeño (ver «Sin cifras en la portada» en docs/deferidos-y-decisiones.md). Cuántas
    integrantes son lo dice la cejilla."""
    Contributor.objects.create(slug="m1", display_name="Integrante Uno", is_member=True)
    make_event(
        slug="pasado", type=Event.Type.FESTIVAL, starts_at=timezone.now() - timedelta(days=30)
    )
    make_publication(slug="p", title="P")
    titular = _portada(client).select_one("section.hero")
    assert titular.select_one(".hero-ctas .hero-dossier")  # control: la hoja está, con su botón
    assert titular.select_one(".stats-strip, .hero-stats") is None


def test_the_convocatoria_sello_comes_after_the_buttons_in_reading_order(client):
    """El sello va después de los botones: por debajo de 900 px se ve bajo ellos; desde 900,
    sobre la trama de la derecha."""
    ahora = timezone.now()
    Call.objects.create(
        slug="abierta",
        title="Convocatoria",
        opens_at=ahora - timedelta(days=1),
        closes_at=ahora + timedelta(days=30),
    )
    texto = _portada(client).select_one(".hero-texto")
    piezas = [hijo["class"][0] for hijo in texto.find_all(recursive=False)]
    assert piezas.index("sello-convocatoria") > piezas.index("hero-ctas")


def _convocatoria(abre, cierra, slug="conv"):
    ahora = timezone.now()
    return Call.objects.create(
        slug=slug, title="Convocatoria", opens_at=ahora + abre, closes_at=ahora + cierra
    )


def test_la_portada_lleva_el_sello_mientras_hay_una_convocatoria_abierta(client):
    from django.utils.dateformat import format as formato

    abierta = _convocatoria(timedelta(days=-3), timedelta(days=12))
    html = client.get(reverse("site:home")).content.decode()
    sello = re.search(r'<a class="sello-convocatoria" href="([^"]+)">(.*?)</a>', html, re.S)
    assert sello, "con una convocatoria abierta, la portada no lleva el sello"
    assert sello.group(1) == reverse("submissions:submit")
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sello.group(2))).strip()
    cierre = formato(timezone.localtime(abierta.closes_at), r"j \d\e F")
    assert texto == f"Convocatoria abierta hasta el {cierre}"


def test_sin_convocatoria_abierta_no_hay_sello(client):
    _convocatoria(timedelta(days=-40), timedelta(days=-5), slug="cerrada")
    _convocatoria(timedelta(days=5), timedelta(days=40), slug="futura")
    page = soup(client, reverse("site:home"))
    assert page.select_one("section.hero .hero-dossier")  # control: la hoja está, con su botón
    assert page.select_one(".sello-convocatoria") is None


def test_la_portada_no_lleva_cita_de_prensa_ni_aliados(client):
    """Sin la línea de respaldo (una cita de prensa y «Con el apoyo de»): el colectivo aún es
    pequeño."""
    PressMention.objects.create(
        title="b",
        outlet="Radio Dos",
        quote="Destacada.",
        published_on=date(2025, 1, 1),
    )
    Partner.objects.create(name="Casa del Libro")
    sopa = _portada(client)
    assert sopa.select_one("section.hero .hero-dossier")  # control: la hoja está, con su botón
    assert sopa.select_one(".hero-respaldo, .hero-cita") is None
    assert "Destacada." not in sopa.get_text()
    assert "Casa del Libro" not in sopa.get_text()
    html = str(sopa)  # todo el HTML: también los atributos y los guiones
    for fuera in ("Destacada.", "Radio Dos", "Casa del Libro"):  # la cita, su medio, el aliado
        assert fuera not in html, fuera


def test_la_hoja_es_una_lamina_a_dos_tintas():
    """Desde 900 px, el manifiesto en letra de cartel y tinta azul con grano a la izquierda, y
    a la derecha un círculo de trama magenta con el sello de la convocatoria encima (ver «La
    hoja, lámina a dos tintas» en docs/deferidos-y-decisiones.md). El grano es uno solo para
    toda la portada, y no se come el foco."""
    assert css.tokens()["--grano"].startswith("url(")
    assert len([d for _, d in css.declarations() if d.name == "--grano"]) == 1
    lamina = ("@media (min-width:900px)",)
    hoja = css.rule(lamina, ".hero")
    assert hoja["grid-template-columns"] == "minmax(0, 7fr) minmax(0, 5fr)"
    manifiesto = css.rule(lamina, ".hero-manifesto")
    assert manifiesto["color"] == "var(--caratula)" and manifiesto["mask-image"] == "var(--grano)"
    # Letra de cartel: el azul sobre el papel solo cumple AA en letra grande (WCAG: 24 px, o
    # 18,66 px en negrita), también donde la letra crece.
    negrita = int(manifiesto["font-weight"]) >= 700
    for regla in (manifiesto, css.rule(("@media (min-width:1600px)",), ".hero-manifesto")):
        minimo, _ = css.px_range(regla["font-size"])
        assert minimo >= 24 or (negrita and minimo >= 18.66), regla["font-size"]
    foco = css.rule(lamina, ".hero-manifesto:has(:focus-visible)")
    assert (foco["-webkit-mask-image"], foco["mask-image"]) == ("none", "none")
    trama = css.rule(lamina, ".hero::before")["background"]
    assert "radial-gradient(circle, var(--accent) 0 32%, transparent 36%) 0 0 / 13px 13px" in trama
    sello = css.rule(lamina, ".sello-convocatoria")
    assert (sello["grid-column"], sello["grid-row"]) == ("2", "1 / span 3")
