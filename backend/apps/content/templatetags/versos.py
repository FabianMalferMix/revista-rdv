from django import template

register = template.Library()


@register.filter
def primeros_versos(cuerpo, cuantos=3):
    """Los primeros versos de un poema: sus primeras líneas con texto.

    El cuerpo es texto plano y el corte de verso es del autor, así que un verso es una
    línea. Las líneas en blanco (saltos de estrofa, aire al comienzo) no cuentan, y la
    sangría se descarta: en un índice el verso se cita, no se compone.
    """
    versos = []
    for linea in (cuerpo or "").splitlines():
        linea = " ".join(linea.split())
        if linea:
            versos.append(linea)
            if len(versos) == int(cuantos):
                break
    return versos


@register.filter
def primer_verso(cuerpo):
    """El primer verso, o cadena vacía si el poema no tiene ninguna línea con texto."""
    versos = primeros_versos(cuerpo, 1)
    return versos[0] if versos else ""
