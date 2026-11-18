"""La duración de un registro se lee en minutos y horas."""

import pytest

from apps.media.models import Recording


@pytest.mark.parametrize(
    ("minutos", "texto"), [(None, ""), (6, "6 min"), (42, "42 min"), (65, "1 h 05 min")]
)
def test_la_duracion_se_lee_en_minutos_y_horas(minutos, texto):
    assert Recording(duration_minutes=minutos).duracion == texto
