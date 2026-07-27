import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Paso 3/3: retira el FK article y endurece el enlace genérico (no nulo)."""

    dependencies = [
        ("content", "0004_editorial_generic_data"),
    ]

    operations = [
        migrations.RemoveField(model_name="editorialtransition", name="article"),
        migrations.RemoveField(model_name="editorialnote", name="article"),
        migrations.AlterField(
            model_name="editorialtransition",
            name="content_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AlterField(
            model_name="editorialtransition",
            name="object_id",
            field=models.PositiveBigIntegerField(),
        ),
        migrations.AlterField(
            model_name="editorialnote",
            name="content_type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="contenttypes.contenttype",
            ),
        ),
        migrations.AlterField(
            model_name="editorialnote",
            name="object_id",
            field=models.PositiveBigIntegerField(),
        ),
    ]
