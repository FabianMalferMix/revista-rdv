import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Paso 1/3 del enlace genérico en la bitácora editorial.

    Agrega content_type + object_id (temporalmente anulables) junto al FK article
    existente; 0004 copia los datos y 0005 retira el FK y endurece los campos.
    """

    dependencies = [
        ("content", "0002_rename_dossier_to_collection"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="editorialtransition",
            name="content_type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AddField(
            model_name="editorialtransition",
            name="object_id",
            field=models.PositiveBigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="editorialnote",
            name="content_type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AddField(
            model_name="editorialnote",
            name="object_id",
            field=models.PositiveBigIntegerField(null=True),
        ),
        migrations.AddIndex(
            model_name="editorialtransition",
            index=models.Index(
                fields=["content_type", "object_id"], name="edtransition_item_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="editorialnote",
            index=models.Index(fields=["content_type", "object_id"], name="ednote_item_idx"),
        ),
    ]
