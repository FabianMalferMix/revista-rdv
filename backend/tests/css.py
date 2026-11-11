"""La hoja de estilos del sitio, analizada para las pruebas.

Las pruebas que miran la hoja del sitio la leen con este módulo y nunca como texto. La hoja son
varios archivos, uno por capa, que las páginas enlazan en el orden de `STYLESHEETS`
(config/staticfiles.py); el navegador los lee uno tras otro como una sola hoja, y este módulo
también: `site()` los analiza juntos y en ese orden, una sola vez por proceso, con tinycss2. Cada
regla sale con:

- su contexto: la tupla de las at-rules que la contienen, de fuera hacia dentro, como
  `("@media (min-width:900px)",)`; `()` es el nivel de arriba;
- su capa (`regla.layer`): el nombre de la `@layer` que la contiene, o `None` si está fuera de
  las capas. La capa no es contexto: una regla se busca igual dentro y fuera de ellas, y una
  prueba puede afirmar en qué capa vive;
- su selector: la lista entera (`".nav a, .subnav a"`) y cada selector suelto (`selectors`);
- sus declaraciones, en el orden de la hoja: `regla["display"]` da el último valor, que es el
  que aplica el navegador, y `regla.values("min-height")` da todos;
- su lugar: el archivo (`regla.sheet`, su ruta en static/; None en una hoja sin nombre) y la
  línea dentro de él (`regla.line`), que nombran los mensajes (`regla.place`). Antes y después
  se comparan con `regla.position`, el lugar del archivo en la lista y la línea, que es el orden
  en que el navegador lee las reglas.

El orden de las capas es el del navegador: el de la primera vez que se nombra cada una, en una
declaración `@layer a, b;` o en un bloque (`Stylesheet.layers`). Las capas anidadas no se leen:
ordenarlas pide el árbol de capas, y la hoja no las usa.

Una regla se busca siempre por su contexto y su selector (`rule`, `rules_with`), de modo que una
regla que sale de su `@media` ya no se encuentra donde la prueba la busca. Los comentarios no
cuentan, y los espacios y los saltos de línea se escriben siempre igual, así que formatear la
hoja no cambia ningún resultado:

- un espacio donde había cualquier blanco, y ninguno al principio o al final de un paréntesis;
- `", "` tras cada coma, `" / "` y `" * "` alrededor de esas barras y asteriscos, y `" > "`,
  `" + "` y `" ~ "` alrededor de los combinadores de un selector;
- en el preludio de una at-rule, nada alrededor de los dos puntos: `(forced-colors:active)`.

Las cadenas y los números se escriben como en la hoja. Las consultas (el contexto y el selector
que se piden) se normalizan igual.
"""

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import tinycss2

from config.staticfiles import STYLESHEETS

STATIC = Path(__file__).resolve().parent.parent / "static"
# Los archivos de la hoja del sitio, en el orden en que los enlazan las páginas.
SITE_SHEETS = tuple(STATIC / path for path in STYLESHEETS)

# At-rules cuyo bloque contiene reglas: lo que va dentro se analiza con la at-rule como
# contexto. `@layer` también contiene reglas, pero no es contexto (ver `_walk`). Las demás con
# bloque (@font-face, @property…) contienen declaraciones.
_GROUPING = frozenset({"media", "supports", "container", "scope", "starting-style", "document"})
_KEYFRAMES = frozenset({"keyframes", "-webkit-keyframes"})
_NTH = frozenset({"nth-child", "nth-last-child", "nth-of-type", "nth-last-of-type"})
_COMBINATORS = frozenset({">", "+", "~"})
_VALUE_OPERATORS = frozenset({"/", "*"})
_TOKEN = re.compile(r"var\((--[\w-]+)\)")
_PX = re.compile(r"(-?[\d.]+)px")
_CLAMP = re.compile(r"clamp\((-?[\d.]+)px, [^,]+, (-?[\d.]+)px\)")


