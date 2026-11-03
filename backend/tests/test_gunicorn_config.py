"""Las opciones de gunicorn están en un solo sitio, backend/gunicorn.conf.py, y gunicorn las
entiende.

La imagen arranca `gunicorn config.wsgi:application` sin más, y el compose de producción no lo
cambia: así el CI, que levanta la imagen con ese compose, prueba el mismo gunicorn que
producción. gunicorn ignora en silencio un nombre que no conoce, así que una errata en el
archivo no impediría arrancar: solo dejaría la opción sin efecto.

Las pruebas de los compose leen archivos de la raíz del repositorio: corren en el CI y se
saltan en el contenedor de desarrollo, que solo monta backend/.
"""

import json
import re
import runpy
from pathlib import Path

import pytest
from gunicorn.config import Config

BACKEND = Path(__file__).resolve().parents[1]
RAIZ = BACKEND.parent


def _options():
    names = runpy.run_path(str(BACKEND / "gunicorn.conf.py"))
    return {name: value for name, value in names.items() if not name.startswith("_")}


def _service(compose, name):
    """El bloque de un servicio en un archivo de compose."""
    path = RAIZ / compose
    if not path.exists():
        pytest.skip(f"{compose} vive en la raíz del repositorio, fuera del contenedor")
    match = re.search(
        rf"^  {name}:\n(.*?)(?=^  \S|^\S|\Z)", path.read_text(encoding="utf-8"), re.M | re.S
    )
    assert match, f"{compose} no tiene el servicio {name}"
    return match.group(1)


def test_every_name_in_the_config_file_is_a_gunicorn_setting():
    options = _options()
    assert "workers" in options  # control positivo: el archivo se leyó
    assert sorted(set(options) - set(Config().settings)) == []


def test_gunicorn_accepts_the_values_and_serves_with_threads():
    config = Config()
    for name, value in _options().items():
        config.set(name, value)  # valida cada valor, como al arrancar
    # Con más de un hilo por proceso, la clase pasa a gthread: una petición lenta no ocupa un
    # proceso entero.
    assert config.worker_class_str == "gthread"


def test_the_image_starts_gunicorn_without_options():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    commands = [json.loads(cmd) for cmd in re.findall(r"^CMD\s+(\[.*\])$", dockerfile, re.M)]
    assert commands
    assert all(cmd == ["gunicorn", "config.wsgi:application"] for cmd in commands)


@pytest.mark.parametrize("compose", ["docker-compose.yml", "docker-compose.prod.yml"])
def test_production_runs_the_image_command(compose):
    web = _service(compose, "web")
    assert "stop_grace_period" in web or "build:" in web  # control positivo: es el bloque
    assert not re.search(r"^    (command|entrypoint):", web, re.M)


def test_docker_waits_for_gunicorn_to_finish_its_requests():
    """Al parar web, Docker espera stop_grace_period antes de matar el proceso: tiene que
    cubrir el plazo que gunicorn da a las peticiones en curso."""
    grace = re.search(
        r"^    stop_grace_period: (\d+)s$", _service("docker-compose.prod.yml", "web"), re.M
    )
    assert grace and int(grace.group(1)) > _options()["graceful_timeout"]
