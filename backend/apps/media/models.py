from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MediaAsset(models.Model):
    """Biblioteca de imágenes. width/height son derivados del archivo (no editables)."""

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

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("media:recording_detail", args=[self.slug])

    def clean(self):
        if not self.file and not self.embed_url:
            raise ValidationError("Indica un archivo o una URL de embed para el registro.")
