from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import EventPhoto, Milestone
from apps.media.models import Recording
from apps.reviews.models import Publisher
from tests.factories import (  # noqa: E402
    instances_built,
    make_event,
    make_photo,
    make_publication,
    soup,
)

pytestmark = pytest.mark.django_db


def test_agenda_lists_upcoming_published_only(client):
    upcoming = make_event(slug="proximo", title="Evento Próximo")
    make_event(slug="pasado", title="Evento Pasado", starts_at=timezone.now() - timedelta(days=3))
    make_event(slug="oculto", title="Evento Oculto", published=False)
    resp = client.get(reverse("agenda:agenda"))
    assert resp.status_code == 200
    assert b"Evento Pr\xc3\xb3ximo" in resp.content
    assert b"Evento Pasado" not in resp.content
    assert b"Evento Oculto" not in resp.content
    assert upcoming.get_absolute_url().encode() in resp.content


def test_trayectoria_groups_past_events_and_milestones(client):
    past = make_event(
        slug="realizado", title="Recital Realizado", starts_at=timezone.now() - timedelta(days=10)
    )
    make_event(slug="futuro", title="Evento Futuro")
    Milestone.objects.create(year=2019, title="Fundación del grupo")
    resp = client.get(reverse("agenda:trayectoria"))
    assert resp.status_code == 200
    assert b"Recital Realizado" in resp.content
    assert b"Evento Futuro" not in resp.content
    assert b"Fundaci\xc3\xb3n del grupo" in resp.content
    assert str(past.starts_at.year).encode() in resp.content


def test_event_detail_404_when_unpublished(client):
    event = make_event(slug="privado", published=False)
    assert client.get(reverse("agenda:event_detail", args=[event.slug])).status_code == 404


def test_event_detail_shows_photos_participants_and_recordings(client):
    from apps.people.models import Contributor

    event = make_event(slug="completo", title="Evento Completo")
    make_photo(event)
    member = Contributor.objects.create(slug="participante", display_name="Poeta Participante")
    event.participants.add(member)
    Recording.objects.create(
        slug="registro-evento",
        title="Registro Del Evento",
        embed_url="https://example.com/v",
        published=True,
        event=event,
    )
    Recording.objects.create(
        slug="registro-oculto",
        title="Registro Oculto",
        embed_url="https://example.com/v2",
        event=event,
    )
    resp = client.get(reverse("agenda:event_detail", args=[event.slug]))
    assert b"Poeta Participante" in resp.content
    assert b"Registro Del Evento" in resp.content
    assert b"Registro Oculto" not in resp.content
    assert b"photo-grid" in resp.content


def test_gallery_lists_only_events_with_photos(client):
    with_photos = make_event(slug="con-fotos", title="Evento Con Fotos")
    make_photo(with_photos)
    make_event(slug="sin-fotos", title="Evento Sin Fotos")
    resp = client.get(reverse("agenda:gallery"))
    assert b"Evento Con Fotos" in resp.content
    assert b"Evento Sin Fotos" not in resp.content


def test_home_shows_next_event(client):
    make_event(slug="siguiente", title="Actividad Siguiente")
    make_event(slug="hecho", title="Hecho", starts_at=timezone.now() - timedelta(days=5))
    resp = client.get(reverse("site:home"))
    assert b"Actividad Siguiente" in resp.content


def test_event_absolute_url(client):
    event = make_event(slug="ruta")
    assert event.get_absolute_url() == reverse("agenda:event_detail", args=["ruta"])


def test_stats_service_shape_and_counts():
    # `stats` vive en la capa de servicios (no en views): lo importan /trayectoria/ y el
    # dossier, que está en otra app.
    from apps.agenda.services import stats
    from apps.showcase.models import SiteProfile

    make_event(slug="pasado-1", starts_at=timezone.now() - timedelta(days=10))
    make_event(slug="pasado-2", starts_at=timezone.now() - timedelta(days=20))
    make_event(slug="festival", type="festival", starts_at=timezone.now() - timedelta(days=30))
    make_event(slug="festival-2", type="festival", starts_at=timezone.now() - timedelta(days=35))
    make_event(slug="feria", type="feria", starts_at=timezone.now() - timedelta(days=40))
    result = stats(SiteProfile.load())
    assert set(result) == {
        "years",
        "events",
        "festivals_and_fairs",
        "festivals",
        "fairs",
        "publications",
    }
    assert result["events"] == 5
    # La trayectoria rotula «festivales/ferias»: `festivals_and_fairs` suma los dos. El
    # dossier los nombra por separado: `festivals` y `fairs`. Dos festivales y una feria,
    # para que una cuenta no pase por la otra.
    assert (result["festivals_and_fairs"], result["festivals"], result["fairs"]) == (3, 2, 1)


