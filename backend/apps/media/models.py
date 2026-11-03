import logging
import os
from io import BytesIO
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, ImageOps

from config import publishing
from config.protected_media import file_name, random_upload_path

from .validators import (
    MAX_AUDIO_MB,
    MAX_IMAGE_MB,
    validate_audio_extension,
    validate_audio_size,
    validate_image,
    validate_image_size,
)

logger = logging.getLogger(__name__)

# Dónde guarda Pillow los metadatos que delatan la ubicación, la fecha o la cámara: EXIF, XMP
# (en JPEG y WebP, y en PNG bajo su propia clave) e IPTC (el bloque «photoshop» de un JPEG).
METADATA_KEYS = {"exif", "xmp", "XML:com.adobe.xmp", "photoshop", "iptc"}
# Cómo se reescribe cada formato admitido (ver validators.IMAGE_FORMATS).
REWRITE_FORMATS = {
    "JPEG": ("JPEG", {"quality": 92, "optimize": True, "progressive": True}),
    "MPO": ("JPEG", {"quality": 92, "optimize": True, "progressive": True}),
    "WEBP": ("WEBP", {"quality": 92}),
    "PNG": ("PNG", {"optimize": True}),
}


# Lo que lanza Pillow ante un archivo que no puede leer: ilegible, truncado o demasiado grande.
IMAGE_ERRORS = (OSError, Image.DecompressionBombError)


class ImageCleanupError(Exception):
    """No se pudo reescribir sin metadatos una imagen recién subida: no se publica."""


