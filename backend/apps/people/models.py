from django.conf import settings
from django.db import models


class Contributor(models.Model):
    """Perfil público de colaborador. Distinto de la cuenta del sistema (User)."""

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

    class Meta:
        ordering = ["display_name"]
        verbose_name = "colaborador"
        verbose_name_plural = "colaboradores"

    def __str__(self):
        return self.display_name


class SocialLink(models.Model):
    """Enlace social atómico (reemplaza el antiguo JSON — normalizado a 1NF)."""

    contributor = models.ForeignKey(
        Contributor, on_delete=models.CASCADE, related_name="social_links"
    )
    platform = models.CharField(max_length=50)
    url = models.URLField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["contributor", "platform"], name="uniq_contributor_platform"
            )
        ]

    def __str__(self):
        return f"{self.contributor} · {self.platform}"
