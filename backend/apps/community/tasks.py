import smtplib

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.time import get_exponential_backoff_interval
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.showcase.models import SiteProfile
from config.origin import absolute_url

from .models import NewsletterSubscriber

MAX_RETRIES = 8


def smtp_code(exc):
    """El código SMTP que trae el error, o None si no trae ninguno.

    Un rechazo de los destinatarios trae un código por dirección: el correo de confirmación va
    a una sola, así que vale el primero.
    """
    code = getattr(exc, "smtp_code", None)
    if code is None and isinstance(exc, smtplib.SMTPRecipientsRefused) and exc.recipients:
        code = next(iter(exc.recipients.values()))[0]
    return code


def is_temporary(exc):
    """Si insistir puede hacer que el correo salga.

    Si el servidor contestó con un código, lo decide el código y no la excepción que lo trae:
    smtplib lanza la misma con un 4xx, que es temporal (una lista gris, un buzón lleno, un
    servidor saturado), y con un 5xx, que es definitivo. Sin código, se reintentan un corte de
    la conexión, los errores de la red y un servidor que no contesta a tiempo, y no lo que el
    servidor no ofrece (STARTTLS, o un modo de iniciar sesión que smtplib sepa usar), que no
    cambia por insistir.
    """
    code = smtp_code(exc)
    if code is not None:
        return 400 <= code < 500
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return True
    if isinstance(exc, smtplib.SMTPException):
        return False
    return isinstance(exc, (OSError, SoftTimeLimitExceeded))


def describe_error(exc):
    """El error, sin direcciones: su tipo y, si lo trae, el código SMTP."""
    code = smtp_code(exc)
    return f"{type(exc).__name__} {code}" if code else type(exc).__name__


def retry_wait(retries):
    """Los segundos que se esperan antes del reintento que sigue a `retries` reintentos.

    Se sortean por debajo de un tope que crece de 30 s a 15 min: los ocho reintentos suman
    como mucho 60,5 minutos de espera (unos treinta, de media).
    """
    return get_exponential_backoff_interval(
        factor=30, retries=retries, maximum=900, full_jitter=True
    )


# Un servidor que contesta despacio a cada paso de la conversación SMTP agota el límite blando y
# se reintenta (`is_temporary`); EMAIL_TIMEOUT, menor, corta antes al que calla. El duro queda por
# debajo del plazo que Docker da al worker para parar (docker-compose.prod.yml): un correo en
# curso termina antes de que lo maten.
@shared_task(bind=True, max_retries=MAX_RETRIES, soft_time_limit=30, time_limit=60)
def send_confirmation_email(self, subscriber_id):
    """Correo de confirmación de suscripción (doble opt-in).

    Fuera del hilo de la petición (no bloquea un worker de gunicorn ante un SMTP
    lento) y con reintento ante los fallos temporales (`is_temporary`), con esperas que
    crecen (`retry_wait`). Sin fail_silently: un fallo definitivo, o el último de los
    reintentos, sube a Sentry en vez de tragarse en silencio. Lleva las cabeceras
    List-Unsubscribe, con el enlace de baja, y List-Unsubscribe-Post (RFC 8058), para
    que el cliente de correo ofrezca un botón de baja en un clic y mejore la reputación
    de envío.

    Recibe solo el id: el correo y los tokens no viajan por el broker, ni quedan en los
    argumentos que Celery escribe en el log o adjunta a un error. Las URL se arman con
    SITE_URL. Deja en el suscriptor la fecha del envío o el último error, que el panel
    enseña junto a una acción para reenviar.
    """
    sub = NewsletterSubscriber.objects.filter(pk=subscriber_id).first()
    if sub is None or not sub.confirm_token:
        return  # se dio de baja, ya confirmó o se borró mientras esperaba en la cola
    context = {
        "name": SiteProfile.load().site_name,
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
            # URL por GET —que no muta nada— y la baja no llegaría a ejecutarse.
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    try:
        # Como contexto, el backend cierra la conexión al salir, falle donde falle. Sin él, una
        # conexión que el servidor rechaza en EHLO, STARTTLS o el inicio de sesión quedaría
        # abierta: send_messages solo cierra la que llegó a abrir entera.
        with get_connection(fail_silently=False) as connection:
            connection.send_messages([message])
    except Exception as exc:
        NewsletterSubscriber.objects.filter(pk=sub.pk).update(
            confirmation_error=describe_error(exc)[:120]
        )
        if is_temporary(exc):
            raise self.retry(exc=exc, countdown=retry_wait(self.request.retries)) from exc
        raise
    NewsletterSubscriber.objects.filter(pk=sub.pk).update(
        confirmation_sent_at=timezone.now(), confirmation_error=""
    )
