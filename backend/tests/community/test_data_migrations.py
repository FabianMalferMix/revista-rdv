"""Las migraciones de datos del boletín, probadas con filas.

Al darle a cada suscripción su propio enlace de confirmación (0003), la pendiente conserva el
que ya se le mandó y su plazo para confirmar empieza al migrar; al deshacer esa migración, cada
suscripción sigue con su estado y su token. Cada prueba crea con los modelos de entonces las
filas que la migración transforma, migra y comprueba qué quedó, con el fixture `migrate` de
`conftest.py`.

La migración que funde los correos repetidos antes de su restricción se prueba en
`test_constraint_migrations.py`.
"""

from django.utils import timezone


def test_a_pending_subscriber_keeps_the_confirmation_link_already_sent(migrate):
    old = migrate("community", "0002_delete_comment")
    Subscriber = old.get_model("community", "NewsletterSubscriber")
    pending = Subscriber.objects.create(email="ana@correo.cl", status="pending", token="ana")
    confirmed = Subscriber.objects.create(email="bea@correo.cl", status="confirmed", token="bea")
    tokenless = Subscriber.objects.create(email="eva@correo.cl", status="pending", token="")
    before = timezone.now()

    new = migrate("community", "0003_newslettersubscriber_confirm_token_and_more")
    rows = {
        s.pk: (s.token, s.confirm_token, s.confirm_token_at)
        for s in new.get_model("community", "NewsletterSubscriber").objects.all()
    }
    token, confirm_token, confirm_token_at = rows[pending.pk]
    assert (token, confirm_token) == ("ana", "ana")
    assert before <= confirm_token_at <= timezone.now(), "el plazo para confirmar empieza al migrar"
    assert rows[confirmed.pk] == ("bea", "", None)
    assert rows[tokenless.pk] == ("", "", None)


def test_undoing_the_confirmation_token_keeps_every_subscriber_and_their_token(migrate):
    new = migrate("community", "0003_newslettersubscriber_confirm_token_and_more")
    Subscriber = new.get_model("community", "NewsletterSubscriber")
    now = timezone.now()
    Subscriber.objects.create(
        email="ana@correo.cl",
        status="pending",
        token="ana",
        confirm_token="ana",
        confirm_token_at=now,
    )
    Subscriber.objects.create(
        email="bea@correo.cl", status="confirmed", token="bea", confirmed_at=now
    )

    back = migrate("community", "0002_delete_comment")
    rows = back.get_model("community", "NewsletterSubscriber").objects.values_list(
        "email", "status", "token", "confirmed_at"
    )
    assert sorted(rows) == [
        ("ana@correo.cl", "pending", "ana", None),
        ("bea@correo.cl", "confirmed", "bea", now),
    ]
