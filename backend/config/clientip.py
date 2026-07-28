"""Resolución de la IP real del cliente para los controles anti-abuso.

Punto único de verdad compartido por django-ratelimit (`RATELIMIT_IP_META_KEY`) y
django-axes (`AXES_CLIENT_IP_CALLABLE`), de modo que el rate-limit por IP y el
bloqueo antifuerza-bruta cuenten SIEMPRE por la misma IP. Que divergieran era el
hallazgo #01 de la auditoría de QA (rate-limit colapsado en un cubo global tras el
proxy).

En producción `web` solo es accesible a través de Caddy —el único proxy de
confianza, en el borde—, que AÑADE la IP real del cliente al final de la cabecera
`X-Forwarded-For`. Cualquier valor anterior lo suministra el cliente y no es de
fiar, así que tomamos la entrada más a la derecha (`proxy_order='right-most'`): es
a prueba de spoofing, un `X-Forwarded-For` inyectado por el cliente queda a la
izquierda y se ignora. Sin cabecera (desarrollo/local o conexión directa) se cae a
`REMOTE_ADDR`.

Asume que Caddy es el borde. Si en el futuro se antepone un CDN o balanceador,
habrá que revisar cuántos proxies de confianza hay delante.
"""

from ipware import get_client_ip


def client_ip(request):
    ip, _ = get_client_ip(request, proxy_order="right-most")
    return ip or request.META.get("REMOTE_ADDR", "")
