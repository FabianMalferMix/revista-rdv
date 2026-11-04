"""Cada estático que pide el sitio existe.

La suite y el desarrollo corren con DEBUG=1: un `{% static %}` hacia un archivo que no existe da
ahí un 404 silencioso del recurso. En producción, el manifiesto de WhiteNoise lanza ValueError y
la página entera responde 500. Estas pruebas buscan cada referencia —en las plantillas y en los
Media de los formularios y del panel— y pintan una página de cada tipo con el almacenamiento de
producción, también las que solo piden un guion cuando hay datos, y las que lo nombran desde
Python (`static()`: el icono y la lámina de la portada).
"""

import importlib
import re
from importlib.util import find_spec
from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.forms import BaseForm, Media
from django.template import loader
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.content.models import Collection, EditorialStatus
from apps.people.models import Contributor
from tests.factories import make_event, make_publication, make_recording, publish

STATIC_TAG = re.compile(r"""{%\s*static\s+(['"])(?P<path>[^'"]+)\1""")
PROJECT_APPS = [c for c in apps.get_app_configs() if c.name.startswith("apps.")]


def _missing(paths):
    """Las rutas relativas a STATIC_URL que ningún buscador de estáticos encuentra."""
    return sorted(
        p for p in paths if not p.startswith(("http:", "https:", "/")) and not finders.find(p)
    )


def _media_paths(media):
    rutas = [*media._js, *(ruta for rutas in media._css.values() for ruta in rutas)]
    return [getattr(ruta, "path", ruta) for ruta in rutas]


def test_every_static_tag_in_the_templates_points_to_a_file():
    carpetas = [
        settings.BASE_DIR / "templates",
        *(Path(c.path) / "templates" for c in PROJECT_APPS),
    ]
    referencias = {}
    for carpeta in carpetas:
        for plantilla in carpeta.rglob("*.html"):
            for match in STATIC_TAG.finditer(plantilla.read_text(encoding="utf-8")):
                referencias.setdefault(match["path"], plantilla.name)
    assert len(referencias) >= 10, "la expresión dejó de encontrar las referencias"
    faltan = _missing(referencias)
    assert not faltan, [f"{ruta} (en {referencias[ruta]})" for ruta in faltan]


def _project_forms():
    for app in PROJECT_APPS:
        if find_spec(f"{app.name}.forms"):
            importlib.import_module(f"{app.name}.forms")
    vistas, pendientes = set(), [BaseForm]
    while pendientes:
        for sub in pendientes.pop().__subclasses__():
            if sub not in vistas:
                vistas.add(sub)
                pendientes.append(sub)
    return [f for f in vistas if f.__module__.startswith(("apps.", "config."))]


@pytest.mark.django_db
def test_the_media_of_the_forms_and_the_panel_point_to_files(django_user_model):
    """Los Media de cada formulario del sitio y, en el panel, los de cada ficha, su formulario
    y sus inlines (la hoja de las notas editoriales, el editor de texto)."""
    peticion = RequestFactory().get("/admin/")
    peticion.user = django_user_model.objects.create_superuser("estaticos", "e@example.com", "x")
    medios = [
        sum((campo.widget.media for campo in form.base_fields.values()), Media())
        for form in _project_forms()
    ]
    for model_admin in admin.site._registry.values():
        medios += [model_admin.media, model_admin.get_form(peticion)().media]
        for inline in model_admin.get_inline_instances(peticion):
            medios += [inline.media, inline.get_formset(peticion)().media]
    rutas = {ruta for media in medios for ruta in _media_paths(media)}
    assert "admin/editorial_notes.css" in rutas and "admin/richtext_init.js" in rutas
    assert not _missing(rutas)


@pytest.fixture
def production_statics(tmp_path):
    """El almacenamiento de producción, con collectstatic en un directorio temporal. Con
    DEBUG=0 cada {% static %} pasa por el manifiesto, como en el servidor."""
    estaticos = {"BACKEND": "config.staticfiles.VendoredStaticFilesStorage"}
    with override_settings(
        DEBUG=False, STATIC_ROOT=tmp_path, STORAGES={**settings.STORAGES, "staticfiles": estaticos}
    ):
        call_command("collectstatic", interactive=False, verbosity=0)
        yield


@pytest.fixture
def one_of_each(make_article, make_poem):
    """Una pieza de cada tipo, y lo que hace que la portada pida sus guiones: dos registros
    destacados (la tirada), más integrantes de las que caben en el teléfono (el relevo) y dos
    publicaciones (el estante)."""
    for n in range(5):
        Contributor.objects.create(
            slug=f"voz-{n}", display_name=f"Voz {n}", is_member=True, active=True, position=n
        )
    for n in range(2):
        make_recording(featured=True, position=n)
        make_publication()
    return {
        "texto": publish(make_article(slug="texto-estatico")).get_absolute_url(),
        "poema": publish(make_poem(slug="poema-estatico")).get_absolute_url(),
        "actividad": reverse("agenda:event_detail", args=[make_event().slug]),
        "registro": reverse("media:recording_detail", args=["registro-0"]),
        "publicacion": reverse("showcase:publication_detail", args=["pub-0"]),
        "integrante": reverse("people:member_detail", args=["voz-0"]),
        "coleccion": Collection.objects.create(
            slug="coleccion-estatica", title="Colección", status=EditorialStatus.PUBLISHED
        ).get_absolute_url(),
    }


@pytest.mark.django_db
def test_every_kind_of_page_renders_with_the_production_static_storage(
    client, django_user_model, production_statics, one_of_each
):
    portada = client.get(reverse("content:home")).content.decode()
    for guion in ("registros", "integrantes", "estante"):
        assert re.search(rf"/static/js/{guion}\.[0-9a-f]{{12}}\.js", portada), guion
    assert re.search(r"/static/img/portada/lamina-ancha-1440\.[0-9a-f]{12}\.jpg", portada)
    paginas = [
        *one_of_each.values(),
        reverse("showcase:dossier"),
        reverse("content:search") + "?q=texto",
        reverse("submissions:submit"),
        reverse("admin:login"),
    ]
    for url in paginas:
        assert client.get(url).status_code == 200, url
    assert client.get("/no-existe/").status_code == 404
    assert re.search(r"\.[0-9a-f]{12}\.ico$", client.get("/favicon.ico")["Location"])
    assert "</html>" in loader.render_to_string("500.html")
    client.force_login(django_user_model.objects.create_superuser("panel", "p@example.com", "x"))
    assert client.get(reverse("admin:content_article_add")).status_code == 200
