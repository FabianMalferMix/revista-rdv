"""Archivos que solo se sirven mientras su pieza está publicada.

El audio de los registros y los PDF de las publicaciones no salen de /media/, que Caddy sirve
sin preguntar a nadie: despublicar una pieza dejaba su archivo accesible para quien tuviera
la URL (el feed de pódcast ya la había repartido). Los entrega una vista que primero busca la
pieza como cualquier ficha (404 si no está publicada; el equipo la ve como vista previa).
En producción, la vista responde con X-Accel-Redirect y Caddy lee el archivo del volumen
(infra/caddy/Caddyfile), de modo que el audio admite saltos (Range) y gunicorn no ocupa un
hilo en enviarlo. En desarrollo, sin Caddy, lo envía Django.

El audio se pide por el nombre de su archivo, que cambia al reemplazarlo. Los PDF que se
descargan y se reenvían (el dossier y el de cada publicación) tienen una dirección fija que no
lo nombra: el archivo nuevo no puede tomar el nombre del viejo hasta que se confirma el guardado.
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
    return marked_as_preview(_file_response(fieldfile), preview)


def serve_current(request, fieldfile, preview):
    """El archivo vigente en una dirección que no lo nombra, o 404 si no hay archivo. Tras un
    reemplazo, la misma dirección da el nuevo: se revalida en cada uso, para que ninguna caché
    retenga el anterior, y se guarda con el nombre de la dirección, no con el del archivo."""
    if not fieldfile:
        raise Http404
    response = _file_response(fieldfile, PurePosixPath(request.path).name)
    response["Cache-Control"] = "no-cache"
    return marked_as_preview(response, preview)


def _file_response(fieldfile, download_name=""):
    if settings.PROTECTED_MEDIA_ACCEL:
        # Caddy copia las cabeceras de caché y de vista previa, y la descarga toma el nombre
        # de la dirección.
        response = HttpResponse()
        response["X-Accel-Redirect"] = "/" + quote(fieldfile.name)
        return response
    return FileResponse(fieldfile.open("rb"), filename=download_name)


def random_upload_path(folder, filename):
    """La ruta de un archivo subido, con un nombre al azar y su extensión: el nombre original
    (a menudo el slug) no deja adivinar la dirección de un archivo que no se publicó."""
    extension = PurePosixPath(filename).suffix.lower()
    return f"{folder}/{timezone.now():%Y/%m}/{uuid4().hex}{extension}"
