"""La primera pantalla precarga sus dos fuentes desde base.html, con la misma URL que pide la
hoja.
"""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_las_fuentes_de_la_primera_pantalla_se_precargan(client):
    """La fuente de titulares y la redonda de la serif se piden sin esperar a que el navegador
    lea el CSS y descubra que las necesita. La cursiva no: rara vez está en la primera pantalla,
    y una precarga que no se usa compite con lo que sí.

    La URL de la precarga debe ser la MISMA que resuelve el url() de la hoja (sin
    parámetro de versión); si difieren, el archivo se descarga dos veces. `crossorigin`
    es obligatorio en una precarga de fuente, aunque sea del mismo origen: sin él el
    navegador la descarta y vuelve a pedirla.
    """
    html = client.get(reverse("site:home")).content.decode()
    precargas = re.findall(r'<link rel="preload"[^>]*>', html)
    assert len(precargas) == 2, f"se esperaban dos precargas, hay {len(precargas)}"
    archivos = sorted(re.search(r'href="[^"?]*fonts/([^"?/]+)"', p).group(1) for p in precargas)
    assert [re.sub(r"\.[0-9a-f]{12}\.", ".", a) for a in archivos] == [
        "bricolage-grotesque.woff2",
        "rdv-serif.woff2",
    ]
    for etiqueta in precargas:
        assert 'as="font"' in etiqueta and 'type="font/woff2"' in etiqueta
        assert "crossorigin" in etiqueta
