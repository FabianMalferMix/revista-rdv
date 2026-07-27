from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.search, name="search"),
    path("articulo/<slug:slug>/", views.article_detail, name="article_detail"),
    path("poemas/", views.poem_index, name="poem_index"),
    path("poema/<slug:slug>/", views.poem_detail, name="poem_detail"),
    path("seccion/<slug:slug>/", views.section_detail, name="section_detail"),
    path("etiqueta/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("colaborador/<slug:slug>/", views.contributor_detail, name="contributor_detail"),
    path("colecciones/", views.collection_index, name="collection_index"),
    path("coleccion/<slug:slug>/", views.collection_detail, name="collection_detail"),
    path("pagina/<slug:slug>/", views.page_detail, name="page_detail"),
]
