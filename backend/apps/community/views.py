import logging
from functools import wraps

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from kombu.exceptions import OperationalError as BrokerError

from . import services
from .forms import SubscribeForm
from .models import NewsletterSubscriber
from .tasks import send_confirmation_email

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
    """La ruta del propio sitio adonde volver tras el alta; si no hay una válida, la portada.

    Devuelve siempre una URL, nunca un nombre de vista. Solo vale una ruta que empieza por
    «/»: `url_has_allowed_host_and_scheme` acepta también una palabra suelta («agenda»), que
    `redirect()` intentaba resolver como nombre de vista (un 500), y rechaza `//evil.com`
    (redirección abierta, CWE-601).
    """
    nxt = request.POST.get("next", "")
    if nxt.startswith("/") and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse("content:home")


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
        return HttpResponseRedirect(nxt)
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa el correo ingresado.")
        return HttpResponseRedirect(nxt)
    if form.cleaned_data["apodo"]:  # honeypot
        messages.success(request, ALTA_NEUTRA)
        return HttpResponseRedirect(nxt)

    # A quien ya confirmó, o recibió la confirmación hace poco, no se le reenvía nada, pero
    # la respuesta es idéntica.
    sub = services.subscribe(form.cleaned_data["email"])
    if sub is not None:
        _send_confirmation(sub)
    messages.success(request, ALTA_NEUTRA)
    return HttpResponseRedirect(nxt)


def _send_confirmation(sub):
    # El envío va a Celery cuando la transacción se confirma, y con el id: ni el correo ni
    # los tokens viajan por el broker.
    try:
        send_confirmation_email.delay_on_commit(sub.pk)
    except BrokerError:
        # Broker inaccesible al encolar: el suscriptor ya quedó guardado, así que no
        # rompemos la suscripción con un 500. Se registra (sube a Sentry) para que la
        # operación lo atienda; el usuario puede reintentar el alta si no llega el correo.
        # Sin la dirección en el mensaje: el log no es sitio para datos personales.
        logger.exception("No se pudo encolar el correo de confirmación (suscriptor id=%s)", sub.pk)


def _no_referrer(view):
    """Las páginas con token en la URL no la mandan como Referer a nada de lo que cargan
    (estilos, guiones, el buscador): la URL es el secreto."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response["Referrer-Policy"] = "no-referrer"
        return response

    return wrapper


@_no_referrer
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
    sub.confirm()
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
@_no_referrer
def unsubscribe(request, token):
    """Baja.

    Muta solo por POST, con dos caminos: el formulario de la página y el un-clic de los
    clientes de correo (RFC 8058), que envían `List-Unsubscribe=One-Click` en el cuerpo.
    Ese POST viene de un agente externo sin sesión ni token CSRF, así que la vista entera
    queda exenta, también para el formulario: no hay nada que un atacante pueda lograr
    salvo dar de baja a quien ya posee el enlace secreto, y el perjuicio de no poder
    darse de baja es mayor. La exención la fija `test_one_click_unsubscribe_skips_csrf`.
    """
    sub = _por_token("token", token)
    if request.method != "POST":
        return render(request, "community/newsletter_unsubscribe.html", {"token": token})

    sub.unsubscribe()
    return render(
        request,
        "community/newsletter_message.html",
        {
            "title": "Te diste de baja",
            "body": "No recibirás más correos. Si fue un error, puedes volver a suscribirte.",
        },
    )
