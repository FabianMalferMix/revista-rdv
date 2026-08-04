"""Las plantillas no filtran sus comentarios al HTML.

Django documenta `{# … #}` como comentario **de una sola línea**. Si abarca varias, el
motor NO lo reconoce y lo emite tal cual: el texto del comentario aparece en la página,
a la vista de cualquier visitante. Es un fallo silencioso —no rompe nada, no lanza
ninguna excepción, ninguna prueba funcional falla— y así se coló seis veces en distintas
tandas de trabajo, hasta que se vio a simple vista en la portada.

Se comprueba de dos formas complementarias: sobre el FUENTE de las plantillas (barato y
exhaustivo, cubre también las que ningún test renderiza) y sobre el HTML RENDERIZADO de
las vistas públicas (comprueba el efecto real).
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse

PLANTILLAS = Path(__file__).resolve().parent.parent / "templates"

# Marcadores que jamás deben llegar al navegador.
RESTOS = ["{#", "#}", "{% comment %}", "{% endcomment %}"]


def _plantillas():
    return sorted(PLANTILLAS.rglob("*.html"))


def test_hay_plantillas_que_revisar():
    """Si el descubrimiento fallara, los demás tests pasarían por vacío."""
    assert len(_plantillas()) > 20


@pytest.mark.parametrize("plantilla", _plantillas(), ids=lambda p: str(p.name))
def test_ningun_comentario_de_una_linea_abarca_varias(plantilla):
    """`{# … #}` multilínea se RENDERIZA como texto visible. Para comentarios de varias
    líneas hay que usar `{% comment %} … {% endcomment %}`."""
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ruta",
    [
        "content:home",
        "content:text_archive",
        "content:poem_index",
        "content:collection_index",
        "content:search",
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
    contenido = client.get(reverse(ruta)).content.decode("utf-8", "replace")
    for resto in RESTOS:
        assert resto not in contenido, f"{ruta} deja escapar {resto!r} al HTML"


@pytest.mark.django_db
def test_las_paginas_del_boletin_tampoco(client):
    """Estas dos plantillas nacieron con el fallo y ningún test las renderizaba."""
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
        contenido = client.get(url).content.decode("utf-8", "replace")
        for resto in RESTOS:
            assert resto not in contenido, f"{url} deja escapar {resto!r}"
