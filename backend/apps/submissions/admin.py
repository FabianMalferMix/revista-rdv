from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import Call, Submission


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ["title", "opens_at", "closes_at", "open_now"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}

    @admin.display(boolean=True, description="Abierta")
    def open_now(self, obj):
        return obj.is_open


def _move_to(status):
    """Una acción que lleva los envíos elegidos a `status`: deja el valor anterior en el
    historial y asigna como revisor a quien la usa. La fecha de resolución la fija el modelo."""
    label = Submission.Status(status).label

    @admin.action(description=f"Pasar a «{label}»", permissions=["change"])
    def move(modeladmin, request, queryset):
        moved = 0
        for submission in queryset.exclude(status=status):
            previous = submission.get_status_display()
            submission.status = status
            submission.reviewer = request.user
            submission.save()
            modeladmin.log_change(request, submission, f"Estado: {previous} → {label}.")
            moved += 1
        modeladmin.message_user(request, f"{moved} envío(s) pasaron a «{label}».", messages.SUCCESS)

    move.__name__ = f"move_to_{status}"
    return move


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Lo que mandó la autora no se reescribe en el panel, y el estado cambia solo con las
    acciones, que fechan la resolución (la purga cuenta desde ella) y dejan constancia."""

    list_display = ["title", "author_name", "status", "call", "created_at"]
    list_filter = ["status", "call"]
    search_fields = ["title", "author_name", "author_email"]
    autocomplete_fields = ["call"]
    exclude = ["file"]  # el adjunto se descarga por la vista protegida, no se sirve
    readonly_fields = [
        "author_name",
        "author_email",
        "type",
        "title",
        "body",
        "archivo",
        "status",
        "reviewer",
        "resolved_at",
        "created_at",
    ]
    actions = [
        _move_to(status) for status in Submission.Status if status != Submission.Status.RECEIVED
    ]

    @admin.display(description="Archivo adjunto")
    def archivo(self, obj):
        if obj.pk and obj.file:
            url = reverse("submissions:file", args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">Descargar adjunto</a>', url
            )
        return "—"
