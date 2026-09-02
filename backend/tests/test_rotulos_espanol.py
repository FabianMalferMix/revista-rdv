"""El panel se lee en español, incluida la pantalla de bloqueo.

Convivían «MEDIOS» y «ENVÍOS» (con verbose_name) con «CONTENT», «PEOPLE», «REVIEWS» y
«COMMUNITY» sin traducir, y los modelos de relación y auditoría tampoco lo tenían: en la
ficha de un artículo se leía «EDITORIAL TRANSITIONS», «FROM STATUS», «Published at»,
«Owner». El patrón se entendía —se tradujo lo que el equipo abre a diario— pero para un
colectivo que trabaja en español es un roce constante.

Nada se comportaba mal: es presentación. Por eso estas pruebas miran el rótulo que se LEE
y no la configuración que lo produce.
"""

import re

import pytest
from django.apps import apps

pytestmark = pytest.mark.django_db

# Rótulo esperado de cada app propia, tal como se lee en el índice del panel.
ROTULOS = {
    "content": "Contenido",
    "people": "Personas",
    "reviews": "Obras reseñadas",
    "community": "Comunidad",
    "media": "Medios",
    "submissions": "Envíos",
    "showcase": "Colectivo",
    "agenda": "Agenda y trayectoria",
}
APPS_PROPIAS = list(ROTULOS)


@pytest.mark.parametrize(("etiqueta", "esperado"), ROTULOS.items())
def test_cada_app_propia_tiene_rotulo_en_espanol(etiqueta, esperado):
    """El encabezado de sección del índice del panel.

    Sin `verbose_name`, Django usa el nombre del módulo capitalizado —«Content»,
    «People»— y eso es lo que se leía.
    """
    assert apps.get_app_config(etiqueta).verbose_name == esperado


def test_ningun_modelo_propio_se_muestra_con_su_nombre_en_ingles():
    """Sin verbose_name, Django parte el CamelCase: «editorial transition».

    Se comprueba sobre los modelos REGISTRADOS en el admin, que son los que alguien lee.
    """
    from django.contrib.admin.sites import site

    sospechosos = []
    for modelo in site._registry:
        if modelo._meta.app_label not in APPS_PROPIAS:
            continue
        nombre = str(modelo._meta.verbose_name)
        # El nombre por defecto es el CamelCase separado y en minúsculas.
        defecto = re.sub(r"(?<!^)(?=[A-Z])", " ", modelo.__name__).lower()
        if nombre == defecto:
            sospechosos.append(f"{modelo._meta.label} -> «{nombre}»")
    assert not sospechosos, "modelos sin rótulo propio: " + ", ".join(sospechosos)


@pytest.mark.parametrize(
    "modelo_label,campo,esperado",
    [
        ("content.Article", "published_at", "fecha de publicación"),
        ("content.Article", "owner", "dueño"),
        ("content.Poem", "published_at", "fecha de publicación"),
        ("content.EditorialTransition", "from_status", "estado de origen"),
        ("content.EditorialTransition", "to_status", "estado de destino"),
        ("content.EditorialTransition", "actor", "actor"),
    ],
)
def test_los_campos_de_la_ficha_se_leen_en_espanol(modelo_label, campo, esperado):
    modelo = apps.get_model(modelo_label)
    assert str(modelo._meta.get_field(campo).verbose_name) == esperado


def test_la_bitacora_se_titula_en_espanol():
    from apps.content.models import EditorialTransition

    assert str(EditorialTransition._meta.verbose_name_plural) == "transiciones editoriales"


def test_la_pantalla_de_bloqueo_esta_en_espanol():
    """El rótulo sin traducir más visible: lo ve cualquiera que llegue a /admin/login/."""
    from django.conf import settings
    from django.template import loader

    assert settings.AXES_LOCKOUT_TEMPLATE == "axes_lockout.html"
    html = loader.render_to_string(settings.AXES_LOCKOUT_TEMPLATE)
    assert "Demasiados intentos fallidos" in html
    assert "Account locked" not in html


def test_la_pantalla_de_bloqueo_no_revela_el_temporizador():
    """No decir cuánto falta ni cuántos intentos quedaban: calibraría a quien prueba claves."""
    from django.conf import settings
    from django.template import loader

    html = loader.render_to_string(settings.AXES_LOCKOUT_TEMPLATE).lower()
    for pista in ("1 hora", "60 minutos", "intentos restantes", "5 intentos"):
        assert pista not in html
