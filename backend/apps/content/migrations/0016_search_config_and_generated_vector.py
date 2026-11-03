import importlib

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.contrib.postgres.search import SearchVector
from django.db import migrations, models

# La búsqueda en español con los acentos plegados por `unaccent` (la extensión la creó 0011):
# la misma configuración al indexar y al buscar, para que las letras sin descomposición Unicode
# (ø, ł, æ, ß) casen igual a los dos lados.
CONFIG = """
CREATE TEXT SEARCH CONFIGURATION spanish_unaccent (COPY = pg_catalog.spanish);
ALTER TEXT SEARCH CONFIGURATION spanish_unaccent
    ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;
"""
CONFIG_REVERSE = "DROP TEXT SEARCH CONFIGURATION IF EXISTS spanish_unaccent;"

# El vector pasa a ser una columna generada: sobran los triggers de 0011.
TRIGGERS = """
DROP TRIGGER IF EXISTS article_search_vector_trg ON content_article;
DROP FUNCTION IF EXISTS content_article_search_vector_update();
DROP TRIGGER IF EXISTS poem_search_vector_trg ON content_poem;
DROP FUNCTION IF EXISTS content_poem_search_vector_update();
"""
TRIGGERS_REVERSE = importlib.import_module("apps.content.migrations.0011_unaccent_search").FORWARD
CONFIG_NAME = "spanish_unaccent"


def _vector(*weighted):
    parts = [SearchVector(field, weight=weight, config=CONFIG_NAME) for field, weight in weighted]
    vector = parts[0]
    for part in parts[1:]:
        vector = vector + part
    return vector


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0015_remove_unused_fields"),
    ]

    operations = [
        migrations.RunSQL(CONFIG, CONFIG_REVERSE),
        migrations.RunSQL(TRIGGERS, TRIGGERS_REVERSE),
        migrations.RemoveIndex(model_name="article", name="article_search_gin"),
        migrations.RemoveIndex(model_name="poem", name="poem_search_gin"),
        migrations.RemoveField(model_name="article", name="search_vector"),
        migrations.RemoveField(model_name="poem", name="search_vector"),
        migrations.AddField(
            model_name="article",
            name="search_vector",
            field=models.GeneratedField(
                db_persist=True,
                expression=_vector(("title", "A"), ("subtitle", "B"), ("body", "D")),
                output_field=django.contrib.postgres.search.SearchVectorField(),
            ),
        ),
        migrations.AddField(
            model_name="poem",
            name="search_vector",
            field=models.GeneratedField(
                db_persist=True,
                expression=_vector(("title", "A"), ("body", "D")),
                output_field=django.contrib.postgres.search.SearchVectorField(),
            ),
        ),
        migrations.AddIndex(
            model_name="article",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"], name="article_search_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="poem",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"], name="poem_search_gin"
            ),
        ),
    ]
