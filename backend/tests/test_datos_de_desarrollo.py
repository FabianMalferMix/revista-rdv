"""Los datos de desarrollo (`datos_de_desarrollo cargar|exportar|marcar`): la copia que viaja en
el repositorio y con la que se puebla cualquier base de desarrollo.

El repositorio es público: solo puede viajar lo que el sitio ya muestra. Ni cuentas, ni
sesiones, ni registros de acceso, ni suscriptores, ni envíos a convocatorias, ni el historial
editorial, ni lo no publicado, salvo las piezas de demostración del flujo editorial. Y cargar la
copia no toca lo que dejan las migraciones: las páginas legales conservan su texto vigente.
"""

import json
import re
from datetime import timedelta
from io import StringIO

import pytest
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.agenda.models import Event
from apps.content import legal
from apps.content.models import LEGAL_PAGES, Article, EditorialStatus, Page, PublishStatus, Tag
from apps.devtools import identity
from apps.devtools.management.commands import datos_de_desarrollo as comando
from apps.devtools.models import DevelopmentMarker
from apps.media.models import MediaAsset
from apps.showcase.models import Publication, SiteProfile
from apps.submissions.models import Call
from tests.factories import (
    make_event,
    make_image,
    make_publication,
    make_published_article,
    make_published_poem,
)

TEXTO = (comando.CARPETA / "datos.json").read_text("utf-8")
EXPORTED_AT, DATOS = comando.read_copy(comando.CARPETA / "datos.json")
# El correo del colectivo, que es público, y uno inventado de los textos largos.
CORREOS_PUBLICOS = {
    identity.PROFILE["general_email"],
    "lecturas.y.relecturas.obstinadas.del.taller.de.los.jueves@correo-electronico-del-colectivo.cl",
}
ARCHIVOS = {
    "media.mediaasset": "file",
    "media.recording": "file",
    "showcase.siteprofile": "dossier_pdf",
    "showcase.publication": "pdf",
}


def etiqueta(fila):
    return apps.get_model(fila["model"])._meta.label


def test_en_el_repositorio_solo_viaja_el_contenido_publico():
    modelos = {fila["model"] for fila in DATOS}
    assert modelos <= {m.lower() for m in comando.MODELOS}
    privadas = {"auth", "sessions", "admin", "axes", "community", "devtools"}
    assert not [m for m in modelos if m.split(".")[0] in privadas]
    assert "submissions.submission" not in modelos
    assert "content.editorialtransition" not in modelos


def test_cada_modelo_y_cada_campo_tienen_su_regla():
    """Un modelo o un campo nuevo no viaja hasta que alguien decide si es público."""
    assert comando.unclassified() == []


def test_nothing_that_travels_points_to_what_travels_by_slug(monkeypatch):
    """Lo que viaja sin clave primaria no se puede nombrar por ella: una referencia así se
    cargaría rota, y `unclassified` la señala."""
    monkeypatch.setattr(comando, "BY_SLUG", {"media.MediaAsset"})
    assert "people.Contributor.photo: apunta a algo que viaja sin clave" in comando.unclassified()


def test_solo_viaja_lo_publicado_y_las_piezas_de_demostracion():
    for fila in DATOS:
        campos = fila["fields"]
        if "status" in campos:
            demo = comando.DEMO_UNPUBLISHED.get(etiqueta(fila), set())
            assert campos["status"] == "published" or campos["slug"] in demo, fila
        if "published" in campos:
            assert campos["published"], fila
        if fila["model"] == "showcase.partner":
            assert campos["active"], fila


def test_sin_campos_privados():
    # Control: viajan filas de modelos que tienen campos privados, así que hay algo que mirar.
    assert any(comando.PRIVATE_FIELDS.get(etiqueta(fila)) for fila in DATOS)
    for fila in DATOS:
        privados = comando.PRIVATE_FIELDS.get(etiqueta(fila), set())
        assert not privados & set(fila["fields"]), fila["model"]


def test_the_copy_is_dated_and_carries_neither_the_identity_nor_its_social_links():
    """La identidad del colectivo tiene una sola fuente, apps/devtools/identity.py: `cargar` la
    pone, y la copia no la repite."""
    assert EXPORTED_AT is not None and EXPORTED_AT <= timezone.now()
    (profile,) = [row for row in DATOS if row["model"] == "showcase.siteprofile"]
    assert "featured_poem" in profile["fields"], "control: el perfil viaja"
    assert not set(identity.PROFILE) & set(profile["fields"])
    assert "showcase.sitesociallink" not in {row["model"] for row in DATOS}


