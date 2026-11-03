"""URLconf de prueba: las rutas del boletín con otro nombre, y una ruta con token nueva."""

from django.urls import include, path

from apps.community import views

newsletter = (
    [
        path("alta/confirmar/<str:token>/", views.confirm, name="confirm"),
        path("salir/<str:token>/", views.unsubscribe, name="unsubscribe"),
        path("salir-en-un-clic/<str:token>/", views.unsubscribe, name="one_click_unsubscribe"),
    ],
    "community",
)

urlpatterns = [path("boletin/", include(newsletter))]
