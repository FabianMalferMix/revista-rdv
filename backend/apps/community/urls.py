from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("novedades/", views.subscribe, name="subscribe"),
    path("novedades/confirmar/<str:token>/", views.confirm, name="confirm"),
    path("novedades/baja/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
