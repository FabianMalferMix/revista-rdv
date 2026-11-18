"""La ficha de una integrante enseña las actividades publicadas en que participó."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.people.models import Contributor
from tests.factories import make_event, soup

pytestmark = pytest.mark.django_db


def test_la_ficha_de_una_integrante_lleva_sus_actividades(client):
    """Las más recientes primero; un evento sin publicar no sale."""
    fernanda = Contributor.objects.create(slug="fernanda", display_name="Fernanda", is_member=True)
    ahora = timezone.now()
    vieja = make_event(slug="vieja", title="Lectura vieja", starts_at=ahora - timedelta(days=90))
    reciente = make_event(
        slug="reciente", title="Recital reciente", starts_at=ahora - timedelta(days=9)
    )
    oculta = make_event(slug="oculta", title="Borrador", published=False)
    otra = make_event(slug="otra", title="De otra persona")
    for evento in (vieja, reciente, oculta):
        evento.participants.add(fernanda)
    assert otra.participants.count() == 0
    sopa = soup(client, fernanda.get_absolute_url())
    seccion = next(s for s in sopa.select("article section") if s.h2.get_text() == "Actividades")
    assert [a.get_text() for a in seccion.select("li > a")] == ["Recital reciente", "Lectura vieja"]
