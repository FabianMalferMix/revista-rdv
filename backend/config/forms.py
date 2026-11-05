"""Lo que comparten los formularios públicos del sitio."""

from django import forms

HONEYPOT = "apodo"


class HoneypotMixin:
    """Un campo trampa para los bots que rellenan todo lo que encuentran: un campo de texto que
    la hoja de estilos saca de la vista (`.hp`), fuera del tabulador y del lector de pantalla.
    No es un `<input type="hidden">`, que los bots suelen devolver vacío. La plantilla lo pinta
    aparte (`{{ form.apodo }}`), y `visible_fields()` no lo incluye: no lleva etiqueta."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[HONEYPOT] = forms.CharField(
            required=False,
            widget=forms.TextInput(
                attrs={
                    "class": "hp",
                    "tabindex": "-1",
                    "autocomplete": "off",
                    "aria-hidden": "true",
                }
            ),
        )

    def visible_fields(self):
        return [field for field in super().visible_fields() if field.name != HONEYPOT]

    @property
    def is_spam(self):
        """True si el campo trampa vino relleno: lo rellenó un bot."""
        return bool(self.cleaned_data.get(HONEYPOT))
