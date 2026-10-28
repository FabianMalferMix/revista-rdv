import logging
from io import BytesIO
from pathlib import PurePosixPath

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from PIL import Image, ImageOps

from .validators import validate_audio_video_extension, validate_image

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


class ImageCleanupError(Exception):
    """No se pudo reescribir sin metadatos una imagen recién subida: no se publica."""


class MediaAsset(models.Model):
    """Biblioteca de imágenes. width/height son derivados del archivo (no editables)."""

    # Anchos de los derivados para `srcset` (solo se generan los menores al original).
    SRCSET_WIDTHS = (480, 960, 1440)
    # La obra de la portada va a sangre (D18): pide copias más anchas y en formatos
    # modernos. Se hacen solo para la imagen elegida como portada (ver
    # apps.showcase.apps), no para cada imagen que se sube. Las calidades dejan la lámina
    # del estreno bajo 300 KB en escritorio y 150 KB en el teléfono.
    PORTADA_WIDTHS = (640, 960, 1080, 1440, 1920, 2560)
    PORTADA_FORMATS = (("avif", "AVIF", {"quality": 50}), ("webp", "WEBP", {"quality": 70}))

    file = models.ImageField(
        upload_to="assets/%Y/%m/",
        width_field="width",
        height_field="height",
        validators=[validate_image],
        help_text="JPEG, PNG o WebP, hasta 40 megapíxeles.",
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
        # Una imagen recién subida todavía no está en el almacenamiento.
        recien_subida = bool(self.file) and not self.file._committed
        # En una transacción: si la limpieza de una imagen recién subida falla, la fila tampoco
        # queda, aunque quien guarda no haya abierto una.
        with transaction.atomic():
            super().save(*args, **kwargs)
            # El orden importa: limpiar el original ANTES de derivar, para que las copias
            # se generen a partir de la imagen ya despojada y con la orientación aplicada.
            self.strip_metadata(force=recien_subida)
        self.ensure_derivatives()

    def _derivative_name(self, width):
        p = PurePosixPath(self.file.name)
        return str(p.with_name(f"{p.stem}__{width}w{p.suffix}"))

    def derivative_names(self):
        """Nombres de las copias reducidas. Lo consume apps.media.filecleanup para que
        al borrar el recurso no queden derivados huérfanos en el almacenamiento."""
        if not self.file or not self.file.name:
            return []
        # Las de portada, en todos los anchos posibles: borrar una que no existe no falla.
        anchos_portada = {*self.PORTADA_WIDTHS, *([self.width] if self.width else [])}
        return [self._derivative_name(w) for w in self.SRCSET_WIDTHS] + [
            self._portada_name(w, ext)
            for w in sorted(anchos_portada)
            for ext, _, _ in self.PORTADA_FORMATS
        ]

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

    def ensure_portada_derivatives(self):
        """Genera, si faltan, las copias de portada en AVIF y WebP. Idempotente y tolerante a
        fallos, como `ensure_derivatives`: sin ellas, la portada cae al `srcset` de siempre."""
        if not self.file or not self.file.name:
            return
        existe = self.file.storage.exists
        if self.width and all(
            existe(self._portada_name(w, ext))
            for w in self.portada_widths()
            for ext, _, _ in self.PORTADA_FORMATS
        ):
            return
        try:
            with self.file.open("rb") as fh:
                img = Image.open(fh)
                img.load()
        except Exception:
            return
        # Derecha y con su ancho real. Una foto de cámara puede venir girada por su etiqueta
        # EXIF, y estas copias pueden hacerse antes de que strip_metadata la enderece y
        # corrija `width` (la señal post_save de apps.showcase llega dentro del save()): los
        # anchos salen de la imagen enderezada, no de la columna.
        img = ImageOps.exif_transpose(img)
        # La transparencia se conserva (AVIF y WebP la admiten): pasada a RGB sin más, lo
        # transparente salía negro y el logo en tinta desaparecía encima.
        transparente = img.mode in ("RGBA", "LA", "PA") or (
            img.mode == "P" and "transparency" in img.info
        )
        img = img.convert("RGBA" if transparente else "RGB")
        for w in self._anchos_portada(img.width):
            for ext, fmt, opciones in self.PORTADA_FORMATS:
                nombre = self._portada_name(w, ext)
                if existe(nombre):
                    continue
                copia = img
                if w != img.width:
                    copia = img.resize(
                        (w, max(1, round(img.height * w / img.width))), Image.Resampling.LANCZOS
                    )
                buf = BytesIO()
                try:
                    copia.save(buf, format=fmt, **opciones)
                except Exception:  # noqa: BLE001 - un Pillow sin AVIF deja al menos el WebP
                    continue
                self.file.storage.save(nombre, ContentFile(buf.getvalue()))

    def portada_srcset(self, ext):
        """`srcset` de las copias de portada en un formato: solo las que existen."""
        if not self.file or not self.file.name:
            return ""
        return ", ".join(
            f"{self.file.storage.url(self._portada_name(w, ext))} {w}w"
            for w in self.portada_widths()
            if self.file.storage.exists(self._portada_name(w, ext))
        )

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
                img.load()
                fmt = (img.format or "").upper()
                metadatos = bool(img.getexif()) or bool(METADATA_KEYS & img.info.keys())
                if not force and not metadatos:
                    return True
                if fmt not in REWRITE_FORMATS:
                    raise ImageCleanupError(f"formato {fmt or 'desconocido'}")
                icc = img.info.get("icc_profile")
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
        name = self.file.name
        # Sobrescribe conservando el nombre (el valor de la columna no cambia).
        self.file.storage.delete(name)
        self.file.storage.save(name, ContentFile(buf.getvalue()))
        self.width, self.height = limpia.width, limpia.height
        type(self).objects.filter(pk=self.pk).update(width=limpia.width, height=limpia.height)
        return True

    def ensure_derivatives(self):
        """Repara width/height ausentes y genera (si faltan) las copias reducidas para
        `srcset`. Nunca sube de tamaño. Tolerante a fallos: un archivo ilegible o un
        formato no rasterizable no rompe el guardado (sin derivados, `srcset` cae al
        original y `width/height` quedan como estén)."""
        if not self.file:
            return
        # Lo que hay REALMENTE en la columna, no lo que muestra la instancia. `ImageField`
        # conecta `update_dimension_fields` a la señal `post_init`, que al cargar una fila
        # con la columna a NULL abre el archivo y rellena `self.width`/`self.height` en
        # memoria (sin escribir). Mirar el atributo, como se hacía antes, dejaba esta
        # función convencida de que las dimensiones ya estaban guardadas: la reparación
        # resultaba inalcanzable justo en el caso para el que se escribió, y la fila se
        # quedaba en NULL para siempre pagando una apertura de archivo por instanciación.
        # `values_list` no instancia el modelo, así que no dispara `post_init`.
        guardadas = (
            type(self).objects.filter(pk=self.pk).values_list("width", "height").first()
            if self.pk
            else None
        )
        ancho_guardado, alto_guardado = guardadas or (None, None)

        # ¿Hace falta abrir el archivo? Solo si faltan dimensiones o algún derivado.
        need_open = not ancho_guardado or not alto_guardado
        if not need_open:
            targets = [w for w in self.SRCSET_WIDTHS if w < ancho_guardado]
            need_open = any(not self.file.storage.exists(self._derivative_name(w)) for w in targets)
        if not need_open:
            return
        try:
            with self.file.open("rb") as fh:
                img = Image.open(fh)
                img.load()
        except Exception:
            return
        # Repara dimensiones (fuente única: el archivo real).
        if (ancho_guardado, alto_guardado) != (img.width, img.height):
            self.width, self.height = img.width, img.height
            if self.pk:
                type(self).objects.filter(pk=self.pk).update(width=img.width, height=img.height)

        fmt = (img.format or "JPEG").upper()
        if fmt in ("JPEG", "JPG", "MPO"):
            fmt_out, save_kwargs = "JPEG", {"quality": 82, "optimize": True, "progressive": True}
        elif fmt == "PNG":
            fmt_out, save_kwargs = "PNG", {"optimize": True}
        elif fmt == "WEBP":
            fmt_out, save_kwargs = "WEBP", {"quality": 82}
        else:
            return  # formato sin soporte de derivados
        for w in (w for w in self.SRCSET_WIDTHS if w < img.width):
            name = self._derivative_name(w)
            if self.file.storage.exists(name):
                continue
            resized = img.resize(
                (w, max(1, round(img.height * w / img.width))), Image.Resampling.LANCZOS
            )
            if fmt_out == "JPEG" and resized.mode not in ("RGB", "L"):
                resized = resized.convert("RGB")
            buf = BytesIO()
            resized.save(buf, format=fmt_out, **save_kwargs)
            self.file.storage.save(name, ContentFile(buf.getvalue()))

    def color_de_borde(self):
        """El color del borde de la imagen, en «#rrggbb»: la mediana del anillo exterior (un 4 %
        de cada lado). Con él el estante de la portada pinta el lomo y el canto de cada
        publicación (D28), para que el libro sea el mismo de lomo y de frente. Se mide una vez
        por archivo y queda en la caché; "" si la imagen no se puede leer, y ese fallo solo se
        recuerda unos minutos: una lectura que falló una vez no queda fijada para siempre."""
        if not self.file or not self.file.name:
            return ""
        clave = f"color-de-borde:{self.file.name}"
        color = cache.get(clave)
        if color is None:
            color = self._medir_color_de_borde()
            cache.set(clave, color, None if color else 300)
        return color

    def _medir_color_de_borde(self):
        try:
            with self.file.open("rb") as fh:
                img = Image.open(fh)
                img.draft("RGB", (120, 168))  # un JPEG se decodifica ya reducido
                img = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return ""
        img = img.resize((60, 84))
        ancho, alto = img.size
        borde = max(1, round(min(ancho, alto) * 0.04))
        anillo = [
            img.getpixel((x, y))
            for x in range(ancho)
            for y in range(alto)
            if x < borde or y < borde or x >= ancho - borde or y >= alto - borde
        ]
        mediana = [sorted(p[c] for p in anillo)[len(anillo) // 2] for c in range(3)]
        return "#{:02x}{:02x}{:02x}".format(*mediana)

    def srcset(self):
        """Cadena `srcset` con los derivados existentes + el original. Robusta: solo
        lista archivos presentes (nunca apunta a derivados que falten) y devuelve ""
        si no hay ningún derivado (el partial usa solo `src` + `width/height`)."""
        if not self.file or not self.width:
            return ""
        derivatives = []
        for w in self.SRCSET_WIDTHS:
            if w >= self.width:
                continue
            name = self._derivative_name(w)
            if self.file.storage.exists(name):
                derivatives.append(f"{self.file.storage.url(name)} {w}w")
        if not derivatives:
            return ""
        derivatives.append(f"{self.file.url} {self.width}w")
        return ", ".join(derivatives)


class Recording(models.Model):
    """Registro de audio o video de una lectura/recital.

    La fuente es un archivo subido (`file`) **o** un embed externo (`embed_url`,
    YouTube/Vimeo/SoundCloud/Bandcamp); se exige al menos uno. Alimenta la portada
    (destacado) y, más adelante, el feed podcast de audio.
    """

    class Kind(models.TextChoices):
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"

    # Los nombres van en castellano: son los rótulos del panel (2026-10-22, D21).
    slug = models.SlugField(max_length=255, unique=True, verbose_name="dirección")
    title = models.CharField(max_length=255, verbose_name="título")
    kind = models.CharField(
        max_length=10, choices=Kind.choices, default=Kind.VIDEO, verbose_name="tipo"
    )
    file = models.FileField(
        upload_to="recordings/%Y/%m/",
        blank=True,
        validators=[validate_audio_video_extension],
        verbose_name="archivo",
    )
    embed_url = models.URLField(
        blank=True,
        verbose_name="enlace para incrustar",
        help_text="URL de YouTube/Vimeo/SoundCloud/Bandcamp (alternativa al archivo).",
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

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("media:recording_detail", args=[self.slug])

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
