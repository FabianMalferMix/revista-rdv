"""La ficha de una integrante enseña sus poemas y las actividades publicadas en que participó."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.content.models import PoemContributor
from apps.people.models import Contributor
from tests.factories import make_event, make_published_poem, soup

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


def test_member_profile_lists_poems(client):
    member = Contributor.objects.create(slug="poeta-p", display_name="Poeta Perfil", is_member=True)
    poem = make_published_poem(slug="suyo", title="Poema Del Perfil")
    PoemContributor.objects.create(poem=poem, contributor=member)
    resp = client.get(reverse("people:member_detail", args=[member.slug]))
    assert b"Poema Del Perfil" in resp.content
