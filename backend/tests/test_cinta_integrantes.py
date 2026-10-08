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


# ── Movimiento y pausa (WCAG 2.2.2, nivel A) ───────────────────────────────
#
# La cinta tiene dos modos. Por defecto es una FILA quieta que se recorre a mano; solo
# se anima donde hay puntero que pueda posarse y no se ha pedido menos movimiento. Estas
# pruebas no pueden pintar, así que fijan sobre la hoja de estilos lo que sostiene ese
# reparto. El comportamiento real (pausa al posar el puntero, con el icono, y arrastre
# con el dedo) se comprueba en navegador con tools/ux.

CONSULTA_DE_CINTA = (
    r"@media \(hover:hover\) and \(prefers-reduced-motion:no-preference\)\{(.*?)\n\}"
)


def _css():
    """La hoja sin comentarios: los de la cinta citan selectores a modo de explicación."""
    css = (settings.BASE_DIR / "static" / "css" / "site.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _modos():
    """(lo que rige siempre, lo que rige solo cuando la cinta se anima)."""
    css = _css()
    bloque = re.search(CONSULTA_DE_CINTA, css, re.S)
    assert bloque, "desapareció la media query que decide cuándo se anima la cinta"
    return css.replace(bloque.group(0), ""), bloque.group(1)


def test_la_cinta_solo_se_mueve_con_puntero_y_sin_pedir_menos_movimiento():
    """En una pantalla táctil no hay puntero con que detenerla: ahí no se mueve.

    Y quien pide menos movimiento en su sistema tampoco la recibe animada. Si la
    animación se declara fuera de esta media query, vuelve a moverse para todos.
    """
    siempre, animada = _modos()
    assert "animation:cinta-desliza" in animada, "la cinta ya no se anima en ningún caso"
    assert "animation:cinta-desliza" not in siempre, (
        "la animación se declara fuera de la media query: se movería también en táctil "
        "y para quien pidió menos movimiento"
    )


def test_sin_animacion_la_cinta_se_recorre_a_mano():
    """Si no se desliza sola, su contenido tiene que seguir siendo alcanzable."""
    siempre, animada = _modos()
    assert re.search(r"\.cinta\{[^}]*overflow-x:auto", siempre), (
        "sin animación la cinta debe poder desplazarse, o lo que no cabe queda inalcanzable"
    )
    assert '.cinta-card[aria-hidden="true"]{display:none}' in siempre, (
        "la copia solo sirve al bucle animado; en la fila cada integrante saldría dos veces"
    )
    assert ".cinta-pie a::after" not in siempre and ".cinta-pie a::after" in animada, (
        "el enlace extendido cubre la pista: fuera del modo animado impide arrastrarla"
    )


def test_la_pausa_cuelga_de_la_caja_no_de_la_pista():
    """El defecto que se corrige: la regla era `.cinta:hover`, y nunca se cumplía.

    El enlace extendido de `.cinta-pie a::after` cubre la pista entera, así que el
    puntero estaba siempre sobre el enlace —hijo de .cinta-pie— y jamás sobre .cinta.
    La pausa al pasar el ratón no funcionaba aunque el CSS lo pretendiera, y era el
    argumento con que se había retirado el control de pausa.
    """
    siempre, animada = _modos()
    pausa = re.search(r"([^{}]+)\{animation-play-state:paused\}", animada)
    assert pausa, "ya no hay ninguna regla que pause la cinta"
    selectores = pausa.group(1)
    assert ".cinta-caja:hover .cinta-pista" in selectores
    assert ".cinta-caja:focus-within .cinta-pista" in selectores, (
        "sin pausa por foco, quien navega con teclado no tiene cómo detenerla"
    )
    assert ".cinta:hover" not in siempre + animada, "volvió el selector que nunca se cumple"


def test_la_cinta_no_lleva_control_de_pausa(client):
    """Decisión del usuario, tomada dos veces: primero retiró el rótulo de texto que
    pausaba la cinta y después el icono que lo sustituyó (2026-10-08).

    Esta prueba no defiende un requisito técnico: fija la decisión para que un control
    no reaparezca sin que nadie lo pida. Lo que protege a quien lo necesita está en las
    pruebas de arriba: en táctil y con «menos movimiento» la cinta no se mueve, y con
    puntero se detiene al señalarla o al llevar el foco dentro.
    """
    _integrantes(UMBRAL_CINTA)
    caja = re.search(r'<div class="cinta-caja">(.*?)</section>', _portada(client), re.S).group(1)
    assert "<input" not in caja and "<label" not in caja and "<button" not in caja


def test_la_cinta_no_crece_sin_limite(client):
    """TOPE_CINTA acota la vuelta; del resto se encarga el enlace al índice."""
    _integrantes(TOPE_CINTA + 5)
    html = _portada(client)
    bloque = re.search(r'<ul class="[^"]*cinta-pista[^"]*">(.*?)</ul>', html, re.S).group(1)
    assert len(re.findall(r"<li class=\"member-card cinta-card\"", bloque)) == TOPE_CINTA * 2
