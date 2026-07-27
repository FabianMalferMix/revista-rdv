from django.db import models


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
    dossier_pdf = models.FileField(
        upload_to="dossier/",
        blank=True,
        help_text="PDF del kit de prensa (override manual opcional del dossier generado).",
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
