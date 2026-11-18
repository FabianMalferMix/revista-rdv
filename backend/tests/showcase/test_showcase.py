"""El perfil del sitio (`SiteProfile`): una sola fila, que se carga sin duplicarse y no se borra,
y su procesador de contexto, que siempre entrega un perfil, aunque la base esté vacía."""

import pytest

from apps.showcase.context_processors import site_profile as site_profile_cp
from apps.showcase.models import SiteProfile

pytestmark = pytest.mark.django_db


def test_load_is_idempotent_singleton():
    a = SiteProfile.load()
    b = SiteProfile.load()
    assert a.pk == b.pk == 1
    assert SiteProfile.objects.count() == 1


def test_save_forces_single_row():
    SiteProfile.load()
    other = SiteProfile(name="Otro")
    other.save()
    assert other.pk == 1
    assert SiteProfile.objects.count() == 1
    assert SiteProfile.objects.get().name == "Otro"


def test_delete_is_noop():
    profile = SiteProfile.load()
    profile.delete()
    assert SiteProfile.objects.filter(pk=1).exists()


def test_context_processor_returns_profile(rf):
    profile = SiteProfile.load()
    assert site_profile_cp(rf.get("/"))["site_profile"] == profile


def test_context_processor_never_none_even_on_empty_db(rf):
    # Aunque no exista la fila (QuerySet.delete elude el no-op), load() la recrea: el
    # context_processor global nunca entrega None.
    SiteProfile.objects.all().delete()
    assert SiteProfile.objects.count() == 0
    profile = site_profile_cp(rf.get("/"))["site_profile"]
    # El perfil es perezoso: preguntar qué es lo carga.
    assert isinstance(profile, SiteProfile)
    assert SiteProfile.objects.count() == 1