def test_nothing_the_database_computes_travels():
    """El vector de búsqueda es una columna que la base calcula al guardar cada texto: en la copia
    sería peso muerto."""
    generated = {
        (model._meta.label_lower, field.name)
        for model in apps.get_models()
        for field in model._meta.local_fields
        if field.generated
    }
    assert ("content.article", "search_vector") in generated, "control: los textos tienen vector"
    texts = [row for row in DATOS if row["model"] in ("content.article", "content.poem")]
    assert texts and all("body" in row["fields"] for row in texts)
    assert not [
        (row["model"], name)
        for row in DATOS
        for name in row["fields"]
        if (row["model"], name) in generated
    ]


def test_the_copy_leaves_the_legal_pages_to_migrate_and_names_the_others_by_slug():
    pages = [row for row in DATOS if row["model"] == "content.page"]
    assert pages, "control: las demás páginas viajan"
    assert not {row["fields"]["slug"] for row in pages} & set(LEGAL_PAGES)
    assert not [row for row in pages if "pk" in row]


def test_cada_imagen_que_viaja_la_usa_algo_que_viaja():
    usadas = {
        fila["fields"][campo.name]
        for fila in DATOS
        for campo in apps.get_model(fila["model"])._meta.get_fields()
        if getattr(campo, "related_model", None) is MediaAsset and campo.name in fila["fields"]
    }
    imagenes = {fila["pk"] for fila in DATOS if fila["model"] == "media.mediaasset"}
    assert imagenes and imagenes <= usadas


def test_sin_contrasenas_ni_cuentas_ni_correos_privados():
    assert "pbkdf2" not in TEXTO and '"password"' not in TEXTO
    assert set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", TEXTO)) <= CORREOS_PUBLICOS
    # Las referencias a cuentas, leídas de los modelos: `author` de una mención en prensa es el
    # nombre del periodista, no una cuenta.
    usuario = apps.get_model(settings.AUTH_USER_MODEL)
    checked = 0
    for fila in DATOS:
        for campo in apps.get_model(fila["model"])._meta.get_fields():
            if isinstance(campo, models.ForeignKey) and campo.related_model is usuario:
                checked += 1
                assert fila["fields"].get(campo.name) is None, (fila["model"], campo.name)
    assert checked, "control: viajan filas de modelos que apuntan a una cuenta"


def test_cada_archivo_que_nombra_viaja_con_el():
    for fila in DATOS:
        campo = ARCHIVOS.get(fila["model"])
        if campo and fila["fields"][campo]:
            assert (comando.CARPETA / "media" / fila["fields"][campo]).is_file()


@pytest.mark.django_db
def test_the_repository_copy_fills_a_fresh_base_and_keeps_what_migrate_left(
    settings, legal_pages, monkeypatch
):
    """Una base recién migrada queda con cada fila de la copia, con sus valores y con todas sus
    fechas corridas los mismos días, la identidad del colectivo y las páginas legales con su
    texto vigente. Si un cambio de modelo rompe la copia (un campo nuevo obligatorio, uno que se
    va), esto falla y hay que volver a exportarla."""
    settings.DEBUG = True
    # Lo que se mira son las filas: las copias de setenta imágenes no cambian nada aquí y tardan.
    monkeypatch.setattr(
        "apps.media.management.commands.generate_image_derivatives.process_image", lambda pk: True
    )
    legal_texts = {page.slug: page.body for page in Page.objects.filter(slug__in=LEGAL_PAGES)}
    assert legal_texts == {slug: page.body for slug, page in legal.pages().items()}, (
        "control: migrate dejó las tres páginas legales con su texto"
    )

    call_command("datos_de_desarrollo", "cargar", verbosity=0)

    missing, different, shifts = [], [], set()
    for row in DATOS:
        model = apps.get_model(row["model"])
        if "pk" in row:
            loaded = model.objects.filter(pk=row["pk"]).first()
        else:
            loaded = model.objects.filter(slug=row["fields"]["slug"]).first()
        if loaded is None:
            missing.append((row["model"], row.get("pk"), row["fields"].get("slug")))
            continue
        (now_row,) = json.loads(serializers.serialize("json", [loaded], fields=list(row["fields"])))
        for name, value in row["fields"].items():
            field, got = model._meta.get_field(name), now_row["fields"][name]
            if value is not None and isinstance(field, models.DateTimeField):
                local = [
                    timezone.localtime(parse_datetime(v)).replace(tzinfo=None) for v in (got, value)
                ]
                shifts.add(local[0] - local[1])
            elif value is not None and isinstance(field, models.DateField):
                shifts.add(parse_date(got) - parse_date(value))
            elif (sorted(got) if isinstance(got, list) else got) != (
                sorted(value) if isinstance(value, list) else value
            ):
                different.append((row["model"], row.get("pk"), name))
    assert missing == [] and different == []
    (shift,) = shifts
    assert shift == timedelta(days=shift.days) and shift.days >= 0, "las fechas se corren por días"
    assert legal_texts == {p.slug: p.body for p in Page.objects.filter(slug__in=LEGAL_PAGES)}
    assert identity.differences(SiteProfile.load()) == []
    assert DevelopmentMarker.is_marked()


