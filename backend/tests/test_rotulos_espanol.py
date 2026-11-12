"""El panel se lee en español, incluida la pantalla de bloqueo.

Convivían «MEDIOS» y «ENVÍOS» (con verbose_name) con «CONTENT», «PEOPLE», «REVIEWS» y
«COMMUNITY» sin traducir, y los modelos de relación y auditoría tampoco lo tenían: en la
ficha de un artículo se leía «EDITORIAL TRANSITIONS», «FROM STATUS», «Published at»,
«Owner». El patrón se entendía —se tradujo lo que el equipo abre a diario— pero para un
colectivo que trabaja en español es un roce constante.

Nada se comportaba mal: es presentación. Por eso estas pruebas miran el rótulo que se LEE
y no la configuración que lo produce.
"""

import re
from datetime import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.content.models import (
    Article,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialNote,
)
from apps.submissions.models import Submission
from tests.factories import make_article, make_poem, soup

pytestmark = pytest.mark.django_db

# Rótulo esperado de cada app propia, tal como se lee en el índice del panel.
ROTULOS = {
    "content": "Contenido",
    "people": "Personas",
    "reviews": "Obras reseñadas",
    "community": "Comunidad",
    "media": "Medios",
    "submissions": "Envíos",
    "showcase": "Colectivo",
    "agenda": "Agenda y trayectoria",
}
APPS_PROPIAS = list(ROTULOS)


@pytest.mark.parametrize(("etiqueta", "esperado"), ROTULOS.items())
def test_cada_app_propia_tiene_rotulo_en_espanol(etiqueta, esperado):
    """El encabezado de sección del índice del panel.

    Sin `verbose_name`, Django usa el nombre del módulo capitalizado —«Content»,
    «People»— y eso es lo que se leía.
    """
    assert apps.get_app_config(etiqueta).verbose_name == esperado


def test_ningun_modelo_propio_se_muestra_con_su_nombre_en_ingles():
    """Sin verbose_name, Django parte el CamelCase: «editorial transition».

    Se comprueba sobre los modelos REGISTRADOS en el admin, que son los que alguien lee.
    """
    from django.contrib.admin.sites import site

    sospechosos = []
    checked = 0
    for modelo in site._registry:
        if modelo._meta.app_label not in APPS_PROPIAS:
            continue
        checked += 1
        nombre = str(modelo._meta.verbose_name)
        # El nombre por defecto es el CamelCase separado y en minúsculas.
        defecto = re.sub(r"(?<!^)(?=[A-Z])", " ", modelo.__name__).lower()
        if nombre == defecto:
            sospechosos.append(f"{modelo._meta.label} -> «{nombre}»")
    assert checked >= 10, "control: el panel dejó de registrar los modelos propios"
    assert not sospechosos, "modelos sin rótulo propio: " + ", ".join(sospechosos)


@pytest.mark.parametrize(
    "modelo_label,campo,esperado",
    [
        ("content.Article", "published_at", "fecha de publicación"),
        ("content.Article", "owner", "dueño"),
        ("content.Poem", "published_at", "fecha de publicación"),
        ("content.EditorialTransition", "from_status", "estado de origen"),
        ("content.EditorialTransition", "to_status", "estado de destino"),
        ("content.EditorialTransition", "actor", "actor"),
    ],
)
def test_los_campos_de_la_ficha_se_leen_en_espanol(modelo_label, campo, esperado):
    modelo = apps.get_model(modelo_label)
    assert str(modelo._meta.get_field(campo).verbose_name) == esperado


def test_la_bitacora_se_titula_en_espanol():
    from apps.content.models import EditorialTransition

    assert str(EditorialTransition._meta.verbose_name_plural) == "transiciones editoriales"


def _project_models():
    """Los modelos de las apps del proyecto, estén o no registrados en el panel. Las tablas
    intermedias que Django crea por su cuenta no entran: no tienen clase propia que rotular."""
    models = [
        model
        for config in apps.get_app_configs()
        if config.name.startswith("apps.")
        for model in config.get_models()
    ]
    labels = {model._meta.label for model in models}
    # Control: el recorrido llega a todas las apps con modelos y a los modelos que el panel
    # no registra por separado (las notas y los puentes de las colecciones van dentro de otra
    # ficha; la marca de desarrollo no está en el panel).
    assert {model._meta.app_label for model in models} >= {*APPS_PROPIAS, "devtools"}, labels
    assert {
        "content.EditorialNote",
        "content.CollectionArticle",
        "content.CollectionPoem",
        "devtools.DevelopmentMarker",
    } <= labels, labels
    return models


def test_every_project_field_has_its_own_label():
    """Sin `verbose_name`, el panel rotula el campo con su nombre en inglés: «Author name»,
    «Created at». Vale el rótulo escrito en el campo o en la clase abstracta de la que viene.
    El `id` que Django añade solo no se enseña en ninguna ficha."""
    fields = [
        (model._meta.label, field)
        for model in _project_models()
        for field in [*model._meta.local_concrete_fields, *model._meta.local_many_to_many]
        if not field.auto_created
    ]
    names = {f"{label}.{field.name}" for label, field in fields}
    # Control: llega a los campos de cada clase: los propios, los heredados de una clase
    # abstracta, el que calcula la base y las relaciones de varios a varios.
    assert {
        "submissions.Submission.author_email",
        "content.EditorialNote.body",
        "content.Article.created_at",
        "content.Article.status",
        "content.Article.search_vector",
        "content.Article.tags",
    } <= names, names
    unlabelled = sorted(
        f"{label}.{field.name}"
        for label, field in fields
        if "verbose_name" not in field.deconstruct()[3]
    )
    assert not unlabelled, "campos sin rótulo propio: " + ", ".join(unlabelled)


