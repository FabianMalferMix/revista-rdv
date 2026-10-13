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


@register.simple_tag
def firmas_sin(personas, persona):
    """Las personas de la lista menos una: la firma propia en la ficha de quien firma.

    En la ficha de una integrante, cada fila de sus poemas y textos repetía su nombre. Un
    texto a cuatro manos sigue nombrando a la otra persona. Es una etiqueta y no un
    filtro porque la parcial de fila se incluye también donde nadie define `persona`: un
    argumento de filtro sin definir rompe la plantilla, el de una etiqueta llega vacío.
    """
    if not persona:
        return list(personas)
    return [p for p in personas if p.pk != getattr(persona, "pk", None)]
