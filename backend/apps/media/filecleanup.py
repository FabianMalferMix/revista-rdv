"""Borrado de los archivos al borrar o reemplazar la fila (hallazgo S-13).

Django NO borra el archivo del disco al borrar el modelo, ni al reemplazar el valor de
un `FileField`. El resultado era acumulación silenciosa: borrar un envío desde el admin
dejaba el manuscrito en `private_media` —y en todos los respaldos posteriores—, de modo
que una petición de supresión de datos no se cumplía de verdad. Solo
`purge_stale_data` borraba adjuntos, y únicamente por su camino.

Se usan señales en vez de sobrescribir `delete()` porque `QuerySet.delete()` (borrado
masivo desde el admin) no pasa por el método del modelo, pero sí emite `post_delete`
por cada instancia.
"""

import logging

from django.db.models.signals import post_delete, pre_save

logger = logging.getLogger(__name__)


def _borrar(storage, name):
    if not name:
        return
    try:
        storage.delete(name)
    except Exception:  # noqa: BLE001 - nunca debe impedir el borrado de la fila
        logger.warning("No se pudo borrar el archivo %r del almacenamiento", name, exc_info=True)


def _nombres(instance, field_name):
    """El archivo del campo y, si el modelo los declara, sus derivados."""
    fieldfile = getattr(instance, field_name, None)
    if not fieldfile or not fieldfile.name:
        return []
    nombres = [fieldfile.name]
    derivados = getattr(instance, "derivative_names", None)
    if callable(derivados):
        nombres += list(derivados())
    return nombres


def _al_borrar(field_name):
    def handler(sender, instance, **kwargs):
        fieldfile = getattr(instance, field_name, None)
        if not fieldfile:
            return
        for name in _nombres(instance, field_name):
            _borrar(fieldfile.storage, name)

    return handler


def _al_reemplazar(field_name):
    def handler(sender, instance, **kwargs):
        # `_state.adding` y no `instance.pk`: hay modelos que fijan la clave antes de
        # existir en la base —`SiteProfile` fuerza pk=1 por ser un singleton— y con la
        # comprobación por pk se hacía un SELECT inútil en cada alta.
        if instance._state.adding or not instance.pk:
            return  # alta: no hay archivo previo
        try:
            anterior = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return
        viejo = getattr(anterior, field_name, None)
        nuevo = getattr(instance, field_name, None)
        if not viejo or not viejo.name:
            return
        if viejo.name == (nuevo.name if nuevo else None):
            return  # mismo archivo: no tocar
        for name in _nombres(anterior, field_name):
            _borrar(viejo.storage, name)

    return handler


def register(model, *field_names):
    """Conecta el borrado de archivos para los campos indicados de `model`."""
    etiqueta = f"{model._meta.app_label}.{model._meta.model_name}"
    for field_name in field_names:
        post_delete.connect(
            _al_borrar(field_name),
            sender=model,
            weak=False,
            dispatch_uid=f"filecleanup:delete:{etiqueta}:{field_name}",
        )
        pre_save.connect(
            _al_reemplazar(field_name),
            sender=model,
            weak=False,
            dispatch_uid=f"filecleanup:replace:{etiqueta}:{field_name}",
        )
