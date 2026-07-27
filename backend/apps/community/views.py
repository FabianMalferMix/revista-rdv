from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import NewsletterSubscriber


@require_POST
def subscribe(request):
    """Alta en la lista de novedades para prensa y gestores (queda pendiente).

    Sin doble opt-in por ahora: el equipo confirma desde el admin antes de usar
    la lista. El honeypot descarta bots en silencio.
    """
    form = SubscribeForm(request.POST)
    if form.is_valid() and not form.cleaned_data["apodo"]:
        NewsletterSubscriber.objects.get_or_create(email=form.cleaned_data["email"])
        messages.success(request, "¡Gracias! Te avisaremos de novedades y actividades.")
    elif not form.is_valid():
        messages.error(request, "Revisa el correo ingresado.")
    return redirect(request.POST.get("next") or "content:home")
