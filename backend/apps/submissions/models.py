from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


def private_storage():
    """Almacenamiento fuera de MEDIA_ROOT: los adjuntos no se sirven públicamente."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Call(models.Model):
    """Convocatoria. `is_open` es derivado (se calcula, no se almacena)."""

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()

    class Meta:
        ordering = ["-opens_at"]
        verbose_name = "convocatoria"
        verbose_name_plural = "convocatorias"

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.opens_at <= timezone.now() <= self.closes_at


class Submission(models.Model):
    """Envío externo (portal de colaboraciones)."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Recibido"
        IN_REVIEW = "in_review", "En revisión"
        ACCEPTED = "accepted", "Aceptado"
        REJECTED = "rejected", "Rechazado"
        WITHDRAWN = "withdrawn", "Retirado"

    author_name = models.CharField(max_length=255)
    author_email = models.EmailField()
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    body = models.TextField()
    file = models.FileField(
        upload_to="submissions/%Y/%m/", blank=True, storage=private_storage
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions_reviewed",
    )
    notes = models.TextField(blank=True)
    call = models.ForeignKey(
        Call,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "envío"
        verbose_name_plural = "envíos"

    def __str__(self):
        return f"{self.title} — {self.author_name}"
