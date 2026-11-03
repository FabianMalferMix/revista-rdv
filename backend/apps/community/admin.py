from django.contrib import admin, messages

from . import services
from .models import NewsletterSubscriber
from .tasks import send_confirmation_email


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    """El consentimiento no se edita a mano: el doble opt-in es su única prueba.

    El estado y sus fechas son de solo lectura y los tokens no se muestran. Dar de alta a
    alguien a mano le envía la confirmación, como el formulario del sitio, y la baja es una
    acción que deja constancia en el historial.
    """

    list_display = ["email", "status", "confirmed_at", "status_changed_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["email"]
    actions = ["do_unsubscribe"]
    readonly_fields = [
        "status",
        "confirmed_at",
        "confirm_token_at",
        "status_changed_at",
        "created_at",
    ]

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["email"]  # el alta: el resto lo fija la confirmación
        return ["email", *self.readonly_fields]

    def get_readonly_fields(self, request, obj=None):
        # El correo de un suscriptor existente tampoco: con otro correo, su consentimiento
        # pasaría a una persona que no lo dio.
        return [*self.readonly_fields, "email"] if obj else self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        sub = services.subscribe(obj.email)
        obj.pk = (sub or NewsletterSubscriber.objects.get(email=obj.email)).pk
        if sub is not None:
            send_confirmation_email.delay_on_commit(sub.pk)
            self.message_user(request, f"Se envió la confirmación a {sub.email}.")

    @admin.action(description="Dar de baja")
    def do_unsubscribe(self, request, queryset):
        for sub in queryset:
            if sub.status != NewsletterSubscriber.Status.UNSUBSCRIBED:
                previous = sub.get_status_display()
                sub.unsubscribe()
                self.log_change(request, sub, f"Dado de baja (antes: {previous}).")
        self.message_user(
            request, "Las suscripciones elegidas quedaron dadas de baja.", messages.SUCCESS
        )
