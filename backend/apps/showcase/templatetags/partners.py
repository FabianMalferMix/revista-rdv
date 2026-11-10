from django import template

from apps.showcase.models import Partner

register = template.Library()

# El rótulo de cada grupo de aliados: su tipo (`Partner.Kind`), en plural. Cada tipo tiene el
# suyo (tests/test_partner_groups.py); la vista lleva a «Otro» al aliado de un tipo desconocido,
# para que la cabecera no cuente a nadie que la página no enseña.
GROUP_TITLES = {
    Partner.Kind.FINANCIAMIENTO: "Financiamiento",
    Partner.Kind.INSTITUCION: "Instituciones",
    Partner.Kind.EDITORIAL: "Editoriales",
    Partner.Kind.MEDIO: "Medios",
    Partner.Kind.ESPACIO: "Espacios",
    Partner.Kind.OTRO: "Otros apoyos",
}


@register.filter
def partner_group_title(kind):
    """El rótulo del grupo de aliados de un tipo."""
    return GROUP_TITLES[kind]
