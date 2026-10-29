from django.db import models
from django.urls import reverse
from django.utils import timezone

from config import publishing


class EventQuerySet(publishing.PublishableQuerySet):
    def upcoming(self):
        """Eventos publicados futuros, del más próximo al más lejano (Agenda). Con su afiche
        en la misma consulta: la agenda y la portada lo enseñan."""
        return (
            self.published()
            .filter(starts_at__gte=timezone.now())
            .select_related("poster")
            .order_by("starts_at")
        )

    def past(self):
        """Eventos publicados ya realizados, del más reciente al más antiguo (Trayectoria).
        Con su afiche en la misma consulta: la trayectoria lo enseña en cada fila."""
        return self.published().filter(starts_at__lt=timezone.now()).select_related("poster")


class Event(models.Model):
    """Actividad del colectivo: recital, lanzamiento, taller, festival…

    Un solo modelo alimenta dos vistas públicas: los eventos futuros forman la
    **Agenda** y los pasados la **Trayectoria** (el «CV» del colectivo ante
    gestores culturales). La Galería se cuelga de los eventos vía EventPhoto.
    """

    class Type(models.TextChoices):
        RECITAL = "recital", "Recital"
        LANZAMIENTO = "lanzamiento", "Lanzamiento"
        TALLER = "taller", "Taller"
        FESTIVAL = "festival", "Festival"
        FERIA = "feria", "Feria"
        OTRO = "otro", "Otro"

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.RECITAL)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    venue_name = models.CharField(max_length=255, blank=True, help_text="Lugar (sala, café…).")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    poster = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    participants = models.ManyToManyField("people.Contributor", blank=True, related_name="events")
    is_external = models.BooleanField(
        default=False, help_text="Participación en un evento organizado por terceros."
    )
    host = models.CharField(
        max_length=255, blank=True, help_text="Organizador externo (si aplica)."
    )
    registration_url = models.URLField(blank=True, help_text="Inscripción o entradas.")
    published = models.BooleanField(default=False)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at"]
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gte=models.F("starts_at")),
                name="event_ends_after_it_starts",
                violation_error_message="Una actividad no puede terminar antes de empezar.",
            )
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("agenda:event_detail", args=[self.slug])

    def social_image(self):
        """La imagen para compartir la actividad: su afiche (ver `{% social_meta %}`)."""
        return self.poster

    @property
    def is_past(self):
        return self.starts_at < timezone.now()


class EventPhoto(models.Model):
    """Foto del álbum de un evento: la Galería pública se arma por evento."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="photos")
    asset = models.ForeignKey("media.MediaAsset", on_delete=models.CASCADE, related_name="+")
    caption = models.CharField(
        max_length=255, blank=True, help_text="Pie de foto (si difiere del recurso)."
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["event", "asset"], name="uniq_event_asset")]
        verbose_name = "foto de evento"
        verbose_name_plural = "fotos de evento"

    def __str__(self):
        return f"{self.event} · foto {self.position}"


class Milestone(models.Model):
    """Hito de la línea de tiempo que no es un evento (fundación, premio, publicación)."""

    year = models.PositiveSmallIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-year", "id"]
        verbose_name = "hito"
        verbose_name_plural = "hitos"

    def __str__(self):
        return f"{self.year} — {self.title}"
