from django.db import migrations
from django.db.models import F


def forward(apps, schema_editor):
    """Copia article_id → (content_type, object_id) en transiciones y notas."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct, _ = ContentType.objects.get_or_create(app_label="content", model="article")
    for model_name in ("EditorialTransition", "EditorialNote"):
        model = apps.get_model("content", model_name)
        model.objects.update(content_type_id=ct.pk, object_id=F("article_id"))


def backward(apps, schema_editor):
    """Restaura article_id desde object_id (solo filas de artículos)."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct = ContentType.objects.filter(app_label="content", model="article").first()
    if ct is None:
        return
    for model_name in ("EditorialTransition", "EditorialNote"):
        model = apps.get_model("content", model_name)
        model.objects.filter(content_type_id=ct.pk).update(article_id=F("object_id"))


class Migration(migrations.Migration):
    """Paso 2/3: migración de datos del FK directo al enlace genérico."""

    dependencies = [
        ("content", "0003_editorial_generic_schema"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
