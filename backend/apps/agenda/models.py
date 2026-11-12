from django.db import models
from django.urls import reverse
from django.utils import timezone

from config import publishing
from config.models import TimestampedModel


def url_for_event(slug):
    """La dirección de la ficha de una actividad. La usan su modelo y las filas de la búsqueda,
    que solo traen el slug."""
    return reverse("agenda:event_detail", args=[slug])


def year_anchor(year):
    """El ancla de un año en la trayectoria, `anio-2025`: el id de su bloque y el final de
    `url_for_year`."""
    return f"anio-{year}"


def url_for_year(year):
    """La dirección de un año en la trayectoria, `/trayectoria/#anio-2025`. Llevan a ella las
    salidas al pie de una actividad pasada y de una publicación."""
    return f"{reverse('agenda:trayectoria')}#{year_anchor(year)}"


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


class Event(TimestampedModel):
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

    slug = models.SlugField(max_length=255, unique=True, verbose_name="dirección")
    title = models.CharField(max_length=255, verbose_name="título")
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.RECITAL, verbose_name="tipo"
    )
    starts_at = models.DateTimeField(db_index=True, verbose_name="empieza el")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="termina el")
    venue_name = models.CharField(
        max_length=255, blank=True, verbose_name="lugar", help_text="Lugar (sala, café…)."
    )
    address = models.CharField(max_length=255, blank=True, verbose_name="dirección del lugar")
    city = models.CharField(max_length=100, blank=True, verbose_name="ciudad")
    description = models.TextField(blank=True, verbose_name="descripción")
    poster = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="afiche",
    )
    participants = models.ManyToManyField(
        "people.Contributor", blank=True, related_name="events", verbose_name="participantes"
    )
    is_external = models.BooleanField(
        default=False,
        verbose_name="organizado por terceros",
        help_text="Participación en un evento organizado por terceros.",
    )
    host = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="organizador",
        help_text="Organizador externo (si aplica).",
    )
    registration_url = models.URLField(
        blank=True, verbose_name="enlace de inscripción", help_text="Inscripción o entradas."
    )
    published = models.BooleanField(default=False, verbose_name="publicado")

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
        return url_for_event(self.slug)

    def social_image(self):
        """La imagen para compartir la actividad: su afiche (ver `{% social_meta %}`)."""
        return self.poster

    @property
    def is_past(self):
        return self.starts_at < timezone.now()


class EventPhoto(models.Model):
    """Foto del álbum de un evento: la Galería pública se arma por evento."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="photos", verbose_name="evento"
    )
    asset = models.ForeignKey(
        "media.MediaAsset", on_delete=models.PROTECT, related_name="+", verbose_name="recurso"
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="pie de foto",
        help_text="Pie de foto (si difiere del recurso).",
    )
    position = models.PositiveSmallIntegerField(default=0, verbose_name="posición")

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["event", "asset"], name="uniq_event_asset")]
        verbose_name = "foto de evento"
        verbose_name_plural = "fotos de evento"

    def __str__(self):
        return f"{self.event} · foto {self.position}"


class Milestone(models.Model):
    """Hito de la línea de tiempo que no es un evento (fundación, premio, publicación)."""

    year = models.PositiveSmallIntegerField(db_index=True, verbose_name="año")
    title = models.CharField(max_length=255, verbose_name="título")
    description = models.TextField(blank=True, verbose_name="descripción")

    class Meta:
        ordering = ["-year", "id"]
        verbose_name = "hito"
        verbose_name_plural = "hitos"

    def __str__(self):
        return f"{self.year} — {self.title}"
