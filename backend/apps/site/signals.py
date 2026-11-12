"""Lo que vacía la caché del sitemap y de los feeds (config/listing_cache.py)."""

from django.db import transaction
from django.db.models import QuerySet
from django.db.models.signals import m2m_changed, post_delete, post_save

from apps.showcase.models import SiteProfile
from config.listing_cache import bump_generation

from .feeds import FEEDS
from .sitemaps import SITEMAPS


def listed_models():
    """Los modelos de lo que listan las secciones del sitemap y los feeds, con las tablas de sus
    relaciones de muchos a muchos: de quién firma un texto depende que su ficha esté en el
    sitemap, y de las autoras de una obra, que la tengan ellas. Y el perfil del colectivo, del
    que cada feed saca su título y su descripción (`get_object`)."""
    querysets = [section().items() for section in SITEMAPS.values()]
    querysets += [feed.items() for feed in FEEDS.values()]
    models = {items.model for items in querysets if isinstance(items, QuerySet)}
    through = {field.remote_field.through for model in models for field in model._meta.many_to_many}
    return models | through | {SiteProfile}


def listing_changed(sender, action=None, using=None, **kwargs):
    # Al confirmarse el cambio: una respuesta armada antes, con la base todavía sin él, queda
    # guardada en una generación que ya nadie pide. Del `m2m_changed` cuentan los `post_*`.
    if action is None or action.startswith("post_"):
        transaction.on_commit(bump_generation, using=using, robust=True)


def connect():
    for model in listed_models():
        # `m2m_changed` llega con la tabla de la relación como `sender`.
        for signal in (post_save, post_delete, m2m_changed):
            signal.connect(
                listing_changed, sender=model, dispatch_uid=f"listing:{model._meta.label}"
            )
