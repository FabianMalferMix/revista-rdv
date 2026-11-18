"""Las imágenes del cuerpo de un artículo o de una página.

Al guardar desde el panel, las imágenes de otro sitio se copian a la biblioteca y el cuerpo pasa a
mostrar la copia (`copy_remote_images`): la CSP no deja que una página pida imágenes a otro origen,
y pedirlas le contaría a ese sitio cada visita. Y cada guardado anota qué imágenes de la biblioteca
muestra el cuerpo (`sync_body_images`, desde signals.py), para que Recursos diga dónde se usa cada
una y no deje borrar la que se ve.
"""

import logging
import time
from urllib.parse import unquote, urljoin, urlsplit

from django.conf import settings
from django.db import transaction

from apps.media.models import MediaAsset
from apps.media.services import ImageNotCopied, copy_remote_image
from config.content_policy import browser_url, is_own_url

from .models import Article, Page
from .sanitize import clean_html, images_in, own_images_only

logger = logging.getLogger(__name__)

# Lo que se espera a otro sitio: por imagen, y por guardado, que así termina antes de que Caddy deje
# de esperar la respuesta (`write 60s`, infra/caddy/Caddyfile).
IMAGE_SECONDS = 10
SAVE_SECONDS = 30


def copy_remote_images(body, user):
    """Copia a la biblioteca las imágenes de otro sitio que muestra `body`.

    Devuelve el cuerpo, con cada imagen copiada apuntando a su copia y sin las que no se pudieron
    copiar; las copias, como {src: recurso}, y las que no, como (sitio, motivo). Quien no puede
    subir imágenes a la biblioteca no copia ninguna.
    """
    remote = {src: alt for src, alt in images_in(body).items() if not is_own_url(src)}
    if not remote:
        return body, {}, []
    allowed = user.has_perm("media.add_mediaasset")
    budget = time.monotonic() + SAVE_SECONDS
    copies, failures = {}, []
    for src, alt in remote.items():
        url = _as_requested(src)
        host = _host(url)
        if not allowed:
            failures.append((host, "no tienes permiso para subir imágenes"))
        elif time.monotonic() >= budget:
            failures.append((host, "no quedó tiempo para copiarla"))
        else:
            try:
                with transaction.atomic():
                    copies[src] = copy_remote_image(
                        url,
                        alt_text=(alt.strip() or f"Imagen copiada de {host}")[:255],
                        uploaded_by=user,
                        deadline=min(time.monotonic() + IMAGE_SECONDS, budget),
                    )
            except ImageNotCopied as exc:
                logger.warning("No se copió una imagen de %s: %s", host, exc)
                failures.append((host, str(exc)))
            except Exception:
                logger.exception("Falló la copia de una imagen de %s", host)
                failures.append((host, "un error inesperado, que quedó en el registro"))

    def shown(src):
        return copies[src].file.url if src in copies else own_images_only(src)

    return clean_html(body, image_source=shown), copies, failures


def _as_requested(src):
    """La dirección que pide el navegador: «//sitio/…» va con el esquema de la página, https."""
    url = browser_url(src)
    return f"https://{url.lstrip('/')}" if url.startswith("//") else url


def _host(url):
    """El nombre del sitio, para los mensajes y el registro: la dirección entera puede llevar algo
    que solo debía conocer quien la tenía."""
    try:
        return urlsplit(url).hostname or "otro sitio"
    except ValueError:  # un IPv6 mal cerrado
        return "otro sitio"


def body_image_names(item):
    """Los nombres de los archivos de la biblioteca que muestra el cuerpo de `item`, un artículo o
    una página, sin consultar la base.

    Las direcciones relativas se resuelven desde la ficha, como en el navegador, y desde su
    dirección absoluta: con una ruta sola, urljoin no resuelve los «../» igual. Una copia del
    `srcset` o de la portada cuenta como su original. La dirección de la ficha solo se pide si
    el cuerpo muestra alguna imagen del sitio: guardar un cuerpo sin ellas no depende de ella.
    """
    own = [src for src in images_in(item.body) if is_own_url(src)]
    if not own:
        return set()
    page = f"{settings.SITE_URL}{item.get_absolute_url()}"
    media = urlsplit(urljoin(page, settings.MEDIA_URL)).path
    names = set()
    for src in own:
        path = unquote(urlsplit(urljoin(page, browser_url(src))).path)
        if path.startswith(media):
            name = path.removeprefix(media)
            names |= {name, MediaAsset.original_name(name)}
    return names


def body_image_ids(item):
    """Los recursos de la biblioteca que muestra el cuerpo de `item` (`body_image_names`)."""
    names = body_image_names(item)
    if not names:
        return set()
    return set(MediaAsset.objects.filter(file__in=names).values_list("pk", flat=True))


def sync_body_images(item):
    """Rehace la lista de imágenes de la biblioteca que muestra el cuerpo de `item`, un artículo o
    una página."""
    wanted = body_image_ids(item)
    item.body_images.exclude(image_id__in=wanted).delete()
    present = set(item.body_images.values_list("image_id", flat=True))
    model = item.body_images.model
    model.objects.bulk_create(
        [model(item=item, image_id=pk) for pk in wanted - present], ignore_conflicts=True
    )


def sync_all_body_images():
    """Rehace la lista de todas las piezas, tras cargar datos sin pasar por `save()`."""
    for model in (Article, Page):
        for item in model._base_manager.iterator():
            sync_body_images(item)
