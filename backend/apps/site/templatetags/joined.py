"""Una línea de datos unidos con « · » en la que no queda ningún separador colgando.

`{% joined %}A{% part %}B{% part %}C{% endjoined %}` pinta «A · B · C» con las partes que tienen
algo que enseñar: la que no pinta nada, o solo espacios, se omite con su separador. Cada parte
es plantilla, así que puede llevar marcado (un enlace) y sus propias condiciones, y lo que pinta
se escapa como en el resto de la plantilla. El espacio en blanco que rodea una parte en la
plantilla no se pinta. Otro separador se pasa como argumento: el título de la pestaña une con
« — » (`{% joined " — " %}`, en `base.html`).

Las uniones de una lista (`|join:" · "`, o un bucle con `forloop.last`) no la necesitan: entre
dos elementos de una lista siempre hay algo a cada lado.
"""

from django import template
from django.template.base import TextNode
from django.utils.html import format_html_join

register = template.Library()

SEPARATOR = " · "


def _trimmed(nodelist):
    """La parte sin el espacio en blanco del texto con que empieza y termina en la plantilla."""
    if nodelist and isinstance(nodelist[0], TextNode):
        nodelist[0].s = nodelist[0].s.lstrip()
    if nodelist and isinstance(nodelist[-1], TextNode):
        nodelist[-1].s = nodelist[-1].s.rstrip()
    return nodelist


class JoinedNode(template.Node):
    def __init__(self, separator, parts):
        self.separator = separator
        self.parts = parts

    def get_nodes_by_type(self, nodetype):
        # Lo que va dentro de las partes (un `{% block %}`, un `{% include %}`) se encuentra
        # como dentro de cualquier otra etiqueta de bloque.
        nodes = [self] if isinstance(self, nodetype) else []
        for part in self.parts:
            nodes.extend(part.get_nodes_by_type(nodetype))
        return nodes

    def render(self, context):
        separator = self.separator.resolve(context) if self.separator else SEPARATOR
        shown = [out for out in (part.render(context) for part in self.parts) if out.strip()]
        # Cada parte ya sale escapada de la plantilla: `format_html_join` la deja tal cual y
        # escapa el separador.
        return format_html_join(separator, "{}", ((out,) for out in shown))


@register.tag
def joined(parser, token):
    """`{% joined [separador] %}…{% part %}…{% endjoined %}`: ver el módulo."""
    bits = token.split_contents()
    if len(bits) > 2:
        raise template.TemplateSyntaxError("«joined» recibe, a lo más, el separador")
    separator = parser.compile_filter(bits[1]) if len(bits) == 2 else None
    parts = []
    while True:
        parts.append(_trimmed(parser.parse(("part", "endjoined"))))
        if parser.next_token().contents == "endjoined":
            return JoinedNode(separator, parts)
