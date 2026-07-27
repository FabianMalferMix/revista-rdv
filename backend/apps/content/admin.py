from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied

from . import workflow
from .models import (
    Article,
    ArticleContributor,
    Collection,
    CollectionArticle,
    EditorialNote,
    EditorialTransition,
    Page,
    ReviewedWork,
    Section,
    Tag,
)
from .permissions import can_edit_article, is_editor


class RichTextWidget(forms.Textarea):
    """Textarea con editor TinyMCE (ver static/admin/richtext_init.js)."""

    class Media:
        js = (
            "https://cdn.jsdelivr.net/npm/tinymce@7/tinymce.min.js",
            "admin/richtext_init.js",
        )

    def __init__(self, *args, **kwargs):
        attrs = kwargs.setdefault("attrs", {})
        attrs.setdefault("class", "richtext")
        super().__init__(*args, **kwargs)


class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        widgets = {"body": RichTextWidget()}


class PageAdminForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = "__all__"
        widgets = {"body": RichTextWidget()}


class ArticleContributorInline(admin.TabularInline):
    model = ArticleContributor
    extra = 1
    autocomplete_fields = ["contributor"]


class ReviewedWorkInline(admin.TabularInline):
    model = ReviewedWork
    extra = 1
    autocomplete_fields = ["work"]


class EditorialNoteInline(admin.TabularInline):
    model = EditorialNote
    extra = 1
    readonly_fields = ["created_at"]


class EditorialTransitionInline(admin.TabularInline):
    model = EditorialTransition
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "actor", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = ["title", "type", "status", "featured", "published_at"]
    list_filter = ["status", "type", "featured", "section"]
    search_fields = ["title", "subtitle", "body"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["section", "owner", "cover_image", "og_image"]
    filter_horizontal = ["tags"]
    readonly_fields = ["reading_time", "created_at", "updated_at"]
    inlines = [
        ArticleContributorInline,
        ReviewedWorkInline,
        EditorialNoteInline,
        EditorialTransitionInline,
    ]
    actions = ["do_submit", "do_accept", "do_publish", "do_archive"]

    # ── Permisos por objeto y estado ─────────────────────────
    def save_model(self, request, obj, form, change):
        # Al crear, el dueño es quien lo crea (habilita "mis borradores").
        if not change and not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_editor(request.user):
            return qs
        return qs.filter(owner=request.user)  # el autor solo ve lo suyo

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request)
        if is_editor(request.user):
            return True
        return can_edit_article(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return is_editor(request.user)

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if not is_editor(request.user):
            # El autor no cambia estado/owner a mano: solo por el flujo editorial.
            ro += ["status", "published_at", "owner"]
        return ro

    def _run(self, request, queryset, name):
        ok = 0
        for article in queryset:
            try:
                workflow.perform_transition(article, name, request.user)
                ok += 1
            except (PermissionDenied, ValueError) as exc:
                self.message_user(request, f"{article}: {exc}", level=messages.WARNING)
        if ok:
            self.message_user(request, f"{ok} artículo(s) → '{name}'.", level=messages.SUCCESS)

    @admin.action(description="Enviar a revisión")
    def do_submit(self, request, queryset):
        self._run(request, queryset, "submit")

    @admin.action(description="Aceptar")
    def do_accept(self, request, queryset):
        self._run(request, queryset, "accept")

    @admin.action(description="Publicar")
    def do_publish(self, request, queryset):
        self._run(request, queryset, "publish")

    @admin.action(description="Archivar")
    def do_archive(self, request, queryset):
        self._run(request, queryset, "archive")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name", "position"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class CollectionArticleInline(admin.TabularInline):
    model = CollectionArticle
    extra = 1
    autocomplete_fields = ["article"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "published_at"]
    list_filter = ["status"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CollectionArticleInline]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = ["title", "status"]
    list_filter = ["status"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
