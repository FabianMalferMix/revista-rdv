"""Dónde vive cada parcial: la que pintan las plantillas de una sola app, en la carpeta de esa
app; la que pintan varias apps, `base.html` o las páginas de error, en `templates/partials/`.

Las plantillas se leen con el motor de Django, así que cuentan las inclusiones dentro de
bloques, bucles y condiciones, y también las etiquetas de inclusión: `{% responsive_img %}`
pinta `partials/_responsive_img.html` desde la plantilla que la usa.
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.template import engines
from django.template.library import InclusionNode
from django.template.loader_tags import IncludeNode


def _app_folders():
    """Las carpetas de plantillas de las apps del proyecto: llevan el nombre de su app."""
    return {config.label for config in apps.get_app_configs() if config.name.startswith("apps.")}


def _owner(name, app_folders):
    """La app dueña de una plantilla, por su carpeta. Ninguna para las de la raíz (`base.html`,
    las páginas de error), las de `partials/` y las del panel (`admin/`)."""
    folder = name.split("/", 1)[0] if "/" in name else None
    return folder if folder in app_folders else None


def _template_names():
    for folder in map(Path, settings.TEMPLATES[0]["DIRS"]):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix in {".html", ".txt"}:
                yield path.relative_to(folder).as_posix()


def _inclusions():
    """(plantilla, parcial) por cada `{% include %}` y cada etiqueta de inclusión de las
    plantillas del sitio, y aparte las inclusiones cuyo nombre es una variable."""
    engine = engines["django"].engine
    found, variable = set(), []
    for name in _template_names():
        nodelist = engine.get_template(name).nodelist
        for node in nodelist.get_nodes_by_type(IncludeNode):
            target = node.template.var
            if isinstance(target, str):
                found.add((name, target))
            else:
                variable.append(f"{name}: {node.template.token}")
        for node in nodelist.get_nodes_by_type(InclusionNode):
            found.add((name, node.filename))
    return found, variable


def test_no_template_includes_a_partial_from_another_apps_folder():
    app_folders = _app_folders()
    found, variable = _inclusions()
    # Control positivo: la lectura reconoce las carpetas de las apps y ve una parcial de la
    # propia app (dentro de un bloque y de un bucle), una común desde base.html y la de una
    # etiqueta de inclusión.
    assert {"agenda", "content", "media", "people"} <= app_folders
    assert ("agenda/agenda.html", "agenda/partials/_event_card.html") in found
    assert ("base.html", "partials/_sello.html") in found
    assert ("content/home.html", "partials/_portada_img.html") in found
    assert not variable, f"inclusiones con nombre variable, que no se pueden seguir: {variable}"
    foreign = sorted(
        f"{template} pinta {partial}"
        for template, partial in found
        if (owner := _owner(partial, app_folders)) is not None
        and owner != _owner(template, app_folders)
    )
    assert not foreign, (
        "parciales de otra app: la que usan varias apps, base.html o las páginas de error va "
        "en templates/partials/, y la que usa una sola, en la carpeta de esa app:\n"
        + "\n".join(foreign)
    )
