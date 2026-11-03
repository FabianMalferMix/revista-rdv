#!/usr/bin/env python3
"""Comprueba o actualiza lo vendorizado en backend/static/vendor, desde npm.

    python3 tools/vendor/update.py check
    python3 tools/vendor/update.py update tinymce 7.9.4

El manifiesto (backend/static/vendor/manifest.json) dice, por librería, su paquete de npm, su
versión, la integridad del paquete (`dist.integrity`), de dónde salen sus archivos en el paquete,
adónde van y el sha256 de cada uno. `check` baja cada paquete, verifica su integridad y compara
cada archivo con el árbol. `update` baja la versión pedida, la verifica, pone sus archivos en su
carpeta (la de TinyMCE lleva la versión: la URL cambia con ella, y la caché del navegador no
sirve la vieja) y reescribe el manifiesto y package.json. Después: revisar el cambio, correr la
suite y la prueba de humo del panel.
"""

import base64
import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[2] / "backend" / "static" / "vendor"
MANIFEST = VENDOR / "manifest.json"
PACKAGE = VENDOR / "package.json"
REGISTRY = "https://registry.npmjs.org"


def _fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - solo el registro de npm
        return response.read()


def _download(package, version):
    """El tarball verificado contra su `dist.integrity`, y esa integridad."""
    dist = json.loads(_fetch(f"{REGISTRY}/{package}/{version}"))["dist"]
    tarball = _fetch(dist["tarball"])
    algorithm, expected = dist["integrity"].split("-", 1)
    if base64.b64encode(hashlib.new(algorithm, tarball).digest()).decode() != expected:
        sys.exit(f"{package}@{version}: el paquete no coincide con su integridad")
    return tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz"), dist["integrity"]


def _read(tar, path):
    member = tar.extractfile(f"package/{path}")
    if member is None:
        sys.exit(f"el paquete no trae {path}")
    return member.read()


def _target(lib):
    return VENDOR / lib["target"].format(version=lib["version"])


def check():
    manifest, problems = json.loads(MANIFEST.read_text("utf-8")), []
    for name, lib in manifest.items():
        tar, integrity = _download(lib["package"], lib["version"])
        if integrity != lib["integrity"]:
            problems.append(f"{name}: la integridad del manifiesto no es la de npm")
        for relative, sha in lib["files"].items():
            published = hashlib.sha256(_read(tar, lib["source"] + relative)).hexdigest()
            local = hashlib.sha256((_target(lib) / relative).read_bytes()).hexdigest()
            if not published == sha == local:
                problems.append(f"{name}: {relative} no coincide con {lib['package']}@{lib['version']}")
    for problem in problems:
        print(problem)
    print("OK: lo vendorizado es lo publicado en npm" if not problems else "FALLO")
    return 1 if problems else 0


def update(name, version):
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    lib = manifest[name]
    tar, integrity = _download(lib["package"], version)
    old = _target(lib)
    lib.update(version=version, integrity=integrity)
    new = _target(lib)
    contents = {relative: _read(tar, lib["source"] + relative) for relative in lib["files"]}
    if old != new and old.exists():
        shutil.rmtree(old)
    for relative, data in contents.items():
        (new / relative).parent.mkdir(parents=True, exist_ok=True)
        (new / relative).write_bytes(data)
        lib["files"][relative] = hashlib.sha256(data).hexdigest()
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", "utf-8")
    package = json.loads(PACKAGE.read_text("utf-8"))
    package["dependencies"][lib["package"]] = version
    PACKAGE.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"{name} {version}: {len(contents)} archivos en {new.relative_to(VENDOR)}")
    return 0


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["check"]:
            sys.exit(check())
        case ["update", name, version]:
            sys.exit(update(name, version))
        case _:
            sys.exit(__doc__)