@pytest.fixture
def carpeta(settings, tmp_path, monkeypatch):
    # Los comandos de desarrollo solo corren con DEBUG.
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(comando, "CARPETA", tmp_path / "datos")
    return tmp_path / "datos"


@pytest.fixture
def development_base(carpeta):
    """Una base marcada como de desarrollo y con la identidad del colectivo: la que `exportar`
    acepta."""
    DevelopmentMarker.mark()
    identity.apply(SiteProfile.load())
    return carpeta


@pytest.fixture
def exported(carpeta):
    """Exporta lo que crea `build` y deshace después todo lo que hizo en la base, que queda lista
    para cargar la copia. Con `exported_at`, la copia dice que se exportó entonces."""

    def export(build, exported_at=None):
        with transaction.atomic():
            DevelopmentMarker.mark()
            identity.apply(SiteProfile.load())
            build()
            call_command("datos_de_desarrollo", "exportar", verbosity=0)
            transaction.set_rollback(True)
        path = carpeta / "datos.json"
        if exported_at is not None:
            copy = json.loads(path.read_text("utf-8"))
            copy["exported_at"] = DjangoJSONEncoder().default(exported_at)
            path.write_text(json.dumps(copy, ensure_ascii=False), encoding="utf-8")
        return comando.read_copy(path)[1]

    return export


@pytest.mark.django_db
def test_de_ida_y_vuelta_sin_la_cuenta(development_base, django_user_model):
    carpeta = development_base
    tapa = make_image("tapa-ida-y-vuelta")
    tapa.uploaded_by = django_user_model.objects.create_user("alguien", "alguien@ejemplo.cl")
    tapa.save()
    make_publication(slug="ida-y-vuelta", title="Ida y vuelta", cover=tapa)
    call_command("datos_de_desarrollo", "exportar", verbosity=0)
    exportado = (carpeta / "datos.json").read_text("utf-8")
    assert "alguien" not in exportado
    assert (carpeta / "media" / tapa.file.name).is_file()
    nombre = tapa.file.name
    Publication.objects.all().delete()
    MediaAsset.objects.all().delete()
    call_command("datos_de_desarrollo", "cargar", verbosity=0)
    cargada = Publication.objects.get(slug="ida-y-vuelta")
    assert cargada.cover.file.name == nombre and cargada.cover.uploaded_by is None
    assert cargada.cover.file.storage.exists(nombre)


