"""Las vistas de infraestructura, que no son páginas del sitio: las sondas de salud,
`robots.txt` y `/favicon.ico`."""

import json

from django.http import HttpResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import reverse

from config.health import readiness
from config.origin import absolute_url


def healthz(request):
    """Liveness: sonda barata para el healthcheck del contenedor y el proxy (no toca la BD)."""
    return HttpResponse("ok", content_type="text/plain")


def readyz(request):
    """Readiness para el monitor externo: 200 si el sitio puede operar, 503 si no, con lo que
    falla (config/health.py). Distinto de healthz (liveness), que solo dice que el proceso
    responde."""
    checks = readiness()
    ready = all(checks.values())
    return HttpResponse(
        json.dumps({"status": "ready" if ready else "not-ready", "checks": checks}),
        content_type="application/json",
        status=200 if ready else 503,
    )


def favicon(request):
    """Quien pide /favicon.ico (lectores de RSS, navegadores viejos, buscadores) recibe el
    icono del colectivo. Temporal: el archivo estático lleva su huella en la URL, que
    cambia con el icono, y una redirección permanente quedaría guardada para siempre."""
    return redirect(static("img/favicon.ico"))


def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Disallow: {reverse('admin:index')}",
        f"Sitemap: {absolute_url(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
