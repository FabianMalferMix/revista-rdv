from django.db import models

from apps.media.validators import validate_pdf_extension


class SiteProfile(models.Model):
    """Identidad del colectivo (fila única). Alimenta cabecera, pie y dossier.

    Se obtiene con `SiteProfile.load()`; `save()` fuerza pk=1 y el borrado se ignora,
    de modo que exista a lo más una fila (patrón singleton, sin dependencias extra).
    """

    name = models.CharField(max_length=255, default="Colectivo")
    tagline = models.CharField(max_length=255, blank=True, help_text="Poética corta / lema.")
    manifesto = models.TextField(blank=True, help_text="Manifiesto o poética del colectivo.")
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, help_text="Ciudad / comuna.")
    general_email = models.EmailField(blank=True)
    booking_email = models.EmailField(
        blank=True, help_text="Contacto de gestión / contrataciones (prensa, programación)."
    )
    phone = models.CharField(max_length=50, blank=True)
    featured_recording = models.ForeignKey(
        "media.Recording", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    featured_poem = models.ForeignKey(
        "content.Poem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Poema destacado en la portada.",
    )
    dossier_pdf = models.FileField(
        upload_to="dossier/",
        blank=True,
        validators=[validate_pdf_extension],
        help_text="PDF del kit de prensa (override manual opcional del dossier generado).",
    )
    og_image = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Imagen social por defecto (og:image) y logo en los datos estructurados.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil del sitio"
        verbose_name_plural = "perfil del sitio"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # el singleton no se borra

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SiteSocialLink(models.Model):
    """Red social del colectivo (Instagram, YouTube, Bandcamp…)."""

    profile = models.ForeignKey(SiteProfile, on_delete=models.CASCADE, related_name="social_links")
    platform = models.CharField(max_length=50)
    url = models.URLField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "platform"]

    def __str__(self):
        return self.platform


class Publication(models.Model):
    """Publicación del catálogo vitrina (libro, plaquette, fanzine…). Sin pagos:
    la compra se deriva a enlaces externos (WhereToBuy) o a un PDF de descarga."""

    class Kind(models.TextChoices):
        LIBRO = "libro", "Libro"
        PLAQUETTE = "plaquette", "Plaquette"
        FANZINE = "fanzine", "Fanzine"
        ANTOLOGIA = "antologia", "Antología"
        REVISTA = "revista", "Revista"
        DISCO = "disco", "Disco"

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PLAQUETTE)
    publisher = models.ForeignKey(
        "reviews.Publisher", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    cover = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    synopsis = models.TextField(blank=True)
    participants = models.ManyToManyField(
        "people.Contributor", blank=True, related_name="publications"
    )
    is_own = models.BooleanField(
        default=True, help_text="Editada por el colectivo (vs participación en obra ajena)."
    )
    pdf = models.FileField(
        upload_to="publications/",
        blank=True,
        validators=[validate_pdf_extension],
        help_text="PDF de descarga gratuita (plaquettes/fanzines digitales).",
    )
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "-year", "title"]
        verbose_name = "publicación"
        verbose_name_plural = "publicaciones"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("showcase:publication_detail", args=[self.slug])


class WhereToBuy(models.Model):
    """Dónde conseguir una publicación: solo enlaces externos (editorial, feria, librería)."""

    publication = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name="where_to_buy"
    )
    label = models.CharField(max_length=120, help_text="Editorial / feria / librería.")
    url = models.URLField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "label"]
        verbose_name = "punto de venta"
        verbose_name_plural = "puntos de venta"

    def __str__(self):
        return f"{self.publication} · {self.label}"


class PressMention(models.Model):
    """Mención en prensa: entrevistas, reseñas de terceros, notas (legitimidad externa)."""

    class Kind(models.TextChoices):
        ENTREVISTA = "entrevista", "Entrevista"
        RESENA = "resena", "Reseña"
        NOTA = "nota", "Nota"
        PERFIL = "perfil", "Perfil"
        MENCION = "mencion", "Mención"

    title = models.CharField(max_length=255)
    outlet = models.CharField(max_length=255, help_text="Medio (diario, revista, radio…).")
    author = models.CharField(max_length=255, blank=True, help_text="Periodista (opcional).")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTA)
    published_on = models.DateField(null=True, blank=True)
    url = models.URLField(blank=True)
    quote = models.TextField(blank=True, help_text="Cita destacada para portada y dossier.")
    logo = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "-published_on"]
        verbose_name = "mención en prensa"
        verbose_name_plural = "menciones en prensa"

    def __str__(self):
        return f"{self.outlet} — {self.title}"


class Partner(models.Model):
    """Aliado del colectivo: fondos, instituciones, editoriales, espacios."""

    class Kind(models.TextChoices):
        FINANCIAMIENTO = "financiamiento", "Financiamiento"
        INSTITUCION = "institucion", "Institución"
        EDITORIAL = "editorial", "Editorial"
        MEDIO = "medio", "Medio"
        ESPACIO = "espacio", "Espacio"
        OTRO = "otro", "Otro"

    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTRO)
    logo = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "aliado"
        verbose_name_plural = "aliados"

    def __str__(self):
        return self.name
