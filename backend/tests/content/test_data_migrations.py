"""Las migraciones de datos de los textos, probadas con filas.

Las entradas de la bitácora editorial pasan a apuntar a su texto por el enlace genérico (0004),
y al deshacer esa migración, las que apuntan a un texto vuelven a él. Las páginas legales que
faltan se crean (0007), la política de privacidad sembrada toma el texto vigente (0010), y las
de cookies y de privacidad que conservan el texto anterior pasan al que nombra los reproductores
de video (0024), así que una base que ya migró termina igual que una nueva; una página editada
en el panel se conserva. Cada prueba crea con los modelos de entonces las filas que la migración
transforma, migra y comprueba qué quedó, con el fixture `migrate` de `conftest.py`.

La migración que corrige los textos antes de su restricción se prueba en
`test_constraint_migrations.py`, y la que copia el título y la firma en las entradas de la
bitácora, en `test_editorial_log.py`.
"""

import importlib

from apps.content import legal


def _editorial_entries(models, article, **link):
    """Una transición y una nota de `article`, con el enlace genérico `link` si se da."""
    transition = models.get_model("content", "EditorialTransition").objects.create(
        article=article, from_status="draft", to_status="in_review", **link
    )
    note = models.get_model("content", "EditorialNote").objects.create(
        article=article, body="Falta la bajada.", **link
    )
    return {"EditorialTransition": transition.pk, "EditorialNote": note.pk}


def test_each_editorial_entry_points_to_its_article_through_the_generic_link(migrate):
    old = migrate("content", "0003_editorial_generic_schema")
    Article = old.get_model("content", "Article")
    first = Article.objects.create(slug="primera", title="Primera", body="Texto")
    second = Article.objects.create(slug="segunda", title="Segunda", body="Texto")
    # Dos entradas de la misma pieza: el enlace sale de la pieza, no del número de la entrada.
    entries = [(_editorial_entries(old, article), article) for article in (first, second, second)]

    new = migrate("content", "0004_editorial_generic_data")
    article_type = new.get_model("contenttypes", "ContentType").objects.get(
        app_label="content", model="article"
    )
    for name in ("EditorialTransition", "EditorialNote"):
        links = {
            pk: (content_type, object_id)
            for pk, content_type, object_id in new.get_model("content", name).objects.values_list(
                "pk", "content_type_id", "object_id"
            )
        }
        assert links == {pks[name]: (article_type.pk, article.pk) for pks, article in entries}


def test_undoing_the_generic_link_gives_the_article_entries_their_article_back(migrate):
    new = migrate("content", "0004_editorial_generic_data")
    Article = new.get_model("content", "Article")
    first = Article.objects.create(slug="primera", title="Primera", body="Texto")
    second = Article.objects.create(slug="segunda", title="Segunda", body="Texto")
    ContentType = new.get_model("contenttypes", "ContentType")
    article_type, _ = ContentType.objects.get_or_create(app_label="content", model="article")
    poem_type, _ = ContentType.objects.get_or_create(app_label="content", model="poem")
    of_the_second = _editorial_entries(new, first, content_type=article_type, object_id=second.pk)
    of_a_poem = _editorial_entries(new, first, content_type=poem_type, object_id=second.pk)

    back = migrate("content", "0003_editorial_generic_schema")
    for name in ("EditorialTransition", "EditorialNote"):
        articles = dict(back.get_model("content", name).objects.values_list("pk", "article_id"))
        assert articles == {of_the_second[name]: second.pk, of_a_poem[name]: first.pk}


def test_the_missing_legal_pages_are_created_and_an_edited_one_is_kept(migrate):
    old = migrate("content", "0006_alter_article_owner_poem_collectionpoem_and_more")
    Page = old.get_model("content", "Page")
    Page.objects.all().delete()
    edited = "<p>Términos revisados por la abogada del colectivo.</p>"
    Page.objects.create(slug="terminos", title="Términos", body=edited, status="published")

    new = migrate("content", "0007_legal_pages")
    pages = {
        page.slug: (page.title, page.body, page.status)
        for page in new.get_model("content", "Page").objects.all()
    }
    current = legal.pages()
    assert pages == {
        "privacidad": (current["privacidad"].title, current["privacidad"].body, "published"),
        "cookies": (current["cookies"].title, current["cookies"].body, "published"),
        "terminos": ("Términos", edited, "published"),
    }


