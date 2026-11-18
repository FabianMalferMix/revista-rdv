"""Resolución de la IP real del cliente para los controles anti-abuso.

Punto único de verdad compartido por django-ratelimit (`RATELIMIT_IP_META_KEY`) y
django-axes (`AXES_CLIENT_IP_CALLABLE`), de modo que el rate-limit por IP y el
bloqueo antifuerza-bruta cuenten SIEMPRE por la misma IP, la del cliente: tras el proxy,
`REMOTE_ADDR` es la de Caddy, y contar por ella juntaría a todos los clientes en un solo
cubo.

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
    # El algoritmo «legacy» de django-ipware 8 (el de la 7): el «modern», el de por defecto,
    # salta las direcciones que no considera públicas, y entonces devolvería una entrada más
    # a la izquierda, la que puede inventar el cliente. Lo prueba
    # test_client_ip_uses_rightmost_forwarded_for_and_is_spoof_safe.
    ip, _ = get_client_ip(request, proxy_order="right-most", algorithm="legacy")
    return ip or request.META.get("REMOTE_ADDR", "")
