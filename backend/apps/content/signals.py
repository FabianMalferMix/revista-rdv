"""Lo que sigue a cada guardado de un artículo o de una página: la lista de imágenes de la
biblioteca que muestra su cuerpo (`services.sync_body_images`)."""

from django.db.models.signals import post_save

from .models import Article, Page
from .services import sync_body_images


def body_images_follow_the_body(sender, instance, raw=False, update_fields=None, **kwargs):
    # `loaddata` guarda las filas tal cual (`raw`): `datos_de_desarrollo cargar` rehace la lista
    # después. Un guardado que no toca el cuerpo no la cambia.
    if raw or (update_fields is not None and "body" not in update_fields):
        return
    sync_body_images(instance)


def connect():
    for model in (Article, Page):
        post_save.connect(
            body_images_follow_the_body,
            sender=model,
            dispatch_uid=f"content.body_images:{model._meta.label}",
        )
