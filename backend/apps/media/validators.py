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

from django.core.validators import FileExtensionValidator

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
