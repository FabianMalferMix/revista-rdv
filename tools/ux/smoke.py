#!/usr/bin/env python3
"""Humo de rutas: recorre los enlaces internos del sitio y comprueba que respondan.

    python3 tools/ux/smoke.py [http://localhost:8000]

Parte de la portada y sigue los enlaces internos hasta dos saltos. Falla (código 1) si
alguna ruta responde 400 o más. Un 301/302 cuenta como correcto: `/colaborador/<slug>/`
redirige a propósito cuando esa persona es integrante. Solo biblioteca estándar.
"""

import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urldefrag, urljoin, urlparse

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OMITIR = ("/admin", "/static/", "/media/", "/enviar/gracias")
SALTOS = 2
TOPE = 400


class SinRedirigir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


ABRIR = urllib.request.build_opener(SinRedirigir)


def pedir(url):
    try:
        with ABRIR.open(url, timeout=20) as r:
            tipo = r.headers.get("Content-Type", "")
            cuerpo = r.read().decode("utf-8", "replace") if "html" in tipo else ""
            return r.status, cuerpo
    except urllib.error.HTTPError as e:
        return e.code, ""
    except OSError as e:
        return f"error: {e}", ""


def enlaces(html, origen):
    for href in re.findall(r'href="([^"]+)"', html):
        url = urldefrag(urljoin(origen, href))[0]
        partes = urlparse(url)
        if partes.netloc != urlparse(BASE).netloc or partes.query:
            continue
        if any(partes.path.startswith(p) for p in OMITIR):
            continue
        yield url


def main():
    vistos, cola, fallos = {}, [(BASE + "/", 0)], []
    while cola and len(vistos) < TOPE:
        url, salto = cola.pop(0)
        if url in vistos:
            continue
        estado, html = pedir(url)
        vistos[url] = estado
        if not isinstance(estado, int) or estado >= 400:
            fallos.append((url, estado))
        if html and salto < SALTOS:
            cola.extend((u, salto + 1) for u in enlaces(html, url) if u not in vistos)
    redirigen = sum(1 for e in vistos.values() if e in (301, 302))
    print(f"{len(vistos)} rutas: {len(vistos) - len(fallos) - redirigen} con 200, {redirigen} redirigen, {len(fallos)} fallan")
    for url, estado in fallos:
        print(f"  FALLA {estado}  {url}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
