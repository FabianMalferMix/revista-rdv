from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("agenda/", views.agenda, name="agenda"),
    path("trayectoria/", views.trayectoria, name="trayectoria"),
    path("galeria/", views.gallery, name="gallery"),
    path("evento/<slug:slug>/", views.event_detail, name="event_detail"),
]
