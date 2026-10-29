from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.formats import date_format

from . import workflow
from .models import (
    LEGAL_PAGES,
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
from .sanitize import clean_html


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


class SanitizedBodyMixin:
    """Sanea el cuerpo también en la capa de FORMULARIO.

    El saneo vive en `Model.save()`, que es la garantía real. Pero eso lo convierte en una
    convención de la capa Python: quien escriba por otro camino —una migración de datos,
    un `bulk_create`, un import— la esquiva. Repetirlo aquí hace que el editor vea el
    resultado ya depurado al guardar desde el panel, en vez de descubrirlo al releer.
    """

    def clean_body(self):
        return clean_html(self.cleaned_data.get("body", ""))


class ArticleAdminForm(SanitizedBodyMixin, forms.ModelForm):
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


LEGAL_PAGE_NOTICE = (
    "Página legal: el pie de todas las páginas y los formularios enlazan a ella. Se puede "
    "editar su título y su texto, pero no cambiar su dirección, despublicarla ni borrarla."
)


class PageAdminForm(SanitizedBodyMixin, forms.ModelForm):
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


def _action_permission(transition):
    """El permiso del panel que pide una acción: el de cambiar la pieza si la transición es de la
    dueña (enviar a revisión) y, si no, el de revisar o publicar."""
    who = workflow.TRANSITIONS[transition].who
    return "change" if workflow.OWNER in who else who[0]


class ScheduleForm(forms.Form):
    """La fecha que pide «Programar»: sin ella una pieza programada no saldría nunca."""

    published_at = forms.DateTimeField(
        label="Fecha de publicación",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    def clean_published_at(self):
        when = self.cleaned_data["published_at"]
        if when <= timezone.now():
            raise forms.ValidationError("La fecha tiene que ser futura.")
        return when


class EditorialItemAdmin(admin.ModelAdmin):
    """Base para piezas del flujo editorial (Article, Poem).

    Concentra los permisos por objeto y estado, el dueño automático y las
    acciones de transición; las subclases solo declaran campos e inlines.
    """

    # Todo cambio de estado pasa por estas acciones (perform_transition, con guardas
    # de permiso y de estado, y bitácora). El desplegable `status` es readonly (ver get_readonly_fields).
    actions = [
        "do_submit",
        "do_request_changes",
        "do_accept",
        "do_reject",
        "do_reopen",
        "do_schedule",
        "do_unschedule",
        "do_publish",
        "do_unpublish",
        "do_archive",
        "do_restore",
    ]

    # Las acciones de revisar y publicar piden su permiso de Django (`allowed_permissions`):
    # quien no lo tiene no las ve en el desplegable, y perform_transition vuelve a mirarlo.
    def has_review_permission(self, request):
        return request.user.has_perm(workflow.permission_for(self.model, workflow.REVIEW))

    def has_publish_permission(self, request):
        return request.user.has_perm(workflow.permission_for(self.model, workflow.PUBLISH))

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

    # Las comprobaciones por rol/estado COMPONEN con el permiso de modelo de Django, no
    # lo sustituyen: antes, retirar `content.change_article` a alguien del grupo editor
    # no surtía efecto, porque la respuesta se decidía solo por pertenencia al grupo. Con
    # el `and super()...` delante, revocar el permiso en el admin vuelve a bastar.
    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None:
            return True
        return is_editor(request.user) or can_edit_item(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and is_editor(request.user)

    def get_readonly_fields(self, request, obj=None):
        # `status` es readonly SIEMPRE (también para editores): solo cambia por las
        # acciones de transición, que aplican guardas y dejan rastro en la bitácora.
        ro = [*self.readonly_fields, "status"]
        if not is_editor(request.user):
            # El autor tampoco toca la fecha de publicación ni el dueño.
            ro += ["published_at", "owner"]
        return ro

    def _run(self, request, queryset, name, **kwargs):
        ok = 0
        for item in queryset:
            try:
                workflow.perform_transition(item, name, request.user, **kwargs)
                ok += 1
            except (PermissionDenied, ValueError) as exc:
                self.message_user(request, f"{item}: {exc}", level=messages.WARNING)
        if ok:
            label = self.model._meta.verbose_name_plural
            self.message_user(request, f"{ok} {label} → '{name}'.", level=messages.SUCCESS)

    @admin.action(description="Enviar a revisión", permissions=[_action_permission("submit")])
    def do_submit(self, request, queryset):
        self._run(request, queryset, "submit")

    @admin.action(description="Pedir cambios", permissions=[_action_permission("request_changes")])
    def do_request_changes(self, request, queryset):
        self._run(request, queryset, "request_changes")

    @admin.action(description="Aceptar", permissions=[_action_permission("accept")])
    def do_accept(self, request, queryset):
        self._run(request, queryset, "accept")

    @admin.action(description="Rechazar", permissions=[_action_permission("reject")])
    def do_reject(self, request, queryset):
        self._run(request, queryset, "reject")

    @admin.action(
        description="Rechazada: reabrir (vuelve a borrador)",
        permissions=[_action_permission("reopen")],
    )
    def do_reopen(self, request, queryset):
        self._run(request, queryset, "reopen")

    @admin.action(description="Programar…", permissions=[_action_permission("schedule")])
    def do_schedule(self, request, queryset):
        """Una página intermedia pide la fecha; al confirmarla, programa con ella."""
        form = ScheduleForm(request.POST if "apply" in request.POST else None)
        if form.is_valid():
            when = form.cleaned_data["published_at"]
            self._run(request, queryset, "schedule", when=when)
            self.message_user(
                request,
                f"Fecha de publicación: {date_format(timezone.localtime(when), 'j F Y, H:i')}.",
            )
            return None
        return TemplateResponse(
            request,
            "admin/content/schedule.html",
            {
                **self.admin_site.each_context(request),
                "title": "Programar la publicación",
                "opts": self.model._meta,
                "queryset": queryset,
                "form": form,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            },
        )

    @admin.action(
        description="Programada: desprogramar (vuelve a aprobada)",
        permissions=[_action_permission("unschedule")],
    )
    def do_unschedule(self, request, queryset):
        self._run(request, queryset, "unschedule")

    @admin.action(description="Publicar", permissions=[_action_permission("publish")])
    def do_publish(self, request, queryset):
        self._run(request, queryset, "publish")

    @admin.action(
        description="Despublicar (volver a borrador)", permissions=[_action_permission("unpublish")]
    )
    def do_unpublish(self, request, queryset):
        self._run(request, queryset, "unpublish")

    @admin.action(description="Archivar", permissions=[_action_permission("archive")])
    def do_archive(self, request, queryset):
        self._run(request, queryset, "archive")

    @admin.action(
        description="Restaurar (archivado → publicado)", permissions=[_action_permission("restore")]
    )
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
    # El orden del modelo también en las legales, donde el slug y el estado son de solo
    # lectura: sin él, Django los manda al final del formulario.
    fields = ["slug", "title", "body", "status", "seo_title", "seo_description"]

    # Las legales: el texto sigue editable (lo revisa un abogado desde aquí); el slug, el
    # estado y el borrado, no. `has_delete_permission` con la página también frena la
    # acción «Eliminar seleccionados», que la consulta objeto por objeto.
    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.slug in LEGAL_PAGES:
            campos += ["slug", "status"]
        return campos

    def get_prepopulated_fields(self, request, obj=None):
        if obj is not None and obj.slug in LEGAL_PAGES:
            return {}
        return super().get_prepopulated_fields(request, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is not None and obj.slug in LEGAL_PAGES:
            nombre, opciones = fieldsets[0]
            fieldsets = [(nombre, {**opciones, "description": LEGAL_PAGE_NOTICE}), *fieldsets[1:]]
        return fieldsets

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.slug in LEGAL_PAGES:
            return False
        return super().has_delete_permission(request, obj)
