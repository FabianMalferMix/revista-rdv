"""El desplegable de acciones ofrece solo lo que el rol podría ejecutar.

Antes, un autor veía las nueve transiciones del flujo aunque ocho fueran inalcanzables
para él contra cualquier pieza y en cualquier estado: seleccionar veinte artículos y
pulsar «Publicar» devolvía veinte avisos de rechazo. El filtro es de comodidad; el
control sigue siendo la guarda de `workflow.perform_transition`, y estas pruebas fijan
ese orden para que quitar el filtro no se lea como abrir un permiso.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from apps.content import workflow
from apps.content.admin import ArticleAdmin, PoemAdmin
from apps.content.models import Article, EditorialStatus, Poem

pytestmark = pytest.mark.django_db
User = get_user_model()

# Las que un autor no podrá disparar jamás, sea cual sea la pieza o su estado.
SOLO_EDITOR = {
    "do_request_changes",
    "do_accept",
    "do_reject",
    "do_schedule",
    "do_publish",
    "do_unpublish",
    "do_archive",
    "do_restore",
}


def _usuario(username, grupo):
    user = User.objects.create_user(username=username, password="x", is_staff=True)
    user.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return User.objects.get(pk=user.pk)  # recarga la caché de permisos


def _peticion(user):
    req = RequestFactory().get("/admin/content/article/")
    req.user = user
    return req


def _acciones(admin_obj, user):
    return set(admin_obj.get_actions(_peticion(user)))


def test_al_autor_solo_le_queda_enviar_a_revision():
    acciones = _acciones(ArticleAdmin(Article, AdminSite()), _usuario("autora", "autor"))
    assert "do_submit" in acciones
    assert acciones & SOLO_EDITOR == set()


def test_la_editora_conserva_las_nueve():
    acciones = _acciones(ArticleAdmin(Article, AdminSite()), _usuario("editora", "editor"))
    assert {f"do_{nombre}" for nombre in workflow.TRANSITIONS} <= acciones


def test_el_filtro_alcanza_tambien_a_los_poemas():
    """Vive en la base compartida: si se declarara por subclase, se olvidaría en una."""
    acciones = _acciones(PoemAdmin(Poem, AdminSite()), _usuario("autora", "autor"))
    assert "do_submit" in acciones
    assert acciones & SOLO_EDITOR == set()


def test_no_se_lleva_por_delante_las_acciones_que_no_son_transiciones():
    """El filtro solo conoce la tabla de transiciones; lo demás no le incumbe.

    Se prueba con una acción propia y no con `delete_selected` porque esa nunca llega
    hasta aquí para un autor: `has_delete_permission` ya la retiró antes por rol.
    """

    class ArticleAdminConExtra(ArticleAdmin):
        actions = [*ArticleAdmin.actions, "exportar"]

        def exportar(self, request, queryset):  # pragma: no cover - no se ejecuta
            pass

    acciones = _acciones(ArticleAdminConExtra(Article, AdminSite()), _usuario("autora", "autor"))
    assert "exportar" in acciones
    assert acciones & SOLO_EDITOR == set()


def test_esconder_la_accion_no_es_lo_que_protege():
    """El control real: aunque se invoque la transición a mano, el servidor la rechaza.

    Si esta prueba se cae, el filtro del desplegable habrá pasado a ser la única defensa
    —que es justo lo que no debe ocurrir—.
    """
    autora = _usuario("autora", "autor")
    articulo = Article.objects.create(
        title="En revisión", slug="en-revision", owner=autora, status=EditorialStatus.IN_REVIEW
    )
    with pytest.raises(PermissionDenied):
        workflow.perform_transition(articulo, "accept", autora)
    articulo.refresh_from_db()
    assert articulo.status == EditorialStatus.IN_REVIEW
