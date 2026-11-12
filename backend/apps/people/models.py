from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse

from apps.content.models import Article, Poem


def url_for_person(slug, is_member):
    """La dirección de la ficha de una persona: la integrante tiene su perfil en /integrante/ y
    quien colabora desde fuera, su página de firmas en /colaborador/. Es la única regla: la usan
    `Contributor.get_absolute_url`, las filas de la búsqueda y la redirección entre las dos."""
    if is_member:
        return reverse("people:member_detail", args=[slug])
    return reverse("content:contributor_detail", args=[slug])


class ContributorQuerySet(models.QuerySet):
    def visible(self):
        """Quien tiene ficha pública: las integrantes, también las históricas, y quien firma
        algo publicado. Una firma sin nada publicado no tiene qué enseñar, y responde 404."""
        signs = OuterRef("pk")
        return self.filter(
            Q(is_member=True)
            | Exists(Article.objects.published().filter(authors=signs))
            | Exists(Poem.objects.published().filter(authors=signs))
        )

    def with_page(self):
        """Cada persona con `has_page`, si tiene ficha, con el criterio de su ficha
        (`visible()`). Quien participa en una publicación, una actividad o un registro sin ser
        integrante ni firmar nada publicado no la tiene: su enlace llevaría a un 404."""
        return self.annotate(
            has_page=Exists(Contributor.objects.visible().filter(pk=OuterRef("pk")))
        )

    def members(self):
        """Integrantes activos en orden curado (grillas, sitemap, dossier)."""
        # select_related('photo'): las tarjetas usan m.photo.file.url (cierra el N+1).
        return (
            self.filter(is_member=True, active=True)
            .select_related("photo")
            .order_by("position", "display_name")
        )


class Contributor(models.Model):
    """Perfil público de colaborador. Distinto de la cuenta del sistema (User).

    Con `is_member=True` la persona es además **integrante del colectivo**: aparece
    en /integrantes/ con perfil enriquecido (bio corta, poética, rol, año de ingreso).
    """

    slug = models.SlugField(max_length=255, unique=True, verbose_name="dirección")
    display_name = models.CharField(max_length=255, verbose_name="nombre")
    bio = models.TextField(blank=True, verbose_name="biografía")
    photo = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="foto",
    )
    website = models.URLField(blank=True, verbose_name="sitio web")
    # Un colaborador puede tener (o no) cuenta en el sistema.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contributor_profile",
        verbose_name="cuenta",
    )
    # ── Membresía del colectivo ──────────────────────────────
    is_member = models.BooleanField(
        "integrante del colectivo",
        default=False,
        help_text="Tiene ficha de integrante y aparece en /integrantes/. Si deja el colectivo, "
        "desmarca «En activo», no esta casilla: así conserva su ficha.",
    )
    active = models.BooleanField(
        "en activo",
        default=True,
        help_text="Desmarcada, deja de aparecer en las listas del colectivo, pero conserva su "
        "ficha de integrante.",
    )
    role = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="rol",
        help_text="Rol en el colectivo (p. ej. «fundadora», «gestión»).",
    )
    member_since = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="integrante desde",
        help_text="Año de ingreso al colectivo.",
    )
    short_bio = models.CharField(
        max_length=280,
        blank=True,
        verbose_name="biografía breve",
        help_text="Bio breve para tarjetas y dossier (1–2 frases).",
    )
    poetics = models.TextField(
        blank=True, verbose_name="poética", help_text="Poética personal (declaración breve)."
    )
    position = models.PositiveSmallIntegerField(
        default=0, verbose_name="posición", help_text="Orden en la grilla de integrantes."
    )

    objects = ContributorQuerySet.as_manager()

    class Meta:
        ordering = ["display_name"]
        verbose_name = "colaborador"
        verbose_name_plural = "colaboradores"

    def __str__(self):
        return self.display_name

    def get_absolute_url(self):
        return url_for_person(self.slug, self.is_member)


class SocialLink(models.Model):
    """Enlace social atómico (reemplaza el antiguo JSON — normalizado a 1NF)."""

    contributor = models.ForeignKey(
        Contributor,
        on_delete=models.CASCADE,
        related_name="social_links",
        verbose_name="colaborador",
    )
    platform = models.CharField(max_length=50, verbose_name="plataforma")
    url = models.URLField(verbose_name="dirección")
    position = models.PositiveSmallIntegerField(default=0, verbose_name="posición")

    class Meta:
        verbose_name = "red social"
        verbose_name_plural = "redes sociales"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["contributor", "platform"], name="uniq_contributor_platform"
            )
        ]

    def __str__(self):
        return f"{self.contributor} · {self.platform}"


class RoleGrant(models.Model):
    """Lo que `setup_groups` ya repartió a cada grupo según la matriz de roles (roles.py).

    Un permiso de la matriz que figura aquí y ya no está en el grupo lo retiró el operador: las
    sincronizaciones siguientes lo respetan. Uno que no figura es nuevo en la matriz, y se añade.
    """

    group = models.ForeignKey(
        "auth.Group", on_delete=models.CASCADE, related_name="+", verbose_name="grupo"
    )
    permission = models.ForeignKey(
        "auth.Permission", on_delete=models.CASCADE, related_name="+", verbose_name="permiso"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="repartido el")

    class Meta:
        verbose_name = "permiso repartido"
        verbose_name_plural = "permisos repartidos"
        constraints = [
            models.UniqueConstraint(fields=["group", "permission"], name="uniq_role_grant")
        ]

    def __str__(self):
        return f"{self.group} · {self.permission.codename}"
