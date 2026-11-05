"""URLconf de prueba: el sitio entero, con el panel en otra dirección."""

from django.contrib import admin
from django.urls import path

from config.urls import urlpatterns as site_urlpatterns

urlpatterns = [
    path("gestion/", admin.site.urls),
    *(pattern for pattern in site_urlpatterns if getattr(pattern, "namespace", None) != "admin"),
]
