import secrets
from datetime import timedelta

from django.db import models
from django.db.models.functions import Lower
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

    # Normalizado (minúsculas, sin espacios): «Ana@X.cl» y «ana@x.cl» son la misma persona.
    email = models.EmailField(verbose_name="correo")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="estado"
    )
    # Token de BAJA: permanente y estable, para que el enlace de cualquier correo ya
    # enviado siga funcionando siempre.
    token = models.CharField(max_length=64, blank=True, db_index=True, verbose_name="clave de baja")
    # Token de CONFIRMACIÓN: de un solo uso y con caducidad. Se separa del de baja
    # porque tenían el mismo ciclo de vida y ninguno caducaba (S-15).
    confirm_token = models.CharField(
        max_length=64, blank=True, db_index=True, verbose_name="clave de confirmación"
    )
    confirm_token_at = models.DateTimeField(
        null=True, blank=True, verbose_name="confirmación pedida"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="confirmación recibida")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="alta")
    # El último cambio de estado: desde aquí mide la purga, no desde el alta original.
    status_changed_at = models.DateTimeField(
        default=timezone.now, verbose_name="último cambio de estado"
    )
    # El rastro del correo de confirmación, que el panel enseña: cuándo salió y, si no
    # salió, el último error (sin direcciones).
    confirmation_sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="confirmación enviada"
    )
    confirmation_error = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="error del último envío",
        help_text="Vacío si el último envío salió. Un rechazo de la dirección "
        "(SMTPRecipientsRefused) no se reintenta; los demás errores se reintentan solos.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "suscriptor"
        verbose_name_plural = "suscriptores"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="suscriptor_email_ci"),
        ]

    def __str__(self):
        return self.email

    @staticmethod
    def normalize_email(email):
        return email.strip().lower()

    # ── Transiciones ─────────────────────────────────────────
    # Cada una fija `status_changed_at` y limpia lo que deja de valer. El alta y su tope de
    # reenvío viven en community/services.py.

    def request_confirmation(self):
        """Pendiente, con un token de confirmación nuevo que caduca. Una confirmación
        anterior ya no vale: si vuelve tras darse de baja, tiene que confirmar otra vez."""
        now = timezone.now()
        if not self.token:
            self.token = secrets.token_urlsafe(32)  # baja: estable de por vida
        self.confirm_token = secrets.token_urlsafe(32)
        self.confirm_token_at = now
        self.confirmed_at = None
        self.status = self.Status.PENDING
        self.status_changed_at = now
        self.save()

    def confirm(self):
        """Confirmada. El token de confirmación es de un solo uso."""
        now = timezone.now()
        self.status = self.Status.CONFIRMED
        self.confirmed_at = now
        self.confirm_token = ""
        self.confirm_token_at = None
        self.status_changed_at = now
        self.save()

    def unsubscribe(self):
        """De baja. Un enlace de confirmación aún vigente deja de valer."""
        if self.status == self.Status.UNSUBSCRIBED:
            return
        self.status = self.Status.UNSUBSCRIBED
        self.confirm_token = ""
        self.confirm_token_at = None
        self.status_changed_at = timezone.now()
        self.save()

    def confirm_token_is_valid(self):
        """True si el token de confirmación existe y no ha caducado."""
        if not self.confirm_token or self.confirm_token_at is None:
            return False
        return timezone.now() - self.confirm_token_at <= CONFIRM_TOKEN_TTL
