from django.contrib import admin

from .models import NewsletterSubscriber


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "status", "confirmed_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["email"]
