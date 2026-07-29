import logging
import secrets

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from kombu.exceptions import OperationalError as BrokerError

from .forms import SubscribeForm
from .models import NewsletterSubscriber
from .tasks import send_confirmation_email

S = NewsletterSubscriber.Status
logger = logging.getLogger(__name__)


def _by_token(token):
    sub = NewsletterSubscriber.objects.filter(token=token).first() if token else None
    if sub is None:
        raise Http404("Enlace no válido o expirado.")
    return sub


def _safe_next(request):
    """Destino de redirección validado: solo rutas del propio sitio. Evita el open
    redirect (CWE-601) de un `next` arbitrario (p. ej. //evil.com) — hallazgo #07."""
    nxt = request.POST.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return "content:home"


@require_POST
@ratelimit(key="ip", rate="5/m", method="POST", block=False)
def subscribe(request):
    """Alta con **doble opt-in**: crea (o reusa) el suscriptor en 'pending' y envía un
    correo con enlace de confirmación. Solo tras confirmar se le puede escribir. El
    honeypot descarta bots en silencio."""
    nxt = _safe_next(request)
    if getattr(request, "limited", False):  # rate-limit por IP superado
        messages.error(request, "Demasiados intentos. Espera un momento e inténtalo de nuevo.")
        return redirect(nxt)
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa el correo ingresado.")
        return redirect(nxt)
    if form.cleaned_data["apodo"]:  # honeypot
        return redirect(nxt)

    sub, _ = NewsletterSubscriber.objects.get_or_create(email=form.cleaned_data["email"])
    if sub.status == S.CONFIRMED:
        messages.success(request, "Ya estabas suscrito/a. ¡Gracias!")
        return redirect(nxt)

    if not sub.token:
        sub.token = secrets.token_urlsafe(32)
    sub.status = S.PENDING
    sub.save(update_fields=["token", "status"])
    _send_confirmation(request, sub)
    messages.success(request, "Te enviamos un correo para confirmar tu suscripción.")
    return redirect(nxt)


def _send_confirmation(request, sub):
    # Las URLs se arman con la request (host absoluto) y el envío va a Celery.
    confirm_url = request.build_absolute_uri(reverse("community:confirm", args=[sub.token]))
    unsub_url = request.build_absolute_uri(reverse("community:unsubscribe", args=[sub.token]))
    try:
        send_confirmation_email.delay(sub.email, confirm_url, unsub_url)
    except BrokerError:
        # Broker inaccesible al encolar: el suscriptor ya quedó guardado, así que no
        # rompemos la suscripción con un 500. Se registra (sube a Sentry) para que la
        # operación lo atienda; el usuario puede reintentar el alta si no llega el correo.
        logger.exception("No se pudo encolar el correo de confirmación para %s", sub.email)


def confirm(request, token):
    sub = _by_token(token)
    if sub.status != S.CONFIRMED:
        sub.status = S.CONFIRMED
        sub.confirmed_at = timezone.now()
        sub.save(update_fields=["status", "confirmed_at"])
    return render(
        request,
        "community/newsletter_message.html",
        {
            "title": "Suscripción confirmada",
            "body": "¡Listo! Recibirás nuestras novedades. Puedes darte de baja cuando quieras.",
            "unsubscribe_token": sub.token,
        },
    )


def unsubscribe(request, token):
    sub = _by_token(token)
    if sub.status != S.UNSUBSCRIBED:
        sub.status = S.UNSUBSCRIBED
        sub.save(update_fields=["status"])
    return render(
        request,
        "community/newsletter_message.html",
        {
            "title": "Te diste de baja",
            "body": "No recibirás más correos. Si fue un error, puedes volver a suscribirte.",
        },
    )
