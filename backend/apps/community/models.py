from django.db import models


class NewsletterSubscriber(models.Model):
    """Suscriptor con doble opt-in.

    Lista LATENTE: hoy solo capta y confirma suscriptores; NO existe aún un camino
    de envío (no hay campaña ni comando de difusión). Por minimización de datos, los
    suscriptores que nunca confirman se purgan periódicamente (comando
    purge_stale_data, programado en Celery beat). Construir el envío —con
    List-Unsubscribe y confirmación por POST— cuando se vaya a usar de verdad.
    """

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
