"""Borrado de los archivos al borrar o reemplazar la fila (hallazgo S-13).

Django NO borra el archivo del disco al borrar el modelo, ni al reemplazar el valor de
un `FileField`. El resultado era acumulación silenciosa: borrar un envío desde el admin
dejaba el manuscrito en `private_media` —y en todos los respaldos posteriores—, de modo
que una petición de supresión de datos no se cumplía de verdad. Solo
`purge_stale_data` borraba adjuntos, y únicamente por su camino.

Se usan señales en vez de sobrescribir `delete()` porque `QuerySet.delete()` (borrado
masivo desde el admin) no pasa por el método del modelo, pero sí emite `post_delete`
por cada instancia.

Nada se borra antes de que la transacción confirme el cambio (`transaction.on_commit`): si
el guardado o el borrado se deshacen —un disco lleno al escribir el archivo nuevo, una
excepción en el resto del `save()`—, la fila vuelve a apuntar a su archivo, y el archivo
sigue en el disco. Al reemplazar, el nombre viejo se anota en `pre_save` y se programa su
borrado en `post_save`, cuando el archivo nuevo ya está escrito y la fila, actualizada.
"""

import logging
from functools import partial

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save

logger = logging.getLogger(__name__)
# Donde `pre_save` deja, en la instancia, los archivos que reemplaza el guardado en curso.
_REPLACED = "_filecleanup_replaced"


def _borrar(storage, names, label, pk):
    for name in names:
        try:
            storage.delete(name)
        except Exception:  # noqa: BLE001 - nunca debe impedir el borrado de la fila
            # Un archivo que queda huérfano: el ERROR dice de qué fila era para poder borrarlo.
            logger.exception("No se pudo borrar el archivo %r de %s pk=%s", name, label, pk)


def _delete_on_commit(storage, names, instance, using):
    """Borra los archivos cuando confirme la transacción en curso; si se deshace, no."""
    names = [name for name in names if name]
    if names:
        transaction.on_commit(
            partial(_borrar, storage, names, instance._meta.label, instance.pk), using=using
        )


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
    def handler(sender, instance, using, **kwargs):
        fieldfile = getattr(instance, field_name, None)
        if not fieldfile:
            return
        _delete_on_commit(fieldfile.storage, _nombres(instance, field_name), instance, using)

    return handler


def _al_reemplazar(field_name):
    def handler(sender, instance, update_fields=None, **kwargs):
        # Lo que anotó un guardado anterior que falló antes de su post_save ya no vale.
        instance.__dict__.setdefault(_REPLACED, {}).pop(field_name, None)
        # `_state.adding` y no `instance.pk`: hay modelos que fijan la clave antes de
        # existir en la base —`SiteProfile` fuerza pk=1 por ser un singleton— y con la
        # comprobación por pk se hacía un SELECT inútil en cada alta.
        if instance._state.adding or not instance.pk:
            return  # alta: no hay archivo previo
        if update_fields is not None and field_name not in update_fields:
            return  # este guardado no escribe el campo
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
        instance.__dict__[_REPLACED][field_name] = (viejo.storage, _nombres(anterior, field_name))

    return handler


def _after_replace(field_name):
    def handler(sender, instance, using, **kwargs):
        replaced = instance.__dict__.get(_REPLACED, {}).pop(field_name, None)
        if replaced is not None:
            _delete_on_commit(*replaced, instance, using)

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
        post_save.connect(
            _after_replace(field_name),
            sender=model,
            weak=False,
            dispatch_uid=f"filecleanup:replaced:{etiqueta}:{field_name}",
        )
