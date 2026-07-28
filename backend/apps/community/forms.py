from django import forms


class SubscribeForm(forms.Form):
    """Alta en la lista de novedades (prensa y gestores). Honeypot en `apodo`."""

    # max_length iguala la columna varchar(254) del modelo: un correo válido pero más
    # largo se rechaza con un error de validación limpio en vez de reventar en un 500
    # (DataError) al insertarse (hallazgo #03).
    email = forms.EmailField(max_length=254)
    apodo = forms.CharField(required=False)  # honeypot: los humanos lo dejan vacío
