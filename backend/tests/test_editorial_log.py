"""La bitácora editorial sobrevive y no se toca.

Borrar una pieza deja sus movimientos con el título de la pieza y el nombre de quien los hizo, y
borrar la cuenta, también. Ni el modelo ni una consulta directa pueden cambiar o borrar una
entrada. En el panel, una nota lleva como autora a quien la escribe, y las notas ajenas no se
editan ni se borran.
"""

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.content import workflow
from apps.content.models import (
    Article,
    EditorialNote,
    EditorialTransition,
    ImmutableLogError,
)
from apps.content.models import (
    EditorialStatus as S,
)
from apps.content.tasks import publish_due_items

pytestmark = pytest.mark.django_db


def _article(owner, title="Correspondencias"):
    return Article.objects.create(
        slug="correspondencias", title=title, body="<p>x</p>", owner=owner
    )


def _log(content_type, pk):
    entries = EditorialTransition.objects.filter(content_type=content_type, object_id=pk)
    return list(entries.order_by("pk").values_list("item_title", "actor_name", "to_status"))


def _form_data(page, form_id):
    """Lo que enviaría el formulario del panel tal como se dibuja."""
    form = BeautifulSoup(page.content, "html.parser").select_one(f"form#{form_id}")
    data = {}
    for field in form.select("input[name], textarea[name], select[name]"):
        if field.get("type") in {"submit", "checkbox", "file"} or field["name"].startswith("_"):
            continue
        if field.name == "select":
            chosen = [option["value"] for option in field.select("option[selected]")]
            if field.has_attr("multiple"):
                if chosen:
                    data[field["name"]] = chosen
                continue
            data[field["name"]] = chosen[0] if chosen else ""
        else:
            data[field["name"]] = field.text if field.name == "textarea" else field.get("value", "")
    return data


def test_deleting_a_published_text_keeps_its_log(client, editor):
    article = _article(editor)
    for step in ("submit", "accept", "publish"):
        workflow.perform_transition(article, step, editor)
    pk, content_type = article.pk, ContentType.objects.get_for_model(Article)
    client.force_login(editor)
    client.post(reverse("admin:content_article_delete", args=[pk]), {"post": "yes"})
    assert not Article.objects.filter(pk=pk).exists()
    assert _log(content_type, pk) == [
        ("Correspondencias", "editor_test", S.IN_REVIEW),
        ("Correspondencias", "editor_test", S.APPROVED),
        ("Correspondencias", "editor_test", S.PUBLISHED),
    ]


def test_a_deleted_account_leaves_its_name_in_the_log(editor):
    article = _article(editor)
    workflow.perform_transition(article, "submit", editor)
    editor.delete()
    entry = article.transitions.get()
    assert entry.actor is None and entry.actor_name == "editor_test"


def test_the_scheduled_publication_is_signed_by_the_system(editor):
    article = _article(editor)
    for step in ("submit", "accept"):
        workflow.perform_transition(article, step, editor)
    workflow.perform_transition(
        article, "schedule", editor, when=timezone.now() + timezone.timedelta(minutes=1)
    )
    Article.objects.filter(pk=article.pk).update(published_at=timezone.now())
    publish_due_items()
    assert article.transitions.latest("created_at").actor_name == "Sistema"


def test_an_entry_cannot_be_changed_or_deleted(editor):
    article = _article(editor)
    workflow.perform_transition(article, "submit", editor)
    entry = article.transitions.get()
    entry.note = "otra cosa"
    with pytest.raises(ImmutableLogError):
        entry.save()
    with pytest.raises(ImmutableLogError):
        entry.delete()
    for change in (lambda q: q.update(note="otra cosa"), lambda q: q._raw_delete(q.db)):
        with pytest.raises(DatabaseError), transaction.atomic():
            change(EditorialTransition.objects.filter(pk=entry.pk))
    assert EditorialTransition.objects.get(pk=entry.pk).note == ""


