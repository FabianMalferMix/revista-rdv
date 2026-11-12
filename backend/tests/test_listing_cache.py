"""El sitemap y los feeds se guardan una hora, o hasta que cambia algo de lo que listan, y a quien
ya tiene la versión vigente le responden 304 sin cuerpo. Una página HTML no lo da nunca.

Los cambios se confirman dentro de `django_capture_on_commit_callbacks`: la caché se vacía al
confirmarse la transacción, y la de cada prueba no se confirma nunca."""

import inspect
from datetime import timedelta

import pytest
from django.contrib.syndication.views import Feed
from django.core.cache import cache
from django.urls import URLPattern, get_resolver, reverse
from django.utils import timezone
from django.utils.http import http_date

from apps.content import workflow
from apps.content.models import Article, ArticleContributor, EditorialStatus
from apps.media.models import Recording
from apps.people.models import Contributor
from apps.showcase.models import SiteProfile
from apps.site.feeds import FEEDS
from config import listing_cache
from config.cache import FALLBACKS
from tests.factories import make_article, make_event, make_published_article, make_recording

pytestmark = pytest.mark.django_db

LISTINGS = ["/sitemap.xml", "/feed/", "/feed/registros/"]


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Confirma lo que se haga dentro, como el panel al guardar."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


@pytest.mark.parametrize("path", LISTINGS)
def test_a_listing_is_built_once_while_nothing_changes(client, path, django_assert_num_queries):
    first = client.get(path)
    with django_assert_num_queries(0):
        again = client.get(path)
    assert again.status_code == 200
    assert again.content == first.content


class _CacheDown:
    """La caché de producción cuando Redis no responde: cada operación devuelve lo de una caché
    vacía o que no pudo escribir."""

    def __getattr__(self, name):
        return FALLBACKS[name]


@pytest.mark.parametrize("case", ["development", "parameters", "cache down"])
def test_a_listing_is_not_kept_in_development_with_parameters_or_with_the_cache_down(
    client, settings, monkeypatch, case
):
    """En desarrollo la caché es de cada proceso, y no la vaciaría lo que guarda un comando; con
    parámetros, cada combinación sería otra clave; sin caché no hay generación que la vacíe."""
    path = "/feed/?formato=otro" if case == "parameters" else "/feed/"
    settings.DEBUG = case == "development"
    if case == "cache down":
        monkeypatch.setattr(listing_cache, "cache", _CacheDown())
    draft = make_article(title="Llega sin señal")
    assert "Llega sin señal" not in client.get(path).content.decode()
    # Sin señales que vacíen la caché: una respuesta guardada no lo listaría.
    Article.objects.filter(pk=draft.pk).update(
        status=EditorialStatus.PUBLISHED, published_at=timezone.now()
    )
    assert "Llega sin señal" in client.get(path).content.decode()


@pytest.mark.parametrize("path", LISTINGS)
def test_whoever_reads_a_listing_has_to_ask_again(client, path):
    """Fuera de aquí no se guarda: un lector que se quedara la lista una hora seguiría viendo lo
    que se retiró."""
    for response in (client.get(path), client.get(path)):
        directives = {d.strip() for d in response["Cache-Control"].split(",")}
        assert directives == {"max-age=0", "no-cache"}


def test_withdrawing_a_text_takes_it_out_of_the_cached_feed(client, commit):
    make_published_article(title="El que se queda")
    leaving = make_published_article(title="El que se va")
    assert "El que se va" in client.get("/feed/").content.decode()

    with commit():
        workflow.perform_transition(leaving, "unpublish", workflow.SYSTEM)

    body = client.get("/feed/").content.decode()
    assert "El que se va" not in body
    assert "El que se queda" in body


def test_publishing_a_text_adds_it_to_the_cached_feed(client, commit):
    make_published_article(title="El que ya estaba")
    arriving = make_article(title="El que llega", status=EditorialStatus.APPROVED)
    assert "El que llega" not in client.get("/feed/").content.decode()

    with commit():
        workflow.perform_transition(arriving, "publish", workflow.SYSTEM)

    body = client.get("/feed/").content.decode()
    assert "El que llega" in body
    assert "El que ya estaba" in body


@pytest.mark.parametrize("path", ["/feed/", "/feed/registros/"])
def test_renaming_the_collective_retitles_the_cached_feed(client, commit, path):
    """Cada feed se titula con el nombre del colectivo, que sale de su perfil."""
    profile = SiteProfile.load()
    profile.name = "Nombre de antes"
    with commit():
        profile.save()
    assert "Nombre de antes" in client.get(path).content.decode()

    profile.name = "Nombre de ahora"
    with commit():
        profile.save()

    body = client.get(path).content.decode()
    assert "Nombre de ahora" in body
    assert "Nombre de antes" not in body


def test_withdrawing_a_recording_takes_it_out_of_the_cached_podcast(client, commit):
    make_recording(title="La lectura que sigue", kind=Recording.Kind.AUDIO)
    leaving = make_recording(title="La lectura que se va", kind=Recording.Kind.AUDIO)
    assert "La lectura que se va" in client.get("/feed/registros/").content.decode()

    with commit():
        leaving.published = False
        leaving.save()

    body = client.get("/feed/registros/").content.decode()
    assert "La lectura que se va" not in body
    assert "La lectura que sigue" in body


