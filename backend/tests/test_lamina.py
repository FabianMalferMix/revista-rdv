"""La lámina de la portada sale de sus maestras con una receta fija.

Las maestras, sin pérdida, y el comando que rehace las copias (`generate_lamina_variants`) están
en apps/devtools. Rehacerlas desde el repositorio da los mismos bytes que las copias versionadas,
porque la receta fija cada parámetro de los codificadores, también los que Pillow elegiría según
la máquina. Lo que la portada sirve de la lámina, y su peso, está en test_portada_obra.py.
"""

import re
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from PIL import Image

from apps.devtools.management.commands import generate_lamina_variants as cmd
from apps.site.templatetags.portada import LAMINA

PORTADA = Path(__file__).resolve().parent.parent / "static" / "img" / "portada"
# Lo que sirve la portada: cada copia de LAMINA en AVIF y en WebP, y la reserva en JPEG.
SERVED = {
    f"img/portada/lamina-{forma}-{width}.{ext}"
    for forma, sizes in LAMINA.items()
    for width, _ in sizes
    for ext in ("avif", "webp")
} | {"img/portada/lamina-ancha-1440.jpg"}


def test_regenerating_the_lamina_from_its_masters_gives_the_versioned_bytes():
    variants = cmd.render_variants()
    assert set(variants) == SERVED, "control: la receta da las quince copias que sirve la portada"
    assert cmd.stale_variants(variants) == ([], [], []), (
        "las copias de static/img/portada/ no son las que dan las maestras: las rehace "
        "`python manage.py generate_lamina_variants`"
    )
    for path in PORTADA.glob("lamina-*"):
        with Image.open(path) as image:
            assert not {"icc_profile", "exif", "xmp"} & image.info.keys(), path.name


def test_the_check_names_what_differs_what_is_missing_and_what_is_left_over(
    settings, monkeypatch, tmp_path
):
    """El control de la anterior, con una receta de mentira y sin codificar nada: la comparación
    ve la copia distinta, la que falta y la que sobra, `--check` falla nombrándolas, y el comando
    deja la carpeta como dice la receta sin tocar lo que no es de la lámina."""
    settings.DEBUG = True
    portada = tmp_path / "img" / "portada"
    portada.mkdir(parents=True)
    recipe = {
        "img/portada/lamina-ancha-960.avif": b"igual",
        "img/portada/lamina-ancha-960.webp": b"nueva",
        "img/portada/lamina-alta-640.avif": b"falta",
    }
    (portada / "lamina-ancha-960.avif").write_bytes(b"igual")
    (portada / "lamina-ancha-960.webp").write_bytes(b"vieja")
    (portada / "lamina-ancha-480.avif").write_bytes(b"sobra")
    (portada / "otra-imagen.png").write_bytes(b"ajena")
    monkeypatch.setattr(cmd, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(cmd, "render_variants", lambda: recipe)

    assert cmd.stale_variants(recipe) == (
        ["img/portada/lamina-ancha-960.webp"],
        ["img/portada/lamina-alta-640.avif"],
        ["img/portada/lamina-ancha-480.avif"],
    )
    named = (
        "difieren: img/portada/lamina-ancha-960.webp; faltan: img/portada/lamina-alta-640.avif; "
        "sobran: img/portada/lamina-ancha-480.avif"
    )
    with pytest.raises(CommandError, match=re.escape(named)):
        call_command("generate_lamina_variants", "--check", verbosity=0)

    call_command("generate_lamina_variants", verbosity=0)
    assert {path.name: path.read_bytes() for path in portada.iterdir()} == {
        "lamina-ancha-960.avif": b"igual",
        "lamina-ancha-960.webp": b"nueva",
        "lamina-alta-640.avif": b"falta",
        "otra-imagen.png": b"ajena",
    }
    call_command("generate_lamina_variants", "--check", verbosity=0)
