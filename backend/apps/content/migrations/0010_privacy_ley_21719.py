from django.db import migrations

from apps.content import legal


def update_privacy(apps, schema_editor):
    """La política de privacidad sembrada pasa al texto vigente, que cita también la Ley 21.719 y
    detalla cuánto se conservan los datos."""
    Page = apps.get_model("content", "Page")
    page = Page.objects.filter(slug="privacidad").first()
    if not page:
        return
    # Solo actualiza el texto SEMBRADO original (cita 19.628 pero aún no 21.719): no
    # pisa una edición manual posterior hecha en el admin.
    if "19.628" in page.body and "21.719" not in page.body:
        page.body = legal.pages()["privacidad"].body
        page.save(update_fields=["body"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0009_search_vector_triggers"),
    ]

    operations = [
        migrations.RunPython(update_privacy, migrations.RunPython.noop),
    ]
