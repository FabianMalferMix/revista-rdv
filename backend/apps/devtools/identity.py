"""La identidad del colectivo en las bases de desarrollo: el nombre, el lema, el año, el lugar,
los correos, el manifiesto y las redes del perfil del sitio.

Este módulo es su única fuente. La copia de desarrollo (datos.json) no la lleva:
`datos_de_desarrollo cargar` la pone en el perfil, `datos_de_desarrollo exportar` se niega a
exportar una base cuya identidad es otra (en otro equipo se vería una distinta) y
`seed_material_generico` la dibuja en la foto de grupo y en las cubiertas propias. En
producción, la identidad se pone en el panel (Perfil del sitio).
"""

import textwrap

from django.conf import settings

# Los campos del perfil del sitio que son la identidad, con su valor. El nombre es el fijo del
# sitio (`SITE_NAME`). El correo general es el del colectivo, que es público; no hay correo de
# gestión ni teléfono. El manifiesto es provisional, hasta que el colectivo escriba el suyo.
PROFILE = {
    "name": settings.SITE_NAME,
    "tagline": "Colectivo de poesía",
    "founded_year": 2023,
    "location": "Chile",
    "general_email": "repitentesdelverso@gmail.com",
    "booking_email": "",
    "phone": "",
    "manifesto": (
        "Repitentes del Verso es un colectivo de poesía que se reúne para leer en voz alta, "
        "escribir en compañía y llevar los poemas a lugares donde no suelen llegar: salas de "
        "clases, ferias, plazas, bibliotecas y escenarios compartidos con otras disciplinas. "
        "Trabajamos la escritura como un oficio que se afina en público: lo que resiste la "
        "lectura colectiva se publica, lo demás vuelve al taller. Guardamos registro de cada "
        "encuentro porque la memoria de un colectivo también se escribe entre todos."
    ),
}

# Las redes del colectivo, (plataforma, dirección), en el orden en que salen en el sitio.
SOCIAL_LINKS = (("Instagram", "https://www.instagram.com/repitentesdelverso"),)


def apply(profile):
    """Pone la identidad en el perfil del sitio y deja solo sus redes.

    Escribe los campos con `update`: el perfil no se guarda, así que no pide otra vez las copias
    de la obra de la portada ni cambia su fecha de actualización.
    """
    type(profile).objects.filter(pk=profile.pk).update(**PROFILE)
    profile.refresh_from_db()
    profile.social_links.all().delete()
    for position, (platform, url) in enumerate(SOCIAL_LINKS):
        profile.social_links.create(platform=platform, url=url, position=position)


def differences(profile):
    """Lo que el perfil del sitio tiene distinto de la identidad, campo por campo."""
    if profile is None:
        return ["la base no tiene perfil del sitio"]

    def shown(value):
        return textwrap.shorten(repr(value), 60, placeholder="…")

    found = [
        f"{name}: {shown(getattr(profile, name))} en la base, {shown(value)} en identity.py"
        for name, value in PROFILE.items()
        if getattr(profile, name) != value
    ]
    links = tuple(profile.social_links.order_by("position", "pk").values_list("platform", "url"))
    if links != SOCIAL_LINKS:
        found.append(f"redes: {links!r} en la base, {SOCIAL_LINKS!r} en identity.py")
    return found
