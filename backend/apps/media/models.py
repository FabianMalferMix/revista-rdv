from io import BytesIO
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from PIL import Image


class MediaAsset(models.Model):
    """Biblioteca de imágenes. width/height son derivados del archivo (no editables)."""

    # Anchos de los derivados para `srcset` (solo se generan los menores al original).
    SRCSET_WIDTHS = (480, 960, 1440)

    file = models.ImageField(
        upload_to="assets/%Y/%m/",
        width_field="width",
        height_field="height",
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
        super().save(*args, **kwargs)
        self.ensure_derivatives()

    def _derivative_name(self, width):
        p = PurePosixPath(self.file.name)
        return str(p.with_name(f"{p.stem}__{width}w{p.suffix}"))

    def ensure_derivatives(self):
        """Repara width/height ausentes y genera (si faltan) las copias reducidas para
        `srcset`. Nunca sube de tamaño. Tolerante a fallos: un archivo ilegible o un
        formato no rasterizable no rompe el guardado (sin derivados, `srcset` cae al
        original y `width/height` quedan como estén)."""
        if not self.file:
            return
        # ¿Hace falta abrir el archivo? Solo si faltan dimensiones o algún derivado.
        need_open = not self.width or not self.height
        if self.width and not need_open:
            targets = [w for w in self.SRCSET_WIDTHS if w < self.width]
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
        if self.width != img.width or self.height != img.height:
            self.width, self.height = img.width, img.height
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

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.VIDEO)
    file = models.FileField(upload_to="recordings/%Y/%m/", blank=True)
    embed_url = models.URLField(
        blank=True, help_text="URL de YouTube/Vimeo/SoundCloud/Bandcamp (alternativa al archivo)."
    )
    poster = models.ForeignKey(
        MediaAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    description = models.TextField(blank=True)
    recorded_on = models.DateField(null=True, blank=True)
    event = models.ForeignKey(
        "agenda.Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recordings",
        help_text="Evento del que proviene el registro (opcional).",
    )
    participants = models.ManyToManyField(
        "people.Contributor", blank=True, related_name="recordings"
    )
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

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

    def clean(self):
        if not self.file and not self.embed_url:
            raise ValidationError("Indica un archivo o una URL de embed para el registro.")