@dataclass(frozen=True)
class Declaration:
    name: str
    value: str
    important: bool = False


@dataclass(frozen=True)
class _Block:
    """Lo común a una regla y a una at-rule con declaraciones."""

    context: tuple[str, ...]
    declarations: tuple[Declaration, ...]
    line: int = field(default=0, compare=False)
    # La capa: su nombre, None fuera de las capas; en una regla que `rule()` junta de varias
    # capas, la tupla de esas capas en el orden de la cascada.
    layer: str | tuple[str | None, ...] | None = None
    # El archivo: su nombre (None si la hoja no lo tiene) y su lugar entre los de la hoja.
    sheet: str | None = field(default=None, compare=False)
    sheet_index: int = field(default=0, compare=False)

    @property
    def position(self):
        """El orden en que el navegador lee la regla: el lugar de su archivo y su línea."""
        return self.sheet_index, self.line

    @property
    def place(self):
        """El archivo y la línea, para los mensajes: «css/base.css, línea 12»."""
        return _place(self.sheet, self.line)

    def __contains__(self, name):
        return any(d.name == name for d in self.declarations)

    def __getitem__(self, name):
        found = self.values(name)
        if not found:
            raise KeyError(f"{self._where()} no declara «{name}»")
        return found[-1]

    def get(self, name, default=None):
        found = self.values(name)
        return found[-1] if found else default

    def values(self, name):
        """Todos los valores de esa propiedad, en el orden de la hoja."""
        return tuple(d.value for d in self.declarations if d.name == name)

    def is_important(self, name):
        """Si la última declaración de esa propiedad lleva `!important`."""
        found = [d for d in self.declarations if d.name == name]
        return bool(found) and found[-1].important


@dataclass(frozen=True)
class Rule(_Block):
    selector: str = ""
    selectors: tuple[str, ...] = ()

    def _where(self):
        return (
            f"«{self.selector}» en {_describe(self.context)}{_in_layer(self.layer)} ({self.place})"
        )


@dataclass(frozen=True)
class AtRule(_Block):
    name: str = ""
    prelude: str = ""

    def _where(self):
        return (
            f"@{self.name} {self.prelude} en {_describe(self.context)}{_in_layer(self.layer)} "
            f"({self.place})"
        )


class _Source:
    """El archivo que se está leyendo: lo que cada regla guarda de su lugar."""

    def __init__(self, name, index):
        self.name, self.index = name, index

    def place(self, line):
        return _place(self.name, line)


