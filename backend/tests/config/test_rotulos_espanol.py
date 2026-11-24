"""El panel se lee en español, incluida la pantalla de bloqueo.

Cada app, cada modelo y cada campo propios llevan su rótulo en español: sin él, Django los
rotula en inglés, y en la ficha de un artículo se leería «EDITORIAL TRANSITIONS», «FROM
STATUS», «Published at» u «Owner». Para un colectivo que trabaja en español es un roce
constante.

Es presentación: por eso estas pruebas miran el rótulo que se LEE y no la configuración que
lo produce.
"""

import ast
import gettext
import json
import re
from datetime import datetime

import pytest
from bs4 import BeautifulSoup
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import CheckConstraint, F, Model, UniqueConstraint
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community.models import NewsletterSubscriber
from apps.content import workflow
from apps.content.models import (
    Article,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialNote,
)
from apps.people.models import Contributor
from apps.reviews.models import Work
from apps.submissions.models import Submission
from tests.factories import admin_form_fields, make_article, make_poem, soup

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
    «People»— y eso es lo que se leería.
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


def _field_names(expression):
    """Los campos que nombra una expresión, también dentro de una función: `Lower("email")`."""
    if isinstance(expression, F):
        return [expression.name]
    return [part.name for part in expression.flatten() if isinstance(part, F)]


def _unique_rules():
    """Cada regla de unicidad propia, con su aviso y los rótulos que ese aviso nombra: los campos
    únicos y las restricciones de unicidad con condición o con expresiones. Las de varios campos
    sin condición son las de los inlines, y las avisa la frase de Django para un dato repetido
    entre sus filas, con los rótulos de sus campos (tests/config/test_panel.py)."""
    for model in _project_models():
        meta = model._meta
        for field in meta.local_concrete_fields:
            if field.unique and not field.primary_key:
                yield (
                    f"{meta.label}.{field.name}",
                    str(field.error_messages["unique"]),
                    [meta.verbose_name, field.verbose_name],
                )
        for constraint in meta.constraints:
            if isinstance(constraint, UniqueConstraint) and (
                constraint.condition or constraint.expressions
            ):
                names = [
                    *constraint.fields,
                    *(
                        name
                        for expression in constraint.expressions
                        for name in _field_names(expression)
                    ),
                ]
                yield (
                    f"{meta.label}.{constraint.name}",
                    str(constraint.violation_error_message),
                    [meta.verbose_name, *(meta.get_field(name).verbose_name for name in names)],
                )


def test_every_unique_field_has_its_own_warning():
    """El aviso de Django para un valor repetido pega el nombre de la pieza y el rótulo del campo
    en una frase en masculino: «Ya existe Artículo con este Dirección.», y el de una restricción
    con condición o con expresiones dice su nombre interno: «No se cumple la restricción
    "uniq_work_isbn".». Cada regla lleva el suyo, que nombra la pieza y el campo: «Ya hay un
    artículo con esta dirección.»."""
    rules = list(_unique_rules())
    names = {name for name, _message, _labels in rules}
    # Control: llega a las direcciones, a la cuenta de quien colabora, a la publicación del
    # colectivo de una obra, al ISBN, que solo es único cuando lo hay, y al correo de quien se
    # suscribe, que lo es sin distinguir mayúsculas.
    assert {
        "content.Article.slug",
        "people.Contributor.user",
        "reviews.Work.publicacion",
        "reviews.Work.uniq_work_isbn",
        "community.NewsletterSubscriber.suscriptor_email_ci",
    } <= names, names
    wrong = sorted(
        f"{name}: «{message}»"
        for name, message, labels in rules
        if "%(" in message or not all(str(label) in message for label in labels)
    )
    assert not wrong, "avisos que no nombran la pieza y su campo: " + ", ".join(wrong)


