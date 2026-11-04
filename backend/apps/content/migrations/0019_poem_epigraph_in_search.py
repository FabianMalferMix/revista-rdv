import importlib

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations, models

# El vector de los poemas suma el epígrafe. Una columna generada no se altera: se quita y se
# vuelve a añadir, con su índice, y la base la rellena para las filas que ya existen.
_vector = importlib.import_module(
    "apps.content.migrations.0016_search_config_and_generated_vector"
)._vector


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0018_protect_published_references"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="poem", name="poem_search_gin"),
        migrations.RemoveField(model_name="poem", name="search_vector"),
        migrations.AddField(
            model_name="poem",
            name="search_vector",
            field=models.GeneratedField(
                db_persist=True,
                expression=_vector(("title", "A"), ("epigraph", "D"), ("body", "D")),
                output_field=django.contrib.postgres.search.SearchVectorField(),
            ),
        ),
        migrations.AddIndex(
            model_name="poem",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"], name="poem_search_gin"
            ),
        ),
    ]