class Stylesheet:
    """Una hoja analizada: sus reglas y sus at-rules con declaraciones, en orden.

    La hoja puede ser varios archivos, que se leen uno tras otro, como los lee el navegador
    cuando una página los enlaza en ese orden: cada uno es su texto o un par (nombre, texto), y
    el nombre es el que dan los mensajes.
    """

    def __init__(self, *sheets):
        rules, at_rules, layers = [], [], []
        for index, sheet in enumerate(sheets):
            name, text = sheet if isinstance(sheet, tuple) else (None, sheet)
            nodes = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)
            _walk(nodes, (), None, rules, at_rules, layers, _Source(name, index))
        self.rules = tuple(rules)
        self._at_rules = tuple(at_rules)
        # Las capas, de la que menos pesa a la que más: el orden de su primera mención.
        self.layers = tuple(layers)

    def _rank(self, block):
        """El lugar de la capa de una regla en la cascada: fuera de las capas, la última."""
        return len(self.layers) if block.layer is None else self.layers.index(block.layer)

    def _cascade_order(self, found):
        """Las declaraciones de esas reglas en el orden en que las aplica la cascada, con la que
        gana al final: las normales por capa (la última gana; fuera de las capas, a todas) y por
        orden de la hoja; después las `!important`, con las capas al revés (la primera gana; las
        de fuera de las capas pierden con todas)."""
        normal = sorted(found, key=lambda r: (self._rank(r), r.position))
        important = sorted(found, key=lambda r: (-self._rank(r), r.position))
        return (
            *(d for r in normal for d in r.declarations if not d.important),
            *(d for r in important for d in r.declarations if d.important),
        )

    def at_rules(self, name=None):
        """Las at-rules con ese nombre (sin la arroba), o todas, en cualquier contexto."""
        return tuple(a for a in self._at_rules if name is None or a.name == name)

    def declarations(self):
        """Cada declaración de la hoja, con la regla o la at-rule que la lleva."""
        return tuple(
            (block, d) for block in (*self.rules, *self._at_rules) for d in block.declarations
        )

    def rule(self, context, selector):
        """La regla con exactamente esa lista de selectores en exactamente ese contexto.

        Si el mismo selector aparece varias veces en el mismo contexto, también en capas
        distintas, sus declaraciones se juntan como las junta la cascada (`_cascade_order`).
        Si no está, falla diciendo en qué contextos sí está.
        """
        context, selector = normalize_context(context), normalize_selector(selector)
        found = [r for r in self.rules if r.context == context and r.selector == selector]
        if not found:
            elsewhere = sorted({_describe(r.context) for r in self.rules if r.selector == selector})
            within = sorted(
                f"«{r.selector}» en {_describe(r.context)}"
                for r in self.rules
                if selector in r.selectors and r.selector != selector
            )
            raise AssertionError(
                f"la hoja no tiene la regla «{selector}» en {_describe(context)}; "
                f"está en: {elsewhere or 'ningún contexto'}"
                + (f"; forma parte de: {within}" if within else "")
            )
        layers = tuple(dict.fromkeys(r.layer for r in sorted(found, key=self._rank)))
        return Rule(
            context,
            self._cascade_order(found),
            found[0].line,
            layers[0] if len(layers) == 1 else layers,
            found[0].sheet,
            found[0].sheet_index,
            selector=selector,
            selectors=found[0].selectors,
        )

    def rules_with(self, context, selector):
        """Las reglas de ese contexto cuya lista de selectores incluye ese selector."""
        context, selector = normalize_context(context), normalize_selector(selector)
        return tuple(r for r in self.rules if r.context == context and selector in r.selectors)

    def tokens(self, context=()):
        """Las propiedades personalizadas que declaran las reglas `:root` de ese contexto, en
        cualquier capa: si dos declaran la misma, la que gana en la cascada."""
        context = normalize_context(context)
        found = [r for r in self.rules if r.context == context and r.selector == ":root"]
        return {d.name: d.value for d in self._cascade_order(found) if d.name.startswith("--")}

    def resolve(self, value, context=()):
        """El valor con cada `var(--x)` sustituido por el token de ese contexto, si existe."""
        tokens = self.tokens(context)
        for _ in range(10):
            resolved = _TOKEN.sub(lambda m: tokens.get(m.group(1), m.group(0)), value)
            if resolved == value:
                return resolved
            value = resolved
        raise AssertionError(f"tokens que se citan en círculo: {value}")

    def px_range(self, value, context=()):
        """(mínimo, máximo) en px de un tamaño fijo o de un `clamp()` en px, con los tokens
        resueltos."""
        resolved = self.resolve(value, context)
        if fixed := _PX.fullmatch(resolved):
            return float(fixed.group(1)), float(fixed.group(1))
        if clamp := _CLAMP.fullmatch(resolved):
            return float(clamp.group(1)), float(clamp.group(2))
        raise AssertionError(f"tamaño que no sé leer: {value} ({resolved})")


def _describe(context):
    return " › ".join(context) if context else "el nivel de arriba"


def _place(sheet, line):
    return f"{sheet}, línea {line}" if sheet else f"línea {line}"


def _in_layer(layer):
    if layer is None:
        return ", fuera de las capas"
    if isinstance(layer, tuple):
        return f", en las capas {', '.join(str(n) for n in layer)}"
    return f", en la capa {layer}"


