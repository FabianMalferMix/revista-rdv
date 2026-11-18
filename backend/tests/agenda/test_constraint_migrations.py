"""La migración que corrige la agenda antes de la restricción que pide terminar tras empezar.

Una actividad que terminaba antes de empezar pierde su hora de término, y una bien fechada la
conserva (0002). La prueba crea con los modelos de entonces las filas que la restricción
prohibiría, migra y comprueba qué quedó, con el fixture `migrate` de `conftest.py`.
"""

from datetime import timedelta

from django.utils import timezone


def test_an_event_that_ended_before_it_started_loses_its_end(migrate):
    old = migrate("agenda", "0001_initial")
    Event = old.get_model("agenda", "Event")
    start = timezone.now()
    wrong = Event.objects.create(
        slug="al-reves", title="E", starts_at=start, ends_at=start - timedelta(hours=1)
    )
    right = Event.objects.create(
        slug="bien", title="E", starts_at=start, ends_at=start + timedelta(hours=1)
    )

    new = migrate("agenda", "0002_actividades_terminan_despues_de_empezar")
    Event = new.get_model("agenda", "Event")
    assert Event.objects.get(pk=wrong.pk).ends_at is None
    assert Event.objects.get(pk=right.pk).ends_at == right.ends_at