class MediaAsset(models.Model):
    """Biblioteca de imágenes. width/height son derivados del archivo (no editables)."""

    # Anchos de los derivados para `srcset` (solo se generan los menores al original).
    SRCSET_WIDTHS = (240, 480, 960, 1440)
    # La obra de la portada va a sangre (D18): pide copias más anchas y en formatos
    # modernos. Se hacen solo para la imagen elegida como portada (apps.showcase lo dice al
    # servicio de imágenes), no para cada imagen que se sube. Las calidades dejan la lámina
    # del estreno bajo 300 KB en escritorio y 150 KB en el teléfono.
    PORTADA_WIDTHS = (640, 960, 1080, 1440, 1920, 2560)
    PORTADA_FORMATS = (("avif", "AVIF", {"quality": 50}), ("webp", "WEBP", {"quality": 70}))

    file = models.ImageField(
        upload_to="assets/%Y/%m/",
        width_field="width",
        height_field="height",
        validators=[validate_image_size, validate_image],
        help_text=f"JPEG, PNG o WebP, hasta 40 megapíxeles y {MAX_IMAGE_MB} MB.",
    )
    alt_text = models.CharField(
        max_length=255,
        help_text="Texto alternativo. Obligatorio por accesibilidad y SEO.",
    )
    caption = models.TextField(blank=True)
    credit = models.CharField(max_length=255, blank=True)
    # Derivados: los rellena Django desde el archivo. Fuente única, no editables a mano.
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    # Cuándo se comprobó que el original no lleva metadatos, o se reescribió sin ellos. Vacío: aún
    # no se comprobó (el comando de derivados lo hace con las imágenes anteriores).
    metadata_stripped_at = models.DateTimeField(null=True, blank=True, editable=False)
    # El color del borde de la imagen, en «#rrggbb», con el que el estante pinta el lomo de una
    # publicación. Lo mide el servicio de imágenes; vacío si aún no se midió o no se puede leer.
    border_color = models.CharField(max_length=7, blank=True, editable=False)
    # Las copias que generó el servicio de imágenes, por clase («srcset», o la extensión de las de
    # portada) y ancho: {"srcset": {"480": "assets/…/foto__480w.jpg"}, "avif": {…}}. De aquí salen
    # el `srcset`, sin preguntar al almacenamiento en cada página, y lo que se borra con la imagen.
    derivatives = models.JSONField(default=dict, blank=True, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "recurso"
        verbose_name_plural = "recursos"

    def __str__(self):
        return self.alt_text or self.file.name

    # ── Imágenes responsivas (srcset) ─────────────────────────
    def save(self, *args, **kwargs):
        file_changed = self._file_changed(kwargs.get("update_fields"))
        if file_changed:
            self.border_color = ""
            self.derivatives = {}
        # En una transacción: si la limpieza de una imagen recién subida falla, la fila tampoco
        # queda, aunque quien guarda no haya abierto una.
        with transaction.atomic():
            super().save(*args, **kwargs)
            if file_changed:
                # En la misma petición: una imagen que no se puede limpiar se rechaza, y ninguna
                # se sirve con su ubicación mientras espera su turno en la cola.
                self.strip_metadata(force=True)
        if file_changed:
            from .tasks import process_image

            # Las copias y el color, fuera de la petición y con el archivo ya confirmado. Guardar
            # sin cambiar el archivo no abre la imagen.
            process_image.delay_on_commit(self.pk)

    def _file_changed(self, update_fields):
        """Si este guardado escribe un archivo distinto del que guarda la base."""
        if not self.file or (update_fields is not None and "file" not in update_fields):
            return False
        if not self.file._committed or self._state.adding or not self.pk:
            return True
        stored = type(self).objects.filter(pk=self.pk).values_list("file", flat=True).first()
        return stored != self.file.name

    def _derivative_name(self, width):
        p = PurePosixPath(self.file.name)
        return str(p.with_name(f"{p.stem}__{width}w{p.suffix}"))

    def derivative_names(self):
        """Los nombres de las copias registradas. Lo consume apps.media.filecleanup: al borrar o
        reemplazar la imagen se borran estas, también las de un ancho que ya no se usa."""
        return [name for copies in (self.derivatives or {}).values() for name in copies.values()]

    def registered_copies(self, kind):
        """Las copias registradas de una clase, como (ancho, nombre), de la más angosta a la más
        ancha."""
        copies = (self.derivatives or {}).get(kind, {})
        return sorted((int(width), name) for width, name in copies.items())

    # ── La obra de la portada (D18) ───────────────────────────
    def _portada_name(self, width, ext):
        # Con la extensión del original en el nombre: «obra.jpg» y «obra.png» de la misma
        # carpeta no comparten copias (ni las borra una al borrar la otra).
        p = PurePosixPath(self.file.name)
        return str(p.with_name(f"{p.stem}__portada-{p.suffix.lstrip('.')}-{width}w.{ext}"))

    def _anchos_portada(self, ancho):
        anchos = [w for w in self.PORTADA_WIDTHS if w < ancho]
        if ancho <= self.PORTADA_WIDTHS[-1]:
            anchos.append(ancho)
        return anchos

    def portada_widths(self):
        """Los anchos de las copias de portada: los menores que el original y, si el original
        no pasa del mayor, una copia a su propio ancho. Así la portada nunca sirve el
        archivo subido, que puede pesar varios megas."""
        return self._anchos_portada(self.width) if self.width else []

    def portada_srcset(self, ext):
        """`srcset` de las copias de portada registradas en un formato."""
        if not self.file or not self.file.name:
            return ""
        url = self.file.storage.url
        return ", ".join(f"{url(name)} {w}w" for w, name in self.registered_copies(ext))

    def strip_metadata(self, force=False):
        """Reescribe el original sin metadatos (EXIF, XMP, IPTC). Las copias salen limpias
        porque Pillow no copia los metadatos al guardarlas, pero el original, que se sirve a
        tamaño completo, publicaría la ubicación, la fecha y la cámara de la foto.

        Al subir una imagen (`force`) se reescribe siempre; después, solo si trae metadatos,
        para no recomprimirla en cada guardado. Aplica antes `exif_transpose`, para que la
        orientación quede en los píxeles y la imagen no se vea girada al perder la etiqueta.

        Falla cerrado: si una imagen recién subida no se puede reescribir, se borra su archivo
        y se lanza ImageCleanupError, que deshace el guardado. Con una imagen ya publicada,
        registra el fallo y devuelve False. Devuelve True si el original queda limpio.
        """
        if not self.file:
            return True
        try:
            with self.file.open("rb") as fh:
                img = Image.open(fh)
                fmt = (img.format or "").upper()
                # Los metadatos están en la cabecera: se miran sin decodificar la imagen (un PNG
                # sí la decodifica, porque los suyos pueden ir después de los píxeles).
                metadatos = bool(img.getexif()) or bool(METADATA_KEYS & img.info.keys())
                if not force and not metadatos:
                    self._mark_stripped()
                    return True
                if fmt not in REWRITE_FORMATS:
                    raise ImageCleanupError(f"formato {fmt or 'desconocido'}")
                icc = img.info.get("icc_profile")
                img.load()
                limpia = ImageOps.exif_transpose(img)
        except Exception as exc:
            if force:
                logger.exception(
                    "La imagen recién subida %s (recurso %s) no se pudo limpiar: no se publica",
                    self.file.name,
                    self.pk,
                )
                self.file.storage.delete(self.file.name)
                raise ImageCleanupError(self.file.name) from exc
            if not isinstance(exc, (*IMAGE_ERRORS, ImageCleanupError)):
                raise
            logger.warning(
                "La imagen %s (recurso %s) no se pudo limpiar: %s", self.file.name, self.pk, exc
            )
            return False

        fmt_out, kwargs = REWRITE_FORMATS[fmt]
        if fmt_out == "JPEG" and limpia.mode not in ("RGB", "L"):
            limpia = limpia.convert("RGB")
        if icc:
            kwargs = {**kwargs, "icc_profile": icc}  # el perfil de color no delata nada

        buf = BytesIO()
        limpia.save(buf, format=fmt_out, **kwargs)  # sin exif= ni xmp=: los metadatos se pierden
        self._replace_original(buf.getvalue())
        self.width, self.height = limpia.width, limpia.height
        type(self).objects.filter(pk=self.pk).update(width=limpia.width, height=limpia.height)
        self._mark_stripped()
        return True

    def _mark_stripped(self):
        self.metadata_stripped_at = timezone.now()
        type(self).objects.filter(pk=self.pk).update(metadata_stripped_at=self.metadata_stripped_at)

    def _replace_original(self, content):
        """Pone `content` en lugar del original, con el mismo nombre (la columna no cambia).

        La copia se escribe al lado, con otro nombre, y ocupa el lugar del original con
        `os.replace`, que es atómico: si la escritura falla (un disco lleno), el original sigue
        entero en el disco.
        """
        storage, name = self.file.storage, self.file.name
        p = PurePosixPath(name)
        copy = storage.save(str(p.with_name(f"{p.stem}__limpia{p.suffix}")), ContentFile(content))
        try:
            os.replace(storage.path(copy), storage.path(name))
        except BaseException:
            storage.delete(copy)
            raise

    def srcset(self):
        """Cadena `srcset` con las copias registradas y el original, sin consultar el
        almacenamiento: el registro solo lista las que el servicio escribió o encontró. Devuelve
        "" si no hay ninguna copia (el partial usa solo `src` + `width/height`)."""
        if not self.file or not self.width:
            return ""
        copies = self.registered_copies("srcset")
        if not copies:
            return ""
        url = self.file.storage.url
        return ", ".join(
            [f"{url(name)} {w}w" for w, name in copies] + [f"{self.file.url} {self.width}w"]
        )


# Los registros que caben en la tirada de la portada. Las buenas prácticas de carruseles
# piden de 2 a 5, para llegar al último en pocos pasos; el panel no deja destacar más.
TIRADA_SIZE = 5


def recording_upload_to(instance, filename):
    return random_upload_path("recordings", filename)


class Recording(models.Model):
    """Registro de audio o video de una lectura/recital.

    La fuente es un archivo subido (`file`) **o** un enlace de YouTube o Vimeo
    (`embed_url`); se exige al menos uno. Si es de audio, alimenta el feed de podcast
    (`feed/registros/`).

    Destacado: los registros publicados con `featured` forman la tirada de la portada, en
    el orden de `position` y como mucho TIRADA_SIZE (`clean()` no deja marcar más). Sin
    ninguno marcado, hace de respaldo `SiteProfile.featured_recording`; sin registros,
    la portada enseña `SiteProfile.featured_poem`.
    """

    class Kind(models.TextChoices):
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"

    # Los nombres van en castellano: son los rótulos del panel (2026-10-22, D21).
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="dirección",
        help_text="Lo que va tras /registro/ en la dirección pública. Al publicar el registro "
        "queda fija, porque los enlaces que ya circulan no se pueden cambiar.",
    )
    title = models.CharField(max_length=255, verbose_name="título")
    kind = models.CharField(
        max_length=10, choices=Kind.choices, default=Kind.VIDEO, verbose_name="tipo"
    )
    file = models.FileField(
        upload_to=recording_upload_to,
        blank=True,
        validators=[validate_audio_extension, validate_audio_size],
        verbose_name="archivo",
        help_text=(
            f"Audio de hasta {MAX_AUDIO_MB} MB. Un vídeo se publica con su enlace de YouTube o "
            "Vimeo, en «Enlace para incrustar»."
        ),
    )
    embed_url = models.URLField(
        blank=True,
        verbose_name="enlace para incrustar",
        help_text="Un enlace de YouTube o Vimeo (alternativa al archivo).",
    )
    poster = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="póster",
        help_text=(
            "Un fotograma de la lectura, sin texto encima: en la portada el título va aparte, "
            "en grande. Sin póster, la portada usa la primera foto del evento."
        ),
    )
    description = models.TextField(blank=True, verbose_name="descripción")
    recorded_on = models.DateField(null=True, blank=True, verbose_name="grabado el")
    duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="duración (minutos)",
        help_text="Cuántos minutos dura. Sale en el sello del registro en la portada («Video · 42 min»).",
    )
    event = models.ForeignKey(
        "agenda.Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recordings",
        verbose_name="evento",
        help_text="Evento del que proviene el registro (opcional).",
    )
    participants = models.ManyToManyField(
        "people.Contributor", blank=True, related_name="recordings", verbose_name="participantes"
    )
    featured = models.BooleanField(
        default=False,
        verbose_name="destacado",
        help_text="Sale en la tirada de la portada (hasta cinco), en el orden de «Posición».",
    )
    published = models.BooleanField(default=False, verbose_name="publicado")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="publicado el")
    position = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="posición",
        help_text="Orden en la tirada de la portada y en el índice: primero el número más bajo.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creado el")

    objects = publishing.PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["position", "-recorded_on", "-created_at"]
        verbose_name = "registro"
        verbose_name_plural = "registros"
        constraints = [
            # Debe existir una fuente: archivo O embed. Lo que clean() valida en el
            # form, garantizado también en BD ante create()/update directos.
            models.CheckConstraint(
                name="recording_file_or_embed",
                condition=~(models.Q(file="") & models.Q(embed_url="")),
            )
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Lo publicado lleva fecha: la del momento en que se publica, si no se dio otra. La
        # leen el pódcast y «Actualizado el…».
        if self.published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("media:recording_detail", args=[self.slug])

    def file_url(self):
        """La dirección de el audio: la vista que lo entrega solo si el registro es público."""
        from django.urls import reverse

        if not self.file:
            return ""
        return reverse("media:recording_file", args=[self.slug, file_name(self.file)])

    def social_image(self):
        """La imagen para compartir el registro: su póster (ver `{% social_meta %}`)."""
        return self.poster

    @property
    def public_event(self):
        """El evento del registro, solo si está publicado: un registro publicado no puede enseñar
        la sala, la ciudad, la fecha ni las fotos de un evento oculto (cancelado o privado)."""
        event = self.event
        return event if event is not None and event.published else None

    @property
    def duracion(self):
        """La duración como se lee en el sello: «42 min» o «1 h 05 min». Vacía si no se sabe."""
        if not self.duration_minutes:
            return ""
        horas, minutos = divmod(self.duration_minutes, 60)
        return f"{horas} h {minutos:02d} min" if horas else f"{minutos} min"

    def clean(self):
        if not self.file and not self.embed_url:
            raise ValidationError("Indica un archivo o una URL de embed para el registro.")
        if self.featured:
            otros = Recording.objects.filter(featured=True).exclude(pk=self.pk).count()
            if otros >= TIRADA_SIZE:
                raise ValidationError(
                    f"La tirada de la portada ya tiene sus {TIRADA_SIZE} registros destacados: "
                    "quita uno antes de destacar este."
                )
