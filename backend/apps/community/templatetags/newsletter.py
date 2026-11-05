from django import template

from ..forms import SubscribeForm

register = template.Library()


@register.inclusion_tag("community/partials/_newsletter_form.html", takes_context=True)
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
