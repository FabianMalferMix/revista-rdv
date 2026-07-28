import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse

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


class EditorialStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    IN_REVIEW = "in_review", "En revisión"
    CHANGES_REQUESTED = "changes_requested", "Cambios pedidos"
    APPROVED = "approved", "Aprobado"
    SCHEDULED = "scheduled", "Programado"
    PUBLISHED = "published", "Publicado"
    ARCHIVED = "archived", "Archivado"
    REJECTED = "rejected", "Rechazado"


class EditorialItem(models.Model):
    """Base abstracta del flujo editorial: estado + dueño + fecha de publicación.

    La comparten Artículo y Poema. Las transiciones y notas viven en tablas genéricas
    (EditorialTransition / EditorialNote) enlazadas por content_type + object_id.
    """

    status = models.CharField(
        max_length=20,
        choices=EditorialStatus.choices,
        default=EditorialStatus.DRAFT,
        db_index=True,
    )
    # Dueño de la pieza en el sistema (para permisos "mis borradores").
    # Distinto de los autores del byline (Contributor).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_%(class)ss",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Acceso inverso a la bitácora (p. ej. article.transitions / poem.editorial_notes);
    # related_query_name habilita EditorialTransition.objects.filter(article=…) y (poem=…).
    transitions = GenericRelation("content.EditorialTransition", related_query_name="%(class)s")
    editorial_notes = GenericRelation("content.EditorialNote", related_query_name="%(class)s")

    class Meta:
        abstract = True


class Article(EditorialItem):
    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, help_text="Bajada")
    body = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Extracto autoral (opcional)")
    type = models.CharField(max_length=20, choices=ArticleType.choices, default=ArticleType.RESENA)
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
        # `search_vector` lo mantiene un trigger de Postgres (ver migración): se
        # actualiza en TODA escritura de title/subtitle/body (también bulk_update),
        # no solo al pasar por save().


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


class Poem(EditorialItem):
    """Poema de un integrante (obra propia del colectivo).

    A diferencia de Article.body (HTML saneado), el cuerpo se guarda como texto plano
    y la plantilla lo escapa y renderiza con `white-space: pre-wrap`: se preservan
    versos, sangrías y espacios tal como se escribieron.
    """

    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    epigraph = models.TextField(blank=True, help_text="Epígrafe o dedicatoria (opcional).")
    body = models.TextField(help_text="Texto plano: se preservan saltos de línea y sangrías.")
    authors = models.ManyToManyField(
        "people.Contributor",
        through="content.PoemContributor",
        related_name="poems",
    )
    recording = models.ForeignKey(
        "media.Recording",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="poems",
        help_text="Registro del poema leído por su autor/a (opcional).",
    )
    featured = models.BooleanField(default=False)
    og_image = models.ForeignKey(
        "media.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    # Mantenido por un trigger de Postgres (ver migración): los poemas son buscables.
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="poem_search_gin"),
            models.Index(fields=["status", "-published_at"], name="poem_status_pub_idx"),
        ]
        verbose_name = "poema"
        verbose_name_plural = "poemas"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("content:poem_detail", args=[self.slug])


class PoemContributor(models.Model):
    """Puente Poema ↔ Colaborador. `position` = orden de firma (coautoría)."""

    poem = models.ForeignKey(Poem, on_delete=models.CASCADE)
    contributor = models.ForeignKey("people.Contributor", on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["poem", "contributor"], name="uniq_poem_contributor")
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
    poems = models.ManyToManyField(
        Poem, through="content.CollectionPoem", blank=True, related_name="collections"
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


class CollectionPoem(models.Model):
    """Puente Colección ↔ Poema. `position` comparte la secuencia curada con artículos."""

    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    poem = models.ForeignKey(Poem, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "poem"], name="uniq_collection_poem")
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
    """Rastro inmutable de cada movimiento del flujo editorial (artículos y poemas).

    Enlace genérico (content_type + object_id) a cualquier pieza que herede de
    EditorialItem; `item` es el acceso directo al objeto.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    object_id = models.PositiveBigIntegerField()
    item = GenericForeignKey("content_type", "object_id")
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
        indexes = [models.Index(fields=["content_type", "object_id"], name="edtransition_item_idx")]

    def __str__(self):
        return f"{self.content_type_id}/{self.object_id}: {self.from_status} → {self.to_status}"


class EditorialNote(models.Model):
    """Discusión interna editor ↔ autor, separada de los comentarios públicos."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    object_id = models.PositiveBigIntegerField()
    item = GenericForeignKey("content_type", "object_id")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"], name="ednote_item_idx")]
