from django.db import models


class NewsletterSubscriber(models.Model):
    """Suscriptor con doble opt-in."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmado"
        UNSUBSCRIBED = "unsubscribed", "Dado de baja"

    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    token = models.CharField(max_length=64, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "suscriptor"
        verbose_name_plural = "suscriptores"

    def __str__(self):
        return self.email
