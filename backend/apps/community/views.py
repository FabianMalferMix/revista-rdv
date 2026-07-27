import secrets

from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import NewsletterSubscriber

S = NewsletterSubscriber.Status


def _by_token(token):
    sub = NewsletterSubscriber.objects.filter(token=token).first() if token else None
    if sub is None:
        raise Http404("Enlace no válido o expirado.")
    return sub


@require_POST
def subscribe(request):
    """Alta con **doble opt-in**: crea (o reusa) el suscriptor en 'pending' y envía un
    correo con enlace de confirmación. Solo tras confirmar se le puede escribir. El
    honeypot descarta bots en silencio."""
    form = SubscribeForm(request.POST)
    nxt = request.POST.get("next") or "content:home"
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
    confirm_url = request.build_absolute_uri(reverse("community:confirm", args=[sub.token]))
    unsub_url = request.build_absolute_uri(reverse("community:unsubscribe", args=[sub.token]))
    send_mail(
        subject="Confirma tu suscripción a las novedades",
        message=(
            "Gracias por suscribirte a las novedades del colectivo.\n\n"
            f"Confirma tu suscripción aquí:\n{confirm_url}\n\n"
            f"Si no fuiste tú, ignora este correo o date de baja:\n{unsub_url}\n"
        ),
        from_email=None,  # DEFAULT_FROM_EMAIL
        recipient_list=[sub.email],
        fail_silently=True,
    )


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
