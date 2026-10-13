from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

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


@register.filter
def versos(cuerpo):
    """El poema marcado verso a verso, agrupado en estrofas.

    Cada línea es un `<span class="verso">` y cada grupo de líneas separado por una línea
    en blanco, un `<p class="estrofa">`. Con eso el CSS puede dar sangría francesa a un
    verso largo que no cabe —la continuación se lee como continuación, no como un verso
    nuevo— y un salto propio entre estrofas.

    El texto lo escribe una persona: cada línea se escapa ANTES de envolverla, y solo el
    resultado completo se marca como seguro. La sangría inicial de cada verso se conserva
    tal cual (el CSS la respeta con `white-space:pre-wrap`); varias líneas en blanco
    seguidas cuentan como un solo salto de estrofa.
    """
    estrofas, actual = [], []
    for linea in (cuerpo or "").splitlines():
        if linea.strip():
            actual.append(linea.rstrip())
        elif actual:
            estrofas.append(actual)
            actual = []
    if actual:
        estrofas.append(actual)
    html = "".join(
        '<p class="estrofa">'
        + "".join(f'<span class="verso">{escape(verso)}</span>' for verso in estrofa)
        + "</p>"
        for estrofa in estrofas
    )
    return mark_safe(html)
