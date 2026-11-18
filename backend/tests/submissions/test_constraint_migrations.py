"""Las migraciones de las convocatorias y los envíos que corrigen o completan sus datos.

Una convocatoria que cierra antes de abrir, o al abrir, se corrige antes de la restricción que
exige cerrar después (0003); un envío ya rechazado recibe como fecha de resolución la de la
migración, y uno recibido, ninguna (0004); y los tipos de propuesta pierden la tilde, y uno que
no se ofrece pasa a «otro», antes de la restricción que solo admite los ofrecidos (0005), que
se puede deshacer. Cada prueba crea con los modelos de entonces las filas que la migración
corrige, migra y comprueba qué quedó, con el fixture `migrate` de `conftest.py`.
"""

from datetime import timedelta

from django.utils import timezone


def test_a_call_with_crossed_dates_gets_them_swapped(migrate):
    old = migrate("submissions", "0002_alter_submission_file")
    Call = old.get_model("submissions", "Call")
    start = timezone.now()
    crossed = Call.objects.create(
        slug="cruzada", title="C", opens_at=start, closes_at=start - timedelta(days=5)
    )
    instant = Call.objects.create(slug="instante", title="C", opens_at=start, closes_at=start)

    new = migrate("submissions", "0003_convocatorias_cierran_despues_de_abrir")
    Call = new.get_model("submissions", "Call")
    crossed = Call.objects.get(pk=crossed.pk)
    assert (crossed.opens_at, crossed.closes_at) == (start - timedelta(days=5), start)
    assert Call.objects.get(pk=instant.pk).closes_at == start + timedelta(days=1)


def test_resolved_submissions_get_the_migration_date(migrate):
    old = migrate("submissions", "0003_convocatorias_cierran_despues_de_abrir")
    Submission = old.get_model("submissions", "Submission")
    common = {"author_name": "A", "author_email": "a@example.com", "title": "T", "body": "x"}
    rejected = Submission.objects.create(status="rejected", **common)
    received = Submission.objects.create(status="received", **common)
    new = migrate("submissions", "0004_submission_resolved_at")
    dates = dict(
        new.get_model("submissions", "Submission").objects.values_list("pk", "resolved_at")
    )
    assert dates[rejected.pk] is not None
    assert dates[received.pk] is None


def test_proposals_lose_the_accent_of_their_type_and_an_unknown_type_becomes_other(migrate):
    old = migrate("submissions", "0004_submission_resolved_at")
    Submission = old.get_model("submissions", "Submission")
    fields = {"author_name": "A", "author_email": "a@example.com", "title": "T", "body": "x"}
    tipos = ("reseña", "poesía", "crónica", "ensayo", "cuento")
    ids = {tipo: Submission.objects.create(type=tipo, **fields).pk for tipo in tipos}

    new = migrate("submissions", "0005_submission_types_without_accents")
    Submission = new.get_model("submissions", "Submission")
    assert {tipo: Submission.objects.get(pk=pk).type for tipo, pk in ids.items()} == {
        "reseña": "resena",
        "poesía": "poesia",
        "crónica": "cronica",
        "ensayo": "ensayo",
        "cuento": "otro",
    }

    back = migrate("submissions", "0004_submission_resolved_at")
    Submission = back.get_model("submissions", "Submission")
    assert Submission.objects.get(pk=ids["reseña"]).type == "reseña"
