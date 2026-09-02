import zipfile

from django import forms

from .models import Submission

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "odt", "rtf", "txt"}
MAX_FILE_MB = 10

# Firmas (magic bytes) esperadas por extensión: validan que el CONTENIDO del archivo
# coincide con la extensión declarada, como defensa ante un binario malicioso
# renombrado (p. ej. un .exe subido como .pdf). docx/odt son contenedores ZIP, así que
# su firma la cumple CUALQUIER zip: para ellos no basta y se mira además el índice del
# contenedor (ver `_ZIP_REQUERIDOS`).
_FILE_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "rtf": (b"{\\rtf",),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),  # OLE2 (Word clásico)
    "docx": (b"PK\x03\x04", b"PK\x05\x06"),
    "odt": (b"PK\x03\x04", b"PK\x05\x06"),
    # "txt" no tiene firma: se valida como texto (sin bytes nulos).
}


# Piezas que el formato OBLIGA a llevar dentro del contenedor. Sin esto, `mis-fotos.zip`
# renombrado a `.docx` pasaba la validación: la firma PK es la del ZIP, no la del
# documento. No cierra un agujero de ejecución —el adjunto va a almacenamiento privado y
# solo lo descarga un editor— pero evita aceptar como manuscrito algo que Word no abrirá.
_ZIP_REQUERIDOS = {
    "docx": ("[Content_Types].xml", "word/document.xml"),
    "odt": ("META-INF/manifest.xml", "content.xml"),
}


def _zip_es_del_formato(f, ext):
    """True si el contenedor ZIP lleva dentro las piezas propias de `ext`.

    Se lee SOLO el índice (`namelist()`, es decir el directorio central del zip): no se
    extrae ni se descomprime nada, así que un zip bomba no tiene por dónde entrar. El
    tamaño ya está acotado antes: `clean_file` comprueba extensión, luego tamaño y solo
    después el contenido.
    """
    try:
        with zipfile.ZipFile(f) as contenedor:
            nombres = set(contenedor.namelist())
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError):
        return False
    finally:
        f.seek(0)
    return all(pieza in nombres for pieza in _ZIP_REQUERIDOS[ext])


def _content_matches_extension(f, ext):
    """True si el contenido del archivo corresponde a la extensión declarada.

    Para .txt (sin firma) exige que no parezca binario (sin bytes nulos); para los
    formatos empaquetados en ZIP, que el contenedor sea de verdad ese formato.
    """
    head = f.read(8)
    f.seek(0)
    if ext == "txt":
        sample = f.read(4096)
        f.seek(0)
        return b"\x00" not in sample
    if not any(head.startswith(sig) for sig in _FILE_SIGNATURES.get(ext, ())):
        return False
    if ext in _ZIP_REQUERIDOS:
        return _zip_es_del_formato(f, ext)
    return True


SUBMISSION_TYPES = [
    ("reseña", "Reseña"),
    ("ensayo", "Ensayo"),
    ("entrevista", "Entrevista"),
    ("poesía", "Poesía"),
    ("narrativa", "Narrativa"),
    ("crónica", "Crónica"),
    ("otro", "Otro"),
]


class SubmissionForm(forms.ModelForm):
    # Honeypot anti-spam: oculto para humanos; los bots que rellenan todo caen aquí.
    apodo = forms.CharField(required=False, widget=forms.HiddenInput)
    type = forms.ChoiceField(choices=SUBMISSION_TYPES, label="Tipo de propuesta")

    class Meta:
        model = Submission
        fields = ["author_name", "author_email", "type", "title", "body", "file"]
        labels = {
            "author_name": "Tu nombre",
            "author_email": "Correo de contacto",
            "title": "Título de la propuesta",
            "body": "Descripción o texto",
            "file": "Adjunto (opcional)",
        }
        help_texts = {
            "file": "PDF, DOC, DOCX, ODT, RTF o TXT. Máximo 10 MB.",
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 8}),
        }

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if not f:
            return f
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                "Formato no permitido. Usa: " + ", ".join(sorted(ALLOWED_EXTENSIONS)) + "."
            )
        if f.size > MAX_FILE_MB * 1024 * 1024:
            raise forms.ValidationError(f"El archivo supera los {MAX_FILE_MB} MB.")
        if not _content_matches_extension(f, ext):
            raise forms.ValidationError(
                "El contenido del archivo no coincide con su extensión. Sube un archivo válido."
            )
        return f

    @property
    def is_spam(self):
        """True si el honeypot vino relleno (bot)."""
        return bool(self.cleaned_data.get("apodo"))