def _walk(nodes, context, layer, rules, at_rules, layers, source):
    for node in nodes:
        if node.type == "error":
            raise AssertionError(
                f"CSS mal formado en {source.place(node.source_line)}: {node.message}"
            )
        # Lo que cada bloque guarda de su lugar: su línea, su capa y su archivo.
        where = {
            "line": node.source_line,
            "layer": layer,
            "sheet": source.name,
            "sheet_index": source.index,
        }
        if node.type == "qualified-rule":
            selectors = _selector_list(node.prelude)
            rules.append(
                Rule(
                    context,
                    _declarations(node.content, source),
                    **where,
                    selector=", ".join(selectors),
                    selectors=selectors,
                )
            )
            continue
        name = node.lower_at_keyword
        prelude = _render(node.prelude, "prelude")
        if name == "layer":
            # Una capa ordena, no condiciona: lo de dentro sigue en el mismo contexto, con la
            # capa como dato. `@layer a, b;` solo nombra capas, en ese orden.
            names = split_commas(prelude) if prelude else (f"<anónima {len(layers)}>",)
            if layer is not None or any("." in n for n in names):
                raise AssertionError(
                    f"capas anidadas en {source.place(node.source_line)}: no sé ordenarlas"
                )
            layers.extend(n for n in dict.fromkeys(names) if n not in layers)
            if node.content is None:
                at_rules.append(AtRule(context, (), **where, name=name, prelude=prelude))
            else:
                (inner_layer,) = names
                inner = tinycss2.parse_rule_list(
                    node.content, skip_comments=True, skip_whitespace=True
                )
                _walk(inner, context, inner_layer, rules, at_rules, layers, source)
        elif node.content is None:
            at_rules.append(AtRule(context, (), **where, name=name, prelude=prelude))
        elif name in _GROUPING or name in _KEYFRAMES:
            inner = tinycss2.parse_rule_list(node.content, skip_comments=True, skip_whitespace=True)
            inner_context = (*context, f"@{name} {prelude}".rstrip())
            _walk(inner, inner_context, layer, rules, at_rules, layers, source)
        else:
            declarations = _declarations(node.content, source)
            at_rules.append(AtRule(context, declarations, **where, name=name, prelude=prelude))


def _declarations(content, source):
    found = []
    for item in tinycss2.parse_blocks_contents(content, skip_comments=True, skip_whitespace=True):
        if item.type == "error":
            raise AssertionError(
                f"CSS mal formado en {source.place(item.source_line)}: {item.message}"
            )
        if item.type != "declaration":
            # El anidamiento de CSS cambiaría el selector de lo anidado: falla en vez de
            # dar por buenas unas reglas que no son las que aplica el navegador.
            raise AssertionError(f"regla anidada en {source.place(item.source_line)}: sin resolver")
        name = item.name if item.name.startswith("--") else item.lower_name
        found.append(Declaration(name, _render(item.value, "value"), item.important))
    return tuple(found)


def _split_at_commas(tokens):
    """Los tramos de una lista separada por comas. Las comas de dentro de un paréntesis (las de
    `:is()` o de `rgba()`) van dentro de su nodo, así que no la parten."""
    parts = [[]]
    for token in tokens:
        if token.type == "literal" and token.value == ",":
            parts.append([])
        else:
            parts[-1].append(token)
    return parts


def _selector_list(tokens):
    """Cada selector de una lista, normalizado."""
    return tuple(_render(part, "selector") for part in _split_at_commas(tokens))


