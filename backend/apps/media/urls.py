from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path("registros/", views.recording_index, name="recording_index"),
    path("registro/<slug:slug>/", views.recording_detail, name="recording_detail"),
]
