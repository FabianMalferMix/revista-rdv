"""El procesamiento de las imágenes de la biblioteca: un solo camino para todas.

Al subir una imagen, `MediaAsset.save()` la limpia de metadatos en la misma petición (si no se
puede, la subida se rechaza) y, cuando el guardado confirma, encola la tarea `process_image`
(apps/media/tasks.py), que llama aquí: repara el ancho y el alto, genera las copias del
`srcset`, las de la portada si alguna app la usa como tal, y mide el color del borde. El
comando `generate_image_derivatives` usa este mismo servicio con las imágenes que ya existen.
"""

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

from .models import IMAGE_ERRORS, MediaAsset

logger = logging.getLogger(__name__)

# Las copias del `srcset` van en el formato del original.
SRCSET_FORMATS = {
    "JPEG": ("JPEG", {"quality": 82, "optimize": True, "progressive": True}),
    "MPO": ("JPEG", {"quality": 82, "optimize": True, "progressive": True}),
    "PNG": ("PNG", {"optimize": True}),
    "WEBP": ("WEBP", {"quality": 82}),
}
_portada_uses = []


def register_portada_use(uses):
    """`uses(asset)` dice si alguna app usa la imagen como portada.

    La biblioteca sabe hacer las copias de portada, pero no qué imagen es una portada: lo
    registra quien la elige (apps.showcase, desde su `ready()`).
    """
    _portada_uses.append(uses)


def _wanted(asset, width, portada):
    """Las copias de una imagen de ese ancho: (ancho, nombre, formato y opciones)."""
    copies = [(w, asset._derivative_name(w), None) for w in asset.SRCSET_WIDTHS if w < width]
    if portada:
        copies += [
            (w, asset._portada_name(w, ext), (fmt, options))
            for w in asset._anchos_portada(width)
            for ext, fmt, options in asset.PORTADA_FORMATS
        ]
    return copies


def process_image(asset_id):
    """Deja una imagen lista para servirse.

    Idempotente: solo abre el archivo si falta algo y solo escribe lo que falta. Devuelve False
    si el archivo no se pudo limpiar o leer, con un WARNING que dice qué recurso y qué archivo.
    """
    asset = MediaAsset.objects.filter(pk=asset_id).first()
    if asset is None or not asset.file:
        return True
    if asset.metadata_stripped_at is None and not asset.strip_metadata():
        return False
    portada = any(uses(asset) for uses in _portada_uses)
    exists = asset.file.storage.exists
    # Lo que guarda la base, no lo que muestra la instancia: con la columna a NULL, ImageField
    # abre el archivo al instanciar y rellena el ancho solo en memoria.
    width, height = MediaAsset.objects.filter(pk=asset.pk).values_list("width", "height").get()
    if (
        width
        and height
        and asset.border_color
        and all(exists(name) for _, name, _ in _wanted(asset, width, portada))
    ):
        return True
    try:
        with asset.file.open("rb") as fh:
            img = Image.open(fh)
            srcset_format = SRCSET_FORMATS.get((img.format or "").upper())
            img.load()
    except IMAGE_ERRORS as exc:
        logger.warning(
            "No se pudo leer la imagen %s (recurso %s): %s", asset.file.name, asset.pk, exc
        )
        return False
    if (width, height) != img.size:
        MediaAsset.objects.filter(pk=asset.pk).update(width=img.width, height=img.height)

    # La transparencia se conserva (PNG, AVIF y WebP la admiten): pasada a RGB sin más, lo
    # transparente saldría negro y un logo en tinta desaparecería.
    transparent = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )
    base = img.convert("RGBA" if transparent else "RGB")
    pending = {}
    for w, name, output in _wanted(asset, base.width, portada):
        output = output or srcset_format
        if output and not exists(name):
            pending.setdefault(w, []).append((name, output))
    # De la más ancha a la más angosta, cada copia sale de la anterior, con un solo redimensionado
    # por ancho para todos sus formatos.
    current = base
    for w in sorted(pending, reverse=True):
        if w != current.width:
            size = (w, max(1, round(base.height * w / base.width)))
            current = current.resize(size, Image.Resampling.LANCZOS)
        for name, output in pending[w]:
            _write(asset, name, current, output)
    if not asset.border_color:
        color = border_color(current)
        MediaAsset.objects.filter(pk=asset.pk).update(border_color=color)
    return True


def _write(asset, name, img, output):
    fmt, options = output
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = BytesIO()
    try:
        img.save(buf, format=fmt, **options)
    except (KeyError, OSError) as exc:
        # Un Pillow sin codificador de AVIF deja al menos el WebP.
        logger.warning("No se pudo codificar %s en %s: %s", name, fmt, exc)
        return
    asset.file.storage.save(name, ContentFile(buf.getvalue()))


def border_color(img):
    """El color del borde de la imagen, en «#rrggbb»: la mediana del anillo exterior (un 4 % de
    cada lado), medida sobre una copia reducida."""
    factor = max(1, min(img.width // 120, img.height // 168))
    sample = img.reduce(factor).convert("RGB").resize((60, 84))
    ancho, alto = sample.size
    borde = max(1, round(min(ancho, alto) * 0.04))
    anillo = [
        sample.getpixel((x, y))
        for x in range(ancho)
        for y in range(alto)
        if x < borde or y < borde or x >= ancho - borde or y >= alto - borde
    ]
    mediana = [sorted(p[c] for p in anillo)[len(anillo) // 2] for c in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*mediana)
