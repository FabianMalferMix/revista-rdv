"""El filtro `iniciales` (apps/people/templatetags/personas.py): el monograma de quien no tiene
retrato lleva la inicial de su primer nombre y la de su último apellido.
"""

import pytest

from apps.people.templatetags.personas import iniciales


@pytest.mark.parametrize(
    "nombre,esperado",
    [
        ("Fernanda Soto", "FS"),
        ("Camila", "C"),
        ("María José de la Fuente", "MF"),
        ("  ana   lópez ", "AL"),
        ("", ""),
        (None, ""),
    ],
)
def test_iniciales(nombre, esperado):
    assert iniciales(nombre) == esperado
