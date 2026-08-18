"""Los tests no escriben en las carpetas de medios reales, ni en la pública ni en la privada.

La fixture `_isolated_media` cubría solo `MEDIA_ROOT`. El almacén privado se le escapaba
porque `Submission.file` declara `storage=private_storage`, un invocable que Django evalúa
una vez al cargar el modelo: el `FileSystemStorage` resultante conserva la ruta de
entonces y cambiar el ajuste después no lo mueve. Resultado: cada corrida de la suite
dejaba un `m_*.txt` con «contenido-secreto» en el `private_media` del contenedor, y se
acumulaban.
"""

import os

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def _almacen():
    return Submission._meta.get_field("file").storage


def test_el_almacen_privado_apunta_al_temporal_del_test(tmp_path):
    """Comparar el almacén con `settings.PRIVATE_MEDIA_ROOT` no serviría: sin el arreglo
    ninguno de los dos cambia y la igualdad se cumple sola. Lo que hay que exigir es que la
    ruta caiga DENTRO del temporal de esta prueba."""
    ruta = os.path.abspath(_almacen().location)
    assert ruta.startswith(os.path.abspath(str(tmp_path))), f"el almacén sigue en {ruta}"


def test_un_adjunto_no_aterriza_en_la_carpeta_privada_real(tmp_path):
    envio = Submission.objects.create(
        author_name="Quien Sea",
        author_email="quien@example.com",
        title="Con adjunto",
        body="cuerpo",
        file=SimpleUploadedFile("secreto.txt", b"contenido-que-no-debe-persistir"),
    )
    ruta = os.path.abspath(envio.file.path)
    assert ruta.startswith(os.path.abspath(str(tmp_path))), (
        f"el adjunto se guardó fuera del temporal del test: {ruta}"
    )
    assert os.path.exists(ruta)


def test_las_dos_raices_estan_separadas():
    """Que el privado sea temporal no sirve si cuelga del público, que sí se sirve por HTTP."""
    publico = os.path.abspath(settings.MEDIA_ROOT)
    privado = os.path.abspath(settings.PRIVATE_MEDIA_ROOT)
    assert privado != publico
    assert not privado.startswith(publico + os.sep)
    assert not publico.startswith(privado + os.sep)


def test_el_descubrimiento_encuentra_los_campos_privados():
    """La fixture localiza los campos por la ruta de su almacén, no por una lista fija.

    Así, un modelo futuro que use `private_storage` queda aislado sin tocar el conftest.
    Si alguien cambia ese mecanismo por un `Submission.file` a mano, esto lo delata.
    """
    from conftest import _campos_con_almacen_en

    encontrados = list(_campos_con_almacen_en(settings.PRIVATE_MEDIA_ROOT))
    assert any(c.model is Submission and c.name == "file" for c in encontrados), (
        f"no localizó Submission.file; encontrados: {[(c.model.__name__, c.name) for c in encontrados]}"
    )
