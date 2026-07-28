from django.db import migrations

# `search_vector` deja de recalcularse en Article.save(): lo mantiene un trigger de
# Postgres que se dispara en TODA escritura de las columnas de texto (incluye
# bulk_update / QuerySet.update / imports), evitando vectores desactualizados. Se
# replica en Poem para hacer los poemas buscables. El UPDATE inicial rellena las
# filas existentes (los poemas tenían el vector nulo).

ARTICLE_TRIGGER = """
CREATE TRIGGER article_search_vector_trg
BEFORE INSERT OR UPDATE OF title, subtitle, body ON content_article
FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(search_vector, 'pg_catalog.spanish', title, subtitle, body);
UPDATE content_article SET search_vector = to_tsvector(
    'pg_catalog.spanish',
    coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' || coalesce(body, '')
);
"""
ARTICLE_TRIGGER_REVERSE = "DROP TRIGGER IF EXISTS article_search_vector_trg ON content_article;"

POEM_TRIGGER = """
CREATE TRIGGER poem_search_vector_trg
BEFORE INSERT OR UPDATE OF title, body ON content_poem
FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(search_vector, 'pg_catalog.spanish', title, body);
UPDATE content_poem SET search_vector = to_tsvector(
    'pg_catalog.spanish',
    coalesce(title, '') || ' ' || coalesce(body, '')
);
"""
POEM_TRIGGER_REVERSE = "DROP TRIGGER IF EXISTS poem_search_vector_trg ON content_poem;"


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0008_poem_search_vector_poem_poem_search_gin"),
    ]

    operations = [
        migrations.RunSQL(ARTICLE_TRIGGER, ARTICLE_TRIGGER_REVERSE),
        migrations.RunSQL(POEM_TRIGGER, POEM_TRIGGER_REVERSE),
    ]
