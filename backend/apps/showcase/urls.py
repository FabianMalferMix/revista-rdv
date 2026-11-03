from django.urls import path

from . import views

app_name = "showcase"

urlpatterns = [
    path("dossier/", views.dossier, name="dossier"),
    path("publicaciones/", views.publication_index, name="publication_index"),
    path("publicacion/<slug:slug>/", views.publication_detail, name="publication_detail"),
    path(
        "archivo/publicacion/<slug:slug>/<str:filename>",
        views.publication_pdf,
        name="publication_pdf",
    ),
    path("prensa/", views.press_index, name="press_index"),
    path("aliados/", views.partner_index, name="partner_index"),
]
