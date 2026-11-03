from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path("registros/", views.recording_index, name="recording_index"),
    path("registro/<slug:slug>/", views.recording_detail, name="recording_detail"),
    path(
        "archivo/registro/<slug:slug>/<str:filename>",
        views.recording_file,
        name="recording_file",
    ),
]
