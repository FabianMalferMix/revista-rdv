"""El analizador de la hoja de estilos con el que las pruebas leen site.css (tests/css.py).

Una regla se encuentra por su contexto y su selector, y el formato de la hoja (los espacios, los
saltos de línea, los comentarios) no cambia lo que el analizador lee en ella.
"""

import re

import pytest

from tests import css

COMPACT = """
.a>b,.c+d~e{grid-area:1/1;margin:calc(2*var(--g)) 0}
.f:has(>:nth-child(2n+1)) :is(g,h){color:rgba(0,0,0,.5)!important}
[data-x="y"] i{grid-template-areas:"a b" "c d"}
@media (min-width:900px) and (max-width:1200px){.a{--pila:"X","Y",serif}}
"""

SPREAD = """
.a > b,
.c + d ~ e {
  grid-area: 1 / 1;
  margin: calc( 2 * var( --g ) ) 0;
}
/* Un comentario con llaves y selectores: .z{color:red} */
.f:has( > :nth-child( 2n + 1 ) ) :is( g , h ) {
  color: rgba( 0 , 0 , 0 , .5 ) ! important ;
}
[ data-x = "y" ] i {
  grid-template-areas:
    "a b"
    "c d";
}
@media ( min-width : 900px ) and ( max-width : 1200px ) {
  .a {
    --pila: "X",
      "Y", serif;
  }
}
"""

# Lo que el analizador no toca al cambiar los blancos de la hoja del sitio: los comentarios, las
# cadenas y las url(), también una url() con una cadena dentro.
_UNTOUCHED = re.compile(
    r"/\*.*?\*/"
    r'|"(?:\\.|[^"\\])*"'
    r"|'(?:\\.|[^'\\])*'"
    r"|url\(\s*(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^)]*)\s*\)",
    re.S,
)


def _spread(fragment):
    fragment = re.sub(r"\s+", "\n    ", fragment)
    return re.sub(r"\s*([,/{};])\s*", r" \1\n  ", fragment)


def _reformat(text):
    """La misma hoja con otros blancos: cada tramo de blancos pasa a un salto de línea con
    sangría, y van espacios y saltos alrededor de las comas, las barras, las llaves y los
    puntos y comas."""
    pieces, last = [], 0
    for kept in _UNTOUCHED.finditer(text):
        pieces += [_spread(text[last : kept.start()]), kept.group(0)]
        last = kept.end()
    return "".join([*pieces, _spread(text[last:])])


def test_a_rule_inside_a_media_query_is_not_the_same_rule_outside():
    hoja = css.Stylesheet(
        ".a{color:red} @media (min-width:900px){.a{color:blue} .b{color:green}} .c{color:black}"
    )
    assert hoja.rule((), ".a")["color"] == "red"
    assert hoja.rule(("@media (min-width:900px)",), ".a")["color"] == "blue"
    assert hoja.rule((), ".c")["color"] == "black"
    with pytest.raises(AssertionError, match=r"«\.b».*está en: \['@media \(min-width:900px\)'\]"):
        hoja.rule((), ".b")
    with pytest.raises(AssertionError):
        hoja.rule(("@media (min-width:720px)",), ".a")


def test_formatting_does_not_change_what_the_sheet_says():
    compacta, espaciada = css.Stylesheet(COMPACT), css.Stylesheet(SPREAD)
    assert len(compacta.rules) == 4
    assert espaciada.rules == compacta.rules
    primera = espaciada.rule((), ".a > b, .c + d ~ e")
    assert primera.selectors == (".a > b", ".c + d ~ e")
    assert primera["grid-area"] == "1 / 1"
    assert primera["margin"] == "calc(2 * var(--g)) 0"
    color = espaciada.rule((), ".f:has(> :nth-child(2n+1)) :is(g, h)")
    assert color["color"] == "rgba(0, 0, 0, .5)" and color.is_important("color")
    assert espaciada.rule((), '[data-x="y"] i')["grid-template-areas"] == '"a b" "c d"'
    medio = ("@media (min-width:900px) and (max-width:1200px)",)
    assert espaciada.rule(medio, ".a")["--pila"] == '"X", "Y", serif'


def test_reformatting_the_site_sheet_changes_nothing():
    """Toda la hoja del sitio, con otros blancos en cada sitio donde caben, se lee igual."""
    original = css.SITE_CSS.read_text(encoding="utf-8")
    reformateada = _reformat(original)
    assert reformateada != original
    antes, despues = css.Stylesheet(original), css.Stylesheet(reformateada)
    assert len(antes.rules) > 100 and antes.at_rules("font-face")
    assert despues.rules == antes.rules
    assert despues.at_rules() == antes.at_rules()


