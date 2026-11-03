from django.db import migrations, models

# La bitácora no se modifica ni se borra, tampoco con update() o delete() sobre una consulta.
# Solo se admite vaciar el actor, que es lo que hace Django al borrar su cuenta: su nombre sigue
# en actor_name. Un TRUNCATE (el vaciado de la base de pruebas) no pasa por aquí.
IMMUTABLE = """
CREATE FUNCTION content_editorialtransition_immutable() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.actor_id IS NULL
       AND (NEW.id, NEW.content_type_id, NEW.object_id, NEW.from_status, NEW.to_status,
            NEW.actor_name, NEW.item_title, NEW.note, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.content_type_id, OLD.object_id, OLD.from_status, OLD.to_status,
            OLD.actor_name, OLD.item_title, OLD.note, OLD.created_at)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'La bitácora editorial no se modifica ni se borra';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER content_editorialtransition_immutable
BEFORE UPDATE OR DELETE ON content_editorialtransition
FOR EACH ROW EXECUTE FUNCTION content_editorialtransition_immutable();
"""
IMMUTABLE_REVERSE = """
DROP TRIGGER IF EXISTS content_editorialtransition_immutable ON content_editorialtransition;
DROP FUNCTION IF EXISTS content_editorialtransition_immutable();
"""


def copy_title_and_actor(apps, schema_editor):
    """Las entradas anteriores guardan también el título de su pieza y el nombre de su actor."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Transition = apps.get_model("content", "EditorialTransition")
    for transition in Transition.objects.select_related("actor"):
        content_type = ContentType.objects.get(pk=transition.content_type_id)
        model = apps.get_model(content_type.app_label, content_type.model)
        item = model.objects.filter(pk=transition.object_id).only("title").first()
        Transition.objects.filter(pk=transition.pk).update(
            item_title=item.title if item else "",
            actor_name=transition.actor.username if transition.actor else "",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0016_search_config_and_generated_vector"),
    ]

    operations = [
        migrations.AddField(
            model_name="editorialtransition",
            name="actor_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="quién"),
        ),
        migrations.AddField(
            model_name="editorialtransition",
            name="item_title",
            field=models.CharField(blank=True, max_length=255, verbose_name="pieza"),
        ),
        migrations.RunPython(copy_title_and_actor, migrations.RunPython.noop),
        migrations.RunSQL(IMMUTABLE, IMMUTABLE_REVERSE),
    ]
