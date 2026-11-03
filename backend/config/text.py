"""Utilidades de texto que comparten varias apps."""

import unicodedata


def strip_accents(text):
    """El texto sin diacríticos (á→a, ñ→n), para comparar palabras como las lee una persona.

    Las letras sin descomposición Unicode (ø, ł, æ, ß) quedan como están. La búsqueda de texto
    completo no lo usa: pliega los acentos la configuración de búsqueda de la base
    (`SEARCH_CONFIG`, en apps/content/models.py), igual al indexar que al buscar.
    """
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
