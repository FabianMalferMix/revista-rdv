"""Las herramientas de desarrollo (apps/devtools) solo existen y solo corren en desarrollo.

Sus comandos siembran contenido ficticio, con cuentas del panel incluidas, o copian la base al
repositorio público. La app se instala con DEBUG o con DJANGO_DEV_TOOLS=1, y la imagen de
producción no trae su código (lo comprueba el job build-prod del CI). Los cuatro comandos
heredan una sola guarda, que exige DEBUG y un entorno que no se declare de producción, y
ninguna opción la salta.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import CommandError
from django.db.migrations.loader import MigrationLoader

from apps.devtools.management.base import DevelopmentCommand

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Los comandos de desarrollo, con los argumentos con que se los llama aquí.
DEV_COMMANDS = {
    "seed_demo": (),
    "seed_textos_largos": (),
    "seed_material_generico": (),
    "datos_de_desarrollo": ("marcar",),
}


def test_the_dev_commands_live_in_devtools_and_share_its_guard():
    commands = {name for name, app in get_commands().items() if app == "apps.devtools"}
    assert commands == set(DEV_COMMANDS)
    for name in commands:
        assert isinstance(load_command_class("apps.devtools", name), DevelopmentCommand), name


# ── La guarda ─────────────────────────────────────────────────


@pytest.fixture
def handled(monkeypatch):
    """Los comandos que llegaron a `handle`, que aquí no hace nada: la guarda corre antes."""
    calls = []

    def handle(self, *args, **options):
        calls.append(type(self).__module__.rsplit(".", 1)[-1])

    for name in DEV_COMMANDS:
        monkeypatch.setattr(type(load_command_class("apps.devtools", name)), "handle", handle)
    return calls


def _run(name, *extra):
    call_command(name, *DEV_COMMANDS[name], *extra, verbosity=0)


@pytest.mark.parametrize("name", DEV_COMMANDS)
def test_with_debug_off_a_dev_command_refuses_to_run(name, settings, handled):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG está apagado"):
        _run(name)
    assert handled == []


@pytest.mark.parametrize("name", DEV_COMMANDS)
def test_an_environment_declared_production_refuses_even_with_debug(name, settings, handled):
    settings.DEBUG = True
    settings.ENVIRONMENT = "production"
    with pytest.raises(CommandError, match="se declara de producción"):
        _run(name)
    assert handled == []


@pytest.mark.parametrize("name", DEV_COMMANDS)
def test_in_development_a_dev_command_runs(name, settings, handled):
    """El control de las anteriores: con DEBUG y fuera de producción, llega a `handle`."""
    settings.DEBUG = True
    settings.ENVIRONMENT = "development"
    _run(name)
    assert handled == [name]


@pytest.mark.parametrize("name", DEV_COMMANDS)
def test_no_dev_command_accepts_force(name, settings, handled):
    """Ni como opción propia ni como abreviatura de `--force-color`, que argparse admitiría."""
    settings.DEBUG = True
    with pytest.raises(CommandError, match="unrecognized arguments: --force"):
        _run(name, "--force")
    # Tampoco desde el código, como lo llama tools/ux/preparar-entorno.sh.
    with pytest.raises(TypeError, match="Unknown option"):
        call_command(name, *DEV_COMMANDS[name], force=True, verbosity=0)
    assert handled == []


# ── Instalada solo en desarrollo, en un proceso aparte ────────
# Cada caso arranca Django con su propio entorno. La base apunta a un host que no existe: listar
# los comandos no la toca, y así ningún arranque de estas pruebas llega a la de desarrollo.

# Un entorno de producción que pasa el guard de arranque, con los valores de prueba del CI.
PRODUCTION_ENV = {
    "DJANGO_SECRET_KEY": "ci-prod-secret-Kx7mQ9vLpZ4wR8nT3bY6cF1jH5dG0sA2eU7oI4aN9qW",
    "POSTGRES_PASSWORD": "ci-strong-db-password",
    "REDIS_PASSWORD": "ci-strong-redis-password",
    "DJANGO_ALLOWED_HOSTS": "ci.example.com",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://ci.example.com",
    "SITE_URL": "https://ci.example.com",
    "DJANGO_ALLOW_WEAKENED": "SENTRY_DSN",
    "DEFAULT_FROM_EMAIL": "no-reply@ci.example.com",
}


def _manage(*args, **env):
    """`manage.py` con `env` como único entorno (DEBUG apagado si no se enciende)."""
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=BACKEND_DIR,
        env={"PATH": os.environ["PATH"], "POSTGRES_HOST": "sin-base.invalid", **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _listed_commands(**env):
    result = _manage("help", "--commands", **env)
    assert result.returncode == 0, result.stderr[-500:]
    return set(result.stdout.split())


def test_production_does_not_list_the_dev_commands():
    listed = _listed_commands(**PRODUCTION_ENV)
    assert "setup_groups" in listed, "control: es la lista de los comandos"
    assert listed & set(DEV_COMMANDS) == set()


@pytest.mark.parametrize(
    "env",
    [{"DJANGO_DEBUG": "1"}, {**PRODUCTION_ENV, "DJANGO_DEV_TOOLS": "1"}],
    ids=["DEBUG", "DJANGO_DEV_TOOLS"],
)
def test_debug_or_dev_tools_install_them(env):
    assert set(DEV_COMMANDS) <= _listed_commands(**env)


def test_a_declared_production_refuses_from_the_command_line_even_with_debug():
    result = _manage("seed_demo", DJANGO_DEBUG="1", DJANGO_ENVIRONMENT="production")
    assert result.returncode == 1
    assert "se declara de producción" in result.stderr, result.stderr[-500:]


_SERVICES = re.compile(r"^services:\n((?:(?:  .*)?\n)+)", re.M)
_SERVICE = re.compile(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", re.M)


def _services(compose):
    path = BACKEND_DIR.parent / compose
    if not path.exists():
        pytest.skip(f"{compose} vive en la raíz del repositorio, fuera del contenedor")
    return dict(_SERVICE.findall(_SERVICES.search(path.read_text(encoding="utf-8")).group(1)))


def test_the_production_compose_declares_production_wherever_the_app_runs():
    """Cada servicio que corre la app declara en docker-compose.prod.yml el entorno que la guarda
    rechaza: el valor viaja por el mismo camino que en producción, la variable de entorno."""
    app = {
        name
        for name, block in _services("docker-compose.yml").items()
        if "    image: resenas-app:" in block
    }
    assert {"release", "web", "worker", "beat"} <= app, "control: son los servicios de la app"
    prod = _services("docker-compose.prod.yml")
    declared = {
        name: re.findall(r"^      DJANGO_ENVIRONMENT: (\S+)$", prod.get(name, ""), re.M)
        for name in app
    }
    assert all(len(values) == 1 for values in declared.values()), declared
    (value,) = {values[0] for values in declared.values()}
    result = _manage("seed_demo", DJANGO_DEBUG="1", DJANGO_ENVIRONMENT=value)
    assert result.returncode == 1
    assert "se declara de producción" in result.stderr, result.stderr[-500:]


# ── Nada de producción depende de la app ──────────────────────


def test_no_migration_outside_devtools_depends_on_it():
    """Sin la app instalada, una dependencia así rompería `migrate` en producción."""
    migrations = MigrationLoader(None, ignore_no_migrations=True).disk_migrations
    assert ("devtools", "0001_initial") in migrations, "control: se leyeron las de devtools"
    dependents = [
        key
        for key, migration in migrations.items()
        if key[0] != "devtools" and any(app == "devtools" for app, _ in migration.dependencies)
    ]
    assert dependents == []


def test_no_production_code_imports_it():
    """La imagen de producción no trae apps/devtools: importarla desde otra parte la rompería."""
    importing = re.compile(r"^\s*(?:from|import)\s+apps\.devtools\b", re.M)
    sources = [
        *BACKEND_DIR.glob("*.py"),
        *(BACKEND_DIR / "apps").rglob("*.py"),
        *(BACKEND_DIR / "config").rglob("*.py"),
    ]
    own = [path for path in sources if "devtools" in path.parts]
    assert any(importing.search(path.read_text(encoding="utf-8")) for path in own), (
        "control: la expresión reconoce los imports de la propia app"
    )
    offenders = [
        str(path.relative_to(BACKEND_DIR))
        for path in sources
        if "devtools" not in path.parts and importing.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
