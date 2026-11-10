"""/aliados/ agrupa a los aliados por su tipo (`Partner.Kind`): cada tipo tiene su grupo, con el
rótulo en plural, y ningún aliado se cuenta en la cabecera sin aparecer en la página."""

import pytest
from django.urls import reverse

from apps.showcase.models import Partner
from tests.factories import soup

pytestmark = pytest.mark.django_db

# El rótulo de cada grupo, como se lee hoy en la página.
PLURALS = {
    "financiamiento": "Financiamiento",
    "institucion": "Instituciones",
    "editorial": "Editoriales",
    "medio": "Medios",
    "espacio": "Espacios",
    "otro": "Otros apoyos",
}


def _groups(client):
    page = soup(client, reverse("showcase:partner_index"))
    groups = {
        group.h2.get_text(strip=True): [n.get_text(strip=True) for n in group.select("strong")]
        for group in page.select(".aliados-grupo")
    }
    return page.select_one(".index-head .kicker").get_text(strip=True), groups


def test_every_kind_of_partner_has_its_group(client):
    assert set(PLURALS) == set(Partner.Kind.values), "un tipo de aliado sin rótulo en plural"
    for kind in Partner.Kind:
        Partner.objects.create(name=f"Aliado {kind.label}", kind=kind)
    kicker, groups = _groups(client)
    assert groups == {PLURALS[kind]: [f"Aliado {kind.label}"] for kind in Partner.Kind}
    assert list(groups) == [PLURALS[kind] for kind in Partner.Kind], "en el orden de los tipos"
    assert kicker == f"{len(Partner.Kind)} aliados"


def test_a_partner_of_an_unknown_kind_goes_with_the_other_supports(client):
    """Un tipo que ya no existe (quedó en la base al quitarlo de la lista) no deja al aliado
    contado en la cabecera y fuera de todos los grupos."""
    Partner.objects.create(name="Fondo Conocido", kind=Partner.Kind.FINANCIAMIENTO)
    lost = Partner.objects.create(name="Aliado Perdido")
    Partner.objects.filter(pk=lost.pk).update(kind="patrocinio")
    kicker, groups = _groups(client)
    assert groups == {"Financiamiento": ["Fondo Conocido"], "Otros apoyos": ["Aliado Perdido"]}
    assert kicker == "2 aliados"
