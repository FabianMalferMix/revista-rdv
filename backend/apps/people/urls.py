from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("integrantes/", views.member_index, name="member_index"),
    path("integrante/<slug:slug>/", views.member_detail, name="member_detail"),
]
