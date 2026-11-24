"""Contexto común a todas las plantillas."""

import logging
from pathlib import Path

from django.conf import settings

from config.origin import site_host, site_origin
from config.staticfiles import STYLESHEETS

logger = logging.getLogger(__name__)


def version_estaticos(request):
    """Sufijo para romper la caché de las hojas de estilos y de los guiones EN DESARROLLO.

    En producción el nombre ya lleva hash (ManifestStaticFilesStorage), así que cambiar el
    archivo cambia la URL y el navegador lo pide solo. En desarrollo no: cada hoja se sirve
    con su nombre a secas y con `Last-Modified` pero SIN `Cache-Control`, de modo que el
    navegador aplica caché heurística —la guarda una fracción del tiempo transcurrido
    desde su última modificación—. Con un archivo editado hace semanas eso son días, y se
    siguen viendo estilos viejos aunque el servidor ya sirva los nuevos.

    Lo mismo vale para los guiones: un guion viejo en caché junto a una plantilla nueva puede
    no encontrar lo que busca, fallar al arrancar y dejar su componente sin responder. Por eso
    el sufijo sale del archivo modificado más recientemente entre las hojas (`STYLESHEETS`) y
    los guiones propios, y el mismo va en todos.

    Devuelve cadena vacía fuera de DEBUG para no ensuciar la URL ya hasheada.
    """
    if not settings.DEBUG:
        return {"version_estaticos": ""}
    raiz = Path(settings.BASE_DIR) / "static"
    try:
        propios = [*(raiz / path for path in STYLESHEETS), *(raiz / "js").glob("*.js")]
        return {"version_estaticos": f"?v={int(max(p.stat().st_mtime for p in propios))}"}
    except OSError as exc:
        # Que falte un archivo no debe tumbar todas las páginas del sitio: salen sin sufijo, y el
        # registro dice cuál falta.
        logger.warning("Los estáticos van sin sufijo de versión: %s", exc)
        return {"version_estaticos": ""}


def origin(request):
    """El origen fijo de las URL absolutas (JSON-LD) y el dominio que imprime el dossier."""
    return {"site_origin": site_origin(), "site_host": site_host()}
