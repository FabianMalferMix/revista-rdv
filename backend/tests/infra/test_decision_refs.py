"""La guarda de los identificadores de decisión, de ticket y de sesión (tools/ci/decision_refs.py).

La corre pre-commit en el job hygiene del CI. Aquí se carga como módulo sobre un árbol de prueba,
y la lista de archivos de git, que la imagen no trae, sale de ese árbol.
"""

import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest

from tests.repo_root import locate

CODE = "backend/apps/content/views.py"


@pytest.fixture
def guard(tmp_path, monkeypatch):
    """`guard(archivos, línea_base)`: la guarda sobre un árbol con esos archivos, que son los que
    lista git, y esa línea base. Devuelve con qué código sale."""
    spec = importlib.util.spec_from_file_location(
        "decision_refs", locate("tools/ci/decision_refs.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "BASELINE", tmp_path / "baseline.json")
    monkeypatch.setattr(sys, "argv", ["decision_refs.py"])

    def run(files, baseline):
        for name, text in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text, encoding="utf-8")
        (tmp_path / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        listing = SimpleNamespace(stdout="\0".join(files).encode())
        monkeypatch.setattr(module, "subprocess", SimpleNamespace(run=lambda *a, **k: listing))
        return module.main()

    return run


def test_a_new_identifier_in_the_code_fails_and_says_where(guard, capsys):
    files = {CODE: "x = 1\n# Como se decidió en D18, la portada va primero.\n"}
    assert guard(files, {}) == 1
    out = capsys.readouterr().out
    assert f"{CODE}: 1 (la línea base admite 0)" in out
    assert f"{CODE}:2: «D18»" in out
    # Control: la misma línea, ya contada en la línea base, pasa.
    assert guard(files, {CODE: 1}) == 0


def test_a_baseline_above_the_count_has_to_be_lowered(guard, capsys):
    """Así no queda margen para que vuelva a subir."""
    assert guard({CODE: "# D18\n"}, {CODE: 2}) == 1
    out = capsys.readouterr().out
    assert "Bájala con" in out and f"{CODE}: 1 (la línea base dice 2)" in out


def test_documents_migrations_colours_and_entities_do_not_count(guard, capsys):
    """Los documentos y las migraciones pueden citar decisiones, y un color o una entidad HTML no
    son un número de PR; en el código, un número con una o dos cifras o entre paréntesis, sí."""
    quiet = {
        "docs/notas.md": "Se decidió en D18 (#147).\n",
        "backend/apps/content/migrations/0002_datos.py": "# B07\n",
        "backend/static/css/sitio.css": ".a { color: #333; background: #151515; }\n",
        "backend/templates/pie.html": "<p>&#15; &#147;</p>\n",
    }
    assert guard(quiet, {}) == 0
    # Control: en el código, los números de PR cuentan.
    assert guard({**quiet, CODE: "# Visto en #15 y en (#147).\n"}, {}) == 1
    assert f"{CODE}: 2 (la línea base admite 0)" in capsys.readouterr().out
