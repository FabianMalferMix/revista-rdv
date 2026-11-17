"""Cuándo un título es largo y se compone un paso más chico. Hay dos umbrales y no se unifican:
miden columnas distintas, cada una con su letra."""

from django import template

register = template.Library()

# El título de un pliego de la tirada va en `--t7`, en una columna de 15ch, y reserva dos
# líneas: con más letras pasaría de dos, y baja a `--t6` (`.pliego--largo` en componentes.css).
PLIEGO_LONG_TITLE = 34
# El título de la ficha de un texto o de un poema va en el ancla de la sala de lectura, que a
# 951 px mide unos 300 y en la que caben unas trece letras por línea en un poema y unas veinte
# en un texto: con más letras, un título llenaría el ancla de líneas, y baja un paso
# (`.titulo-largo` en componentes.css), también donde el navegador no divide con guion.
FICHA_LONG_TITLE = 90


@register.filter
def long_for_pliego(titulo):
    """Si el título de un pliego de la tirada baja un paso."""
    return len(titulo) > PLIEGO_LONG_TITLE


@register.filter
def long_for_ficha(titulo):
    """Si el título de la ficha de un texto o de un poema baja un paso."""
    return len(titulo) > FICHA_LONG_TITLE
