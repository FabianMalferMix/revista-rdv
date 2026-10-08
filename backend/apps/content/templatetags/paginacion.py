from django import template

register = template.Library()


@register.simple_tag
def rango_paginas(pagina, a_cada_lado=1, en_extremos=1):
    """Números de página a mostrar, con elipsis donde se salta un tramo.

    Con 40 páginas no se listan las 40: «1 … 6 7 8 … 40». Lo calcula el propio
    paginador de Django; aquí solo se le pasan los argumentos, que una plantilla no
    puede dar a un método. La elipsis llega como `pagina.paginator.ELLIPSIS`.
    """
    return list(
        pagina.paginator.get_elided_page_range(
            pagina.number, on_each_side=a_cada_lado, on_ends=en_extremos
        )
    )
