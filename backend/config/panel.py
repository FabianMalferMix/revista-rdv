"""Lo que el panel de Django dice con sus propias palabras, dicho como el resto del panel.

Django arma algunos textos del panel con el nombre interno de un campo o con una mayúscula a
media frase. `PanelWordingMixin`, en cada ModelAdmin con inlines o con selectores dobles, los
dice con los rótulos de cada modelo:

- un dato repetido entre las filas de un inline se nombra por el rótulo de su campo, y no se
  nombra la pieza a la que pertenecen todas las filas;
- «Agregar … adicional» lleva el nombre del modelo en minúscula, como va a media frase;
- bajo un selector doble (`filter_horizontal`) no sale la ayuda de mantener presionado
  «Control», que es de la lista de selección múltiple.

`account_name` nombra una cuenta de solo lectura sin enlazarla, y `moved_message` dice cuántas
piezas cambiaron de estado. tests/config/test_panel.py lo vigila.
"""

import json

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.text import get_text_list
from django.utils.translation import gettext


class LabeledDuplicatesFormSetMixin:
    """El aviso de un dato repetido entre las filas de un inline, con el rótulo de cada campo.
    La relación con la pieza no se nombra: es la misma en todas las filas."""

    def get_unique_error_message(self, unique_check):
        own_key = getattr(getattr(self, "fk", None), "name", None)
        labels = [
            str(self.model._meta.get_field(name).verbose_name)
            for name in unique_check
            if name != own_key
        ]
        return gettext("Please correct the duplicate data for %(field)s.") % {
            "field": get_text_list(labels, gettext("and"))
        }


class InlineAdminFormSet(helpers.InlineAdminFormSet):
    """El inline que arma Django, con el nombre del modelo en «Agregar … adicional» tal como se
    escribe: Django le pone mayúscula inicial aunque vaya a media frase."""

    def inline_formset_data(self):
        data = json.loads(super().inline_formset_data())
        data["options"]["addText"] = gettext("Add another %(verbose_name)s") % {
            "verbose_name": self.opts.verbose_name
        }
        return json.dumps(data)


class PanelWordingMixin:
    """Los textos del panel que arma Django, con los rótulos de cada modelo."""

    def get_formsets_with_inlines(self, request, obj=None):
        for formset, inline in super().get_formsets_with_inlines(request, obj):
            yield type(formset.__name__, (LabeledDuplicatesFormSetMixin, formset), {}), inline

    def get_inline_formsets(self, request, formsets, inline_instances, obj=None):
        inline_admin_formsets = super().get_inline_formsets(
            request, formsets, inline_instances, obj
        )
        # Django no deja elegir la clase con la que arma cada inline: se cambia la de cada uno.
        for inline_admin_formset in inline_admin_formsets:
            inline_admin_formset.__class__ = InlineAdminFormSet
        return inline_admin_formsets

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if formfield is not None and isinstance(formfield.widget, FilteredSelectMultiple):
            formfield.help_text = kwargs.get("help_text", db_field.help_text)
        return formfield


def account_name(model, field_name):
    """Para `readonly_fields`: la cuenta de `field_name`, por su nombre de usuario y sin enlace.
    Django enlaza un campo de solo lectura a la ficha de la cuenta, que solo abre quien
    administra las cuentas."""

    @admin.display(description=model._meta.get_field(field_name).verbose_name)
    def name(model_admin, obj):
        account = getattr(obj, field_name)
        return account.get_username() if account else model_admin.get_empty_value_display()

    return name


def moved_message(model, count, label):
    """Cuántas piezas pasaron al estado `label`, con el nombre del modelo en su número:
    «1 artículo pasó a «Publicado».», «3 envíos pasaron a «Aceptado».»."""
    if count == 1:
        return f"1 {model._meta.verbose_name} pasó a «{label}»."
    return f"{count} {model._meta.verbose_name_plural} pasaron a «{label}»."