def _privacy_policy(models, body=None):
    """El cuerpo de la política de privacidad; si se da `body`, antes se lo pone."""
    Page = models.get_model("content", "Page")
    if body is not None:
        Page.objects.update_or_create(
            slug="privacidad",
            defaults={"title": "Política de privacidad", "body": body, "status": "published"},
        )
    return Page.objects.get(slug="privacidad").body


def test_the_seeded_privacy_policy_gets_the_current_text_and_an_edited_one_is_kept(migrate):
    seeded = (
        "<p>Esta política describe cómo el colectivo trata los datos personales, conforme a la "
        "Ley N.º 19.628 sobre protección de la vida privada (Chile).</p>"
    )
    _privacy_policy(migrate("content", "0009_search_vector_triggers"), seeded)
    new = migrate("content", "0010_privacy_ley_21719")
    assert _privacy_policy(new) == legal.pages()["privacidad"].body

    edited = "<p>Conforme a las leyes 19.628 y 21.719, según la revisión de la abogada.</p>"
    _privacy_policy(migrate("content", "0009_search_vector_triggers"), edited)
    new = migrate("content", "0010_privacy_ley_21719")
    assert _privacy_policy(new) == edited


_POLICIES = ("cookies", "privacidad")


def _previous_policies():
    """El texto de las políticas en una base que ya migró, el que les dieron 0007 y 0010."""
    return importlib.import_module(
        "apps.content.migrations.0024_legal_pages_name_the_players"
    ).PREVIOUS_BODIES


def _policies(models, bodies=None):
    """El cuerpo de las políticas de cookies y de privacidad; si se dan `bodies`, antes se los
    pone."""
    Page = models.get_model("content", "Page")
    for slug, body in (bodies or {}).items():
        Page.objects.update_or_create(
            slug=slug,
            defaults={"title": legal.pages()[slug].title, "body": body, "status": "published"},
        )
    return dict(Page.objects.filter(slug__in=_POLICIES).values_list("slug", "body"))


def test_a_database_that_already_migrated_ends_with_the_policies_of_a_new_one(migrate):
    previous = _previous_policies()
    current = {slug: legal.pages()[slug].body for slug in _POLICIES}
    # Control: el texto anterior no es el vigente, o las dos bases coincidirían sin migrar nada.
    assert set(previous) == set(_POLICIES)
    assert [slug for slug in _POLICIES if previous[slug] == current[slug]] == []

    _policies(migrate("content", "0023_body_images"), previous)
    already_migrated = _policies(migrate("content", "0024_legal_pages_name_the_players"))

    before_legal = migrate("content", "0006_alter_article_owner_poem_collectionpoem_and_more")
    before_legal.get_model("content", "Page").objects.all().delete()
    new = _policies(migrate("content", "0024_legal_pages_name_the_players"))

    assert already_migrated == new == current


def test_a_policy_edited_in_the_panel_keeps_its_text(migrate):
    previous = _previous_policies()
    for edited, seeded in (("cookies", "privacidad"), ("privacidad", "cookies")):
        # Con un párrafo más ya es una página editada: la migración compara el texto entero, no
        # si empieza por el anterior o lo contiene.
        bodies = {
            edited: f"{previous[edited]}\n<p>Revisado por la abogada del colectivo.</p>",
            seeded: previous[seeded],
        }
        _policies(migrate("content", "0023_body_images"), bodies)
        assert _policies(migrate("content", "0024_legal_pages_name_the_players")) == {
            edited: bodies[edited],
            seeded: legal.pages()[seeded].body,
        }
