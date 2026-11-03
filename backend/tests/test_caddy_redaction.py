"""El filtro de logs de Caddy cubre todas las rutas con token del URLconf.

Caddy no puede preguntarle a Django qué rutas llevan un token: su filtro es una expresión
escrita en el Caddyfile. Esta prueba la ata al URLconf. Si se renombra una ruta del boletín
o se añade otra con token, falla hasta que el Caddyfile la cubra, en la URI y en las dos
cabeceras que repiten la URL de la página, en el log de errores y en el de acceso.

El Caddyfile está fuera de la imagen: la prueba corre en el CI, con el repositorio entero.
"""

import re
from pathlib import Path

import pytest

from config.redaction import token_route_prefixes

CADDYFILE = Path(__file__).resolve().parents[2] / "infra" / "caddy" / "Caddyfile"
FIELDS = ("request>uri", "request>headers>Referer", "request>headers>Hx-Current-Url")
_FILTER = re.compile(r'^\s*(request>\S+) regexp "([^"]+)" "([^"]+)"\s*$', re.M)
VALUE = "no-es-una-credencial"


def _filters():
    if not CADDYFILE.exists():
        pytest.skip("el Caddyfile no está en este árbol")
    return _FILTER.findall(CADDYFILE.read_text(encoding="utf-8"))


def test_each_log_redacts_the_uri_and_both_headers():
    fields = [field for field, _, _ in _filters()]
    # Dos logs: el de errores (global) y el de acceso del sitio.
    assert sorted(fields) == sorted(FIELDS * 2)


@pytest.mark.parametrize("prefix", token_route_prefixes())
def test_every_token_route_is_redacted_by_caddy(prefix):
    for field, pattern, replacement in _filters():
        # La sintaxis de estas expresiones es la misma en Go y en Python, salvo $1.
        redacted = re.sub(pattern, replacement.replace("$1", r"\1"), f"https://x{prefix}{VALUE}/")
        assert VALUE not in redacted, (field, prefix)
        assert "<redactado>" in redacted
