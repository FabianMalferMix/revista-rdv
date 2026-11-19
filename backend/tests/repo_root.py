"""Los archivos de la raíz del repositorio, y los compose partidos en servicios, para las pruebas.

Los compose, la plantilla del entorno de producción y las herramientas del CI viven en la raíz,
fuera de la imagen: en el contenedor de desarrollo, que monta solo backend/, las pruebas que los
leen se saltan, y corren en el CI y con el repositorio entero montado. La imagen no trae PyYAML,
así que los servicios se separan por la sangría: cada uno empieza con dos espacios y su nombre, y
su bloque son las líneas que lo siguen con cuatro espacios o más, o en blanco. Las anclas de YAML
no se resuelven: una prueba que las mire busca el `*ancla` en el bloque.
"""

import re

import pytest
from django.conf import settings

ROOT = settings.BASE_DIR.parent
_SERVICES = re.compile(r"^services:\n((?:(?:  .*)?\n)+)", re.M)
_SERVICE = re.compile(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", re.M)


def locate(name):
    """La ruta de un archivo de la raíz; si no está en este árbol, la prueba se salta."""
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} vive en la raíz del repositorio, fuera del contenedor")
    return path


def read(name):
    """El texto de un archivo de la raíz; si no está en este árbol, la prueba se salta."""
    return locate(name).read_text(encoding="utf-8")


def services(name):
    """Los servicios de un compose: {nombre: su bloque, con la sangría tal cual}."""
    return dict(_SERVICE.findall(_SERVICES.search(read(name)).group(1)))
