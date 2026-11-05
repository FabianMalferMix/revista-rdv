from django.db import migrations

from apps.content import legal


def create_pages(apps, schema_editor):
    """Crea las páginas legales con su texto vigente (idempotente; no pisa ediciones posteriores)."""
    legal.create_pages(apps.get_model("content", "Page"))


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0006_alter_article_owner_poem_collectionpoem_and_more"),
    ]

    operations = [
        migrations.RunPython(create_pages, migrations.RunPython.noop),
    ]
