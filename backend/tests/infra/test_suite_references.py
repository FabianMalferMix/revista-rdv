"""El repositorio nombra archivos de la suite: el registro de decisiones, CONTRIBUTING, el CI y
los comentarios que remiten a la prueba que vigila una garantía. Si una prueba se muda o se
renombra, la mención queda apuntando a nada, y quien la sigue no encuentra lo que se le promete.

Estas pruebas leen los archivos de texto del repositorio: cada ruta `tests/….py` (o
`backend/tests/….py`) nombrada existe en esa ruta, y cada `test_….py` nombrado sin ruta existe
en algún lugar de la suite. Recorren el árbol y no lo que sigue git, porque la imagen de
desarrollo no trae git: saltan lo que se genera y lo que hay en la raíz sin ser del repositorio.

DÓNDE CORREN: en el CI, que hace checkout del repositorio completo y lanza pytest desde
`backend/`. En el contenedor de desarrollo se SALTAN, porque solo monta `backend/`.
"""

import re
from functools import cache

import pytest
from django.conf import settings

REPO_ROOT = settings.BASE_DIR.parent
TESTS_DIR = settings.BASE_DIR / "tests"

# Registros de su momento: citan los archivos como eran cuando se escribieron. La huella de
# `.gitleaksignore` nombra el archivo de un commit viejo, y cambiarla la invalida.
RECORDS = {"docs/auditoria-codigo.md", "docs/backlog-codigo.md", ".gitleaksignore"}
# Un nombre inventado: la guía de pruebas manuales lo da como ejemplo de una prueba de un rato.
EXAMPLES = {"test_canario_warning.py"}
# Lo que se genera, en cualquier carpeta, por su nombre; y, por su ruta desde la raíz, lo que
# .gitignore deja fuera y puede tener texto. Por la ruta y no por el nombre: `media` es también
# una app.
SKIPPED_NAMES = {".git", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "node_modules"}
SKIPPED_PATHS = {
    ".claude",
    "backups",
    "htmlcov",
    "backend/media",
    "backend/mediafiles",
    "backend/private_media",
    "backend/staticfiles",
    "tools/ux/out",
}
SUFFIXES = {
    ".css",
    ".html",
    ".in",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
NAMES = {"Caddyfile", "Dockerfile"}

PATH_REF = re.compile(r"(?<![\w/.-])(?:backend/)?(tests/[\w/]+\.py)\b")
NAME_REF = re.compile(r"(?<![\w/.-])(test_\w+\.py)\b")


def _text_files():
    pending = [REPO_ROOT]
    while pending:
        folder = pending.pop()
        for entry in sorted(folder.iterdir()):
            relative = entry.relative_to(REPO_ROOT).as_posix()
            if entry.is_dir():
                skipped = entry.name in SKIPPED_NAMES or relative in SKIPPED_PATHS
                if not skipped and not entry.is_symlink():
                    pending.append(entry)
            elif relative not in RECORDS and (entry.suffix in SUFFIXES or entry.name in NAMES):
                yield relative, entry


@cache
def _references():
    """Las rutas y los nombres de archivos de prueba que nombra el repositorio, cada uno con el
    archivo y la línea donde aparece."""
    if not (REPO_ROOT / "README.md").exists():
        pytest.skip("la raíz del repositorio no está en este árbol")
    paths, names = [], []
    for relative, entry in _text_files():
        try:
            text = entry.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            where = f"{relative}:{number}"
            paths += [(where, match) for match in PATH_REF.findall(line)]
            names += [(where, match) for match in NAME_REF.findall(line)]
    return paths, names


def _existing_tests():
    return {path.name for path in TESTS_DIR.rglob("test_*.py")}


def test_every_named_test_path_exists():
    paths, names = _references()
    # Control positivo: el repositorio nombra decenas de archivos de la suite; CONTRIBUTING
    # remite por su ruta al ayudante de las hojas, y el código de las apps, a sus pruebas.
    assert len({path.rsplit("/", 1)[-1] for _, path in paths} | {n for _, n in names}) >= 40
    assert any(w.startswith("CONTRIBUTING.md:") and p == "tests/css.py" for w, p in paths)
    assert any(where.startswith("backend/apps/") for where, _ in paths)
    missing = [
        f"{where}: {path}"
        for where, path in paths
        if not (settings.BASE_DIR / path).is_file() and path.rsplit("/", 1)[-1] not in EXAMPLES
    ]
    assert not missing, "rutas de la suite que no existen:\n" + "\n".join(missing)


def test_every_named_test_file_exists_somewhere_in_the_suite():
    _, names = _references()
    existing = _existing_tests()
    # Control positivo: los comentarios nombran pruebas sin su ruta, y la suite las tiene.
    assert len({name for _, name in names} & existing) >= 5
    missing = [
        f"{where}: {name}" for where, name in names if name not in existing and name not in EXAMPLES
    ]
    assert not missing, "archivos de prueba nombrados que no existen:\n" + "\n".join(missing)


def test_the_examples_are_still_examples():
    """Un nombre de ejemplo no puede coincidir con una prueba real: la excepción la taparía."""
    existing = _existing_tests()
    assert len(existing) >= 100, "control: se recorre la suite entera, también sus carpetas"
    assert not EXAMPLES & existing
