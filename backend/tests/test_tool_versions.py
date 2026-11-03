"""Las versiones de las herramientas son las mismas donde se repiten.

El CI instala Python con la versión de .python-version, y la imagen parte de una base de
Python: si divergieran, el CI probaría con otro intérprete que el de producción. pip va
fijado en el Dockerfile y en cada job del CI que lo instala, con la misma versión.

Leen archivos de la raíz del repositorio: corren en el CI y se saltan en el contenedor de
desarrollo, que solo monta backend/.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_PIP = re.compile(r"(?<![\w-])pip==([\d.]+)")


def _read(relative):
    path = RAIZ / relative
    if not path.exists():
        pytest.skip(f"{relative} vive en la raíz del repositorio, fuera del contenedor")
    return path.read_text(encoding="utf-8")


def _workflows():
    folder = RAIZ / ".github" / "workflows"
    if not folder.exists():
        pytest.skip("los workflows viven en la raíz del repositorio, fuera del contenedor")
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(folder.glob("*.yml")))


def test_the_ci_python_is_the_image_python():
    version = _read(".python-version").strip()
    base = re.search(r"^FROM python:(\d+\.\d+)", _read("backend/Dockerfile"), re.M)
    assert base and version == base.group(1)
    # Ningún job fija otra: todos la leen de .python-version.
    workflows = _workflows()
    assert "python-version-file: .python-version" in workflows
    assert "python-version:" not in workflows


def test_pip_is_pinned_to_one_version():
    dockerfile, workflows = _read("backend/Dockerfile"), _workflows()
    assert _PIP.search(dockerfile) and _PIP.search(workflows)  # control positivo
    assert len(set(_PIP.findall(dockerfile + workflows))) == 1
    assert "--upgrade pip" not in dockerfile + workflows
