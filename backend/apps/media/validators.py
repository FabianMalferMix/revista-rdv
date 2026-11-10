"""Validadores de los archivos que se suben desde el panel.

Caddy sirve `/media/` directamente desde el volumen, fuera de Django y de su CSP, y deriva
el `Content-Type` de la EXTENSIÓN: un `.html` o un `.svg` subido ahí se ejecutaría en el
origen del sitio. Por eso cada campo de archivo del panel admite una lista cerrada de
extensiones; la otra mitad de la defensa son las cabeceras del bloque `/media/` de
`infra/caddy/Caddyfile` (`nosniff` y una CSP con `sandbox`).

Solo las imágenes se comprueban también por su contenido (`validate_image`). Del audio y los
PDF se mira únicamente la extensión: nada lee su contenido.

Cada campo tiene además un tope de tamaño. Caddy deja pasar algo más por /admin/ (el
Caddyfile, que tests/test_upload_limits.py compara con estos topes), para que quien se pase
lea aquí cuánto pesa su archivo y qué hacer, y no reciba un 413 sin explicación.
"""

import warnings

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible
from PIL import Image

from config.content_policy import embed_provider_names

MB = 1024 * 1024
# Topes de tamaño, en megas, de lo que se sube desde el panel.
MAX_AUDIO_MB = 50
MAX_PDF_MB = 20
MAX_IMAGE_MB = 12

# Formatos de audio admitidos para los registros (Recording.file). Los vídeos no se alojan:
# ocupan disco, respaldo y un proceso del servidor mientras suben, y se publican con su
# enlace de uno de los proveedores de config/content_policy.py.
AUDIO_EXTENSIONS = ["mp3", "m4a", "oga", "ogg", "opus", "wav", "flac"]

validate_audio_extension = FileExtensionValidator(
    allowed_extensions=AUDIO_EXTENSIONS,
    message=(
        "Formato no permitido. Sube el audio en %(allowed_extensions)s. Un vídeo se publica "
        f"con su enlace de {embed_provider_names()}, en «Enlace para incrustar»."
    ),
)


@deconstructible
class MaxSizeValidator:
    """Rechaza un archivo nuevo que pase de `megabytes`, diciendo cuánto pesa y qué hacer.

    Un archivo ya guardado no se vuelve a medir: editar el resto de la ficha no debe depender
    de él.
    """

    def __init__(self, megabytes, what, advice):
        self.megabytes = megabytes
        self.what = what
        self.advice = advice

    def __call__(self, file):
        if getattr(file, "_committed", False) or file.size <= self.megabytes * MB:
            return
        size = f"{file.size / MB:.1f}".replace(".", ",")
        raise ValidationError(
            f"{self.what} pesa {size} MB y el máximo es {self.megabytes} MB. {self.advice}",
            code="file_too_big",
        )

    def __eq__(self, other):
        return isinstance(other, MaxSizeValidator) and (
            (self.megabytes, self.what, self.advice) == (other.megabytes, other.what, other.advice)
        )


validate_audio_size = MaxSizeValidator(
    MAX_AUDIO_MB, "El audio", "Expórtalo en MP3 (128 kbps bastan para la voz) o recórtalo."
)
validate_pdf_size = MaxSizeValidator(
    MAX_PDF_MB, "El PDF", "Vuelve a exportarlo con las imágenes comprimidas."
)
validate_image_size = MaxSizeValidator(
    MAX_IMAGE_MB, "La imagen", "Expórtala en JPEG o WebP con menos calidad."
)

validate_pdf_extension = FileExtensionValidator(
    allowed_extensions=["pdf"],
    message="Solo se admite PDF (%(allowed_extensions)s).",
)


# Las imágenes del panel: los formatos que la limpieza de metadatos sabe reescribir (MPO es el
# JPEG de varias tomas que guardan algunas cámaras) y el tamaño máximo, que MediaConfig.ready()
# también fija como Image.MAX_IMAGE_PIXELS para que Pillow no decodifique nada mayor.
IMAGE_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
MAX_IMAGE_PIXELS = 40_000_000

_UNREADABLE = "No se pudo leer la imagen entera: vuelve a exportarla en JPEG, PNG o WebP."
_TOO_BIG = "La imagen pasa de 40 megapíxeles: redúcela antes de subirla."


def validate_image(file):
    """Una imagen recién subida es JPEG, PNG o WebP de verdad (no solo por la extensión), no
    pasa de 40 megapíxeles y se puede leer entera. Si no, la limpieza de metadatos no podría
    reescribir el original y la foto se publicaría con su ubicación. Las imágenes ya guardadas
    no se vuelven a revisar: editar su texto alternativo no debe depender de su archivo."""
    if getattr(file, "_committed", False):
        return
    try:
        file.seek(0)
        with warnings.catch_warnings():
            # Por encima del máximo, Pillow solo avisa: aquí el aviso es un rechazo.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(file) as img:
                formato = (img.format or "").upper()
                if formato not in IMAGE_FORMATS:
                    raise ValidationError(
                        f"Formato {formato or 'desconocido'} no admitido: sube la imagen en JPEG, "
                        "PNG o WebP. Si viene del teléfono, vuelve a exportarla en uno de ellos.",
                        code="image_format",
                    )
                ancho, alto = img.size
                if ancho * alto > MAX_IMAGE_PIXELS:
                    raise ValidationError(_TOO_BIG, code="image_too_big")
                img.load()
    except ValidationError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValidationError(_TOO_BIG, code="image_too_big") from exc
    except Exception as exc:
        # Un archivo malformado puede hacer fallar a Pillow de muchas maneras (truncado,
        # cabecera rota, bloque corrupto): cualquiera de ellas es un rechazo.
        raise ValidationError(_UNREADABLE, code="image_unreadable") from exc
    finally:
        file.seek(0)
