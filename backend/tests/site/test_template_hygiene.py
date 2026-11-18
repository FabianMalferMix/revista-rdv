"""Las plantillas no filtran sus comentarios al HTML.

Django documenta `{# … #}` como comentario **de una sola línea**. Si abarca varias, el
motor NO lo reconoce y lo emite tal cual: el texto del comentario aparece en la página,
a la vista de cualquier visitante. Es un fallo silencioso —no rompe nada, no lanza
ninguna excepción, ninguna prueba funcional falla—: solo se ve mirando la página. Si ese
texto nombra `<style>`, el navegador abre ahí un estilo en línea, que la CSP bloquea, y se
traga como estilo lo que sigue hasta su cierre.

Se comprueba de dos formas complementarias: sobre el FUENTE de las plantillas (barato y
exhaustivo, cubre también las que ningún test renderiza: ningún `{#` sin su `#}` en la misma
línea, ni un par `{# … #}` que cruce un salto de línea) y sobre el HTML RENDERIZADO de las
vistas públicas (comprueba el efecto real).
"""

import re

import pytest
from django.conf import settings
from django.urls import reverse

PLANTILLAS = settings.BASE_DIR / "templates"

# Marcadores que jamás deben llegar al navegador.
RESTOS = ["{#", "#}", "{% comment %}", "{% endcomment %}"]


def _plantillas():
    return sorted(PLANTILLAS.rglob("*.html"))


def test_hay_plantillas_que_revisar():
    """Si el descubrimiento fallara, o dejara de ver los comentarios, los demás tests pasarían
    por vacío."""
    assert len(_plantillas()) > 20
    comentarios = [
        linea
        for plantilla in _plantillas()
        for linea in plantilla.read_text("utf-8").splitlines()
        if "{#" in linea
    ]
    assert len(comentarios) >= 10, "control: la búsqueda dejó de encontrar los comentarios"


@pytest.mark.parametrize("plantilla", _plantillas(), ids=lambda p: str(p.name))
def test_ningun_comentario_de_una_linea_abarca_varias(plantilla):
    """`{# … #}` multilínea se RENDERIZA como texto visible. Para comentarios de varias
    líneas hay que usar `{% comment %} … {% endcomment %}`. Se miran los dos casos: un par
    `{# … #}` que cruza un salto de línea, aunque lo abra el segundo comentario de la línea, y
    un `{#` sin su `#}` en la misma línea, aunque no se cierre en todo el archivo."""
    texto = plantilla.read_text(encoding="utf-8")
    culpables = [
        m.group(1).strip()[:60]
        for m in re.finditer(r"\{#(.*?)#\}", texto, re.S)
        if "\n" in m.group(1)
    ]
    assert not culpables, (
        f"{plantilla.name}: comentario {{# #}} multilínea, que Django imprime como texto. "
        f"Usa {{% comment %}}. Afectados: {culpables}"
    )
    partidos = [
        f"{plantilla.relative_to(PLANTILLAS)}:{n}"
        for n, linea in enumerate(texto.splitlines(), 1)
        if "{#" in linea and "#}" not in linea.split("{#", 1)[1]
    ]
    assert not partidos, f"{{# sin su #}} en la misma línea, que Django imprime: {partidos}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ruta",
    [
        "site:home",
        "content:text_archive",
        "content:poem_index",
        "content:collection_index",
        "site:search",
        "people:member_index",
        "agenda:agenda",
        "agenda:trayectoria",
        "agenda:gallery",
        "media:recording_index",
        "showcase:publication_index",
        "showcase:press_index",
        "showcase:partner_index",
        "showcase:dossier",
        "submissions:submit",
    ],
)
def test_las_vistas_publicas_no_emiten_restos_de_plantilla(client, ruta):
    response = client.get(reverse(ruta))
    assert response.status_code == 200  # control: es la página, no una de error
    contenido = response.content.decode("utf-8", "replace")
    for resto in RESTOS:
        assert resto not in contenido, f"{ruta} deja escapar {resto!r} al HTML"


@pytest.mark.django_db
def test_las_paginas_del_boletin_tampoco(client):
    """Las páginas de confirmar y de darse de baja del boletín piden un token y no están en la
    lista de vistas públicas: se revisan aparte."""
    from django.utils import timezone

    from apps.community.models import NewsletterSubscriber

    sub = NewsletterSubscriber.objects.create(
        email="higiene@example.com",
        token="tok-baja",
        confirm_token="tok-conf",
        confirm_token_at=timezone.now(),
    )
    for url in (
        reverse("community:confirm", args=[sub.confirm_token]),
        reverse("community:unsubscribe", args=[sub.token]),
    ):
        response = client.get(url)
        assert response.status_code == 200, url  # control: es la página, no una de error
        contenido = response.content.decode("utf-8", "replace")
        for resto in RESTOS:
            assert resto not in contenido, f"{url} deja escapar {resto!r}"
