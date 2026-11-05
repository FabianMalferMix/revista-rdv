from django.urls import path

from . import views

app_name = "site"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.search, name="search"),
]
