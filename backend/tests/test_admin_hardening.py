"""Endurecimiento del panel editorial (hallazgos S-11, S-12 y permisos que no componían).

Los tres tenían en común que el modelo de permisos del panel decidía por su cuenta y se
desentendía del de Django: retirar un permiso a mano no surtía efecto, un rol bajo podía
enumerar cuentas ajenas, y el despliegue restauraba en silencio lo que se hubiera
ajustado.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import RequestFactory

from apps.content.admin import ArticleAdmin
from apps.content.models import Article
from apps.media.admin import MediaAssetAdmin
from apps.media.models import MediaAsset

pytestmark = pytest.mark.django_db
User = get_user_model()


def _permission(dotted):
    app_label, codename = dotted.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def _reloaded(user):
    return User.objects.get(pk=user.pk)  # vacía la caché de permisos


def _peticion(user):
    req = RequestFactory().get("/admin/")
    req.user = user
    return req


# ── S-11: uploaded_by no es editable ni enumera cuentas ───


def test_uploaded_by_es_readonly(editor):
    admin_obj = MediaAssetAdmin(MediaAsset, AdminSite())
    assert "uploaded_by" in admin_obj.get_readonly_fields(_peticion(editor))


def test_uploaded_by_se_asigna_solo_a_quien_sube(autor):
    admin_obj = MediaAssetAdmin(MediaAsset, AdminSite())
    asset = MediaAsset(alt_text="foto")
    admin_obj.save_model(_peticion(autor), asset, form=None, change=False)
    assert asset.uploaded_by == autor


def test_no_se_reasigna_la_autoria_existente(autor, editor):
    admin_obj = MediaAssetAdmin(MediaAsset, AdminSite())
    asset = MediaAsset(alt_text="foto", uploaded_by=autor)
    admin_obj.save_model(_peticion(editor), asset, form=None, change=True)
    assert asset.uploaded_by == autor


# ── Los permisos del panel COMPONEN con los de Django ─────


def test_revocar_el_permiso_de_modelo_surte_efecto(groups, editor):
    """Antes, `has_change_permission` decidía solo por pertenencia al grupo: quitarle
    `content.change_article` a alguien del grupo editor no cambiaba nada."""
    admin_obj = ArticleAdmin(Article, AdminSite())
    groups["editor"].permissions.remove(
        _permission("content.change_article"), _permission("content.delete_article")
    )
    editor = _reloaded(editor)
    art = Article.objects.create(slug="a", title="A", owner=editor)
    assert admin_obj.has_change_permission(_peticion(editor), art) is False
    assert admin_obj.has_delete_permission(_peticion(editor), art) is False


def test_un_editor_con_su_permiso_sigue_pudiendo(editor):
    """La composición no puede romper el caso normal."""
    admin_obj = ArticleAdmin(Article, AdminSite())
    art = Article.objects.create(slug="b", title="B")
    assert admin_obj.has_change_permission(_peticion(editor), art) is True
    assert admin_obj.has_delete_permission(_peticion(editor), art) is True


def test_un_autor_con_permiso_no_puede_borrar(autor):
    """El borrado sigue reservado a editores aunque tenga el permiso de modelo."""
    admin_obj = ArticleAdmin(Article, AdminSite())
    autor.user_permissions.add(_permission("content.delete_article"))
    autor = _reloaded(autor)
    art = Article.objects.create(slug="c", title="C", owner=autor)
    assert admin_obj.has_delete_permission(_peticion(autor), art) is False


# ── S-12: setup_groups no revierte ajustes manuales ───────


def test_setup_groups_no_restaura_un_permiso_retirado_a_mano():
    """El entrypoint lo ejecuta en CADA arranque: con `.set()`, un permiso retirado tras
    un incidente reaparecía en el siguiente despliegue, en silencio."""
    call_command("setup_groups", verbosity=0)
    editor = Group.objects.get(name="editor")
    perm = Permission.objects.get(
        content_type__app_label="submissions", codename="delete_submission"
    )
    editor.permissions.remove(perm)

    call_command("setup_groups", verbosity=0)  # simula el siguiente despliegue

    assert perm not in editor.permissions.all(), "el despliegue restauró el permiso retirado"


def test_setup_groups_sigue_sembrando_los_permisos():
    call_command("setup_groups", verbosity=0)
    for nombre in ["admin", "editor", "autor"]:
        assert Group.objects.get(name=nombre).permissions.exists()


def test_reset_explicito_si_reemplaza():
    """La vía destructiva sigue disponible, pero hay que pedirla."""
    call_command("setup_groups", verbosity=0)
    editor = Group.objects.get(name="editor")
    ajeno = Permission.objects.filter(content_type__app_label="auth").first()
    editor.permissions.add(ajeno)

    call_command("setup_groups", "--reset", verbosity=0)

    assert ajeno not in editor.permissions.all()
