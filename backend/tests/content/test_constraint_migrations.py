"""La migración que corrige los textos antes de la restricción que pide fecha a lo público.

Un texto publicado sin fecha toma la de su última edición, y uno programado sin fecha vuelve a
aprobado, con su entrada en la bitácora; un borrador sigue sin fecha (0014). La prueba crea con
los modelos de entonces las filas que la restricción prohibiría, migra y comprueba qué quedó,
con el fixture `migrate` de `conftest.py`.
"""


def test_public_pieces_get_a_date_and_undated_scheduled_ones_go_back_to_approved(migrate):
    old = migrate("content", "0013_permisos_de_revisar_y_publicar")
    Article = old.get_model("content", "Article")
    fields = {"title": "Pieza", "body": "Texto", "reading_time": 1}
    published = Article.objects.create(slug="publicada", status="published", **fields)
    scheduled = Article.objects.create(slug="programada", status="scheduled", **fields)
    draft = Article.objects.create(slug="borrador", status="draft", **fields)

    new = migrate("content", "0014_piezas_publicas_con_fecha")
    Article = new.get_model("content", "Article")
    published = Article.objects.get(pk=published.pk)
    assert published.published_at == published.updated_at
    assert Article.objects.get(pk=scheduled.pk).status == "approved"
    assert Article.objects.get(pk=draft.pk).published_at is None, "un borrador no necesita fecha"
    log = new.get_model("content", "EditorialTransition").objects.filter(object_id=scheduled.pk)
    assert list(log.values_list("from_status", "to_status")) == [("scheduled", "approved")]