def test_each_page_counts_festivals_and_fairs_as_it_names_them(client):
    """Con dos festivales y una feria ya hechos, la trayectoria los cuenta juntos y el
    dossier, cada uno con su nombre. Son cuentas distintas para que una no pase por la otra."""
    make_event(slug="festival", type="festival", starts_at=timezone.now() - timedelta(days=30))
    make_event(slug="festival-2", type="festival", starts_at=timezone.now() - timedelta(days=35))
    make_event(slug="feria", type="feria", starts_at=timezone.now() - timedelta(days=40))
    trayectoria = soup(client, reverse("agenda:trayectoria"))
    tira = {" ".join(li.get_text().split()) for li in trayectoria.select(".stats-strip li")}
    assert "3 festivales/ferias" in tira, tira
    dossier = soup(client, reverse("showcase:dossier"))
    cifras = {" ".join(li.get_text().split()) for li in dossier.select(".dossier-cifras li")}
    assert {"2 festivales", "1 feria"} <= cifras, cifras


# ── Agenda sin fechas (backlog UX, ticket 1.13) ─────────────────────────────


def test_la_agenda_vacia_ensena_lo_ultimo_y_como_contactar(client):
    """Sin fechas anunciadas la página era una frase. Ahora dice qué pasa, ofrece
    contacto y enseña las últimas actividades: prueba de que el colectivo está activo."""
    from apps.showcase.models import SiteProfile

    perfil = SiteProfile.load()
    perfil.general_email = "colectivo@example.com"
    perfil.booking_email = ""
    perfil.save()
    for i in range(4):
        make_event(
            slug=f"hecho-{i}",
            title=f"Lectura hecha {i}",
            starts_at=timezone.now() - timedelta(days=10 + i),
            registration_url="https://example.com/entradas",
        )
    html = client.get(reverse("agenda:agenda")).content.decode()

    assert "Sin fechas anunciadas" in html
    assert html.count('class="event-card"') == 3, "se enseñan las tres últimas, no todas"
    assert "Lectura hecha 0" in html and "Lectura hecha 3" not in html
    # Sin correo de gestión, el botón cae al correo general: el mismo criterio que el pie.
    assert 'href="mailto:colectivo@example.com"' in html
    assert reverse("showcase:dossier") in html
    # Una actividad ya realizada no ofrece entradas.
    assert "Inscripción / entradas" not in html


@pytest.mark.parametrize(
    "booking, general, contact",
    [
        ("gestion@example.com", "colectivo@example.com", "gestion@example.com"),
        ("", "colectivo@example.com", "colectivo@example.com"),
        ("", "", None),
    ],
)
def test_the_empty_agenda_writes_to_the_same_address_as_the_footer(
    client, booking, general, contact
):
    """«Escríbenos», en la agenda sin fechas, lleva al correo de contacto del sitio, el del pie:
    el de gestión y, si no hay, el general. Sin ninguno, no hay botón, y sí el del dossier."""
    from apps.showcase.models import SiteProfile

    perfil = SiteProfile.load()
    perfil.booking_email, perfil.general_email = booking, general
    perfil.save()
    sopa = soup(client, reverse("agenda:agenda"))
    acciones = sopa.select_one(".vacio .vacio-acciones")
    assert acciones.find("a", string="Ver el dossier")["href"] == reverse("showcase:dossier")
    escribenos = acciones.find("a", string="Escríbenos")
    pie = sopa.select('footer.site-foot a[href^="mailto:"]')
    assert [a["href"] for a in pie] == ([f"mailto:{contact}"] if contact else [])
    assert (escribenos["href"] if escribenos else None) == (pie[0]["href"] if pie else None)


def test_con_fechas_anunciadas_no_se_mezclan_las_pasadas(client):
    make_event(slug="viene", title="Lectura que viene")
    make_event(slug="fue", title="Lectura que fue", starts_at=timezone.now() - timedelta(days=5))
    html = client.get(reverse("agenda:agenda")).content.decode()
    assert "Lectura que viene" in html
    assert "Lectura que fue" not in html
    assert "Sin fechas anunciadas" not in html


# ── Galería como hoja de contactos (backlog UX, ticket 2.2) ─────────────────


def _hojas(client):
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(client.get(reverse("agenda:gallery")).content, "html.parser")
    return {
        tarjeta.select_one(".album-title").get_text(): tarjeta
        for tarjeta in sopa.select("li.album-card")
    }


