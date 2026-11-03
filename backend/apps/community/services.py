"""El alta en el boletín: lo que decide si se envía una confirmación.

Las transiciones (pedir confirmación, confirmar, darse de baja) son métodos del suscriptor;
aquí vive lo que las combina: la normalización del correo y el tope de reenvío.
"""

from datetime import timedelta

from django.utils import timezone

from .models import NewsletterSubscriber

S = NewsletterSubscriber.Status
# Un alta repetida dentro de este plazo no reenvía la confirmación: el formulario no sirve
# para llenar de correos el buzón de otra persona. La respuesta es la misma.
RESEND_AFTER = timedelta(minutes=10)


def subscribe(email):
    """Da de alta (o vuelve a dar de alta) un correo. Devuelve el suscriptor si hay que
    enviarle la confirmación, o None si no: ya confirmó, o se le envió hace poco."""
    sub, _ = NewsletterSubscriber.objects.get_or_create(
        email=NewsletterSubscriber.normalize_email(email)
    )
    if sub.status == S.CONFIRMED:
        return None
    sent_recently = (
        sub.status == S.PENDING
        and sub.confirm_token_is_valid()
        and timezone.now() - sub.confirm_token_at < RESEND_AFTER
    )
    if sent_recently:
        return None
    sub.request_confirmation()
    return sub
