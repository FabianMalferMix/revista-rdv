import re

from django import template
from django.utils.html import format_html_join
from django.utils.text import Truncator

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


# Lo que la portada cita de un poema, como mucho: un poema corriente cabe entero en sus tres
# versos (los de la demostración miden entre 20 y 50 letras).
LETRAS_DEL_ADELANTO = 160


@register.filter
def adelanto(cuerpo, cuantos=3):
    """Los versos que la portada cita de un poema: hasta `cuantos`, y no más de
    LETRAS_DEL_ADELANTO letras entre todos.

    Un poema de versos largos, o en prosa, abre con párrafos: sin tope, sus tres «versos»
    llenaban la portada (una oda de prueba ocupaba diez líneas, y un poema en prosa habría
    puesto tres párrafos enteros). El verso que no cabe se corta en una palabra, con puntos
    suspensivos; si para él quedan menos de cuarenta letras, no se cita.
    """
    citados, quedan = [], LETRAS_DEL_ADELANTO
    for verso in primeros_versos(cuerpo, cuantos):
        if len(verso) <= quedan:
            citados.append(verso)
            quedan -= len(verso)
            continue
        if not citados or quedan >= 40:
            corte = (
                verso[: quedan + 1].rsplit(" ", 1)[0] if " " in verso[:quedan] else verso[:quedan]
            )
            citados.append(corte.rstrip(" ,;:.—") + "…")
        break
    return citados


# El manifiesto en la portada (D33): hasta su primera pausa, si llega antes de estas palabras.
PALABRAS_DEL_MANIFIESTO = 36
_PAUSA = re.compile(r"[.:;?!](?=\s|$)")


@register.filter
def primera_pausa(texto, tope=PALABRAS_DEL_MANIFIESTO):
    """El comienzo de un texto hasta su primera pausa: punto, dos puntos, punto y coma, o
    cierre de pregunta o de exclamación.

    La portada cortaba el manifiesto en la palabra 28, a media frase («donde no suelen …»),
    y en letra de cartel se notaba más. Los dos puntos y el punto y coma se cierran con
    punto: lo que venía después (una enumeración, otra idea) no se cita. Si la primera pausa
    llega después de `tope` palabras, se corta en la palabra 28, como antes.
    """
    texto = " ".join((texto or "").split())
    pausa = _PAUSA.search(texto)
    if pausa and len(texto[: pausa.start()].split()) <= int(tope):
        signo = pausa.group()
        return texto[: pausa.start()] + ("." if signo in ":;" else signo)
    return Truncator(texto).words(28, truncate=" …")


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

    El texto lo escribe una persona: `format_html_join` escapa cada verso al envolverlo,
    y nada se marca como seguro a mano (el SAST del CI bloquea `mark_safe`, con razón: es
    donde se cuela un XSS). La sangría inicial de cada verso se conserva
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
    return format_html_join(
        "",
        '<p class="estrofa">{}</p>',
        (
            (
                format_html_join(
                    "", '<span class="verso">{}</span>', ((verso,) for verso in estrofa)
                ),
            )
            for estrofa in estrofas
        ),
    )
