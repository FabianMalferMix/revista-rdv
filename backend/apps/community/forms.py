from django import forms
from django.forms import BoundField

from config.forms import HoneypotMixin


class ConsentDescribedField(BoundField):
    """El correo lo describen el error, si lo hay (`<id>_error`, que reúne también los del
    formulario), y el texto de consentimiento que va debajo (`<id>_consent`)."""

    @property
    def aria_describedby(self):
        ids = [f"{self.auto_id}_error"] if self.errors or self.form.non_field_errors() else []
        return " ".join([*ids, f"{self.auto_id}_consent"])


class SubscribeForm(HoneypotMixin, forms.Form):
    """Alta en la lista de novedades (prensa y gestores). Lo pintan el pie de todas las páginas
    y la página del boletín, con `{% newsletter_form %}`: los ids empiezan por «news-»."""

    # max_length iguala la columna varchar(254) del modelo: un correo válido pero más
    # largo se rechaza con un error de validación limpio en vez de reventar en un 500
    # (DataError) al insertarse (hallazgo #03).
    email = forms.EmailField(
        max_length=254,
        label="Novedades para prensa y gestores",
        error_messages={"required": "Escribe tu correo.", "invalid": "Revisa el correo ingresado."},
        # `autocomplete` dice al navegador que es el correo de la persona, para que lo ofrezca
        # (WCAG 1.3.5).
        widget=forms.EmailInput(attrs={"placeholder": "tu@correo.cl", "autocomplete": "email"}),
        bound_field_class=ConsentDescribedField,
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("auto_id", "news-%s")
        super().__init__(*args, **kwargs)
