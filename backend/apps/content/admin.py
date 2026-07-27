from django import forms
from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import PermissionDenied

from . import workflow
from .models import (
    Article,
    ArticleContributor,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialNote,
    EditorialTransition,
    Page,
    Poem,
    PoemContributor,
    ReviewedWork,
    Section,
    Tag,
)
from .permissions import can_edit_item, is_editor


class RichTextWidget(forms.Textarea):
    """Textarea con editor TinyMCE (ver static/admin/richtext_init.js).

    TinyMCE va auto-hospedado en `static/vendor/tinymce/` (sin CDN): su cargador
    perezoso resuelve tema/modelo/iconos/skin/plugins relativos a este archivo,
    por eso ese subárbol se sirve sin hash (ver config.staticfiles).
    """

    class Media:
        js = (
            "vendor/tinymce/tinymce.min.js",
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


class PoemAdminForm(forms.ModelForm):
    """El cuerpo del poema es texto plano (sin editor rico): lo que se escribe, queda."""

    class Meta:
        model = Poem
        fields = "__all__"
        widgets = {"body": forms.Textarea(attrs={"rows": 24, "class": "poem-source"})}


class PageAdminForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = "__all__"
        widgets = {"body": RichTextWidget()}


class ArticleContributorInline(admin.TabularInline):
    model = ArticleContributor
    extra = 1
    autocomplete_fields = ["contributor"]


class PoemContributorInline(admin.TabularInline):
    model = PoemContributor
    extra = 1
    autocomplete_fields = ["contributor"]


class ReviewedWorkInline(admin.TabularInline):
    model = ReviewedWork
    extra = 1
    autocomplete_fields = ["work"]


class EditorialNoteInline(GenericTabularInline):
    model = EditorialNote
    extra = 1
    readonly_fields = ["created_at"]


class EditorialTransitionInline(GenericTabularInline):
    model = EditorialTransition
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "actor", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


class EditorialItemAdmin(admin.ModelAdmin):
    """Base para piezas del flujo editorial (Article, Poem).

    Concentra los permisos por objeto y estado, el dueño automático y las
    acciones de transición; las subclases solo declaran campos e inlines.
    """

    # Todo cambio de estado pasa por estas acciones (perform_transition, con guardas
    # de rol/estado y bitácora). El desplegable `status` es readonly (ver get_readonly_fields).
    actions = [
        "do_submit",
        "do_request_changes",
        "do_accept",
        "do_reject",
        "do_schedule",
        "do_publish",
        "do_unpublish",
        "do_archive",
        "do_restore",
    ]

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
        return can_edit_item(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return is_editor(request.user)

    def get_readonly_fields(self, request, obj=None):
        # `status` es readonly SIEMPRE (también para editores): solo cambia por las
        # acciones de transición, que aplican guardas y dejan rastro en la bitácora.
        ro = [*self.readonly_fields, "status"]
        if not is_editor(request.user):
            # El autor tampoco toca la fecha de publicación ni el dueño.
            ro += ["published_at", "owner"]
        return ro

    def _run(self, request, queryset, name):
        ok = 0
        for item in queryset:
            try:
                workflow.perform_transition(item, name, request.user)
                ok += 1
            except (PermissionDenied, ValueError) as exc:
                self.message_user(request, f"{item}: {exc}", level=messages.WARNING)
        if ok:
            label = self.model._meta.verbose_name_plural
            self.message_user(request, f"{ok} {label} → '{name}'.", level=messages.SUCCESS)

    @admin.action(description="Enviar a revisión")
    def do_submit(self, request, queryset):
        self._run(request, queryset, "submit")

    @admin.action(description="Pedir cambios")
    def do_request_changes(self, request, queryset):
        self._run(request, queryset, "request_changes")

    @admin.action(description="Aceptar")
    def do_accept(self, request, queryset):
        self._run(request, queryset, "accept")

    @admin.action(description="Rechazar")
    def do_reject(self, request, queryset):
        self._run(request, queryset, "reject")

    @admin.action(description="Programar (usa la fecha de publicación indicada)")
    def do_schedule(self, request, queryset):
        self._run(request, queryset, "schedule")

    @admin.action(description="Publicar")
    def do_publish(self, request, queryset):
        self._run(request, queryset, "publish")

    @admin.action(description="Despublicar (volver a borrador)")
    def do_unpublish(self, request, queryset):
        self._run(request, queryset, "unpublish")

    @admin.action(description="Archivar")
    def do_archive(self, request, queryset):
        self._run(request, queryset, "archive")

    @admin.action(description="Restaurar (archivado → publicado)")
    def do_restore(self, request, queryset):
        self._run(request, queryset, "restore")


@admin.register(Article)
class ArticleAdmin(EditorialItemAdmin):
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


@admin.register(Poem)
class PoemAdmin(EditorialItemAdmin):
    form = PoemAdminForm
    list_display = ["title", "status", "featured", "published_at"]
    list_filter = ["status", "featured"]
    search_fields = ["title", "body"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["owner", "recording", "og_image"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [
        PoemContributorInline,
        EditorialNoteInline,
        EditorialTransitionInline,
    ]


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


class CollectionPoemInline(admin.TabularInline):
    model = CollectionPoem
    extra = 1
    autocomplete_fields = ["poem"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "published_at"]
    list_filter = ["status"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CollectionArticleInline, CollectionPoemInline]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    list_display = ["title", "status"]
    list_filter = ["status"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