def test_queries_are_normalized_like_the_sheet():
    hoja = css.Stylesheet("@media (forced-colors: active){.a > .b, .c{fill:currentColor}}")
    regla = hoja.rule(("@media (forced-colors:active)",), ".a>.b,.c")
    assert regla.context == ("@media (forced-colors:active)",)
    assert regla.selector == ".a > .b, .c"
    assert hoja.rules_with(("@media (forced-colors: active)",), ".c") == (regla,)
    with pytest.raises(TypeError):
        hoja.rule("@media (forced-colors:active)", ".c")


def test_the_same_selector_twice_in_one_context_reads_as_the_cascade():
    hoja = css.Stylesheet(".a{color:red; margin:0} .b{color:green} .a{color:blue}")
    regla = hoja.rule((), ".a")
    assert regla["color"] == "blue"
    assert regla.values("color") == ("red", "blue")
    assert regla["margin"] == "0"
    assert "padding" not in regla and regla.get("padding") is None
    with pytest.raises(KeyError):
        regla["padding"]


def test_comments_do_not_count():
    hoja = css.Stylesheet("/* .a{color:green} } */ .a{color:red /* { */; /* ; */ margin:0}")
    assert [r.selector for r in hoja.rules] == [".a"]
    assert hoja.rule((), ".a").values("color") == ("red",)


def test_nested_at_rules_stack_their_context():
    hoja = css.Stylesheet(
        "@media print{@supports (display:grid){.a{display:grid}}}"
        "@container filas (min-width:700px){.b{display:flex}}"
    )
    contextos = {r.selector: r.context for r in hoja.rules}
    assert contextos == {
        ".a": ("@media print", "@supports (display:grid)"),
        ".b": ("@container filas (min-width:700px)",),
    }


def test_font_faces_custom_properties_and_keyframes():
    hoja = css.Stylesheet(
        "@font-face{font-family:'X'; src:url(\"../fonts/x.woff2\") format('woff2')}"
        "@property --tinta{syntax:'<color>'; inherits:true; initial-value:transparent}"
        "@keyframes entra{from{opacity:0} to{opacity:1}}"
    )
    (cara,) = hoja.at_rules("font-face")
    assert cara["font-family"] == '"X"'
    assert cara["src"] == 'url("../fonts/x.woff2") format("woff2")'
    (tinta,) = hoja.at_rules("property")
    assert tinta.prelude == "--tinta" and tinta["syntax"] == '"<color>"'
    assert hoja.rule(("@keyframes entra",), "from")["opacity"] == "0"
    assert hoja.rule(("@keyframes entra",), "to")["opacity"] == "1"


def test_tokens_resolve_to_their_values():
    hoja = css.Stylesheet(
        ":root{--a:12px; --b:var(--a); --c:clamp(10px, 2vw, 20px)}"
        "@media (min-width:900px){:root{--a:14px}}"
    )
    assert hoja.tokens() == {"--a": "12px", "--b": "var(--a)", "--c": "clamp(10px, 2vw, 20px)"}
    assert hoja.tokens(("@media (min-width:900px)",)) == {"--a": "14px"}
    assert hoja.resolve("calc(var(--b) + var(--sin-token))") == "calc(12px + var(--sin-token))"
    assert hoja.px_range("var(--b)") == (12, 12)
    assert hoja.px_range("var(--c)") == (10, 20)
    with pytest.raises(AssertionError, match="no sé leer"):
        hoja.px_range("1em")


def test_lists_are_split_at_their_own_commas():
    assert css.split_commas("color var(--d) cubic-bezier(.2, .6, .3, 1), translate 1s") == (
        "color var(--d) cubic-bezier(.2, .6, .3, 1)",
        "translate 1s",
    )


def test_what_the_parser_cannot_read_fails_instead_of_passing():
    with pytest.raises(AssertionError, match="anidada"):
        css.Stylesheet(".a{color:red; .b{color:blue}}")
    with pytest.raises(AssertionError, match="mal formado"):
        css.Stylesheet(".a{color}")


def test_the_site_sheet_is_read_once():
    assert css.site() is css.site()
    assert css.rules() is css.site().rules
    assert css.rule((), ":root")["color-scheme"] == "light"
