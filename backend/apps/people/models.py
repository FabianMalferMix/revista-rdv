from django.conf import settings
from django.db import models
from django.urls import reverse


class Contributor(models.Model):
    """Perfil público de colaborador. Distinto de la cuenta del sistema (User).

    Con `is_member=True` la persona es además **integrante del colectivo**: aparece
    en /integrantes/ con perfil enriquecido (bio corta, poética, rol, año de ingreso).
    """

    slug = models.SlugField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    bio = models.TextField(blank=True)
    photo = models.ForeignKey(
        "media.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    website = models.URLField(blank=True)
    # Un colaborador puede tener (o no) cuenta en el sistema.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contributor_profile",
    )
    # ── Membresía del colectivo ──────────────────────────────
    is_member = models.BooleanField(
        default=False, help_text="Integrante del colectivo (aparece en /integrantes/)."
    )
    active = models.BooleanField(
        default=True, help_text="Integrante activo; desmarcado = histórico."
    )
    role = models.CharField(
        max_length=100, blank=True, help_text="Rol en el colectivo (p. ej. «fundadora», «gestión»)."
    )
    member_since = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Año de ingreso al colectivo."
    )
    short_bio = models.CharField(
        max_length=280, blank=True, help_text="Bio breve para tarjetas y dossier (1–2 frases)."
    )
    poetics = models.TextField(blank=True, help_text="Poética personal (declaración breve).")
    position = models.PositiveSmallIntegerField(
        default=0, help_text="Orden en la grilla de integrantes."
    )

    class Meta:
        ordering = ["display_name"]
        verbose_name = "colaborador"
        verbose_name_plural = "colaboradores"

    def __str__(self):
        return self.display_name

    @classmethod
    def members(cls):
        """Integrantes activos en orden curado (grillas, sitemap, dossier)."""
        # select_related('photo'): las tarjetas usan m.photo.file.url (cierra el N+1).
        return (
            cls.objects.filter(is_member=True, active=True)
            .select_related("photo")
            .order_by("position", "display_name")
        )

    def get_absolute_url(self):
        # Integrante → perfil rico; colaborador externo → página de byline.
        if self.is_member:
            return reverse("people:member_detail", args=[self.slug])
        return reverse("content:contributor_detail", args=[self.slug])


class SocialLink(models.Model):
    """Enlace social atómico (reemplaza el antiguo JSON — normalizado a 1NF)."""

    contributor = models.ForeignKey(
        Contributor, on_delete=models.CASCADE, related_name="social_links"
    )
    platform = models.CharField(max_length=50)
    url = models.URLField()
    position = models.PositiveSmallIntegerField(default=0)

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
