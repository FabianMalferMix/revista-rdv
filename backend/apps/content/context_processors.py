from django.urls import reverse

# La barra principal: cinco enlaces (D9, decidido por el dueño del sitio). Cada uno marca
# como suyas las vistas de su territorio: en la ficha de un poema queda marcado «Poemas»,
# y en la agenda, «Colectivo», que es el centro de todo lo del colectivo. Las fichas de una
# obra reseñada, su editorial y su autor son de «Textos»: se llega a ellas desde una reseña.
# Las colecciones y los colaboradores no marcan ninguno: reúnen poemas y textos.
NAV_PRINCIPAL = (
    ("Poemas", "content:poem_index", ("content:poem_detail",)),
    (
        "Textos",
        "content:text_archive",
        (
            "content:article_detail",
            "content:section_detail",
            "content:tag_detail",
            "reviews:work_detail",
            "reviews:publisher_detail",
            "reviews:bookauthor_detail",
        ),
    ),
    ("Registros", "media:recording_index", ("media:recording_detail",)),
    ("Publicaciones", "showcase:publication_index", ("showcase:publication_detail",)),
    (
        "Colectivo",
        "people:member_index",
        (
            "people:member_detail",
            "agenda:agenda",
            "agenda:trayectoria",
            "agenda:gallery",
            "agenda:event_detail",
            "showcase:press_index",
            "showcase:partner_index",
        ),
    ),
)

# La sub-fila del colectivo (D9): en la cabecera de cada uno de estos índices, el resto.
SUBNAV_COLECTIVO = (
    ("Integrantes", "people:member_index"),
    ("Trayectoria", "agenda:trayectoria"),
    ("Agenda", "agenda:agenda"),
    ("Galería", "agenda:gallery"),
    ("Prensa", "showcase:press_index"),
    ("Aliados", "showcase:partner_index"),
)


def nav(request):
    """La barra principal y la sub-fila del colectivo, con lo actual marcado.

    `actual` es el valor de `aria-current`: «page» en el índice mismo y «true» en una
    página de su territorio (la ficha de un poema no es la página «Poemas», pero está en
    ella). La sub-fila solo existe en los índices del colectivo. En el dossier, lo marca su
    botón, que está fuera de la barra."""
    vista = getattr(getattr(request, "resolver_match", None), "view_name", "") or ""
    principal = [
        {
            "rotulo": rotulo,
            "url": reverse(nombre),
            "actual": "page" if vista == nombre else ("true" if vista in suyas else ""),
        }
        for rotulo, nombre, suyas in NAV_PRINCIPAL
    ]
    subnav = []
    if vista in {nombre for _, nombre in SUBNAV_COLECTIVO}:
        subnav = [
            {"rotulo": rotulo, "url": reverse(nombre), "actual": "page" if vista == nombre else ""}
            for rotulo, nombre in SUBNAV_COLECTIVO
        ]
    return {
        "nav_principal": principal,
        "subnav_colectivo": subnav,
        "dossier_actual": vista == "showcase:dossier",
    }


def canonical(request):
    """URL canónica: esquema + host + ruta, SIN el query string (utm_*, q, …) que
    ensuciaría la señal de canonicalización. Preserva solo ?page= en listados
    paginados, donde cada página es un recurso distinto (hallazgo #06)."""
    url = f"{request.scheme}://{request.get_host()}{request.path}"
    page = request.GET.get("page", "")
    if page.isdigit() and page != "1":
        url = f"{url}?page={page}"
    return {"canonical_url": url}
