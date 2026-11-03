"""Identidad estable de los ítems de los feeds.

Los lectores de feeds y las aplicaciones de pódcast reconocen un ítem por su GUID: si
cambia, el texto o el episodio aparece como nuevo y se descarga otra vez. Por eso el GUID
no es la dirección del ítem, que depende del slug, del dominio y del esquema, sino un
`tag:` (RFC 4151) con una autoridad fija y la clave primaria.
"""

# El correo del colectivo y el año desde el que lo usa. No depende del dominio, así que
# sobrevive a una mudanza. No se cambia nunca: cambiarlo duplicaría todos los ítems en los
# lectores de feeds y en las aplicaciones de pódcast.
FEED_GUID_AUTHORITY = "repitentesdelverso@gmail.com,2026"


def stable_guid(kind, pk):
    """El GUID de un ítem. `kind` es fijo en cada feed, no el nombre del modelo, que puede
    cambiar."""
    return f"tag:{FEED_GUID_AUTHORITY}:{kind}/{pk}"
