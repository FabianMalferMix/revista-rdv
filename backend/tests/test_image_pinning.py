"""Las imágenes de contenedor van fijadas por digest (hallazgo S-34).

Un tag como `postgres:16` o `python:3.12-slim` es MUTABLE: el mismo texto puede resolver
mañana a una imagen distinta, así que ni la construcción es reproducible ni se puede
afirmar qué se está ejecutando. Fijar el digest además reactiva a Dependabot, que con un
tag sin componente de parche no tenía nada que proponer.

Estas comprobaciones son de formato y no consultan la red: existen para que nadie
desfije una imagen sin darse cuenta.

DÓNDE CORREN: en el CI, que hace checkout del repositorio completo y lanza pytest desde
`backend/`, de modo que la raíz queda accesible. En el contenedor de desarrollo se
SALTAN, porque solo monta `backend/` y los ficheros de la raíz no existen ahí. El salto
es explícito (`pytest.skip` con motivo) y no un falso verde.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

DOCKERFILES = ["backend/Dockerfile", "infra/backup/Dockerfile"]
COMPOSES = ["docker-compose.yml", "docker-compose.prod.yml", "docker-compose.override.yml"]

_FROM = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
_IMAGE = re.compile(r"^\s*image:\s*(\S+)", re.MULTILINE)
_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _leer(relativa):
    ruta = RAIZ / relativa
    if not ruta.exists():
        pytest.skip(f"{relativa} no existe en este árbol")
    return ruta.read_text(encoding="utf-8")


@pytest.mark.parametrize("relativa", DOCKERFILES)
def test_las_imagenes_base_van_por_digest(relativa):
    for imagen in _FROM.findall(_leer(relativa)):
        # Los stages internos (`FROM base AS dev`) no son imágenes remotas.
        if "/" not in imagen and ":" not in imagen:
            continue
        assert _DIGEST.search(imagen), f"{relativa}: {imagen} no está fijada por digest"


@pytest.mark.parametrize("relativa", COMPOSES)
def test_las_imagenes_de_compose_van_por_digest(relativa):
    for imagen in _IMAGE.findall(_leer(relativa)):
        if imagen.startswith("$"):  # parametrizada por entorno
            continue
        assert _DIGEST.search(imagen), f"{relativa}: {imagen} no está fijada por digest"


def test_el_digest_de_postgres_es_el_mismo_en_todas_partes():
    """El sidecar de respaldos y la base de datos deben compartir imagen: si divergen,
    un `pg_dump` puede generar un volcado que la otra versión no restaure."""
    compose = _leer("docker-compose.yml")
    dockerfile = _leer("infra/backup/Dockerfile")
    en_compose = re.search(r"image:\s*(postgres:\S+)", compose)
    en_backup = re.search(r"FROM\s+(postgres:\S+)", dockerfile)
    assert en_compose and en_backup
    assert en_compose.group(1) == en_backup.group(1)
