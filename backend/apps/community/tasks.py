import smtplib

from celery import shared_task
from django.core.mail import EmailMessage
from django.urls import reverse

from config.origin import absolute_url


@shared_task(
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
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
    SITE_URL.
    """
    from .models import NewsletterSubscriber

    sub = NewsletterSubscriber.objects.filter(pk=subscriber_id).first()
    if sub is None or not sub.confirm_token:
        return  # se dio de baja, ya confirmó o se borró mientras esperaba en la cola
    confirm_url = absolute_url(reverse("community:confirm", args=[sub.confirm_token]))
    unsub_url = absolute_url(reverse("community:unsubscribe", args=[sub.token]))
    message = EmailMessage(
        subject="Confirma tu suscripción a las novedades",
        body=(
            "Gracias por suscribirte a las novedades del colectivo.\n\n"
            f"Confirma tu suscripción aquí:\n{confirm_url}\n\n"
            f"Si no fuiste tú, ignora este correo o date de baja:\n{unsub_url}\n"
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        to=[sub.email],
        headers={
            "List-Unsubscribe": f"<{unsub_url}>",
            # RFC 8058: habilita el botón de baja en un clic del cliente de correo, que
            # envía un POST con este cuerpo. Sin esta cabecera, el cliente visitaría la
            # URL por GET —que ya no muta nada— y la baja no llegaría a ejecutarse.
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )
    message.send(fail_silently=False)
