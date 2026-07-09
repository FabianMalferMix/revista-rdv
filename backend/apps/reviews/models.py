from django.db import models


class Publisher(models.Model):
    """Editorial. Extraída de Work (3NF): habilita 'reseñas por editorial'."""

    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

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
    # ISBN es clave candidata: null (no "") para permitir varias obras sin ISBN.
    isbn = models.CharField(max_length=20, unique=True, null=True, blank=True)
    language = models.CharField(max_length=8, blank=True)
    cover_image = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    description = models.TextField(blank=True)
    authors = models.ManyToManyField(BookAuthor, blank=True, related_name="works")

    class Meta:
        ordering = ["title"]
        verbose_name = "obra"
        verbose_name_plural = "obras"

    def __str__(self):
        return self.title
