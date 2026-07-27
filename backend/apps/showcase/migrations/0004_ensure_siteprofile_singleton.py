from django.db import migrations


def ensure_singleton(apps, schema_editor):
    """Garantiza que exista la fila del perfil del sitio (pk=1).

    Sin esto, en una BD de producción recién migrada el context_processor global
    entregaba site_profile=None hasta que un admin lo creara a mano (cabecera/pie
    en blanco). Idempotente: si ya existe, no hace nada.
    """
    SiteProfile = apps.get_model("showcase", "SiteProfile")
    SiteProfile.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("showcase", "0003_partner_pressmention_publication_wheretobuy"),
    ]

    operations = [
        migrations.RunPython(ensure_singleton, migrations.RunPython.noop),
    ]
