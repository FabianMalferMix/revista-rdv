"""Contexto común a todas las plantillas."""

from pathlib import Path

from django.conf import settings


def version_estaticos(request):
    """Sufijo para romper la caché de la hoja de estilos y de los guiones EN DESARROLLO.

    En producción el nombre ya lleva hash (ManifestStaticFilesStorage), así que cambiar el
    archivo cambia la URL y el navegador lo pide solo. En desarrollo no: la hoja se sirve
    como `site.css` a secas y con `Last-Modified` pero SIN `Cache-Control`, de modo que el
    navegador aplica caché heurística —la guarda una fracción del tiempo transcurrido
    desde su última modificación—. Con un archivo editado hace semanas eso son días, y se
    siguen viendo estilos viejos aunque el servidor ya sirva los nuevos.

    Pasó dos veces durante el cambio de paleta: el sitio se veía en modo oscuro después de
    haberlo eliminado, y la segunda vez después de haber cambiado la paleta entera. Y con los
    guiones, que no llevaban sufijo: al quitar las flechas de la tirada (D29), el navegador
    siguió con el `registros.js` viejo, que las buscaba, fallaba al arrancar y dejaba la pila
    y el índice sin responder. Por eso manda el más reciente de la hoja y los guiones propios.

    Devuelve cadena vacía fuera de DEBUG para no ensuciar la URL ya hasheada.
    """
    if not settings.DEBUG:
        return {"version_estaticos": ""}
    raiz = Path(settings.BASE_DIR) / "static"
    try:
        propios = [raiz / "css" / "site.css", *(raiz / "js").glob("*.js")]
        return {"version_estaticos": f"?v={int(max(p.stat().st_mtime for p in propios))}"}
    except OSError:
        # Que falte el archivo no debe tumbar todas las páginas del sitio.
        return {"version_estaticos": ""}
