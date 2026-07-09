from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("enviar/", views.submit, name="submit"),
    path("enviar/gracias/", views.submit_thanks, name="submit_thanks"),
    path("envios/<int:pk>/archivo/", views.submission_file, name="file"),
]
