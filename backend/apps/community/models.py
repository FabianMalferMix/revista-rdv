from django.conf import settings
from django.db import models


class Comment(models.Model):
    """Comentario con moderación. XOR: o lector autenticado, o invitado (nunca ambos)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        SPAM = "spam", "Spam"
        REJECTED = "rejected", "Rechazado"

    article = models.ForeignKey(
        "content.Article", on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
    )
    guest_name = models.CharField(max_length=120, blank=True)
    guest_email = models.EmailField(blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "comentario"
        verbose_name_plural = "comentarios"
        constraints = [
            # Exactamente uno: usuario autenticado XOR invitado con nombre.
            models.CheckConstraint(
                name="comment_user_xor_guest",
                condition=(
                    models.Q(user__isnull=False, guest_name="")
                    | (models.Q(user__isnull=True) & ~models.Q(guest_name=""))
                ),
            )
        ]

    def __str__(self):
        who = self.user or self.guest_name
        return f"{who} en {self.article_id}"


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
