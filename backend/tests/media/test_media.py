"""La validación de un registro.

Necesita una fuente, un archivo o un enlace, y la tirada de la portada no admite un destacado
más de los que caben (TIRADA_SIZE): el último que cabe se sigue editando.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.media.models import TIRADA_SIZE, Recording
from tests.factories import make_recording

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


def test_one_recording_more_than_the_tirada_holds_is_refused():
    for _ in range(TIRADA_SIZE - 1):
        make_recording(featured=True)
    ultimo_que_cabe = make_recording(featured=True)
    ultimo_que_cabe.full_clean()  # ya destacado: se puede seguir editando
    sobra = make_recording()
    sobra.featured = True
    with pytest.raises(ValidationError, match="quita uno"):
        sobra.full_clean()
    ultimo_que_cabe.featured = False
    ultimo_que_cabe.save()
    sobra.full_clean()
