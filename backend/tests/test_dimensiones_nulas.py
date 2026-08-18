"""`ensure_derivatives` repara de verdad las dimensiones ausentes en la BASE.

`MediaAsset.file` es un `ImageField` con `width_field`/`height_field`, y Django conecta
`update_dimension_fields` a `post_init`: al cargar una fila cuya columna está a NULL, abre
el archivo y rellena los atributos en memoria sin escribir nada. La reparación comparaba
contra esos atributos, así que la condición nunca se cumplía y la columna se quedaba en
NULL para siempre —pagando una apertura de archivo por cada instanciación—. Encontrado en
las pruebas manuales del §6.4: 10 de 11 recursos estaban así, y el comando informaba
«Derivados verificados» sin haber reparado nada.
"""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from PIL import Image

from apps.media.models import MediaAsset

pytestmark = pytest.mark.django_db


def _jpeg(ancho=1600, alto=1000):
    buf = BytesIO()
    Image.new("RGB", (ancho, alto), (10, 80, 160)).save(buf, "JPEG", quality=70)
    return buf.getvalue()


def _columna(pk):
    """Lee width/height por SQL: `values_list` bastaría, pero esto es inmune a cualquier
    capa del ORM y deja claro qué se está afirmando."""
    with connection.cursor() as cur:
        cur.execute("SELECT width, height FROM media_mediaasset WHERE id = %s", [pk])
        return cur.fetchone()


def _recurso(ancho=1600, alto=1000):
    return MediaAsset.objects.create(
        alt_text="prueba", file=SimpleUploadedFile("foto.jpg", _jpeg(ancho, alto))
    )


def test_post_init_disfraza_la_columna_vacia():
    """Fija el porqué del arreglo: sin esto, el resto de las pruebas parecerían absurdas."""
    a = _recurso()
    MediaAsset.objects.filter(pk=a.pk).update(width=None, height=None)
    assert _columna(a.pk) == (None, None)
    assert MediaAsset.objects.get(pk=a.pk).width == 1600  # el ORM lo tapa


def test_repara_la_columna_cuando_esta_a_nulo():
    a = _recurso()
    MediaAsset.objects.filter(pk=a.pk).update(width=None, height=None)
    MediaAsset.objects.get(pk=a.pk).ensure_derivatives()
    assert _columna(a.pk) == (1600, 1000)


def test_repara_aunque_los_derivados_ya_existan():
    """El caso que el atajo de rendimiento se saltaba: con los derivados en su sitio, la
    función salía antes de abrir el archivo y no llegaba nunca a reparar."""
    a = _recurso()
    a.ensure_derivatives()  # deja 480/960/1440 en disco
    MediaAsset.objects.filter(pk=a.pk).update(width=None, height=None)
    MediaAsset.objects.get(pk=a.pk).ensure_derivatives()
    assert _columna(a.pk) == (1600, 1000)


def test_no_corrige_una_dimension_equivocada_y_es_deliberado():
    """Límite conocido, fijado aquí para que no se descubra por sorpresa.

    Con la columna NO vacía la función se fía de ella y ni siquiera abre el archivo: ese
    atajo es lo que evita releer todo el catálogo en cada pasada. Detectar una columna que
    miente exigiría abrir cada imagen siempre, que es justo el coste que se quiere evitar.
    Y no es un estado que se dé solo: Django rellena las dimensiones desde el archivo al
    guardar, así que el NULL aparece por caminos que se saltan `save()` (una migración de
    datos, `bulk_create`, una siembra), no un valor equivocado.
    """
    a = _recurso()
    MediaAsset.objects.filter(pk=a.pk).update(width=99, height=99)
    MediaAsset.objects.get(pk=a.pk).ensure_derivatives()
    assert _columna(a.pk) == (99, 99)


def test_el_comando_repara_todo_el_catalogo():
    from django.core.management import call_command

    recursos = [_recurso(), _recurso(1200, 800)]
    MediaAsset.objects.update(width=None, height=None)
    call_command("generate_image_derivatives", verbosity=0)
    assert [_columna(r.pk) for r in recursos] == [(1600, 1000), (1200, 800)]


def test_no_reabre_el_archivo_cuando_no_hace_falta(monkeypatch):
    """El atajo de rendimiento sigue vivo: con la columna correcta y los derivados en
    disco, no se abre nada. Si esto cae, el arreglo salió caro."""
    a = _recurso()
    a.ensure_derivatives()
    a = MediaAsset.objects.get(pk=a.pk)

    def _prohibido(*args, **kwargs):
        raise AssertionError("abrió el archivo sin necesidad")

    monkeypatch.setattr(type(a.file), "open", _prohibido)
    a.ensure_derivatives()
