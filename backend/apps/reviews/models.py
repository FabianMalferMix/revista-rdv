from django.db import models
from django.db.models import Exists, OuterRef

from apps.content.models import Article
from apps.showcase.models import Publication

# Obras, editoriales y autoras de obra no tienen estado propio: tienen ficha y van al sitemap
# solo si algo publicado las respalda. Lo demás responde 404.


class PublisherQuerySet(models.QuerySet):
    def visible(self):
        """Las editoriales con alguna obra visible o alguna publicación del colectivo."""
        works = Work.objects.visible().filter(publisher=OuterRef("pk"))
        publications = Publication.objects.published().filter(publisher=OuterRef("pk"))
        return self.filter(Exists(works) | Exists(publications))


class BookAuthorQuerySet(models.QuerySet):
    def visible(self):
        """Las autoras de alguna obra visible."""
        return self.filter(Exists(Work.objects.visible().filter(authors=OuterRef("pk"))))


class WorkQuerySet(models.QuerySet):
    def visible(self):
        """Las obras con una reseña publicada o que son una publicación del colectivo."""
        reviews = Article.objects.published().filter(reviewed_works=OuterRef("pk"))
        own = Publication.objects.published().filter(pk=OuterRef("publicacion"))
        return self.filter(Exists(reviews) | Exists(own))


class Publisher(models.Model):
    """Editorial. Extraída de Work (3NF): habilita 'reseñas por editorial'."""

    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

    objects = PublisherQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "editorial"
        verbose_name_plural = "editoriales"

    def __str__(self):
        return self.name


class BookAuthor(models.Model):
    """Autor de la obra reseñada. Distinto del Contributor de la revista."""

    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    bio = models.TextField(blank=True)

    objects = BookAuthorQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "autor de obra"
        verbose_name_plural = "autores de obra"

    def __str__(self):
        return self.name


class Work(models.Model):
    """Obra reseñada (libro, poemario, etc.)."""

    class Kind(models.TextChoices):
        LIBRO = "libro", "Libro"
        POEMARIO = "poemario", "Poemario"
        ENSAYO = "ensayo", "Ensayo"
        ANTOLOGIA = "antologia", "Antología"
        OTRO = "otro", "Otro"

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.LIBRO)
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="works",
    )
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    # ISBN es clave candidata OPCIONAL: se guarda NULL (no "") cuando falta —save() lo
    # coacciona— para permitir varias obras sin ISBN; la unicidad se aplica solo sobre
    # ISBN reales vía UniqueConstraint parcial (ver Meta), no con unique=True plano
    # (que hacía chocar dos "" en el admin: IntegrityError/500).
    isbn = models.CharField(max_length=20, null=True, blank=True)
    cover_image = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    description = models.TextField(blank=True)
    authors = models.ManyToManyField(BookAuthor, blank=True, related_name="works")
    # Cuando la obra reseñada es una publicación del colectivo: su ficha enseña entonces
    # las reseñas que tiene, y la obra lleva a ella. Una publicación es una sola obra (todas
    # sus reseñas apuntan a la misma); la mayoría de las obras no tienen ninguna.
    publicacion = models.OneToOneField(
        "showcase.Publication",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="obra_resenada",
        verbose_name="publicación del colectivo",
        help_text="Si la obra reseñada es una publicación del colectivo, cuál: su ficha enseñará "
        "las reseñas.",
    )

    objects = WorkQuerySet.as_manager()

    class Meta:
        ordering = ["title"]
        verbose_name = "obra"
        verbose_name_plural = "obras"
        constraints = [
            # Unicidad solo sobre ISBN reales (no NULL ni ""): clave candidata opcional.
            models.UniqueConstraint(
                fields=["isbn"],
                condition=models.Q(isbn__isnull=False) & ~models.Q(isbn=""),
                name="uniq_work_isbn",
            )
        ]

    def save(self, *args, **kwargs):
        self.isbn = self.isbn or None  # "" → NULL: varias obras pueden no tener ISBN
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def public_publication(self):
        """La publicación del colectivo que es esta obra, solo si está publicada."""
        publication = self.publicacion
        return publication if publication is not None and publication.published else None
