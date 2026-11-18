"""El foco se ve en todo lo que se enfoca; el salto al contenido espera fuera de la vista hasta
recibir el foco; los resultados de la lupa flotan sobre la página, y la vista ampliada de una
galería está cerrada hasta que la abre su ancla, sin JavaScript.
"""

from tests import css


def test_css_has_focus_visible_overlay_and_lightbox():
    """El foco se ve en todo lo que se enfoca; el salto al contenido espera fuera de la vista
    hasta recibir el foco; los resultados flotan sobre la página, y la vista ampliada sin
    JavaScript se abre con su ancla."""
    foco = css.rule((), ":where(a, button, summary, input, [tabindex]):focus-visible")
    assert foco["outline"] == "2px solid var(--accent)"
    salto = css.rule((), ".skip")
    assert salto["position"] == "absolute" and salto["top"].startswith("-")
    assert not css.rule((), ".skip:focus")["top"].startswith("-")
    assert css.rule((), ".busqueda-resultados")["position"] == "absolute"
    assert css.rule((), ".lightbox")["display"] == "none"
    assert css.rule((), ".lightbox:target")["display"] == "grid"
