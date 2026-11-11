"""La hoja en capas.

Entre reglas de capas distintas gana la de la capa posterior, sea cual sea su especificidad
(con `!important`, al revés: la anterior), y una regla fuera de las capas les gana a todas. Así
el orden de la cascada lo dan la capa y el lugar de la regla dentro de ella, y un selector no
necesita más especificidad que la de lo que elige: los estados de la cabecera van en una capa
posterior a las piezas, y lo de imprimir, en la última.
"""

import re

from tests import css

# Lo que cambia la cabecera según una marca de la página o de su estado: la barra
# (`data-barra`, que pone js/cabecera.js), la página (`data-pagina`, en el <body>) y la lupa
# abierta.
HEADER_STATE = re.compile(r"\[data-barra|\[data-pagina|\.busqueda\[open\]")
PRINT = "@media print"
REDUCED_MOTION = "@media (prefers-reduced-motion:reduce)"
STILL = "Con el movimiento reducido no se mueve nada, tampoco lo que mueve cada pieza en su capa."
# Cada `!important` de la hoja, con su motivo. Todos van en una capa anterior a las piezas, y
# con `!important` gana la anterior: así le ganan a lo que declare cualquier pieza.
IMPORTANT = {
    ((), "[hidden]", "display"): (
        "El atributo esconde cualquier elemento, también una pieza que declara su `display`."
    ),
    **{
        ((REDUCED_MOTION,), "*, *::before, *::after", name): STILL
        for name in (
            "transition-duration",
            "animation-duration",
            "animation-iteration-count",
            "scroll-behavior",
        )
    },
}


def _selectors(sheet):
    """Cada selector de la hoja con su regla, sin los fotogramas de @keyframes."""
    return [
        (selector, rule)
        for rule in sheet.rules
        if not any(at_rule.startswith("@keyframes") for at_rule in rule.context)
        for selector in rule.selectors
    ]


def _outside_layers(sheet):
    return [
        f"«{block.selector}» (línea {block.line})"
        if isinstance(block, css.Rule)
        else f"@{block.name} (línea {block.line})"
        for block in (*sheet.rules, *sheet.at_rules())
        if block.layer is None and not (isinstance(block, css.AtRule) and block.name == "layer")
    ]


def _misplaced_states(sheet):
    """Los selectores de un estado de la cabecera fuera de su capa, y los de su capa que no son
    un estado de la cabecera."""
    return [
        f"«{selector}» (línea {rule.line}, en {rule.layer})"
        for selector, rule in _selectors(sheet)
        if bool(HEADER_STATE.search(selector)) != (rule.layer == "estados")
    ]


def test_the_layer_order_is_declared_once_before_anything_else():
    """Una sola declaración `@layer`, la primera de la hoja, con todas las capas: el orden de la
    cascada se lee ahí, y no cambia si un bloque se mueve."""
    statements = css.at_rules("layer")
    assert len(statements) == 1, [statement.line for statement in statements]
    (statement,) = statements
    assert css.split_commas(statement.prelude) == css.layers()
    others = [*css.rules(), *(a for a in css.at_rules() if a is not statement)]
    assert statement.line < min(block.line for block in others)
    # Control: con un bloque antes de la declaración, la cascada sigue al bloque.
    moved = css.Stylesheet("@layer b{.x{color:red}}\n@layer a, b;")
    (late,) = moved.at_rules("layer")
    assert css.split_commas(late.prelude) != moved.layers and late.line > moved.rules[0].line


def test_every_rule_is_inside_a_layer():
    """Una regla fuera de las capas les gana a todas, sea cual sea su especificidad."""
    assert _outside_layers(css.site()) == []
    # Control: una regla suelta se informa.
    sheet = css.Stylesheet("@layer a; @layer a{.x{color:red}} .y{color:blue}")
    assert _outside_layers(sheet) == ["«.y» (línea 1)"]


def test_the_header_states_and_only_they_live_in_their_layer():
    """Un estado de la cabecera le gana a la pieza por ir en una capa posterior, así que su
    selector no lleva más que la condición y la pieza; nada más lleva esas marcas."""
    layers = css.layers()
    assert layers.index("estados") > layers.index("componentes")
    assert any(rule.layer == "estados" for rule in css.rules())
    assert _misplaced_states(css.site()) == []
    # Control: la marca fuera de los estados se informa, y en los estados, lo que no la lleva.
    sheet = css.Stylesheet(
        "@layer componentes, estados;"
        "@layer componentes{.busqueda[open] .search{top:0}}"
        "@layer estados{.search{top:0}}"
    )
    assert _misplaced_states(sheet) == [
        "«.busqueda[open] .search» (línea 1, en componentes)",
        "«.search» (línea 1, en estados)",
    ]


def test_print_lives_in_the_last_layer():
    """Lo de imprimir le gana a todo lo de pantalla por ir en la última capa, sin `!important`.
    Fuera de ella va solo lo de imprimir de los elementos sin clase, en la base: ahí pierde con
    la regla de cualquier pieza."""
    assert css.layers()[-1] == "impresion"
    printed = [rule for rule in css.rules() if rule.layer == "impresion"]
    assert printed
    assert [rule.line for rule in printed if PRINT not in rule.context] == []
    elsewhere = [
        f"«{selector}» (línea {rule.line}, en {rule.layer})"
        for selector, rule in _selectors(css.site())
        if PRINT in rule.context
        and rule.layer != "impresion"
        and not (rule.layer == "base" and re.fullmatch(r"[a-z][a-z0-9]*", selector))
    ]
    assert elsewhere == []


def test_important_only_where_a_rule_must_beat_every_piece():
    """En una capa posterior a las piezas, `!important` no haría falta: le ganaría por la capa."""
    found = {
        (
            block.context,
            block.selector if isinstance(block, css.Rule) else f"@{block.name}",
            d.name,
        ): block.layer
        for block, d in css.declarations()
        if d.important
    }
    assert set(found) == set(IMPORTANT)
    layers = css.layers()
    assert all(layers.index(layer) < layers.index("componentes") for layer in found.values())
