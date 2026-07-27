from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("novedades/", views.subscribe, name="subscribe"),
]
