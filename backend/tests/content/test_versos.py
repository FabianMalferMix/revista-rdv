"""Los filtros de los versos (apps/content/templatetags/versos.py): `versos` compone el poema
verso a verso y por estrofas, escapando cada línea; `primeros_versos` y `primer_verso` citan su
comienzo; `adelanto`, el de la portada, cita versos enteros y corta la prosa, y `primera_pausa`
corta el manifiesto en su primera pausa.
"""

import pytest
from django.utils.safestring import SafeString

from apps.content.templatetags.versos import (
    adelanto,
    primer_verso,
    primera_pausa,
    primeros_versos,
    versos,
)


def test_versos_marca_cada_linea_y_agrupa_las_estrofas():
    html = versos("Verso uno\n    verso con sangría\n\nVerso final")
    assert html == (
        '<p class="estrofa"><span class="verso">Verso uno</span>'
        '<span class="verso">    verso con sangría</span></p>'
        '<p class="estrofa"><span class="verso">Verso final</span></p>'
    )
    assert isinstance(html, SafeString)


def test_versos_escapa_cada_linea_antes_de_envolverla():
    """El cuerpo lo escribe una persona: el filtro devuelve HTML seguro solo porque cada
    verso se escapa primero."""
    html = versos('<script>alert("x")</script>\n<b>negrita</b>')
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;negrita&lt;/b&gt;" in html


@pytest.mark.parametrize(
    "cuerpo,estrofas",
    [
        ("\n\nuno\n\n\n\ndos\n\n", 2),  # varias líneas en blanco: un solo salto
        ("uno\n   \ndos", 2),  # una línea con solo espacios también separa
        ("uno\ndos\ntres", 1),
        ("", 0),
        (None, 0),
    ],
)
def test_versos_cuenta_las_estrofas(cuerpo, estrofas):
    assert str(versos(cuerpo)).count('<p class="estrofa">') == estrofas


@pytest.mark.parametrize(
    "cuerpo,cuantos,esperado",
    [
        (
            "Verso uno\n    verso con sangría\n\nVerso final",
            3,
            ["Verso uno", "verso con sangría", "Verso final"],
        ),
        ("\n\n   \nPrimero\nSegundo", 1, ["Primero"]),
        ("uno\ndos\ntres\ncuatro", 2, ["uno", "dos"]),
        ("a   b\tc", 1, ["a b c"]),
        ("solo uno", 3, ["solo uno"]),
        ("", 2, []),
        ("   \n\n", 2, []),
        (None, 2, []),
    ],
)
def test_primeros_versos(cuerpo, cuantos, esperado):
    """Un verso es una línea con texto: las líneas en blanco no cuentan y la sangría,
    que en la ficha se respeta, en una cita de índice se descarta."""
    assert primeros_versos(cuerpo, cuantos) == esperado


def test_primer_verso():
    assert primer_verso("\n   Llueve sobre el patio  \nsegundo") == "Llueve sobre el patio"
    assert primer_verso("") == ""
    assert primer_verso(None) == ""


def test_el_adelanto_de_la_portada_cita_tres_versos_corrientes_enteros():
    assert adelanto("Llueve sobre el patio\ny nadie\nlo escucha\ncuarto") == [
        "Llueve sobre el patio",
        "y nadie",
        "lo escucha",
    ]


def test_el_adelanto_corta_los_versos_larguisimos_y_la_prosa():
    """Un poema en prosa abre con un párrafo: la portada cita su arranque, cortado en una
    palabra, y no tres párrafos enteros."""
    prosa = "En el patio de la casa había un limonero " * 20
    citado = adelanto(prosa)
    assert len(citado) == 1 and citado[0].endswith("…")
    assert len(citado[0]) <= 162 and not citado[0][:-1].endswith(" ")
    assert prosa.startswith(citado[0][:-1]), "no cortó en una palabra"


def test_el_adelanto_no_cita_un_resto_diminuto():
    """Si tras dos versos quedan menos de cuarenta letras, el tercero no se cita a medias."""
    cuerpo = "a" * 70 + "\n" + "b" * 60 + "\n" + "c " * 50
    assert adelanto(cuerpo) == ["a" * 70, "b" * 60]


LARGA = " ".join(f"palabra{n}" for n in range(1, 41)) + "."


@pytest.mark.parametrize(
    "texto,cita",
    [
        ("Leemos en voz alta. Escribimos juntas.", "Leemos en voz alta."),
        ("Leemos en voz alta; escribimos juntas.", "Leemos en voz alta."),
        ("¿Quién lee en voz alta? Nosotras.", "¿Quién lee en voz alta?"),
        ("Somos 2.000 lectores: y más", "Somos 2.000 lectores."),
        ("  Sin  pausa  ninguna  ", "Sin pausa ninguna"),
        (LARGA, " ".join(LARGA.split()[:28]) + " …"),
        ("", ""),
        (None, ""),
    ],
)
def test_primera_pausa(texto, cita):
    """Hasta el primer punto, dos puntos, punto y coma, cierre de pregunta o de exclamación
    (los dos puntos y el punto y coma, cerrados con punto); un punto dentro de una cifra no
    es una pausa. Si la pausa llega tarde (pasado el tope de `primera_pausa`), se corta en la
    palabra 28."""
    assert primera_pausa(texto) == cita
