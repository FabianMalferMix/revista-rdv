"""`is_editor` reconoce al grupo editor, y no al de las autoras."""

import pytest

from apps.people import roles

pytestmark = pytest.mark.django_db


def test_is_editor_flags(editor, autor):
    assert roles.is_editor(editor)
    assert not roles.is_editor(autor)
