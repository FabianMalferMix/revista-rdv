"""Las cifras del dossier y las de la trayectoria. La cifra grande, de cartel, es la del dossier
(`.dossier-cifras`); `.stats-strip` es la tira de cifras de la trayectoria, cifras de dato. La
portada no lleva cifras.
"""

from django.conf import settings

from tests import css


def test_la_cifra_grande_solo_esta_en_el_dossier():
    """Ninguna regla puede agrandar el <strong> de una tira de cifras fuera del dossier. Si
    la regla del número grande pasara a `.stats-strip strong`, /trayectoria/ mostraría
    cifras de cartel sin que nadie lo hubiera pedido. En el dossier sí: es lo primero que
    busca un jurado.
    """
    grandes = [
        regla.selector
        for regla in css.rules()
        if "strong" in regla.selector
        and ("stats" in regla.selector or "cifras" in regla.selector)
        and any(css.px_range(tam)[1] > 24 for tam in regla.values("font-size"))
    ]
    assert grandes == [".dossier-cifras strong"], (
        f"la cifra grande tiene que estar en el dossier y solo ahí: {grandes}"
    )


def test_la_trayectoria_conserva_su_tira_y_el_dossier_tiene_sus_cifras():
    """La trayectoria rotula sus cifras como dato; el dossier, con número grande. Ninguna de
    las dos lleva la marca de portada, que heredaría su estilo."""
    tpl = settings.BASE_DIR / "templates"
    trayectoria = (tpl / "agenda/trayectoria.html").read_text(encoding="utf-8")
    dossier = (tpl / "showcase/dossier.html").read_text(encoding="utf-8")
    assert "stats-strip" in trayectoria, "la trayectoria ya no usa la tira de cifras"
    assert "dossier-cifras" in dossier and "stats-strip" not in dossier
    for texto in (trayectoria, dossier):
        assert "hero-stats" not in texto
