"""Archivos que solo se sirven mientras su pieza está publicada.

El audio de los registros y los PDF de las publicaciones no salen de /media/, que Caddy sirve
sin preguntar a nadie: despublicar una pieza dejaba su archivo accesible para quien tuviera
la URL (el feed de pódcast ya la había repartido). Los entrega una vista que primero busca la
pieza como cualquier ficha (404 si no está publicada; el equipo la ve como vista previa).
En producción, la vista responde con X-Accel-Redirect y Caddy lee el archivo del volumen
(infra/caddy/Caddyfile), de modo que el audio admite saltos (Range) y gunicorn no ocupa un
hilo en enviarlo. En desarrollo, sin Caddy, lo envía Django.
"""

from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone

from config.publishing import marked_as_preview


def file_name(fieldfile):
    """El nombre del archivo, el último tramo de su URL pública."""
    return PurePosixPath(fieldfile.name).name if fieldfile else ""


def serve(fieldfile, requested_name, preview):
    """La respuesta con el archivo, o 404 si no hay archivo o el nombre no es el vigente
    (un archivo reemplazado no se sigue sirviendo por su nombre viejo)."""
    if not fieldfile or requested_name != file_name(fieldfile):
        raise Http404
    if settings.PROTECTED_MEDIA_ACCEL:
        response = HttpResponse()
        response["X-Accel-Redirect"] = "/" + quote(fieldfile.name)
    else:
        response = FileResponse(fieldfile.open("rb"))
    return marked_as_preview(response, preview)


def random_upload_path(folder, filename):
    """La ruta de un archivo subido, con un nombre al azar y su extensión: el nombre original
    (a menudo el slug) no deja adivinar la dirección de un archivo que no se publicó."""
    extension = PurePosixPath(filename).suffix.lower()
    return f"{folder}/{timezone.now():%Y/%m}/{uuid4().hex}{extension}"
