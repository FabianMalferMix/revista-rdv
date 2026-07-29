from django.db import migrations

# Búsqueda insensible a acentos: el `search_vector` pasa a construirse con
# `unaccent(...)` para que "reseña" se encuentre buscando "resena" y viceversa —
# relevante para una audiencia hispanohablante. Se reemplaza el `tsvector_update_trigger`
# interno (que no permite envolver con unaccent) por una función de trigger propia por
# modelo, y se re-indexan las filas existentes. La consulta también unaccenta el término
# (en la vista) para que ambos lados coincidan.

FORWARD = """
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION content_article_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('pg_catalog.spanish', unaccent(
        coalesce(NEW.title, '') || ' ' || coalesce(NEW.subtitle, '') || ' ' || coalesce(NEW.body, '')
    ));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS article_search_vector_trg ON content_article;
CREATE TRIGGER article_search_vector_trg
BEFORE INSERT OR UPDATE OF title, subtitle, body ON content_article
FOR EACH ROW EXECUTE FUNCTION content_article_search_vector_update();

UPDATE content_article SET search_vector = to_tsvector('pg_catalog.spanish', unaccent(
    coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' || coalesce(body, '')
));

CREATE OR REPLACE FUNCTION content_poem_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('pg_catalog.spanish', unaccent(
        coalesce(NEW.title, '') || ' ' || coalesce(NEW.body, '')
    ));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS poem_search_vector_trg ON content_poem;
CREATE TRIGGER poem_search_vector_trg
BEFORE INSERT OR UPDATE OF title, body ON content_poem
FOR EACH ROW EXECUTE FUNCTION content_poem_search_vector_update();

UPDATE content_poem SET search_vector = to_tsvector('pg_catalog.spanish', unaccent(
    coalesce(title, '') || ' ' || coalesce(body, '')
));
"""

# Reversa: vuelve al trigger interno sin unaccent (estado de 0009) y re-indexa.
REVERSE = """
DROP TRIGGER IF EXISTS article_search_vector_trg ON content_article;
DROP FUNCTION IF EXISTS content_article_search_vector_update();
CREATE TRIGGER article_search_vector_trg
BEFORE INSERT OR UPDATE OF title, subtitle, body ON content_article
FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(search_vector, 'pg_catalog.spanish', title, subtitle, body);
UPDATE content_article SET search_vector = to_tsvector(
    'pg_catalog.spanish',
    coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' || coalesce(body, '')
);

DROP TRIGGER IF EXISTS poem_search_vector_trg ON content_poem;
DROP FUNCTION IF EXISTS content_poem_search_vector_update();
CREATE TRIGGER poem_search_vector_trg
BEFORE INSERT OR UPDATE OF title, body ON content_poem
FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(search_vector, 'pg_catalog.spanish', title, body);
UPDATE content_poem SET search_vector = to_tsvector(
    'pg_catalog.spanish',
    coalesce(title, '') || ' ' || coalesce(body, '')
);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0010_privacy_ley_21719"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
