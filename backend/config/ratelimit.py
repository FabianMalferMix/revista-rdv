"""El límite de tasa de las vistas públicas, y una sola respuesta para cuando se supera.

`rate_limited` cuenta las peticiones de cada IP con django-ratelimit. Pasado el límite, la vista
no llega a ejecutarse: responde la función `limited` que la vista le da, con su página de siempre
y el aviso. Así una vista con límite no puede quedarse sin él por olvidar comprobarlo.

El estado de la respuesta dice lo que pasó:

- pasado el límite, 429, con `Retry-After`: los segundos que faltan para que se renueve la
  ventana del contador;
- con la caché de los contadores caída, el límite falla cerrado (`RATELIMIT_FAIL_OPEN`): 503,
  con `Retry-After` y el aviso de que el servicio no está disponible. A Sentry le llega
  `UNAVAILABLE_REPORT`.

Una petición de htmx recibe el aviso con un 200, porque htmx no pinta las respuestas 4xx ni 5xx
y el aviso tiene que llegar al panel que la pidió.
"""

import functools
import logging

from django.utils.cache import patch_vary_headers
from django_ratelimit import ALL
from django_ratelimit.core import get_usage

from config.cache import ERROR_INTERVAL, SERVICE_UNAVAILABLE, OncePerInterval, counters_available

logger = logging.getLogger(__name__)

# Lo que se pide esperar cuando la caché de los contadores no responde. El aviso dice «unos
# minutos».
UNAVAILABLE_RETRY_AFTER = 120  # segundos

# Sentry ignora el logger django.request, que es el que anota cada 503 en la consola. Este ERROR
# le llega en su lugar: una vez por intervalo, el mismo de la caché, para que una caída larga no
# gaste la cuota, y siempre con el mismo texto, que no cita nada de la petición, para que todas
# las caídas queden en un mismo issue.
UNAVAILABLE_REPORT = (
    "La caché de los contadores no responde: las vistas con límite de tasa avisan que el "
    "servicio no está disponible"
)
_report_due = OncePerInterval(ERROR_INTERVAL)


def rate_limited(rate, *, notice, limited, method=ALL):
    """Limita la vista a `rate` peticiones por IP (`"60/m"`, `"10/h"`) de los métodos `method`:
    todos, si no se dicen, para que un método olvidado cuente de más y no de menos.

    Pasado el límite responde `limited(request, aviso, *args, **kwargs)`, la página de la vista
    con el aviso: `notice` o, si la caché no puede contar, SERVICE_UNAVAILABLE."""

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            usage = get_usage(request, fn=view, key="ip", rate=rate, method=method, increment=True)
            if usage is None or not usage["should_limit"]:
                return view(request, *args, **kwargs)
            if counters_available():
                text, status, retry_after = notice, 429, max(usage["time_left"], 1)
            else:
                text, status, retry_after = SERVICE_UNAVAILABLE, 503, UNAVAILABLE_RETRY_AFTER
                if _report_due():
                    logger.error(UNAVAILABLE_REPORT)
            response = limited(request, text, *args, **kwargs)
            patch_vary_headers(response, ["HX-Request"])
            if request.headers.get("HX-Request") != "true":
                response.status_code = status
                response["Retry-After"] = str(retry_after)
            return response

        return wrapper

    return decorator
