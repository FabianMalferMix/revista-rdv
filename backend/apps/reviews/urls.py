from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("obra/<slug:slug>/", views.work_detail, name="work_detail"),
    path("editorial/<slug:slug>/", views.publisher_detail, name="publisher_detail"),
    path("autor/<slug:slug>/", views.bookauthor_detail, name="bookauthor_detail"),
]
