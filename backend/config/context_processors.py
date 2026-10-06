"""Contexto común a todas las plantillas."""

from pathlib import Path

from django.conf import settings


def version_estaticos(request):
    """Sufijo para romper la caché de la hoja de estilos EN DESARROLLO.

    En producción el nombre ya lleva hash (ManifestStaticFilesStorage), así que cambiar el
    archivo cambia la URL y el navegador lo pide solo. En desarrollo no: la hoja se sirve
    como `site.css` a secas y con `Last-Modified` pero SIN `Cache-Control`, de modo que el
    navegador aplica caché heurística —la guarda una fracción del tiempo transcurrido
    desde su última modificación—. Con un archivo editado hace semanas eso son días, y se
    siguen viendo estilos viejos aunque el servidor ya sirva los nuevos.

    Pasó dos veces durante el cambio de paleta: el sitio se veía en modo oscuro después de
    haberlo eliminado, y la segunda vez después de haber cambiado la paleta entera.

    Devuelve cadena vacía fuera de DEBUG para no ensuciar la URL ya hasheada.
    """
    if not settings.DEBUG:
        return {"version_estaticos": ""}
    hoja = Path(settings.BASE_DIR) / "static" / "css" / "site.css"
    try:
        return {"version_estaticos": f"?v={int(hoja.stat().st_mtime)}"}
    except OSError:
        # Que falte el archivo no debe tumbar todas las páginas del sitio.
        return {"version_estaticos": ""}
