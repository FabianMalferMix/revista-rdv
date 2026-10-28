"""Validadores de archivos subidos desde el panel (hallazgo de seguridad S-01).

Los `FileField` del admin no traían ningún validador: `models.FileField` —a
diferencia de `ImageField`, cuyo form field aporta `validate_image_file_extension`—
acepta cualquier extensión y cualquier contenido. Como Caddy sirve `/media/`
directamente desde el volumen (fuera de Django, y por tanto fuera de la CSP), un
`.html` subido ahí se ejecuta en el ORIGEN del sitio: un editor podía escalar a
superusuario. Estos validadores cierran la mitad de aplicación; la otra mitad son
las cabeceras defensivas del bloque `/media/` en `infra/caddy/Caddyfile`.

Nota: el `Content-Type` con el que Caddy sirve un archivo se deriva de su
EXTENSIÓN, así que restringirla es lo que corta el vector. La comprobación de
firma es defensa en profundidad frente a un archivo con extensión válida y
contenido ajeno.
"""

import warnings

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from PIL import Image

# Formatos de audio/vídeo admitidos para los registros (Recording.file).
AUDIO_VIDEO_EXTENSIONS = ["mp3", "m4a", "oga", "ogg", "opus", "wav", "flac", "mp4", "m4v", "webm"]

validate_audio_video_extension = FileExtensionValidator(
    allowed_extensions=AUDIO_VIDEO_EXTENSIONS,
    message=(
        "Formato no permitido. Usa audio o vídeo: %(allowed_extensions)s. "
        "Nunca se aceptan archivos que el navegador pueda ejecutar (.html, .svg…)."
    ),
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