def test_cada_album_ensena_hasta_tres_fotos(client):
    """Una sola miniatura no decía si detrás había una foto o treinta."""
    grande = make_event(slug="grande", title="Álbum Grande")
    for i in range(5):
        make_photo(grande, position=i)
    chico = make_event(slug="chico", title="Álbum Chico")
    make_photo(chico)

    hojas = _hojas(client)
    fotos = hojas["Álbum Grande"].select(".hoja img")
    assert len(fotos) == 3, "la hoja enseña tres fotos, no las cinco"
    # Las tres primeras según su posición en el álbum.
    assert [f["src"].rsplit("/", 1)[-1] for f in fotos] == [
        f"foto-grande-{i}.jpg" for i in range(3)
    ]
    assert "5 fotos" in hojas["Álbum Grande"].get_text()

    assert len(hojas["Álbum Chico"].select(".hoja img")) == 1
    assert "1 foto" in hojas["Álbum Chico"].get_text()
    assert "1 fotos" not in hojas["Álbum Chico"].get_text()


def test_en_la_hoja_solo_la_primera_foto_lleva_texto_alternativo(client):
    """Las tres van dentro del enlace del álbum: con tres textos alternativos el enlace
    se llamaría «foto, foto, foto, Recital…». La primera describe; las otras acompañan."""
    evento = make_event(slug="alt", title="Álbum Alt")
    for i in range(3):
        make_photo(evento, position=i)
    fotos = _hojas(client)["Álbum Alt"].select(".hoja img")
    assert [f["alt"] for f in fotos] == ["foto-alt-0", "", ""]
    assert len(_hojas(client)["Álbum Alt"].select("a")) == 1


def test_la_hoja_de_contactos_no_anade_consultas_por_album(client):
    """Las tres fotos salen de la caché del prefetch: enseñar más álbumes no puede costar
    más consultas (una por álbum sería el N+1 de siempre)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def consultas():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(reverse("agenda:gallery")).status_code == 200
        return len(ctx)

    uno = make_event(slug="g1", title="G1")
    for i in range(4):
        make_photo(uno, position=i)
    consultas()  # la primera petición crea el perfil del sitio: no cuenta
    con_uno = consultas()
    for n in range(2, 6):
        evento = make_event(slug=f"g{n}", title=f"G{n}")
        for i in range(4):
            make_photo(evento, position=i)
    assert consultas() == con_uno, "la galería hace una consulta más por cada álbum"


def test_the_gallery_costs_the_same_with_three_albums_or_thirty(client):
    """Cada página enseña doce álbumes, cada uno con su hoja y su cuenta de fotos: con treinta
    álbumes, las mismas consultas que con tres."""
    url = reverse("agenda:gallery")

    def album(n):
        event = make_event(slug=f"album-{n}", title=f"Álbum {n}")
        for position in range(2):
            make_photo(event, position=position)

    for n in range(3):
        album(n)
    client.get(url)  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as three:
        assert client.get(url).status_code == 200
    for n in range(3, 30):
        album(n)
    with CaptureQueriesContext(connection) as thirty:
        page = soup(client, url)
    # Control: la página está llena y la paginación cuenta los treinta.
    assert len(page.select("li.album-card")) == 12
    assert " ".join(page.select_one(".pagination-count").get_text().split()) == "1–12 de 30 álbumes"
    assert len(thirty) == len(three), "una consulta más por álbum"


def test_the_gallery_brings_only_the_photos_its_sheets_show(client):
    """Un álbum de ocho fotos enseña tres y dice que son ocho: las otras cinco no se traen."""
    big = make_event(slug="grande", title="Álbum Grande")
    for position in range(8):
        make_photo(big, position=position)
    make_photo(make_event(slug="chico", title="Álbum Chico"))
    with instances_built(EventPhoto) as photos:
        sheets = _hojas(client)
    assert len(sheets["Álbum Grande"].select(".hoja img")) == 3
    assert "8 fotos" in sheets["Álbum Grande"].get_text()  # control: la cuenta es la real
    assert "1 foto" in sheets["Álbum Chico"].get_text()
    assert len(photos) == 3 + 1


def test_la_trayectoria_nombra_cada_editorial_sin_una_consulta_por_libro(client):
    """La fila de una publicación nombra su editorial, que viene en la consulta de la lista:
    con cuatro libros, las mismas consultas que con uno."""
    url = reverse("agenda:trayectoria")

    def libro(n):
        editorial = Publisher.objects.create(slug=f"ed{n}", name=f"Editorial {n}")
        make_publication(slug=f"libro-{n}", title=f"Libro {n}", year=2020 + n, publisher=editorial)

    libro(0)
    client.get(url)  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as uno:
        client.get(url)
    for n in (1, 2, 3):
        libro(n)
    with CaptureQueriesContext(connection) as cuatro:
        assert "Editorial 3" in client.get(url).content.decode()
    assert len(cuatro) == len(uno), "una consulta más por libro"
