from django.db import migrations, models


class Migration(migrations.Migration):
    """Renombra Dosier → Colección (libera el término «dossier» para el kit de prensa).

    Rename puro sobre las tablas existentes: conserva los datos (a diferencia de un
    drop+create). El enum DossierStatus → PublishStatus es solo Python (los valores en
    BD siguen siendo "draft"/"published"), por eso no aparece aquí.
    """

    dependencies = [
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="dossierarticle",
            name="uniq_dossier_article",
        ),
        migrations.RenameModel(old_name="Dossier", new_name="Collection"),
        migrations.RenameModel(old_name="DossierArticle", new_name="CollectionArticle"),
        migrations.RenameField(
            model_name="collectionarticle",
            old_name="dossier",
            new_name="collection",
        ),
        migrations.AddConstraint(
            model_name="collectionarticle",
            constraint=models.UniqueConstraint(
                fields=["collection", "article"], name="uniq_collection_article"
            ),
        ),
        migrations.AlterField(
            model_name="collection",
            name="articles",
            field=models.ManyToManyField(
                related_name="collections",
                through="content.CollectionArticle",
                to="content.article",
            ),
        ),
        migrations.AlterModelOptions(
            name="collection",
            options={
                "ordering": ["-published_at"],
                "verbose_name": "colección",
                "verbose_name_plural": "colecciones",
            },
        ),
    ]