@pytest.mark.django_db
def test_lo_no_publicado_y_lo_que_nadie_usa_no_viajan(development_base):
    carpeta = development_base
    Article.objects.create(
        slug="a-la-vista",
        title="Publicado",
        status=EditorialStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    Article.objects.create(slug="borrador-secreto", title="Borrador", status=EditorialStatus.DRAFT)
    make_publication(slug="sin-publicar", published=False)
    make_image("suelta", alt="Imagen que nada usa")
    make_publication(slug="con-tapa", cover=make_image("tapa-usada", alt="Tapa que se usa"))
    call_command("datos_de_desarrollo", "exportar", verbosity=0)
    exportado = (carpeta / "datos.json").read_text("utf-8")
    assert '"a-la-vista"' in exportado
    assert "borrador-secreto" not in exportado and "sin-publicar" not in exportado
    # Control: la tapa de lo publicado viaja, con su archivo.
    assert "Tapa que se usa" in exportado and list((carpeta / "media").rglob("tapa-usada*"))
    assert "Imagen que nada usa" not in exportado
    assert not list((carpeta / "media").rglob("suelta*"))


@pytest.mark.django_db
def test_exporting_writes_the_texts_without_their_search_vector(exported):
    rows = exported(
        lambda: (
            make_published_article(slug="texto-con-vector", title="Un texto que se busca"),
            make_published_poem(slug="poema-con-vector", title="Un poema que se busca"),
        )
    )
    texts = [row for row in rows if row["model"] in ("content.article", "content.poem")]
    assert {row["fields"]["slug"] for row in texts} == {"texto-con-vector", "poema-con-vector"}
    assert all(row["fields"]["title"].endswith("que se busca") for row in texts)
    assert not [row for row in texts if "search_vector" in row["fields"]]


@pytest.mark.django_db
def test_exporting_leaves_the_legal_pages_home(exported, legal_pages):
    rows = exported(
        lambda: Page.objects.create(
            slug="quienes-somos",
            title="Quiénes somos",
            body="<p>Somos un colectivo.</p>",
            status=PublishStatus.PUBLISHED,
        )
    )
    pages = [row for row in rows if row["model"] == "content.page"]
    assert [row["fields"]["slug"] for row in pages] == ["quienes-somos"]
    assert "pk" not in pages[0]


def _page_row(pk, slug, title, body):
    fields = {"slug": slug, "title": title, "body": body, "status": "published"}
    return {"model": "content.page", "pk": pk, "fields": fields}


@pytest.mark.django_db
def test_loading_an_old_copy_keeps_the_legal_text_that_migrate_left(carpeta, legal_pages, client):
    """Una copia sin fecha, con las páginas por su clave primaria, numera sus páginas como otra
    base: la de «quienes-somos» es la misma clave que aquí tiene una página legal. Cargarla no
    cambia el texto legal vigente, y las páginas que no estaban entran igual."""
    pks = sorted(Page.objects.filter(slug__in=LEGAL_PAGES).values_list("pk", flat=True))
    assert len(pks) == 3, "control: migrate dejó las tres páginas legales"
    old_privacy = "<p>Texto anterior de la política, que solo cita la Ley N.º 19.628.</p>"
    carpeta.mkdir()
    old_copy = [
        _page_row(pks[0], "quienes-somos", "Quiénes somos", "<p>Somos un colectivo.</p>"),
        _page_row(pks[1], "privacidad", "Política de privacidad", old_privacy),
        _page_row(pks[2], "cookies", "Política de cookies", "<p>Cookies de antes.</p>"),
        _page_row(pks[2] + 100, "terminos", "Términos", "<p>Términos de antes.</p>"),
    ]
    (carpeta / "datos.json").write_text(json.dumps(old_copy), encoding="utf-8")

    call_command("datos_de_desarrollo", "cargar", verbosity=0)

    for slug, page in legal.pages().items():
        assert Page.objects.get(slug=slug).body == page.body, slug
    privacy = client.get(reverse("content:page_detail", args=["privacidad"])).content.decode()
    assert "21.719" in privacy and "Texto anterior" not in privacy
    about = client.get(reverse("content:page_detail", args=["quienes-somos"]))
    assert about.status_code == 200 and "Somos un colectivo." in about.content.decode()


@pytest.mark.django_db
def test_loading_moves_the_dates_to_today(exported, client):
    """Lo que estaba a N días de la exportación queda a N días de hoy: una copia de hace cuarenta
    días sigue anunciando su próxima lectura y su convocatoria abierta, y su último texto sigue
    siendo de anteayer."""
    # Media jornada de más: el día entero que se corre no depende de un cambio de horario.
    exported_at = timezone.now() - timedelta(days=40, hours=12)

    def build():
        make_event(
            slug="recital-que-viene",
            title="Recital que viene",
            starts_at=exported_at + timedelta(days=3),
        )
        Call.objects.create(
            slug="convocatoria-abierta",
            title="Convocatoria abierta",
            opens_at=exported_at - timedelta(days=5),
            closes_at=exported_at + timedelta(days=20),
        )
        make_published_article(
            slug="texto-de-anteayer",
            title="Texto de anteayer",
            published_at=exported_at - timedelta(days=2),
        )

    exported(build, exported_at=exported_at)
    call_command("datos_de_desarrollo", "cargar", verbosity=0)

    agenda = client.get(reverse("agenda:agenda")).content.decode()
    assert "Recital que viene" in agenda and "Sin fechas anunciadas" not in agenda
    now = timezone.now()
    event = Event.objects.get(slug="recital-que-viene")
    assert timedelta(days=2) < event.starts_at - now <= timedelta(days=3)
    assert Call.objects.open_now().filter(slug="convocatoria-abierta").exists()
    text = Article.objects.published().get(slug="texto-de-anteayer")
    assert timedelta(days=2) <= now - text.published_at < timedelta(days=3)


@pytest.mark.django_db
def test_loading_puts_the_identity_of_the_collective(exported, client):
    exported(lambda: make_publication(slug="una-publicacion", title="Una publicación"))
    assert identity.differences(SiteProfile.load()), "control: la base no tiene la identidad"

    call_command("datos_de_desarrollo", "cargar", verbosity=0)

    home = client.get(reverse("site:home")).content.decode()
    assert f"<title>{identity.PROFILE['name']}" in home
    assert all(f'"{url}"' in home for _, url in identity.SOCIAL_LINKS)
    assert identity.differences(SiteProfile.load()) == []


@pytest.mark.django_db
def test_exporting_requires_the_identity_of_the_module(development_base):
    SiteProfile.objects.filter(pk=1).update(name="Otro colectivo")
    with pytest.raises(CommandError, match="name: 'Otro colectivo' en la base"):
        call_command("datos_de_desarrollo", "exportar", verbosity=0)
    assert not development_base.exists()


@pytest.mark.django_db
def test_loading_never_overwrites_a_row_already_there(exported):
    def build():
        text = make_published_article(slug="texto-con-etiqueta", title="Con etiqueta")
        text.tags.add(Tag.objects.create(slug="poesia", name="poesía"))

    rows = exported(build)
    (pk,) = [row["pk"] for row in rows if row["model"] == "content.tag"]
    Tag.objects.create(pk=pk, slug="ya-estaba", name="Ya estaba")
    with pytest.raises(CommandError, match=r"pisaría: content\.Tag"):
        call_command("datos_de_desarrollo", "cargar", verbosity=0)
    assert Tag.objects.get(pk=pk).slug == "ya-estaba"
    assert not Article.objects.filter(slug="texto-con-etiqueta").exists()


@pytest.mark.django_db
def test_exportar_exige_una_base_marcada_como_de_desarrollo(carpeta):
    with pytest.raises(CommandError, match="no está marcada como de desarrollo"):
        call_command("datos_de_desarrollo", "exportar", verbosity=0)
    assert not carpeta.exists()


@pytest.mark.django_db
def test_un_fallo_a_mitad_deja_la_copia_anterior(development_base):
    carpeta = development_base
    carpeta.mkdir()
    (carpeta / "datos.json").write_text("la copia anterior", encoding="utf-8")
    tapa = make_image("tapa-perdida")
    make_publication(slug="con-tapa-perdida", cover=tapa)
    tapa.file.storage.delete(tapa.file.name)
    with pytest.raises(FileNotFoundError):
        call_command("datos_de_desarrollo", "exportar", verbosity=0)
    assert (carpeta / "datos.json").read_text("utf-8") == "la copia anterior"


@pytest.mark.django_db
def test_marcar_deja_la_base_lista_para_exportar(settings):
    settings.DEBUG = True
    assert not DevelopmentMarker.is_marked()
    call_command("datos_de_desarrollo", "marcar", verbosity=0)
    assert DevelopmentMarker.is_marked()


@pytest.mark.django_db
def test_cargar_no_pisa_una_base_con_contenido(settings):
    settings.DEBUG = True
    make_publication(slug="ya-estaba")
    with pytest.raises(CommandError, match="ya tiene contenido"):
        call_command("datos_de_desarrollo", "cargar")
    assert list(Publication.objects.values_list("slug", flat=True)) == ["ya-estaba"]


@pytest.mark.django_db
def test_on_a_development_base_with_content_loading_does_nothing(settings):
    """Así el guion de preparación se puede repetir: en una base de desarrollo ya poblada,
    `cargar` lo dice y sale sin error, sin tocar nada."""
    settings.DEBUG = True
    DevelopmentMarker.mark()
    make_publication(slug="ya-estaba", title="Ya estaba")
    output = StringIO()
    call_command("datos_de_desarrollo", "cargar", stdout=output)
    assert "ya tiene contenido" in output.getvalue() and "no se carga nada" in output.getvalue()
    assert list(Publication.objects.values_list("slug", flat=True)) == ["ya-estaba"]
