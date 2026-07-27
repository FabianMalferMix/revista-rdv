import re

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models

from .sanitize import clean_html


class Section(models.Model):
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "sección"
        verbose_name_plural = "secciones"

    def __str__(self):
        return self.name


class Tag(models.Model):
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]
        verbose_name = "etiqueta"
        verbose_name_plural = "etiquetas"

    def __str__(self):
        return self.name


class ArticleType(models.TextChoices):
    RESENA = "resena", "Reseña"
    ENSAYO = "ensayo", "Ensayo"
    ENTREVISTA = "entrevista", "Entrevista"
    POESIA = "poesia", "Poesía"
    NARRATIVA = "narrativa", "Narrativa"
    CRITICA = "critica", "Crítica"
    NOTA = "nota", "Nota"


class ArticleStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    IN_REVIEW = "in_review", "En revisión"
    CHANGES_REQUESTED = "changes_requested", "Cambios pedidos"
    APPROVED = "approved", "Aprobado"
    SCHEDULED = "scheduled", "Programado"
    PUBLISHED = "published", "Publicado"
    ARCHIVED = "archived", "Archivado"
    REJECTED = "rejected", "Rechazado"


class Article(models.Model):
    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, help_text="Bajada")
    body = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Extracto autoral (opcional)")
    type = models.CharField(max_length=20, choices=ArticleType.choices, default=ArticleType.RESENA)
    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.DRAFT,
        db_index=True,
    )
    # Dueño del artículo en el sistema (para permisos "mis borradores").
    # Distinto de los autores del byline (Contributor).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_articles",
    )
    section = models.ForeignKey(
        Section, null=True, blank=True, on_delete=models.SET_NULL, related_name="articles"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")
    authors = models.ManyToManyField(
        "people.Contributor",
        through="content.ArticleContributor",
        related_name="articles",
    )
    reviewed_works = models.ManyToManyField(
        "reviews.Work",
        through="content.ReviewedWork",
        blank=True,
        related_name="reviews",
    )
    cover_image = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    og_image = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reading_time = models.PositiveIntegerField(
        default=0, editable=False, help_text="Minutos estimados (derivado del cuerpo)"
    )
    featured = models.BooleanField(default=False)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    search_vector = SearchVectorField(null=True, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="article_search_gin"),
            models.Index(fields=["status", "-published_at"], name="article_status_pub_idx"),
        ]
        verbose_name = "artículo"
        verbose_name_plural = "artículos"

    def __str__(self):
        return self.title

    def _calc_reading_time(self):
        text = re.sub(r"<[^>]+>", " ", self.body or "")
        words = len(text.split())
        return max(1, round(words / 200)) if words else 0

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        self.reading_time = self._calc_reading_time()
        super().save(*args, **kwargs)
        # Recalcula el vector de búsqueda (derivado, sin redundancia editable a mano).
        type(self).objects.filter(pk=self.pk).update(
            search_vector=SearchVector("title", "subtitle", "body", config="spanish")
        )


class ArticleContributor(models.Model):
    """Puente Artículo ↔ Colaborador. `position` = orden de firma (coautoría)."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    contributor = models.ForeignKey("people.Contributor", on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["article", "contributor"], name="uniq_article_contributor"
            )
        ]


class ReviewedWork(models.Model):
    """Puente Reseña ↔ Obra. `is_primary` marca la obra principal de la reseña."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="reviewed_work_links"
    )
    work = models.ForeignKey("reviews.Work", on_delete=models.CASCADE, related_name="review_links")
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["article", "work"], name="uniq_article_work")
        ]


class PublishStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    PUBLISHED = "published", "Publicado"


class Collection(models.Model):
    """Colección / antología: agrupación curada de piezas (ex «dosier»).

    El término «dosier» se reservó para el kit de prensa del colectivo; esta entidad
    agrupa contenido editorial (artículos y, desde el lote de obra, poemas).
    """

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    intro = models.TextField(blank=True)
    cover_image = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=20, choices=PublishStatus.choices, default=PublishStatus.DRAFT
    )
    published_at = models.DateTimeField(null=True, blank=True)
    articles = models.ManyToManyField(
        Article, through="content.CollectionArticle", related_name="collections"
    )

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "colección"
        verbose_name_plural = "colecciones"

    def __str__(self):
        return self.title


class CollectionArticle(models.Model):
    """Puente Colección ↔ Artículo. `position` = secuencia curada."""

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "article"], name="uniq_collection_article"
            )
        ]


class Page(models.Model):
    """Página estática: Quiénes somos, Bases, Contacto."""

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=PublishStatus.choices, default=PublishStatus.DRAFT
    )
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "página"
        verbose_name_plural = "páginas"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)


class EditorialTransition(models.Model):
    """Rastro inmutable de cada movimiento del flujo editorial."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editorial_transitions",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.article_id}: {self.from_status} → {self.to_status}"


class EditorialNote(models.Model):
    """Discusión interna editor ↔ autor, separada de los comentarios públicos."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="editorial_notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
