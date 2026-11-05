"""Las copias de la lámina de la portada, rehechas desde sus maestras.

La lámina es la obra de la portada mientras el colectivo no elige la suya. Sus maestras, sin
pérdida, están en `lamina/`: una por forma de `LAMINA` (la ancha y la alta), en PNG y cortada en
franjas horizontales, numeradas de arriba abajo (`ancha-1.png`, `ancha-2.png`…), para que ningún
archivo del repositorio pase de 2 MB. De cada maestra salen, con LANCZOS, las copias que declara
`LAMINA`, en los formatos y con las calidades de las copias de portada
(`MediaAsset.PORTADA_FORMATS`), y la reserva en JPEG (`LAMINA_FALLBACK`).

Cada codificador lleva sus parámetros fijados y las copias van sin metadatos, así que rehacerlas
da los mismos bytes (tests/test_lamina.py). La AVIF se codifica con un solo hilo y sin mosaicos
automáticos: Pillow elige los mosaicos según los núcleos de la máquina, y la copia cambiaba de un
equipo a otro.

    python manage.py generate_lamina_variants           # reescribe las copias que difieren
    python manage.py generate_lamina_variants --check   # solo compara; falla si alguna difiere

Para cambiar la lámina se reemplazan las franjas de su forma por las de la maestra nueva (sin
pérdida, con la proporción de la forma y al menos el ancho de su copia mayor) y se corre el
comando: desde el contenedor `web`, con `docker compose exec --user "$(id -u):$(id -g)"`, para
que los archivos no queden a nombre de root.
"""

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from PIL import Image

from apps.devtools.management.base import DevelopmentCommand
from apps.media.models import MediaAsset
from apps.media.templatetags.images import LAMINA, LAMINA_FALLBACK, lamina_path

MASTERS_DIR = Path(__file__).resolve().parent / "lamina"
STATIC_DIR = Path(settings.STATICFILES_DIRS[0])

# Lo que Pillow decidiría por su cuenta queda fijado, para que el resultado no dependa de la
# máquina ni de los valores por defecto de otra versión. Sin ICC, Exif ni XMP. Las calidades de
# AVIF y WebP vienen de `MediaAsset.PORTADA_FORMATS`.
ENCODER_OPTIONS = {
    "AVIF": {
        "speed": 6,
        "subsampling": "4:2:0",
        "range": "full",
        "codec": "aom",
        "max_threads": 1,
        "autotiling": False,
        "tile_rows": 0,
        "tile_cols": 0,
        "icc_profile": b"",
        "exif": b"",
        "xmp": b"",
    },
    "WEBP": {
        "lossless": False,
        "method": 4,
        "exact": False,
        "icc_profile": "",
        "exif": b"",
        "xmp": "",
    },
    "JPEG": {"quality": 78, "progressive": True, "optimize": True, "subsampling": "4:2:0"},
}


def _band_number(path):
    return int(path.stem.rsplit("-", 1)[1])


def load_master(forma):
    """La maestra de una forma: sus franjas, apiladas de arriba abajo."""
    bands = []
    for path in sorted(MASTERS_DIR.glob(f"{forma}-*.png"), key=_band_number):
        with Image.open(path) as opened:
            bands.append(opened.convert("RGB"))
    if not bands:
        raise CommandError(f"No hay maestra de la lámina {forma} en {MASTERS_DIR}.")
    width = bands[0].width
    if any(band.width != width for band in bands):
        raise CommandError(f"Las franjas de la maestra {forma} no tienen todas el mismo ancho.")
    # Un lienzo nuevo, sin la información de los archivos: ninguna copia hereda metadatos.
    master = Image.new("RGB", (width, sum(band.height for band in bands)))
    top = 0
    for band in bands:
        master.paste(band, (0, top))
        top += band.height
    return master


def _encode(image, fmt, options):
    buffer = BytesIO()
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def render_variants():
    """Las copias de la lámina, en memoria: {ruta relativa a los estáticos: bytes}."""
    fallback_forma, fallback_width, fallback_ext = LAMINA_FALLBACK
    fallback_format = Image.registered_extensions()[f".{fallback_ext}"]
    variants = {}
    for forma, sizes in LAMINA.items():
        master = load_master(forma)
        for width, height in sizes:
            if width > master.width or master.width * height != master.height * width:
                raise CommandError(
                    f"La maestra {forma} mide {master.width}×{master.height}: no da la copia de "
                    f"{width}×{height}, que es más grande o de otra proporción."
                )
            if (width, height) == master.size:
                scaled = master
            else:
                scaled = master.resize((width, height), Image.Resampling.LANCZOS)
            for ext, fmt, options in MediaAsset.PORTADA_FORMATS:
                variants[lamina_path(forma, width, ext)] = _encode(
                    scaled, fmt, {**options, **ENCODER_OPTIONS[fmt]}
                )
            if (forma, width) == (fallback_forma, fallback_width):
                variants[lamina_path(*LAMINA_FALLBACK)] = _encode(
                    scaled, fallback_format, ENCODER_OPTIONS[fallback_format]
                )
    if lamina_path(*LAMINA_FALLBACK) not in variants:
        raise CommandError(
            f"La reserva ({fallback_forma} de {fallback_width}) no es una copia de `LAMINA`."
        )
    return variants


def stale_variants(variants):
    """Lo que no coincide con la receta, en tres listas: las copias que difieren, las que faltan
    y las que sobran (un archivo `lamina-*` de esas carpetas que la receta ya no da)."""
    folders = {(STATIC_DIR / path).parent for path in variants}
    present = {
        file.relative_to(STATIC_DIR).as_posix()
        for folder in folders
        for file in folder.glob("lamina-*")
    }
    differing = sorted(
        path
        for path, data in variants.items()
        if path in present and (STATIC_DIR / path).read_bytes() != data
    )
    missing = sorted(set(variants) - present)
    extra = sorted(present - set(variants))
    return differing, missing, extra


def _describe(differing, missing, extra):
    return "; ".join(
        f"{label}: {', '.join(paths)}"
        for label, paths in (("difieren", differing), ("faltan", missing), ("sobran", extra))
        if paths
    )


class Command(DevelopmentCommand):
    help = "Rehace las copias de la lámina de la portada desde sus maestras (mismos bytes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Solo compara las copias con las de las maestras, y falla si alguna difiere.",
        )

    def handle(self, *args, **options):
        variants = render_variants()
        differing, missing, extra = stale_variants(variants)
        if options["check"]:
            if differing or missing or extra:
                raise CommandError(
                    "Las copias de la lámina no son las de sus maestras ("
                    f"{_describe(differing, missing, extra)}). "
                    "Las rehace: python manage.py generate_lamina_variants"
                )
            self.stdout.write(f"lámina: las {len(variants)} copias son las de sus maestras")
            return
        for path in differing + missing:
            (STATIC_DIR / path).write_bytes(variants[path])
        for path in extra:
            (STATIC_DIR / path).unlink()
        left = stale_variants(variants)
        if any(left):
            raise CommandError(f"La lámina no quedó como la receta ({_describe(*left)}).")
        self.stdout.write(
            self.style.SUCCESS(
                f"lámina: {len(differing) + len(missing)} copias escritas, {len(extra)} borradas "
                f"y {len(variants) - len(differing) - len(missing)} que ya estaban"
            )
        )
