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
}
# Las que añade alguno de los que las sueltan todas, con su porqué.
ADDED_CAPABILITIES = {
    "proxy": {"NET_BIND_SERVICE": "enlazar los puertos 80 y 443"},
    "backup": {
        "DAC_OVERRIDE": "backup.sh y restore.sh escriben en la carpeta del host y en los volúmenes,"
        " que son de otros usuarios",
        "CHOWN": "restore.sh devuelve cada archivo restaurado a su dueño, el usuario de la app",
        "FOWNER": "restore.sh fija los permisos de cada archivo después de devolvérselo a su dueño",
    },
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
    dueño de un archivo ni abrir sockets crudos. Solo los de KEEP_CAPABILITIES las conservan, los
    de ADDED_CAPABILITIES añaden las que dicen y ni una más, y ninguno corre privilegiado."""
    production = _production()
    assert set(KEEP_CAPABILITIES) < set(production), "una excepción que ya no es un servicio"
    added = {}
    for name, block in production.items():
        drops = "    cap_drop: [ALL]\n" in block
        assert drops != (name in KEEP_CAPABILITIES), name
        assert not re.search(r"^    privileged:", block, re.M), name
        for value in re.findall(r"^    cap_add:(.*)$", block, re.M):
            listed = re.fullmatch(r" \[([A-Z_, ]+)\]", value)
            assert listed, f"{name}: cap_add va en una lista en línea y sin comillas"
            added.setdefault(name, set()).update(cap.strip() for cap in listed.group(1).split(","))
    assert added == {name: set(caps) for name, caps in ADDED_CAPABILITIES.items()}


def test_no_production_container_gains_privileges_from_a_setuid_binary():
    """Con no-new-privileges, ningún proceso gana privilegios al ejecutar un binario setuid, como
    su o sudo: lo llevan todos, también los que conservan las capacidades."""
    production = _production()
    assert {"web", "db", "backup"} <= set(production), "control: los servicios de producción"
    without = [
        name
        for name, block in production.items()
        if '    security_opt: ["no-new-privileges:true"]\n' not in block
    ]
    assert without == []


def test_the_ci_runs_the_backup_scripts_with_their_production_options():
    """El job backup-restore del CI saca del compose de producción las opciones de seguridad del
    respaldo, y corre backup.sh y restore.sh siempre con ellas, por $BK o por $RESTORE: así los
    prueba con las capacidades que tienen en producción."""
    workflow = read(".github/workflows/ci.yml")
    job = re.search(r"^  backup-restore:\n((?:(?:    .*)?\n)*)", workflow, re.M)
    script = re.sub(r"\\\n", " ", job.group(1))
    assert re.search(
        r"SEGURIDAD=\$\(docker compose -f docker-compose.yml -f docker-compose.prod.yml +"
        r"--profile backup config .*\| jq -r '.services.backup$",
        script,
        re.M,
    )
    for name in ("BK", "RESTORE"):
        assert re.search(rf'^ *{name}="docker run [^"]*\$SEGURIDAD\s', script, re.M), name
    launches = re.findall(r"^.*/scripts/(?:backup|restore)\.sh.*$", script, re.M)
    assert len(launches) > 2, "control: el job corre los dos guiones"
    for line in launches:
        assert re.search(r"\$(BK|RESTORE) .*/scripts/(backup|restore)\.sh", line), line


def test_docker_waits_for_a_confirmation_email_to_finish():
    """Al parar el worker, Docker espera su stop_grace_period antes de matarlo: tiene que cubrir el
    límite duro del correo de confirmación, para que uno en curso termine."""
    from apps.community.tasks import send_confirmation_email

    grace = re.search(r"^    stop_grace_period: (\d+)s$", _production()["worker"], re.M)
    assert grace, "control: el worker declara cuánto espera Docker"
    assert int(grace.group(1)) > send_confirmation_email.time_limit


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
