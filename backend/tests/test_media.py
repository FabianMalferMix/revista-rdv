import pytest
from django.core.exceptions import ValidationError

from apps.media.models import Recording

pytestmark = pytest.mark.django_db


def test_recording_requires_a_source():
    rec = Recording(slug="sin-fuente", title="Sin fuente")
    with pytest.raises(ValidationError):
        rec.clean()


def test_recording_with_embed_is_valid():
    rec = Recording(slug="con-embed", title="Con embed", embed_url="https://youtube.com/watch?v=x")
    rec.clean()  # no debe lanzar
    rec.save()
    assert str(rec) == "Con embed"
