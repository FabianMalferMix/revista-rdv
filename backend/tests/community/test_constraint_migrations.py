"""La migración que deja una sola suscripción por correo.

Antes de la restricción que no deja repetir un correo, ni con otras mayúsculas, los correos
pasan a minúsculas y los repetidos se funden en el de actividad más reciente; cada suscripción
toma como fecha de su estado la de su último movimiento (0004). La prueba crea con los modelos
de entonces las filas que la restricción prohibiría, migra y comprueba qué quedó, con el
fixture `migrate` de `conftest.py`.
"""


def test_subscribers_are_lowercased_and_merged_keeping_the_latest(migrate):
    from datetime import timedelta

    from django.utils import timezone

    old = migrate("community", "0003_newslettersubscriber_confirm_token_and_more")
    Subscriber = old.get_model("community", "NewsletterSubscriber")
    now = timezone.now()
    Subscriber.objects.create(
        email="Ana@Correo.cl", status="pending", confirm_token_at=now - timedelta(days=9)
    )
    Subscriber.objects.create(
        email="ana@correo.cl", status="confirmed", confirmed_at=now - timedelta(days=2)
    )
    gone = Subscriber.objects.create(email="Otro@Correo.cl", status="unsubscribed")
    new = migrate("community", "0004_subscriber_lifecycle")
    rows = {
        s.email: (s.status, s.status_changed_at)
        for s in new.get_model("community", "NewsletterSubscriber").objects.all()
    }
    assert set(rows) == {"ana@correo.cl", "otro@correo.cl"}
    assert rows["ana@correo.cl"][0] == "confirmed"
    assert rows["ana@correo.cl"][1] == now - timedelta(days=2)
    assert rows["otro@correo.cl"][1] == gone.created_at