def _render(nodes, mode):
    """Escribe una lista de nodos con los blancos en su forma canónica.

    `mode` es "value" (el valor de una declaración), "selector", "attribute" (dentro de los
    corchetes de un selector), "nth" (los argumentos de `:nth-child()` y sus hermanos) o
    "prelude" (lo que sigue al nombre de una at-rule).
    """
    pieces = []
    for node in nodes:
        kind = node.type
        if kind == "comment":
            continue
        if kind == "whitespace":
            pieces.append(("space", ""))
        elif kind == "literal" and node.value == ",":
            pieces.append(("comma", ","))
        elif kind == "literal" and _is_spaced(node.value, mode):
            pieces.append(("spaced", node.value))
        elif kind == "literal" and _is_tight(node.value, mode):
            pieces.append(("tight", node.value))
        elif kind == "function":
            inner = "nth" if mode == "selector" and node.lower_name in _NTH else mode
            pieces.append(("text", f"{node.name}({_render(node.arguments, inner)})"))
        elif kind == "() block":
            pieces.append(("text", f"({_render(node.content, mode)})"))
        elif kind == "[] block":
            inner = "attribute" if mode == "selector" else mode
            pieces.append(("text", f"[{_render(node.content, inner)}]"))
        elif kind == "{} block":
            pieces.append(("text", f"{{{_render(node.content, mode)}}}"))
        else:
            pieces.append(("text", node.serialize()))
    return _join(pieces)


def _is_spaced(value, mode):
    if mode == "selector":
        return value in _COMBINATORS
    return mode in ("value", "prelude") and value in _VALUE_OPERATORS


def _is_tight(value, mode):
    if mode == "attribute":
        return True
    if mode == "nth":
        return value in ("+", "-")
    return mode == "prelude" and value == ":"


def _join(pieces):
    out = []
    space = False  # hubo un blanco en la hoja
    after = ""  # lo que pide la pieza anterior: "space", "none" o ""
    for kind, text in pieces:
        if kind == "space":
            space = True
            continue
        if kind == "text":
            if out and after != "none" and (space or after == "space"):
                out.append(" ")
            out.append(text)
            after = ""
        elif kind == "comma":
            out.append(",")
            after = "space"
        elif kind == "spaced":
            out.append(f" {text}" if out else text)
            after = "space"
        else:
            out.append(text)
            after = "none"
        space = False
    return "".join(out)


def normalize_selector(selector):
    """Un selector (o una lista) escrito como lo escribe este módulo."""
    return ", ".join(_selector_list(tinycss2.parse_component_value_list(selector)))


def normalize_context(context):
    """Un contexto (tupla de at-rules) escrito como lo escribe este módulo."""
    if isinstance(context, str):
        raise TypeError("el contexto es una tupla de at-rules: ('@media (min-width:900px)',)")
    return tuple(_normalize_at_rule(at_rule) for at_rule in context)


def _normalize_at_rule(text):
    tokens = tinycss2.parse_component_value_list(text, skip_comments=True)
    if not tokens or tokens[0].type != "at-keyword":
        raise ValueError(f"no es una at-rule: {text!r}")
    prelude = _render(tokens[1:], "prelude")
    return f"@{tokens[0].lower_value} {prelude}".rstrip()


def split_commas(value):
    """Los elementos de un valor separado por comas, sin partir lo que va entre paréntesis."""
    tokens = tinycss2.parse_component_value_list(value, skip_comments=True)
    return tuple(_render(part, "value") for part in _split_at_commas(tokens))


@cache
def site():
    """La hoja del sitio, analizada una vez por proceso: sus archivos, en el orden de la lista."""
    return Stylesheet(
        *((path, (STATIC / path).read_text(encoding="utf-8")) for path in STYLESHEETS)
    )


def rules():
    """Todas las reglas de la hoja del sitio, en su orden."""
    return site().rules


def layers():
    """Las capas de la hoja del sitio, en el orden de la cascada."""
    return site().layers


def rule(context, selector):
    return site().rule(context, selector)


def rules_with(context, selector):
    return site().rules_with(context, selector)


def at_rules(name=None):
    return site().at_rules(name)


def declarations():
    return site().declarations()


def tokens(context=()):
    return site().tokens(context)


def resolve(value, context=()):
    return site().resolve(value, context)


def px_range(value, context=()):
    return site().px_range(value, context)
