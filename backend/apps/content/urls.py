from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.search, name="search"),
    path("articulo/<slug:slug>/", views.article_detail, name="article_detail"),
    path("seccion/<slug:slug>/", views.section_detail, name="section_detail"),
    path("etiqueta/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("colaborador/<slug:slug>/", views.contributor_detail, name="contributor_detail"),
    path("dosieres/", views.dossier_index, name="dossier_index"),
    path("dosier/<slug:slug>/", views.dossier_detail, name="dossier_detail"),
    path("pagina/<slug:slug>/", views.page_detail, name="page_detail"),
]
