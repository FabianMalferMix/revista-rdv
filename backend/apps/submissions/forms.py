from django import forms

from .models import Submission

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "odt", "rtf", "txt"}
MAX_FILE_MB = 10

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
        return f

    @property
    def is_spam(self):
        """True si el honeypot vino relleno (bot)."""
        return bool(self.cleaned_data.get("apodo"))
