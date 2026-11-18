"""Una actividad no termina antes de empezar, y una convocatoria cierra después de abrir."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.agenda.models import Event
from apps.submissions.models import Call

pytestmark = pytest.mark.django_db


def test_events_and_calls_cannot_end_before_they_start():
    start = timezone.now()
    event = Event(
        slug="al-reves", title="Al revés", starts_at=start, ends_at=start - timedelta(hours=1)
    )
    with pytest.raises(ValidationError, match="no puede terminar antes de empezar"):
        event.full_clean()
    call = Call(slug="c", title="C", opens_at=start, closes_at=start)
    with pytest.raises(ValidationError, match="tiene que cerrar después de abrir"):
        call.full_clean()
