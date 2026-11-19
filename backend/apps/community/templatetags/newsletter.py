from datetime import timedelta

from django import template

from .. import models
from ..forms import SubscribeForm

register = template.Library()


@register.simple_tag
def confirm_link_hours():
    """Las horas que vale un enlace de confirmación, como las dice la página del enlace caducado:
    las de CONFIRM_TOKEN_TTL, el mismo plazo que decide si caducó."""
    return models.CONFIRM_TOKEN_TTL // timedelta(hours=1)


@register.inclusion_tag("partials/_newsletter_form.html", takes_context=True)
def newsletter_form(context, form=None, next_url=None):
    """El alta del boletín, pintada desde SubscribeForm: vacía en el pie de todas las páginas y,
    en la página del boletín, con lo que se envió y sus errores. Tras el alta se vuelve a
    `next_url`, o a la página donde está el formulario."""
    request = context.get("request")
    return {
        "form": form or SubscribeForm(),
        "next": next_url or (request.path if request else "/"),
        "csrf_token": context.get("csrf_token"),
    }
