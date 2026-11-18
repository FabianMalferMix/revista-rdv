"""Las migraciones de datos de la vitrina, probadas con filas.

El perfil del sitio existe tras migrar, y el que ya había se conserva (0004); el que aún lleva
el nombre por defecto de entonces toma el fijo, y uno nombrado en el panel conserva el suyo
(0016). Las publicaciones, la prensa y los aliados que ya había quedan creados y editados en la
fecha de la migración (0015); la misma prueba migra la agenda, cuyas actividades reciben esa
fecha, y los registros, que conservan la de su creación. Cada prueba crea con los modelos de
entonces las filas que la migración transforma, migra y comprueba qué quedó, con el fixture
`migrate` de `conftest.py`.
"""

from datetime import UTC, datetime

from django.utils import timezone


def test_the_site_profile_exists_after_migrating_and_an_existing_one_is_kept(migrate):
    old = migrate("showcase", "0003_partner_pressmention_publication_wheretobuy")
    old.get_model("showcase", "SiteProfile").objects.all().delete()
    new = migrate("showcase", "0004_ensure_siteprofile_singleton")
    profiles = new.get_model("showcase", "SiteProfile").objects.values_list("pk", "name")
    assert list(profiles) == [(1, "Colectivo")]

    old = migrate("showcase", "0003_partner_pressmention_publication_wheretobuy")
    old.get_model("showcase", "SiteProfile").objects.filter(pk=1).update(name="Repitentes")
    new = migrate("showcase", "0004_ensure_siteprofile_singleton")
    profiles = new.get_model("showcase", "SiteProfile").objects.values_list("pk", "name")
    assert list(profiles) == [(1, "Repitentes")]


def test_the_site_profile_still_named_with_the_old_default_takes_the_fixed_name(migrate):
    """La fila del perfil la crea 0004 con el nombre por defecto de entonces, «Colectivo»: sin
    esta migración, un sitio recién instalado se llamaría así hasta nombrarlo en el panel."""
    old = migrate("showcase", "0015_timestamps")
    old.get_model("showcase", "SiteProfile").objects.update_or_create(
        pk=1, defaults={"name": "Colectivo"}
    )
    new = migrate("showcase", "0016_siteprofile_name_default")
    profiles = new.get_model("showcase", "SiteProfile").objects.values_list("pk", "name")
    assert list(profiles) == [(1, "Repitentes del Verso")]

    # Control: un perfil ya nombrado en el panel conserva su nombre.
    old = migrate("showcase", "0015_timestamps")
    old.get_model("showcase", "SiteProfile").objects.filter(pk=1).update(name="Otro Colectivo")
    new = migrate("showcase", "0016_siteprofile_name_default")
    profiles = new.get_model("showcase", "SiteProfile").objects.values_list("pk", "name")
    assert list(profiles) == [(1, "Otro Colectivo")]


def test_the_rows_already_there_take_the_date_of_the_migration(migrate):
    """Las actividades, las publicaciones, las menciones de prensa y los aliados que ya había quedan
    creados y editados en la fecha de la migración. Un registro, que ya guardaba cuándo se creó, lo
    conserva."""
    long_ago = datetime(2026, 3, 14, 12, tzinfo=UTC)
    old = migrate("agenda", "0004_protect_published_references")
    old.get_model("agenda", "Event").objects.create(
        slug="lectura", title="Lectura", starts_at=long_ago
    )
    old = migrate("showcase", "0014_protect_published_references")
    old.get_model("showcase", "Publication").objects.create(slug="plaquette", title="Plaquette")
    old.get_model("showcase", "PressMention").objects.create(title="Una nota", outlet="Un diario")
    old.get_model("showcase", "Partner").objects.create(name="Un fondo")
    old = migrate("media", "0015_protect_published_references")
    recordings = old.get_model("media", "Recording").objects
    recordings.create(slug="lectura", title="Lectura", embed_url="https://vimeo.com/1")
    recordings.update(created_at=long_ago)
    before = timezone.now()

    new = migrate("agenda", "0005_event_timestamps")
    dates = list(new.get_model("agenda", "Event").objects.values_list("created_at", "updated_at"))
    new = migrate("showcase", "0015_timestamps")
    for name in ("Publication", "PressMention", "Partner"):
        dates += new.get_model("showcase", name).objects.values_list("created_at", "updated_at")
    new = migrate("media", "0016_recording_updated_at")
    recording = new.get_model("media", "Recording").objects.values_list("created_at", "updated_at")
    after = timezone.now()

    assert len(dates) == 4 and all(before <= date <= after for row in dates for date in row)
    ((created, updated),) = recording
    assert created == long_ago
    assert before <= updated <= after
