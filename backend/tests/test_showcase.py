import pytest
from django.urls import reverse

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


def test_context_processor_none_when_absent():
    assert site_profile_cp(None)["site_profile"] is None


def test_context_processor_returns_profile():
    profile = SiteProfile.load()
    assert site_profile_cp(None)["site_profile"] == profile


def test_footer_shows_booking_email(client):
    profile = SiteProfile.load()
    profile.booking_email = "gestion@resenas.cl"
    profile.save()
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    assert b"gestion@resenas.cl" in resp.content
