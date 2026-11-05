"""Las reseñas de una publicación del colectivo (lo pidió el dueño del sitio tras el paso 21).

Una reseña del sitio apunta a una obra reseñada (`reviews.Work`), y las publicaciones del
colectivo (`showcase.Publication`) son el catálogo: no había forma de decir que una obra
reseñada era un libro del colectivo. Ahora la obra puede señalar su publicación, la ficha de
la publicación enseña sus reseñas y la de la obra lleva a la publicación.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from apps.reviews.models import Work
from tests.factories import make_article, make_publication, soup

pytestmark = pytest.mark.django_db


def _resena(obra, titulo, dias, estado=EditorialStatus.PUBLISHED):
    texto = make_article(
        title=titulo, status=estado, published_at=timezone.now() - timedelta(days=dias)
    )
    texto.reviewed_works.add(obra)
    return texto


def test_la_ficha_de_una_publicacion_lleva_sus_resenas(client):
    """Las publicadas, de la más reciente a la más antigua; ni los borradores ni las reseñas
    de otras obras."""
    libro = make_publication(slug="cuadernos", title="Cuadernos del ruido")
    obra = Work.objects.create(slug="cuadernos", title="Cuadernos del ruido", publicacion=libro)
    otra = Work.objects.create(slug="otra", title="Otra obra")
    _resena(obra, "Una lectura antigua", dias=40)
    _resena(obra, "Una lectura reciente", dias=4)
    _resena(obra, "Un borrador", dias=1, estado=EditorialStatus.DRAFT)
    _resena(otra, "De otro libro", dias=2)
    sopa = soup(client, libro.get_absolute_url())
    seccion = sopa.select_one(".publicacion-resenas")
    assert seccion.h2.get_text() == "Reseñas"
    assert [h3.get_text(strip=True) for h3 in seccion.select(".fila-titulo")] == [
        "Una lectura reciente",
        "Una lectura antigua",
    ]


def test_una_publicacion_sin_resenas_no_lleva_la_seccion(client):
    libro = make_publication(slug="sin-resenas", title="Sin reseñas")
    Work.objects.create(slug="sin-resenas", title="Sin reseñas", publicacion=libro)
    page = soup(client, libro.get_absolute_url())
    assert page.select_one("h1").get_text(strip=True) == "Sin reseñas"  # control
    assert page.select_one(".publicacion-resenas") is None


def test_la_obra_resenada_lleva_a_su_publicacion_si_esta_publicada(client):
    libro = make_publication(slug="cuadernos", title="Cuadernos del ruido")
    obra = Work.objects.create(slug="cuadernos", title="Cuadernos del ruido", publicacion=libro)
    # Con una reseña publicada, la ficha de la obra sigue a la vista sin la publicación.
    _resena(obra, "Una lectura", dias=1)
    url = reverse("reviews:work_detail", args=[obra.slug])
    enlace = soup(client, url).select_one(f'header a[href="{libro.get_absolute_url()}"]')
    assert enlace is not None and enlace.get_text() == "Cuadernos del ruido"
    libro.published = False
    libro.save()
    page = soup(client, url)
    assert page.select_one("h1").get_text(strip=True) == "Cuadernos del ruido"  # control
    assert page.select_one(f'a[href="{libro.get_absolute_url()}"]') is None


def test_una_publicacion_es_una_sola_obra_resenada():
    """Todas sus reseñas apuntan a la misma obra: dos obras no pueden ser el mismo libro."""
    libro = make_publication(slug="cuadernos", title="Cuadernos del ruido")
    Work.objects.create(slug="cuadernos", title="Cuadernos del ruido", publicacion=libro)
    with pytest.raises(IntegrityError), transaction.atomic():
        Work.objects.create(slug="duplicada", title="Cuadernos del ruido", publicacion=libro)


def test_las_resenas_de_una_publicacion_cuestan_una_consulta_fija(client):
    """Con tres reseñas o con una, las mismas consultas: firmas e imágenes van en lote."""
    libro = make_publication(slug="cuadernos", title="Cuadernos del ruido")
    obra = Work.objects.create(slug="cuadernos", title="Cuadernos del ruido", publicacion=libro)
    _resena(obra, "Primera", dias=3)
    client.get(libro.get_absolute_url())  # en caliente: el perfil ya existe
    with CaptureQueriesContext(connection) as una:
        client.get(libro.get_absolute_url())
    for i in range(2):
        _resena(obra, f"Otra {i}", dias=10 + i)
    with CaptureQueriesContext(connection) as tres:
        client.get(libro.get_absolute_url())
    assert len(tres) == len(una), "una consulta más por cada reseña"


def test_la_cabecera_de_una_obra_sin_autores_no_empieza_por_un_separador(client):
    """«· Overol · 2024»: el punto medio iba delante de la editorial aunque no hubiera autores."""
    obra = Work.objects.create(slug="sin-autores", title="Sin autores", publication_year=2024)
    _resena(obra, "Su reseña", dias=1)  # la ficha existe si una reseña la respalda
    sopa = soup(client, reverse("reviews:work_detail", args=[obra.slug]))
    linea = " ".join(sopa.select_one(".index-head .meta").get_text().split())
    assert linea == "2024"
