import logging
import secrets

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from kombu.exceptions import OperationalError as BrokerError

from .forms import SubscribeForm
from .models import NewsletterSubscriber
from .tasks import send_confirmation_email

S = NewsletterSubscriber.Status
logger = logging.getLogger(__name__)

# Respuesta única para TODAS las ramas del alta. Antes el mensaje distinguía a quien ya
# estaba confirmado («Ya estabas suscrito/a») de quien no, lo que convertía el formulario
# público en un oráculo de pertenencia: cualquiera podía comprobar si una dirección
# concreta estaba en la lista (hallazgo S-17).
ALTA_NEUTRA = "Si la dirección es válida, te enviamos un correo para confirmar la suscripción."


def _por_token(campo, token):
    if not token:
        raise Http404("Enlace no válido o expirado.")
    sub = NewsletterSubscriber.objects.filter(**{campo: token}).first()
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
    honeypot descarta bots en silencio.

    Todas las ramas responden lo mismo y hacen el mismo trabajo observable, para no
    filtrar si una dirección ya estaba en la lista (S-17)."""
    nxt = _safe_next(request)
    if getattr(request, "limited", False):  # rate-limit por IP superado
        messages.error(request, "Demasiados intentos. Espera un momento e inténtalo de nuevo.")
        return redirect(nxt)
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa el correo ingresado.")
        return redirect(nxt)
    if form.cleaned_data["apodo"]:  # honeypot
        messages.success(request, ALTA_NEUTRA)
        return redirect(nxt)

    sub, _ = NewsletterSubscriber.objects.get_or_create(email=form.cleaned_data["email"])
    # A quien ya confirmó no se le reenvía nada, pero la respuesta es idéntica.
    if sub.status != S.CONFIRMED:
        if not sub.token:
            sub.token = secrets.token_urlsafe(32)  # baja: estable de por vida
        # Confirmación: token NUEVO en cada alta, con marca de tiempo para caducar.
        sub.confirm_token = secrets.token_urlsafe(32)
        sub.confirm_token_at = timezone.now()
        sub.status = S.PENDING
        sub.save(update_fields=["token", "confirm_token", "confirm_token_at", "status"])
        _send_confirmation(request, sub)
    messages.success(request, ALTA_NEUTRA)
    return redirect(nxt)


def _send_confirmation(request, sub):
    # Las URLs se arman con la request (host absoluto) y el envío va a Celery.
    confirm_url = request.build_absolute_uri(reverse("community:confirm", args=[sub.confirm_token]))
    unsub_url = request.build_absolute_uri(reverse("community:unsubscribe", args=[sub.token]))
    try:
        send_confirmation_email.delay(sub.email, confirm_url, unsub_url)
    except BrokerError:
        # Broker inaccesible al encolar: el suscriptor ya quedó guardado, así que no
        # rompemos la suscripción con un 500. Se registra (sube a Sentry) para que la
        # operación lo atienda; el usuario puede reintentar el alta si no llega el correo.
        # Sin la dirección en el mensaje: el log no es sitio para PII (S-21).
        logger.exception("No se pudo encolar el correo de confirmación (suscriptor id=%s)", sub.pk)


def confirm(request, token):
    """Confirmación del doble opt-in.

    Muta solo por POST (S-16): los escáneres de enlaces de los clientes de correo y las
    pasarelas antivirus visitan por GET todo lo que llega en un mensaje, de modo que
    confirmaban la suscripción por su cuenta y vaciaban de sentido el doble opt-in —el
    consentimiento registrado no probaba nada—. El GET solo muestra el botón.
    """
    sub = _por_token("confirm_token", token)
    if request.method != "POST":
        return render(
            request,
            "community/newsletter_confirm.html",
            {"token": token, "caducado": not sub.confirm_token_is_valid()},
        )

    if not sub.confirm_token_is_valid():
        raise Http404("Enlace no válido o expirado.")
    sub.status = S.CONFIRMED
    sub.confirmed_at = timezone.now()
    # De un solo uso: el token se consume al confirmar.
    sub.confirm_token = ""
    sub.confirm_token_at = None
    sub.save(update_fields=["status", "confirmed_at", "confirm_token", "confirm_token_at"])
    return render(
        request,
        "community/newsletter_message.html",
        {
            "title": "Suscripción confirmada",
            "body": "¡Listo! Recibirás nuestras novedades. Puedes darte de baja cuando quieras.",
            "unsubscribe_token": sub.token,
        },
    )


@csrf_exempt
def unsubscribe(request, token):
    """Baja.

    Muta solo por POST, con dos caminos: el formulario de la página (con CSRF) y el
    un-clic de los clientes de correo (RFC 8058), que envían
    `List-Unsubscribe=One-Click` en el cuerpo. Ese POST viene de un agente externo sin
    sesión ni token CSRF, así que la vista queda exenta: no hay nada que un atacante
    pueda lograr salvo dar de baja a quien ya posee el enlace secreto, y el perjuicio
    de no poder darse de baja es mayor.
    """
    sub = _por_token("token", token)
    if request.method != "POST":
        return render(request, "community/newsletter_unsubscribe.html", {"token": token})

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
