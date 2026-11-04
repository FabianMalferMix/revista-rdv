from django.db import migrations, models

# Las claves con tilde que guardaba el formulario, y las que las reemplazan.
WITHOUT_ACCENTS = {"reseña": "resena", "poesía": "poesia", "crónica": "cronica"}
OFFERED = ["resena", "ensayo", "entrevista", "poesia", "narrativa", "cronica", "otro"]


def drop_the_accents(apps, schema_editor):
    """Cada envío pasa a la clave sin tilde de su tipo, y uno con un tipo que el formulario no
    ofrece, a «otro»: la restricción que viene después no admite otro valor."""
    Submission = apps.get_model("submissions", "Submission")
    for old, new in WITHOUT_ACCENTS.items():
        Submission.objects.filter(type=old).update(type=new)
    Submission.objects.exclude(type__in=OFFERED).update(type="otro")


def bring_back_the_accents(apps, schema_editor):
    Submission = apps.get_model("submissions", "Submission")
    for old, new in WITHOUT_ACCENTS.items():
        Submission.objects.filter(type=new).update(type=old)


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0004_submission_resolved_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="submission",
            name="type",
            field=models.CharField(
                choices=[
                    ("resena", "Reseña"),
                    ("ensayo", "Ensayo"),
                    ("entrevista", "Entrevista"),
                    ("poesia", "Poesía"),
                    ("narrativa", "Narrativa"),
                    ("cronica", "Crónica"),
                    ("otro", "Otro"),
                ],
                max_length=50,
            ),
        ),
        migrations.RunPython(drop_the_accents, bring_back_the_accents),
        migrations.AddConstraint(
            model_name="submission",
            constraint=models.CheckConstraint(
                condition=models.Q(type__in=OFFERED),
                name="submission_type_is_offered",
                violation_error_message="Ese tipo de propuesta no está entre los que se ofrecen.",
            ),
        ),
    ]
