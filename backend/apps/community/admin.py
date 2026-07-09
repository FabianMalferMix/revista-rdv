from django.contrib import admin

from .models import Comment, NewsletterSubscriber


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["__str__", "article", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["body", "guest_name", "guest_email"]
    autocomplete_fields = ["article", "user", "parent"]
    actions = ["approve", "mark_spam", "reject"]

    @admin.action(description="Aprobar comentarios")
    def approve(self, request, queryset):
        queryset.update(status=Comment.Status.APPROVED)

    @admin.action(description="Marcar como spam")
    def mark_spam(self, request, queryset):
        queryset.update(status=Comment.Status.SPAM)

    @admin.action(description="Rechazar")
    def reject(self, request, queryset):
        queryset.update(status=Comment.Status.REJECTED)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "status", "confirmed_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["email"]