def test_every_check_constraint_has_its_own_warning():
    """Sin aviso propio, el panel anuncia una restricción incumplida por su nombre interno: «No se
    cumple la restricción "recording_file_or_embed".»."""
    constraints = [
        (model._meta.label, constraint)
        for model in _project_models()
        for constraint in model._meta.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    names = {constraint.name for _label, constraint in constraints}
    # Control: llega a la fuente de un registro y a la fecha de lo publicado.
    assert {"recording_file_or_embed", "content_article_dated_if_public"} <= names, names
    wrong = sorted(
        f"{label}.{constraint.name}: «{message}»"
        for label, constraint in constraints
        for message in [str(constraint.violation_error_message)]
        if "%(" in message or constraint.name in message
    )
    assert not wrong, "restricciones sin aviso propio: " + ", ".join(wrong)


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
        "reviewer_name": "Revisado por",
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
    assert _texts(notes.select("tr.has_original td.field-author_name")) == [
        "editora_dos",
        "editor_test",
        "-",
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


def _post(client, url, form_id, **values):
    """Envía el formulario del panel con sus valores iniciales y los dados, y lo que vuelve."""
    data = admin_form_fields(client.get(url).content, form_id)
    data.update(values)
    response = client.post(url, data)
    assert response.status_code == 200, "el formulario se guardó: no había nada repetido"
    return BeautifulSoup(response.content, "html.parser")


def test_a_repeated_address_says_which_piece_has_it(client, editor):
    make_article(slug="correspondencias", title="Correspondencias")
    client.force_login(editor)
    page = _post(
        client,
        reverse("admin:content_article_add"),
        "article_form",
        title="Correspondencias, otra vez",
        slug="correspondencias",
        body="<p>Otro texto.</p>",
    )
    assert _texts(page.select(".field-slug .errorlist li")) == [
        "Ya hay un artículo con esta dirección."
    ]
    assert "Ya existe" not in page.get_text()


def test_an_account_with_its_contributor_says_so(client, groups):
    """Las cuentas las enlaza el admin: el editor no gestiona cuentas."""
    users = get_user_model().objects
    admin = users.create_user("admin_test", password="pw", is_staff=True)
    admin.groups.add(groups["admin"])
    account = users.create_user("lucia", password="pw", is_staff=True)
    Contributor.objects.create(slug="lucia-prado", display_name="Lucía Prado", user=account)
    client.force_login(admin)
    page = _post(
        client,
        reverse("admin:people_contributor_add"),
        "contributor_form",
        display_name="Lucía P.",
        slug="lucia-p",
        user=str(account.pk),
    )
    assert _texts(page.select(".field-user .errorlist li")) == [
        "Ya hay un colaborador con esta cuenta."
    ]
    assert "Ya existe" not in page.get_text()


def test_a_repeated_isbn_says_a_work_has_it(client, editor):
    Work.objects.create(slug="umbral", title="Umbral", isbn="978-956-9999-01-2")
    client.force_login(editor)
    page = _post(
        client,
        reverse("admin:reviews_work_add"),
        "work_form",
        title="Umbral, segunda edición",
        slug="umbral-segunda-edicion",
        isbn="978-956-9999-01-2",
    )
    assert _texts(page.select(".field-isbn .errorlist li")) == ["Ya hay una obra con este ISBN."]
    assert "uniq_work_isbn" not in str(page)


def test_a_repeated_email_says_there_is_a_subscriber_with_it(client, editor):
    """El correo se compara sin distinguir mayúsculas: es la misma persona."""
    NewsletterSubscriber.objects.create(email="ana@example.com")
    client.force_login(editor)
    page = _post(
        client,
        reverse("admin:community_newslettersubscriber_add"),
        "newslettersubscriber_form",
        email="Ana@Example.com",
    )
    assert _texts(page.select(".errorlist.nonfield li")) == [
        "Ya hay un suscriptor con este correo."
    ]
    assert "suscriptor_email_ci" not in str(page)


def test_a_recording_without_a_source_says_so_once(client, editor):
    client.force_login(editor)
    page = _post(
        client,
        reverse("admin:media_recording_add"),
        "recording_form",
        title="Lectura en el patio",
        slug="lectura-en-el-patio",
    )
    assert _texts(page.select(".errorlist li")) == [
        "Un registro necesita un archivo o un enlace para incrustar."
    ]
    assert "recording_file_or_embed" not in str(page)


def test_the_log_names_each_state_like_the_rest_of_the_panel(client, editor, autor):
    article = make_article(title="Correspondencias", owner=autor)
    workflow.perform_transition(article, "submit", autor)
    workflow.perform_transition(article, "accept", editor)

    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_change", args=[article.pk]))
    log = page.select_one("#content-editorialtransition-content_type-object_id-group")
    rows = sorted(
        _texts(row.select("td.original p, td.field-from_status, td.field-to_status"))
        for row in log.select("tr.has_original")
    )
    assert rows == [
        ["Correspondencias: Borrador → En revisión", "Borrador", "En revisión"],
        ["Correspondencias: En revisión → Aprobado", "En revisión", "Aprobado"],
    ]
    assert "in_review" not in log.get_text()


# El catálogo de textos de los guiones del panel que escribe el proyecto, y su copia compilada,
# la que lee Django.
JS_CATALOG = settings.BASE_DIR / "config" / "locale" / "es" / "LC_MESSAGES" / "djangojs"


def _admin_js_catalog(client, page):
    """El catálogo que carga una página del panel para sus guiones, como lo recibe el navegador."""
    script = client.get(page.select_one('script[src$="/jsi18n/"]')["src"]).content.decode()
    start = script.index("const newcatalog = ") + len("const newcatalog = ")
    return json.JSONDecoder().raw_decode(script, start)[0]


def test_the_double_selector_reads_in_spanish(client, editor):
    """El selector doble de las etiquetas, con sus textos tal como los arma
    admin/js/SelectFilter2.js: el rótulo del campo («etiquetas») en lugar de %s."""
    client.force_login(editor)
    page = soup(client, reverse("admin:content_article_add"))
    label = page.select_one("select#id_tags")["data-field-name"]
    catalog = _admin_js_catalog(client, page)
    texts = {
        "Available %s": "Lista de etiquetas disponibles",
        'Choose %s by selecting them and then select the "Choose" arrow button.': (
            "Para elegir etiquetas, se marcan en esta lista y se pulsa la flecha «Elegir»."
        ),
        "Type into this box to filter down the list of available %s.": (
            "Lo que se escribe en este cuadro filtra la lista de etiquetas disponibles."
        ),
        "Choose all %s": "Elegir todo",
        "Choose selected %s": "Elegir lo marcado",
        "Remove selected %s": "Quitar lo marcado",
        "Chosen %s": "Selección de etiquetas",
        'Remove %s by selecting them and then select the "Remove" arrow button.': (
            "Para quitar etiquetas, se marcan en esta lista y se pulsa la flecha «Quitar»."
        ),
        "Type into this box to filter down the list of selected %s.": (
            "Lo que se escribe en este cuadro filtra la selección de etiquetas."
        ),
        "Remove all %s": "Quitar todo",
    }
    assert {msgid: catalog[msgid].replace("%s", label) for msgid in texts} == texts
    # Bajo la selección, cuando el filtro esconde algo de lo elegido: uno, varios, un millón.
    assert catalog["%s selected option not visible"] == [
        "%s opción elegida no visible",
        "%s opciones elegidas no visibles",
        "%s opciones elegidas no visibles",
    ]
    assert catalog["(click to clear)"] == "(clic para quitar el filtro)"
    assert "%s Disponibles" not in catalog.values()
    # Control: el resto del catálogo sigue siendo el de Django.
    assert catalog["Filter"] == "Filtro"


def _po_catalog(path):
    """Lo que dice un .po, como lo guarda gettext al leer el .mo: cada msgid con su msgstr y, en
    los que tienen plural, cada (msgid, n) con su msgstr[n]."""
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith('"'):  # la continuación de la cadena de arriba
            keyword, text = entries[-1][-1]
            entries[-1][-1] = (keyword, text + ast.literal_eval(line))
        elif line.startswith("msg"):
            keyword, text = line.split(" ", 1)
            if keyword == "msgid":
                entries.append([])
            entries[-1].append((keyword, ast.literal_eval(text)))
    catalog = {}
    for entry in entries:
        fields = dict(entry)
        if "msgid_plural" in fields:
            for keyword, text in entry[2:]:
                catalog[(fields["msgid"], int(keyword.removeprefix("msgstr[")[:-1]))] = text
        else:
            catalog[fields["msgid"]] = fields["msgstr"]
    return catalog


def test_the_compiled_js_catalog_says_what_its_source_says():
    """Django lee el .mo y los textos se cambian en el .po: un .po sin recompilar dejaría en el
    panel los textos de antes. Se rehace con `msgfmt --check-format -o djangojs.mo djangojs.po`."""
    source = _po_catalog(JS_CATALOG.with_suffix(".po"))
    with JS_CATALOG.with_suffix(".mo").open("rb") as compiled:
        copy = gettext.GNUTranslations(compiled)._catalog
    # Control: el .po se lee entero, con su cabecera y con cada forma de un plural.
    assert {"", "Available %s", "(click to clear)", ("%s selected option not visible", 2)} <= set(
        source
    ), source
    assert copy == source


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
    """Sin traducir, sería el rótulo en inglés más visible: lo ve cualquiera que agote los
    intentos en /admin/login/."""
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
