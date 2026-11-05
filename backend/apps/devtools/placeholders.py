"""Los recursos marcadores: las imágenes provisionales con que se diseña mientras llega el
material del colectivo.

Un marcador se reconoce por su crédito, que lo dice: «provisional» en el que dibuja
`seed_material_generico` y «placeholder» en las fotos de demostración que aún guardan algunas
bases. Lo demás es material real, y ningún comando de desarrollo lo pisa ni lo cuenta como
marcador. Aquí se decide, para todos los que necesitan saberlo.
"""

# El crédito de lo que dibuja seed_material_generico.
PLACEHOLDER_CREDIT = "Material genérico provisional (reemplazar por el real)"

# Las palabras que delatan un marcador en un crédito, sin distinguir mayúsculas.
_MARKERS = ("provisional", "placeholder")


def is_placeholder(asset):
    """Si el recurso es un marcador: su crédito dice «provisional» o «placeholder»."""
    credit = (asset.credit or "").lower()
    return any(marker in credit for marker in _MARKERS)
