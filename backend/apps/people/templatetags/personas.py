from django import template

register = template.Library()


@register.filter
def iniciales(nombre):
    """«Fernanda Soto» → «FS». La primera letra del primer nombre y la del último apellido.

    Para el monograma de quien todavía no tiene retrato. Una sola inicial dentro de un
    círculo es el avatar por defecto de cualquier aplicación de mensajería; dos letras
    ya son las de una persona.
    """
    palabras = str(nombre or "").split()
    if not palabras:
        return ""
    letras = palabras[0][:1] if len(palabras) == 1 else palabras[0][:1] + palabras[-1][:1]
    return letras.upper()
