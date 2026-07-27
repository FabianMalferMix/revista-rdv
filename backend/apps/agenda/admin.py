from django.contrib import admin

from .models import Event, EventPhoto, Milestone


class EventPhotoInline(admin.TabularInline):
    model = EventPhoto
    extra = 1
    autocomplete_fields = ["asset"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "starts_at", "city", "published", "featured"]
    list_filter = ["published", "featured", "type", "is_external"]
    search_fields = ["title", "venue_name", "city", "description"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["poster"]
    filter_horizontal = ["participants"]
    date_hierarchy = "starts_at"
    inlines = [EventPhotoInline]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["year", "title"]
    search_fields = ["title"]
