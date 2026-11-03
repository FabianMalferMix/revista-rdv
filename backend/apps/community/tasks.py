import smtplib

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from config.origin import absolute_url

# Rechazos que no cambian por insistir: el destinatario o el remitente rechazados, unas
# credenciales que no valen o una extensión que el servidor no admite. El resto de errores
# de red y de SMTP (SMTPException hereda de OSError), y un servidor que no contesta a tiempo,
# se reintentan.
PERMANENT_ERRORS = (
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPNotSupportedError,
)


def describe_error(exc):
    """El error, sin direcciones: su tipo y, si lo trae, el código SMTP."""
    code = getattr(exc, "smtp_code", None)
    if code is None and isinstance(exc, smtplib.SMTPRecipientsRefused) and exc.recipients:
        code = next(iter(exc.recipients.values()))[0]
    return f"{type(exc).__name__} {code}" if code else type(exc).__name__


# Cada espera se sortea por debajo de un tope que crece de 30 s a 15 min: los ocho reintentos
# se reparten en hasta una hora (unos treinta minutos, de media).
@shared_task(
    autoretry_for=(OSError, SoftTimeLimitExceeded),
    dont_autoretry_for=PERMANENT_ERRORS,
    retry_backoff=30,
    retry_backoff_max=900,
    retry_kwargs={"max_retries": 8},
)
def send_confirmation_email(subscriber_id):
    """Correo de confirmación de suscripción (doble opt-in).

    Fuera del hilo de la petición (no bloquea un worker de gunicorn ante un SMTP
    lento) y con reintento/backoff ante fallos transitorios. Sin fail_silently: un
    fallo definitivo sube a Sentry en vez de tragarse en silencio. Lleva la cabecera
    List-Unsubscribe (RFC 8058) con el enlace de baja, para que el cliente de correo
    ofrezca un botón de darse de baja y mejore la reputación de envío.

    Recibe solo el id: el correo y los tokens no viajan por el broker, ni quedan en los
    argumentos que Celery escribe en el log o adjunta a un error. Las URL se arman con
    SITE_URL. Deja en el suscriptor la fecha del envío o el último error, que el panel
    enseña junto a una acción para reenviar.
    """
    from apps.showcase.models import SiteProfile

    from .models import NewsletterSubscriber

    sub = NewsletterSubscriber.objects.filter(pk=subscriber_id).first()
    if sub is None or not sub.confirm_token:
        return  # se dio de baja, ya confirmó o se borró mientras esperaba en la cola
    context = {
        "name": SiteProfile.load().name,
        "confirm_url": absolute_url(reverse("community:confirm", args=[sub.confirm_token])),
        "unsub_url": absolute_url(reverse("community:unsubscribe", args=[sub.token])),
    }
    message = EmailMessage(
        subject=render_to_string("community/email/confirmacion_asunto.txt", context).strip(),
        body=render_to_string("community/email/confirmacion.txt", context),
        from_email=None,  # DEFAULT_FROM_EMAIL
        to=[sub.email],
        headers={
            "List-Unsubscribe": f"<{context['unsub_url']}>",
            # RFC 8058: habilita el botón de baja en un clic del cliente de correo, que
            # envía un POST con este cuerpo. Sin esta cabecera, el cliente visitaría la
            # URL por GET —que ya no muta nada— y la baja no llegaría a ejecutarse.
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    try:
        message.send(fail_silently=False)
    except Exception as exc:
        NewsletterSubscriber.objects.filter(pk=sub.pk).update(
            confirmation_error=describe_error(exc)[:120]
        )
        raise
    NewsletterSubscriber.objects.filter(pk=sub.pk).update(
        confirmation_sent_at=timezone.now(), confirmation_error=""
    )
