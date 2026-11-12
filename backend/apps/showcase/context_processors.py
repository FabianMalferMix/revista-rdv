from django.utils.functional import SimpleLazyObject

from .profile import request_profile


def site_profile(request):
    """Expone el perfil del colectivo a todas las plantillas.

    Es perezoso: el perfil se consulta la primera vez que una plantilla lo lee, y una sola vez
    por petición (`request_profile`, el mismo que piden las vistas). Lo que no pinta la
    cabecera ni el pie, como el fragmento de resultados de la lupa, no lo consulta.

    `site_name` es el nombre con que firma cada página (el título, el sello, Open Graph y los
    datos estructurados): `SiteProfile.site_name`, el del perfil o, si está en blanco, el fijo
    del sitio, el mismo de los feeds y los correos. Se resuelve aquí, y ninguna plantilla
    escribe su propio respaldo.

    Las redes del colectivo van en una lista que se consulta una sola vez por página, y
    solo si alguien la usa: las piden los datos estructurados, el pie, el menú del
    teléfono y la cejilla de la portada, y cada `social_links.all` en una plantilla era
    una consulta más.
    """
    perfil = SimpleLazyObject(lambda: request_profile(request))
    redes = SimpleLazyObject(lambda: list(perfil.social_links.all()))
    return {
        "site_profile": perfil,
        "site_name": SimpleLazyObject(lambda: perfil.site_name),
        "redes_del_colectivo": redes,
        # La cejilla de la portada lo nombra: sale de la misma lista, sin otra consulta.
        "instagram_del_colectivo": SimpleLazyObject(
            lambda: next((r for r in redes if r.platform.strip().lower() == "instagram"), None)
        ),
    }
