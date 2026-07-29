import smtplib

from celery import shared_task
from django.core.mail import EmailMessage


@shared_task(
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_confirmation_email(email, confirm_url, unsub_url):
    """Correo de confirmación de suscripción (doble opt-in).

    Fuera del hilo de la petición (no bloquea un worker de gunicorn ante un SMTP
    lento) y con reintento/backoff ante fallos transitorios. Sin fail_silently: un
    fallo definitivo sube a Sentry en vez de tragarse en silencio. Lleva la cabecera
    List-Unsubscribe (RFC 8058) con el enlace de baja, para que el cliente de correo
    ofrezca un botón de darse de baja y mejore la reputación de envío.
    """
    message = EmailMessage(
        subject="Confirma tu suscripción a las novedades",
        body=(
            "Gracias por suscribirte a las novedades del colectivo.\n\n"
            f"Confirma tu suscripción aquí:\n{confirm_url}\n\n"
            f"Si no fuiste tú, ignora este correo o date de baja:\n{unsub_url}\n"
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        to=[email],
        headers={"List-Unsubscribe": f"<{unsub_url}>"},
    )
    message.send(fail_silently=False)