def test_a_note_is_signed_by_whoever_writes_it_and_others_cannot_touch_it(client, editor, groups):
    other = get_user_model().objects.create_user("editora_dos", password="pw", is_staff=True)
    other.groups.add(groups["editor"])
    article = _article(editor)
    url = reverse("admin:content_article_change", args=[article.pk])

    client.force_login(editor)
    data = _form_data(client.get(url), "article_form")
    prefix = next(k for k in data if k.endswith("-TOTAL_FORMS") and "editorialnote" in k)[
        : -len("-TOTAL_FORMS")
    ]
    data[f"{prefix}-0-body"] = "Falta la fecha del recital."
    client.post(url, data)
    note = EditorialNote.objects.get()
    assert (note.author, note.body) == (editor, "Falta la fecha del recital.")

    client.force_login(other)
    data = _form_data(client.get(url), "article_form")
    data[f"{prefix}-0-body"] = "Reescrita por otra persona."
    data[f"{prefix}-0-DELETE"] = "on"
    data[f"{prefix}-1-body"] = "La fecha está en el afiche."
    client.post(url, data)
    assert list(EditorialNote.objects.order_by("pk").values_list("author__username", "body")) == [
        ("editor_test", "Falta la fecha del recital."),
        ("editora_dos", "La fecha está en el afiche."),
    ]

    client.force_login(editor)
    data = _form_data(client.get(url), "article_form")
    data[f"{prefix}-0-body"] = "Falta la fecha y el lugar del recital."
    client.post(url, data)
    assert EditorialNote.objects.get(pk=note.pk).body == "Falta la fecha y el lugar del recital."


def test_another_persons_note_looks_locked_and_says_who_can_change_it(client, editor, groups):
    other = get_user_model().objects.create_user("editora_dos", password="pw", is_staff=True)
    other.groups.add(groups["editor"])
    article = _article(editor)
    item = {"content_type": ContentType.objects.get_for_model(Article), "object_id": article.pk}
    EditorialNote.objects.create(**item, author=other, body="Falta la fecha del recital.")
    EditorialNote.objects.create(**item, author=editor, body="La fecha está en el afiche.")

    client.force_login(editor)
    page = client.get(reverse("admin:content_article_change", args=[article.pk]))
    soup = BeautifulSoup(page.content, "html.parser")
    boxes = {box.get_text(strip=True): box for box in soup.select("textarea[name$='-body']")}
    theirs, mine = boxes["Falta la fecha del recital."], boxes["La fecha está en el afiche."]
    assert theirs.has_attr("disabled")
    notice = soup.find(id=theirs["aria-describedby"])
    assert notice.get_text(strip=True) == "Solo la puede cambiar quien la escribió"
    assert not mine.has_attr("disabled") and not mine.has_attr("aria-describedby")
    assert soup.get_text().count("Solo la puede cambiar quien la escribió") == 1


def test_the_migration_copies_title_and_actor_into_existing_entries(migrate):
    old = migrate("content", "0016_search_config_and_generated_vector")
    user = old.get_model("auth", "User").objects.create(username="editora")
    article = old.get_model("content", "Article").objects.create(
        slug="pieza", title="Pieza vieja", body="Texto", reading_time=1
    )
    content_type, _ = old.get_model("contenttypes", "ContentType").objects.get_or_create(
        app_label="content", model="article"
    )
    Transition = old.get_model("content", "EditorialTransition")
    for actor in (user, None):
        Transition.objects.create(
            content_type=content_type,
            object_id=article.pk,
            from_status="draft",
            to_status="in_review",
            actor=actor,
        )

    new = migrate("content", "0017_editorial_log_survives")
    entries = new.get_model("content", "EditorialTransition").objects.order_by("pk")
    assert list(entries.values_list("item_title", "actor_name")) == [
        ("Pieza vieja", "editora"),
        ("Pieza vieja", ""),
    ]
    with pytest.raises(DatabaseError), transaction.atomic():
        entries.update(note="otra cosa")
