"""Los cortes de la hoja de estilos, con nombre: el ancho de ventana desde el que cambia la
maquetación de `static/css/site.css`.

La hoja los escribe en sus `@media`, que no leen variables. Aquí viven para lo que no es la
hoja: los `sizes` de las imágenes (la etiqueta `{% sizes %}`), las fuentes de la obra de la
portada y los guiones, que los reciben de la plantilla en un atributo data-.
`tests/test_shared_values.py` comprueba que la hoja corta en cada uno.
"""

# Desde aquí, la pantalla ancha; por debajo, el teléfono.
PHONE = 720
# Desde aquí, la ficha de un texto o de un poema va a dos columnas: el ancla al lado del texto.
LECTURA_SALA = 840
# Desde aquí, el estante de la portada pone sus libros más grandes.
ESTANTE_WIDE = 1400

CUTS = (PHONE, LECTURA_SALA, ESTANTE_WIDE)


def below(cut):
    """La consulta de lo que queda por debajo de un corte: `(max-width: 719px)`."""
    return f"(max-width: {cut - 1}px)"


def from_cut(cut):
    """La consulta de lo que empieza en un corte: `(min-width: 1400px)`."""
    return f"(min-width: {cut}px)"
