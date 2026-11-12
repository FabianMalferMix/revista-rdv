"""Los cortes de la hoja de estilos, con nombre: el ancho de ventana desde el que cambia la
maquetación de la hoja (las de `static/css/`, una por capa).

La hoja los escribe en sus `@media`, que no leen variables. Aquí viven para lo que no es la
hoja: los `sizes` de las imágenes (la etiqueta `{% sizes %}`), las fuentes de la obra de la
portada y los guiones, que los reciben de la plantilla en un atributo data-.

Con ellos van los carriles (`--wide` y `--measure`, entre dos `--gutter`, en tokens.css), de los
que sale lo que mide pintada casi cada imagen. `tests/test_shared_values.py` comprueba que la
hoja corta en cada corte y que sus carriles miden lo mismo que los de aquí.
"""

# Desde aquí, la pantalla ancha; por debajo, el teléfono.
PHONE = 720
# Desde aquí, la ficha de un texto o de un poema va a dos columnas: el ancla al lado del texto.
LECTURA_SALA = 840
# Desde aquí, la tirada de la portada pone su hoja de contactos al lado de los pliegos.
TIRADA_WIDE = 1100
# Desde aquí, el estante de la portada pone sus libros más grandes.
ESTANTE_WIDE = 1400
# Desde aquí, el carril ancho pasa de WIDE a WIDE_FROM_CARRIL.
CARRIL_WIDE = 1600

CUTS = (PHONE, LECTURA_SALA, TIRADA_WIDE, ESTANTE_WIDE, CARRIL_WIDE)

# El carril ancho: `--wide` y `--gutter` en tokens.css.
WIDE = 1320
WIDE_FROM_CARRIL = 1440
GUTTER = "clamp(20px, 4vw, 64px)"
# El carril de lectura: `--measure`.
MEASURE = 780


def below(cut):
    """La consulta de lo que queda por debajo de un corte: `(max-width: 719px)`."""
    return f"(max-width: {cut - 1}px)"


def from_cut(cut):
    """La consulta de lo que empieza en un corte: `(min-width: 1400px)`."""
    return f"(min-width: {cut}px)"


def lane(wide=WIDE):
    """El ancho de un carril como longitud de `sizes`: `wide`, o lo que deja la ventana entre los
    dos medianiles cuando no cabe. El ancho es `lane()` y, desde CARRIL_WIDE,
    `lane(WIDE_FROM_CARRIL)`; el de lectura, `lane(MEASURE)`."""
    return f"min({wide}px, 100vw - 2 * {GUTTER})"
