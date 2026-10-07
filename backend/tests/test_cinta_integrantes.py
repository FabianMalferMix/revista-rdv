"""La cinta de integrantes aparece solo cuando tiene sentido, y es accesible.

Una cinta con pocos integrantes enseña MENOS que la rejilla: obliga a esperar
para ver lo que ya estaba a la vista. Por eso el umbral no es decorativo, es la
condición que hace que el componente valga la pena.
"""

import re

import pytest
from django.conf import settings
from django.urls import reverse

from apps.content.views import TOPE_CINTA, UMBRAL_CINTA
from apps.people.models import Contributor

pytestmark = pytest.mark.django_db


def _integrantes(n):
    for i in range(n):
        Contributor.objects.create(
            slug=f"integrante-{i}",
            display_name=f"Integrante {i}",
            is_member=True,
            active=True,
            position=i,
        )


def _portada(client):
    return client.get(reverse("content:home")).content.decode()


def test_por_debajo_del_umbral_sigue_la_rejilla(client):
    _integrantes(UMBRAL_CINTA - 1)
    html = _portada(client)
    assert "cinta-pista" not in html, "la cinta se montó con menos gente de la necesaria"
    assert "member-grid" in html, "la rejilla desapareció"


def test_a_partir_del_umbral_se_monta_la_cinta(client):
    _integrantes(UMBRAL_CINTA)
    html = _portada(client)
    assert "cinta-pista" in html, f"la cinta no apareció con {UMBRAL_CINTA} integrantes"
    assert f"cinta-n{UMBRAL_CINTA}" in html, "falta la clase que fija la duración"


def test_la_cinta_tiene_un_solo_enlace(client):
    """Lo pedido: un enlace al índice, no uno por integrante.

    Un objetivo que se mueve no se puede pulsar; por eso las tarjetas de la
    cinta no llevan enlace propio y la zona pulsable es el componente entero.
    """
    _integrantes(UMBRAL_CINTA)
    html = _portada(client)
    bloque = re.search(r'<div class="cinta-caja">(.*?)</section>', html, re.S)
    assert bloque, "no se encontró el componente de la cinta"
    enlaces = re.findall(r"<a\s[^>]*href=\"([^\"]+)\"", bloque.group(1))
    assert enlaces == [reverse("people:member_index")], (
        f"la cinta debe tener exactamente un enlace, al índice; tiene {enlaces}"
    )


def test_la_copia_del_bucle_no_se_anuncia_dos_veces(client):
    """La lista va duplicada para que el bucle no tenga costura.

    Sin aria-hidden en la copia, un lector de pantalla leería a cada integrante
    dos veces seguidas.
    """
    _integrantes(UMBRAL_CINTA)
    html = _portada(client)
    bloque = re.search(r'<ul class="[^"]*cinta-pista[^"]*">(.*?)</ul>', html, re.S).group(1)
    tarjetas = re.findall(r"<li class=\"member-card cinta-card\"([^>]*)>", bloque)
    assert len(tarjetas) == UMBRAL_CINTA * 2, "la pista debe llevar la lista dos veces"
    ocultas = [a for a in tarjetas if 'aria-hidden="true"' in a]
    assert len(ocultas) == UMBRAL_CINTA, (
        f"la copia entera debe ir oculta a lectores de pantalla; "
        f"{len(ocultas)} de {UMBRAL_CINTA} lo están"
    )


def test_la_cinta_se_detiene_con_prefers_reduced_motion():
    """El único resguardo que queda tras retirar el control de pausa.

    El control visible se retiró por decisión expresa del usuario, así que la
    portada ya NO cumple WCAG 2.2.2 «Pausar, detener, ocultar» (nivel A): con
    ratón se detiene al pasar por encima, pero desde un móvil no hay forma de
    pararla. Lo que sigue protegiendo a quien declara sensibilidad al
    movimiento en su sistema es esta media query. Si desaparece, no queda
    nada, y por eso se vigila aquí.
    """
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    bloque = re.search(r"@media \(prefers-reduced-motion: reduce\)\{(.*?)\n\}", css, re.S)
    assert bloque, "desapareció el bloque de prefers-reduced-motion"
    assert "animation:none" in bloque.group(1), (
        "prefers-reduced-motion ya no detiene la animación de la cinta"
    )
    assert "overflow-x:auto" in bloque.group(1), (
        "sin animación la cinta debe poder arrastrarse a mano, o su contenido queda inalcanzable"
    )


def test_la_cinta_no_crece_sin_limite(client):
    """TOPE_CINTA acota la vuelta; del resto se encarga el enlace al índice."""
    _integrantes(TOPE_CINTA + 5)
    html = _portada(client)
    bloque = re.search(r'<ul class="[^"]*cinta-pista[^"]*">(.*?)</ul>', html, re.S).group(1)
    assert len(re.findall(r"<li class=\"member-card cinta-card\"", bloque)) == TOPE_CINTA * 2
