from django import forms


class SubscribeForm(forms.Form):
    """Alta en la lista de novedades (prensa y gestores). Honeypot en `apodo`."""

    email = forms.EmailField()
    apodo = forms.CharField(required=False)  # honeypot: los humanos lo dejan vacío
