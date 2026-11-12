from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


class PrivateFileSystemStorage(FileSystemStorage):
    """Archivos sin URL pública: se descargan solo por una vista que comprueba permisos.

    FileSystemStorage, sin `base_url`, toma MEDIA_URL y devolvería `/media/…`, una
    dirección que una plantilla podría enlazar.
    """

    def url(self, name):
        raise ValueError(
            "Los archivos privados no tienen URL pública: se descargan por su vista protegida."
        )


def private_storage():
    """Almacenamiento fuera de MEDIA_ROOT: los adjuntos no se sirven públicamente."""
    return PrivateFileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class CallQuerySet(models.QuerySet):
    def open_now(self):
        """Convocatorias abiertas en este momento (formulario de envío, sello de la portada)."""
        now = timezone.now()
        return self.filter(opens_at__lte=now, closes_at__gte=now)


class Call(models.Model):
    """Convocatoria. `is_open` es derivado (se calcula, no se almacena)."""

    slug = models.SlugField(max_length=255, unique=True, verbose_name="dirección")
    title = models.CharField(max_length=255, verbose_name="título")
    description = models.TextField(blank=True, verbose_name="descripción")
    opens_at = models.DateTimeField(verbose_name="abre el")
    closes_at = models.DateTimeField(verbose_name="cierra el")

    objects = CallQuerySet.as_manager()

    class Meta:
        ordering = ["-opens_at"]
        verbose_name = "convocatoria"
        verbose_name_plural = "convocatorias"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(closes_at__gt=models.F("opens_at")),
                name="call_closes_after_it_opens",
                violation_error_message="Una convocatoria tiene que cerrar después de abrir.",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.opens_at <= timezone.now() <= self.closes_at


class SubmissionType(models.TextChoices):
    """Los tipos de propuesta que ofrece el formulario, en su orden. Las claves van sin tilde: no
    son texto visible."""

    RESENA = "resena", "Reseña"
    ENSAYO = "ensayo", "Ensayo"
    ENTREVISTA = "entrevista", "Entrevista"
    POESIA = "poesia", "Poesía"
    NARRATIVA = "narrativa", "Narrativa"
    CRONICA = "cronica", "Crónica"
    OTRO = "otro", "Otro"


class Submission(models.Model):
    """Envío externo (portal de colaboraciones)."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Recibido"
        IN_REVIEW = "in_review", "En revisión"
        ACCEPTED = "accepted", "Aceptado"
        REJECTED = "rejected", "Rechazado"
        WITHDRAWN = "withdrawn", "Retirado"

    # Fuera de la clase, porque la restricción de Meta también la nombra.
    Type = SubmissionType

    author_name = models.CharField(max_length=255, verbose_name="remitente")
    author_email = models.EmailField(verbose_name="correo de contacto")
    type = models.CharField(max_length=50, choices=Type.choices, verbose_name="tipo de propuesta")
    title = models.CharField(max_length=255, verbose_name="título")
    body = models.TextField(verbose_name="descripción o texto")
    file = models.FileField(
        upload_to="submissions/%Y/%m/",
        blank=True,
        storage=private_storage,
        verbose_name="adjunto",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
        db_index=True,
        verbose_name="estado",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions_reviewed",
        verbose_name="revisado por",
    )
    notes = models.TextField(blank=True, verbose_name="notas internas")
    call = models.ForeignKey(
        Call,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submissions",
        verbose_name="convocatoria",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="recibido el")
    # Cuándo se rechazó o se retiró: la purga cuenta desde aquí, como promete la política de
    # privacidad («pasado un tiempo desde su resolución»), y no desde que llegó.
    resolved_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="resuelto el"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "envío"
        verbose_name_plural = "envíos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(type__in=SubmissionType.values),
                name="submission_type_is_offered",
                violation_error_message="Ese tipo de propuesta no está entre los que se ofrecen.",
            )
        ]

    def __str__(self):
        return f"{self.title} — {self.author_name}"

    RESOLVED = (Status.REJECTED, Status.WITHDRAWN)

    def save(self, *args, **kwargs):
        # La fecha de resolución sigue al estado, se cambie desde donde se cambie.
        if self.status in self.RESOLVED and self.resolved_at is None:
            self.resolved_at = timezone.now()
        elif self.status not in self.RESOLVED:
            self.resolved_at = None
        super().save(*args, **kwargs)
