from datetime import timedelta

from django.db import models
from django.utils import timezone

# Ventana de validez del enlace de confirmación (hallazgo S-15). El de BAJA no caduca
# nunca: un enlace de baja que deja de funcionar es un problema legal, no una mejora.
CONFIRM_TOKEN_TTL = timedelta(hours=48)


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
    # Token de BAJA: permanente y estable, para que el enlace de cualquier correo ya
    # enviado siga funcionando siempre.
    token = models.CharField(max_length=64, blank=True, db_index=True)
    # Token de CONFIRMACIÓN: de un solo uso y con caducidad. Se separa del de baja
    # porque tenían el mismo ciclo de vida y ninguno caducaba (S-15).
    confirm_token = models.CharField(max_length=64, blank=True, db_index=True)
    confirm_token_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "suscriptor"
        verbose_name_plural = "suscriptores"

    def __str__(self):
        return self.email

    def confirm_token_is_valid(self):
        """True si el token de confirmación existe y no ha caducado."""
        if not self.confirm_token or self.confirm_token_at is None:
            return False
        return timezone.now() - self.confirm_token_at <= CONFIRM_TOKEN_TTL
