"""Los contenedores de producción, tal como los declaran los compose.

Producción corre docker-compose.yml con docker-compose.prod.yml encima: un servicio que está en
los dos suma los dos bloques. Los compose y la plantilla del entorno viven en la raíz del
repositorio: estas pruebas corren en el CI y se saltan en el contenedor de desarrollo.
"""

import re

from tests.repo_root import read, services

COMPOSES = ["docker-compose.yml", "docker-compose.prod.yml"]

# Los que conservan las capacidades del kernel que Docker da por defecto, con su porqué.
KEEP_CAPABILITIES = {
    "db": "la imagen oficial prepara como root su directorio de datos y luego baja de usuario",
    "redis": "la imagen oficial prepara como root su directorio de datos y luego baja de usuario",
    "backup": "corre como root sobre los volúmenes de la app y la carpeta del host",
}
_LIMIT = re.compile(r"\$\{(\w+_(?:MEM_LIMIT|CPUS)):-([^}]+)\}")


def _production():
    """Cada servicio de producción con sus dos bloques sumados, el de la base y el de prod."""
    base, prod = (services(name) for name in COMPOSES)
    return {name: base.get(name, "") + prod.get(name, "") for name in base.keys() | prod.keys()}


def _megabytes(value):
    number, unit = re.fullmatch(r"(\d+)([mg])", value).groups()
    return int(number) * (1024 if unit == "g" else 1)


def test_the_backup_gets_only_the_variables_it_names():
    """El respaldo recibe las variables que nombra (la base, restic y los avisos) y no el .env
    entero: la clave de Django y las credenciales del correo no le hacen falta."""
    production = _production()
    assert "    env_file: .env\n" in production["web"], "control: así se ve un env_file"
    assert "\n    environment:\n" in production["backup"]
    assert not re.search(r"^    env_file:", production["backup"], re.M)


def test_every_production_container_drops_the_kernel_capabilities():
    """Un proceso comprometido en un contenedor sin capacidades no puede, por ejemplo, cambiar el
    dueño de un archivo ni abrir sockets crudos. Solo los de KEEP_CAPABILITIES las conservan, y
    solo el proxy añade una: enlazar los puertos 80 y 443."""
    production = _production()
    assert set(KEEP_CAPABILITIES) < set(production), "una excepción que ya no es un servicio"
    for name, block in production.items():
        drops = "    cap_drop: [ALL]\n" in block
        assert drops != (name in KEEP_CAPABILITIES), name
    added = {
        name: re.findall(r"^    cap_add: (.+)$", block, re.M) for name, block in production.items()
    }
    assert {name: caps for name, caps in added.items() if caps} == {"proxy": ["[NET_BIND_SERVICE]"]}


def test_the_production_template_documents_every_resource_limit():
    """Cada límite de recursos del compose de producción sale en .env.prod.example con su valor
    por defecto, para ajustarlo a la RAM del servidor, y la suma que da la plantilla es la de
    esos valores."""
    pairs = _LIMIT.findall(read("docker-compose.prod.yml"))
    limits = dict(pairs)
    assert {"WEB_MEM_LIMIT", "CACHE_CPUS"} <= set(limits), "control: se leyeron los límites"
    assert sorted(set(pairs)) == sorted(limits.items()), "un límite con dos valores por defecto"
    template = read(".env.prod.example")
    documented = dict(re.findall(r"^# (\w+_(?:MEM_LIMIT|CPUS))=(\S+)$", template, re.M))
    assert documented == limits
    prose = " ".join(line.lstrip("# ") for line in template.splitlines())
    stated = re.search(r"Los valores por defecto suman (\d+)m\.", prose)
    total = sum(_megabytes(value) for name, value in limits.items() if name.endswith("MEM_LIMIT"))
    assert stated and int(stated.group(1)) == total, total
