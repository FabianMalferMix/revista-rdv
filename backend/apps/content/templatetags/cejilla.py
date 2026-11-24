from django import template

from config.text import strip_accents

register = template.Library()


@register.filter
def seccion_aporta(article):
    """¿Dice la sección del texto algo que su tipo no diga ya?

    La cejilla nombra la sección junto al tipo solo cuando añade información, como en
    «Crónica · Entrevista»; si no, diría la misma palabra dos veces («Reseñas · Reseña»).
    Se comparan sin tildes ni mayúsculas, y basta que una empiece por la otra para cubrir
    el plural.
    """
    if not article.section_id:
        return False

    def base(texto):
        return strip_accents(texto).lower().strip()

    seccion, tipo = base(article.section.name), base(article.get_type_display())
    return not (seccion.startswith(tipo) or tipo.startswith(seccion))
