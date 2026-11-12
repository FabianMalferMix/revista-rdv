"""Los feeds del sitio: los textos y el pódcast de los registros.

Las rutas (config/urls.py) y lo que vacía su caché (signals.py) salen de esta lista.
"""

from apps.content.feeds import LatestArticlesFeed
from apps.media.feeds import RecordingsFeed

# Por nombre de ruta. Una instancia por feed, compartida entre los hilos de gunicorn: los feeds
# no guardan nada de la petición (las URL absolutas salen de SITE_URL).
FEEDS = {
    "feed": LatestArticlesFeed(),
    "recordings_feed": RecordingsFeed(),
}
