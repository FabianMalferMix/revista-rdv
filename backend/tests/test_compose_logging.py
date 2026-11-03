"""Todos los contenedores rotan sus logs.

Con el driver json-file por defecto, los logs crecen sin límite en el disco del servidor,
el mismo de la base, los medios y los respaldos. Cada servicio declara la rotación del
ancla `x-logging`, y como las anclas de YAML no cruzan archivos, docker-compose.prod.yml
repite la suya: tienen que ser iguales.

Los compose están fuera de la imagen: la prueba corre en el CI, con el repositorio entero.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSES = ["docker-compose.yml", "docker-compose.prod.yml"]
_ANCHOR = re.compile(r"^x-logging: &logging\n((?:  .*\n)+)", re.M)
_SERVICES = re.compile(r"^services:\n((?:(?:  .*)?\n)+)", re.M)
_SERVICE = re.compile(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", re.M)


def _read(name):
    path = ROOT / name
    if not path.exists():
        pytest.skip(f"{name} no está en este árbol")
    return path.read_text(encoding="utf-8")


def _services(text):
    return dict(_SERVICE.findall(_SERVICES.search(text).group(1)))


def test_both_files_declare_the_same_rotation():
    base, prod = (_ANCHOR.search(_read(name)).group(1) for name in COMPOSES)
    assert base == prod
    assert "driver: json-file" in base
    assert re.search(r'max-size: "\d+m"', base) and re.search(r'max-file: "\d+"', base)


def test_every_service_rotates_its_logs():
    base, prod = (_services(_read(name)) for name in COMPOSES)
    assert {"web", "worker", "beat", "db", "redis", "proxy"} <= set(base) | set(prod)
    for name in set(base) | set(prod):
        # Un servicio de producción que ya existe en la base hereda su `logging`.
        block = base.get(name, "") + prod.get(name, "")
        assert "    logging: *logging\n" in block, name
