from functools import cached_property
from urllib.parse import urlsplit

from django.db import models

from apps.media.validators import validate_pdf_extension
from config import publishing


class PartnerQuerySet(publishing.PublishableQuerySet):
    # Un aliado se enseña mientras la alianza sigue en pie.
    published_field = "active"


class SiteProfile(models.Model):
    """Identidad del colectivo (fila única). Alimenta cabecera, pie y dossier.

    Se obtiene con `SiteProfile.load()`; `save()` fuerza pk=1 y el borrado se ignora,
    de modo que exista a lo más una fila (patrón singleton, sin dependencias extra).
    """

    # Los nombres van en castellano: son los rótulos del panel (2026-10-22, D21).
    name = models.CharField(max_length=255, default="Colectivo", verbose_name="nombre")
    tagline = models.CharField(
        max_length=255, blank=True, verbose_name="lema", help_text="Poética corta / lema."
    )
    manifesto = models.TextField(
        blank=True, verbose_name="manifiesto", help_text="Manifiesto o poética del colectivo."
    )
    founded_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="año de fundación"
    )
    location = models.CharField(
        max_length=255, blank=True, verbose_name="ubicación", help_text="Ciudad / comuna."
    )
    general_email = models.EmailField(blank=True, verbose_name="correo general")
    booking_email = models.EmailField(
        blank=True,
        verbose_name="correo de gestión",
        help_text="Contacto de gestión / contrataciones (prensa, programación).",
    )
    phone = models.CharField(max_length=50, blank=True, verbose_name="teléfono")
    featured_recording = models.ForeignKey(
        "media.Recording",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="registro destacado (respaldo)",
        help_text="Sale en la portada solo si ningún registro está marcado como «Destacado».",
    )
    featured_poem = models.ForeignKey(
        "content.Poem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="poema destacado",
        help_text="Sale en la portada solo si no hay registros destacados.",
    )
    dossier_pdf = models.FileField(
        upload_to="dossier/",
        blank=True,
        validators=[validate_pdf_extension],
        verbose_name="dossier en PDF",
        help_text="PDF del kit de prensa (override manual opcional del dossier generado).",
    )
    og_image = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="imagen para compartir",
        help_text="Imagen social por defecto (og:image) y logo en los datos estructurados.",
    )
    # La primera vista de la portada es una obra a sangre con el logo al pie (D18). Sin
    # imagen elegida, la portada lleva la lámina del colectivo (static/img/portada/).
    hero_image = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="imagen de portada",
        help_text=(
            "La obra a sangre de la primera vista de la portada: horizontal, de 2400 px de "
            "ancho o más, con una zona clara y tranquila abajo, donde va el logo en tinta. "
            "Sin ella, la portada lleva la lámina del colectivo."
        ),
    )
    hero_image_phone = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="imagen de portada para el teléfono",
        help_text=(
            "Opcional: un recorte vertical de la misma obra, de 1080 px de ancho o más. Sin "
            "él, el teléfono recorta la horizontal por el centro."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="actualizado el")

    class Meta:
        verbose_name = "perfil del sitio"
        verbose_name_plural = "perfil del sitio"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        # Las copias de la obra de la portada (AVIF y WebP) se hacen al elegirla, no al
        # pedir la portada. Las que ya existen no se rehacen.
        for imagen in (self.hero_image, self.hero_image_phone):
            if imagen is not None:
                imagen.ensure_portada_derivatives()

    def delete(self, *args, **kwargs):
        pass  # el singleton no se borra

    @classmethod
    def load(cls, *relaciones):
        """La fila única. `relaciones` son claves de `select_related`: lo que la página va a
        leer del perfil viene en la misma consulta (la portada: el registro y el poema
        destacados, con el evento y el póster del registro)."""
        filas = cls.objects.select_related(*relaciones) if relaciones else cls.objects
        obj, _ = filas.get_or_create(pk=1)
        return obj

    @property
    def presentacion(self):
        """De dónde es y desde cuándo: «Colectivo de poesía», «Chile», «desde 2023», lo que
        haya. La usan la cejilla de la portada y el pie, que la unen con puntos medios."""
        return [
            parte
            for parte in (
                self.tagline,
                self.location,
                f"desde {self.founded_year}" if self.founded_year else "",
            )
            if parte
        ]

    @property
    def correo_de_contacto(self):
        """El correo al que se escribe desde el sitio: el de gestión y, si no hay, el
        general. Lo usan el pie y el titular de la portada, que tienen que coincidir."""
        return self.booking_email or self.general_email


class SiteSocialLink(models.Model):
    """Red social del colectivo (Instagram, YouTube, Bandcamp…)."""

    profile = models.ForeignKey(
        SiteProfile, on_delete=models.CASCADE, related_name="social_links", verbose_name="perfil"
    )
    platform = models.CharField(max_length=50, verbose_name="plataforma")
    url = models.URLField(verbose_name="dirección")
    position = models.PositiveSmallIntegerField(default=0, verbose_name="posición")

    class Meta:
        verbose_name = "red social del sitio"
        verbose_name_plural = "redes sociales del sitio"
        ordering = ["position", "platform"]

    def __str__(self):
        return self.platform

    @property
    def usuario(self):
        """El nombre de usuario a partir de la URL del perfil: «@repitentesdelverso» para
        https://www.instagram.com/repitentesdelverso/ y también para …/repitentesdelverso/reels/.
        Es el primer tramo de la ruta. Vacío si la URL no tiene ruta."""
        ruta = urlsplit(self.url).path.strip("/")
        return f"@{ruta.split('/', 1)[0]}" if ruta else ""


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

    objects = publishing.PublishableQuerySet.as_manager()

    class Meta:
        ordering = ["position", "-year", "title"]
        verbose_name = "publicación"
        verbose_name_plural = "publicaciones"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("showcase:publication_detail", args=[self.slug])

    @cached_property
    def lomo(self):
        """Los colores del libro en el estante de la portada (D28): el lomo, del color del borde
        de su tapa; el canto (el grueso que asoma junto a la tapa de frente), un poco más oscuro;
        y `oscuro` si el texto del lomo tiene que ir claro para leerse. Vacío sin tapa legible:
        el lomo queda en la hoja clara."""
        color = self.cover.color_de_borde() if self.cover else ""
        if not color:
            return {}
        rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]

        def lineal(c):
            c /= 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        luz = sum(peso * lineal(c) for peso, c in zip((0.2126, 0.7152, 0.0722), rgb, strict=True))
        # El texto, en tinta (#121823, luminancia 0,009) o en blanco: el que más contraste dé.
        sobre_tinta = (luz + 0.05) / (0.009 + 0.05)
        sobre_blanco = 1.05 / (luz + 0.05)
        canto = "#{:02x}{:02x}{:02x}".format(*(round(c * 0.82) for c in rgb))
        return {"fondo": color, "canto": canto, "oscuro": sobre_blanco > sobre_tinta}


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
    quote = models.TextField(
        blank=True, help_text="Cita destacada para la página de prensa y el dossier."
    )
    logo = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    featured = models.BooleanField(default=False)
    published = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    objects = publishing.PublishableQuerySet.as_manager()

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

    objects = PartnerQuerySet.as_manager()

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "aliado"
        verbose_name_plural = "aliados"

    def __str__(self):
        return self.name