def test_every_project_model_has_its_own_names():
    """Sin nombre propio, Django parte el nombre de la clase: «editorial note», y en plural
    le añade una «s»."""
    unnamed = sorted(
        model._meta.label
        for model in _project_models()
        if not {"verbose_name", "verbose_name_plural"} <= set(model._meta.original_attrs)
    )
    assert not unnamed, "modelos sin nombre propio: " + ", ".join(unnamed)


def test_every_project_model_names_its_rows():
    """Sin `__str__` propio, Django nombra la fila «EditorialNote object (13)», y eso es lo que
    se lee sobre cada nota en la ficha de un artículo y en la confirmación de un borrado."""
    nameless = sorted(
        model._meta.label for model in _project_models() if model.__str__ is Model.__str__
    )
    assert not nameless, "modelos que se nombran con el texto de Django: " + ", ".join(nameless)


def _field_labels(page):
    """El rótulo que se lee en cada fila de la ficha, por el campo que rotula."""
    labels = {}
    for row in page.select("fieldset .form-row"):
        name = next(c.removeprefix("field-") for c in row["class"] if c.startswith("field-"))
        labels[name] = row.select_one("label").get_text(strip=True).removesuffix(":")
    return labels


def test_the_submission_record_reads_in_spanish(client, editor):
    submission = Submission.objects.create(
        author_name="Ana",
        author_email="ana@example.com",
        type=Submission.Type.RESENA,
        title="Una propuesta",
        body="El texto de la propuesta.",
    )
    client.force_login(editor)
    page = soup(client, reverse("admin:submissions_submission_change", args=[submission.pk]))
    assert _field_labels(page) == {
        "notes": "Notas internas",
        "call": "Convocatoria",
        "author_name": "Remitente",
        "author_email": "Correo de contacto",
        "type": "Tipo de propuesta",
        "title": "Título",
        "body": "Descripción o texto",
        "archivo": "Archivo adjunto",
        "status": "Estado",
        "reviewer": "Revisado por",
        "resolved_at": "Resuelto el",
        "created_at": "Recibido el",
    }


def _texts(elements):
    return [" ".join(element.get_text().split()) for element in elements]


def test_editorial_notes_read_in_spanish_and_say_who_wrote_them_and_when(client, editor, groups):
    users = get_user_model().objects
    other = users.create_user("editora_dos", password="pw", is_staff=True)
    other.groups.add(groups["editor"])
    gone = users.create_user("editora_ida", password="pw", is_staff=True)
    article = make_article(owner=editor)
    item = {"content_type": ContentType.objects.get_for_model(Article), "object_id": article.pk}
    for author, body, written in [
        # A las 22:30 de Santiago ya es el día siguiente en UTC: la fila dice el de Santiago.
        (other, "Falta la fecha del recital.", datetime(2026, 11, 10, 22, 30)),
        (editor, "La fecha está en el afiche.", datetime(2026, 11, 11, 9, 40)),
        (gone, "Lo reviso el lunes.", datetime(2026, 11, 12, 8, 0)),
    ]:
        note = EditorialNote.objects.create(**item, author=author, body=body)
        # `created_at` se pone sola al crear la nota: se fija después, en la hora de Santiago.
        EditorialNote.objects.filter(pk=note.pk).update(created_at=timezone.make_aware(written))
    gone.delete()  # su nota se queda, sin autor

    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_change", args=[article.pk]))
    notes = page.select_one("#content-editorialnote-content_type-object_id-group")
    assert _texts(notes.select("thead th")) == ["", "Nota", "Autor", "Fecha", "¿Eliminar?"]
    assert _texts(notes.select("tr.has_original td.original p")) == [
        "Nota de editora_dos, 10 de noviembre de 2026",
        "Nota de editor_test, 11 de noviembre de 2026",
        "Nota de una cuenta borrada, 12 de noviembre de 2026",
    ]


def test_collection_rows_read_their_position_and_title(client, editor):
    collection = Collection.objects.create(slug="cuaderno", title="Cuaderno de otoño")
    CollectionArticle.objects.create(
        collection=collection, article=make_article(title="Correspondencias"), position=1
    )
    CollectionPoem.objects.create(collection=collection, poem=make_poem(title="Arena"), position=2)

    client.force_login(editor)
    page = soup(client, reverse("admin:content_collection_change", args=[collection.pk]))
    rows = {
        group: _texts(page.select(f"#{group} tr.has_original td.original p"))
        for group in ("collectionarticle_set-group", "collectionpoem_set-group")
    }
    assert rows == {
        "collectionarticle_set-group": ["1. Correspondencias"],
        "collectionpoem_set-group": ["2. Arena"],
    }


def _pantalla_de_bloqueo(client):
    """Lo que ve quien falla la clave del panel más veces de las que admite axes."""
    from axes.utils import reset
    from django.urls import reverse

    reset()
    for _ in range(3):
        respuesta = client.post(reverse("admin:login"), {"username": "quien", "password": "mal"})
    reset()
    assert respuesta.status_code == 429
    return respuesta.content.decode()


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=2)
def test_la_pantalla_de_bloqueo_esta_en_espanol(client):
    """El rótulo sin traducir más visible: lo ve cualquiera que llegue a /admin/login/."""
    html = _pantalla_de_bloqueo(client)
    assert "Demasiados intentos fallidos" in html
    assert "Account locked" not in html


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=2)
def test_la_pantalla_de_bloqueo_no_revela_el_temporizador(client):
    """No decir cuánto falta ni cuántos intentos quedaban: calibraría a quien prueba claves."""
    html = _pantalla_de_bloqueo(client).lower()
    assert "demasiados intentos fallidos" in html
    for pista in ("1 hora", "60 minutos", "intentos restantes", "5 intentos"):
        assert pista not in html
