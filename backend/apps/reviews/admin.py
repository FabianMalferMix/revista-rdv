from django.contrib import admin

from .models import BookAuthor, Publisher, Work


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ["name", "country"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BookAuthor)
class BookAuthorAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "publisher", "publication_year"]
    list_filter = ["kind"]
    search_fields = ["title", "isbn"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["publisher", "cover_image"]
    filter_horizontal = ["authors"]