def test_the_cached_sitemap_follows_what_is_published(client, commit):
    staying = make_event(slug="actividad-que-sigue")
    leaving = make_event(slug="actividad-que-se-va")
    arriving = make_event(slug="actividad-que-llega", published=False)
    sitemap = client.get("/sitemap.xml").content.decode()
    assert leaving.get_absolute_url() in sitemap
    assert arriving.get_absolute_url() not in sitemap

    with commit():
        leaving.published = False
        leaving.save()
        arriving.published = True
        arriving.save()

    sitemap = client.get("/sitemap.xml").content.decode()
    assert leaving.get_absolute_url() not in sitemap
    assert arriving.get_absolute_url() in sitemap
    assert staying.get_absolute_url() in sitemap


@pytest.mark.parametrize("how", ["inline", "relation"])
def test_signing_a_published_text_gives_the_sitemap_a_new_page(client, commit, how):
    """Quien firma algo publicado tiene ficha: lo decide la tabla de la firma, no el texto. El
    panel guarda las firmas en un inline; el código, también con la relación."""
    text = make_published_article(slug="texto-firmado")
    signer = Contributor.objects.create(slug="firma-nueva", display_name="Firma Nueva")
    sitemap = client.get("/sitemap.xml").content.decode()
    assert text.get_absolute_url() in sitemap
    assert signer.get_absolute_url() not in sitemap

    with commit():
        if how == "inline":
            ArticleContributor.objects.create(article=text, contributor=signer)
        else:
            text.authors.add(signer)

    assert signer.get_absolute_url() in client.get("/sitemap.xml").content.decode()


def test_a_change_leaves_the_rest_of_the_cache_alone(client, commit):
    """La caché guarda también los contadores del límite de tasa: un cambio no la vacía."""
    cache.set("contador-ajeno", 3)
    leaving = make_event(slug="se-retira")
    client.get("/sitemap.xml")

    with commit():
        leaving.published = False
        leaving.save()

    assert leaving.get_absolute_url() not in client.get("/sitemap.xml").content.decode()
    assert cache.get("contador-ajeno") == 3


def test_every_feed_of_the_site_is_in_the_list_that_empties_the_cache():
    """Lo que vacía la caché sale de FEEDS: un feed registrado por otro lado quedaría guardado
    una hora con lo que ya se retiró."""

    def views(patterns):
        for pattern in patterns:
            if isinstance(pattern, URLPattern):
                yield inspect.unwrap(pattern.callback)
            else:
                yield from views(pattern.url_patterns)

    feeds = [view for view in views(get_resolver().url_patterns) if isinstance(view, Feed)]
    assert {id(feed) for feed in feeds} == {id(feed) for feed in FEEDS.values()}


@pytest.mark.parametrize("path", LISTINGS)
def test_a_listing_answers_304_to_whoever_already_has_it(client, path):
    first = client.get(path)
    assert first.status_code == 200

    by_etag = client.get(path, headers={"if-none-match": first["ETag"]})
    by_date = client.get(path, headers={"if-modified-since": first["Last-Modified"]})
    assert (by_etag.status_code, by_date.status_code) == (304, 304)
    assert by_etag.content == by_date.content == b""


def test_two_changes_in_the_same_instant_both_reach_the_feed(client, commit, monkeypatch):
    """Cada cambio abre una generación nueva aunque el reloj no se mueva entre los dos."""
    monkeypatch.setattr(listing_cache, "time_ns", lambda: 1_800_000_000 * 10**9)
    first = make_published_article(title="El primero que se va")
    second = make_published_article(title="El segundo que se va")
    make_published_article(title="El que se queda")
    assert "El segundo que se va" in client.get("/feed/").content.decode()

    with commit():
        workflow.perform_transition(first, "unpublish", workflow.SYSTEM)
    assert "El primero que se va" not in client.get("/feed/").content.decode()
    with commit():
        workflow.perform_transition(second, "unpublish", workflow.SYSTEM)

    body = client.get("/feed/").content.decode()
    assert "El segundo que se va" not in body
    assert "El que se queda" in body


def test_after_a_change_the_old_date_gets_the_new_feed(client, commit, monkeypatch):
    """La fecha del feed es la del último cambio de lo que listan: con la de su ítem más
    reciente, retirar otro dejaría a quien pregunta por fecha con un 304 y el retirado."""
    clock = [1_800_000_000 * 10**9]
    monkeypatch.setattr(listing_cache, "time_ns", lambda: clock[0])
    leaving = make_published_article(title="El más antiguo", published_at=_days_ago(2))
    make_published_article(title="El más reciente", published_at=_days_ago(1))
    first = client.get("/feed/")

    clock[0] += 60 * 10**9
    with commit():
        workflow.perform_transition(leaving, "unpublish", workflow.SYSTEM)

    again = client.get("/feed/", headers={"if-modified-since": first["Last-Modified"]})
    assert again.status_code == 200
    assert "El más antiguo" not in again.content.decode()
    assert "El más reciente" in again.content.decode()


@pytest.mark.parametrize("name", ["site:home", "agenda:trayectoria"])
def test_an_html_page_never_answers_304(client, name):
    """Cada página lleva su nonce, así que su ETag no se repite, y no dice cuándo cambió. Una
    página guardada en caché lo repetiría, con un nonce que ya no es el de la cabecera CSP."""
    path = reverse(name)
    first = client.get(path)
    assert first.status_code == 200
    by_etag = client.get(path, headers={"if-none-match": first["ETag"]})
    by_date = client.get(path, headers={"if-modified-since": http_date()})
    assert (by_etag.status_code, by_date.status_code) == (200, 200)
    # Control: el feed, preguntado igual, sí responde 304.
    feed = client.get("/feed/")
    by_etag = client.get("/feed/", headers={"if-none-match": feed["ETag"]})
    by_date = client.get("/feed/", headers={"if-modified-since": http_date()})
    assert (by_etag.status_code, by_date.status_code) == (304, 304)


def _days_ago(days):
    return timezone.now() - timedelta(days=days)
