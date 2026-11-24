"""El contrato del saneo de HTML de autor.

`clean_html` es lo único que separa el HTML que escribe un editor de la página: lo aplican el
guardado y el filtro `authored_html`, que pinta los textos y las páginas. Estas pruebas fijan el
contrato, para que no dependa de los valores por defecto de nh3, que podrían cambiar con una
actualización sin que nada avisara.
"""

import pytest
from django.urls import reverse

from apps.content.sanitize import ALLOWED_URL_SCHEMES, clean_html
from tests.factories import admin_form_fields, make_article

# Vectores clásicos: si alguno sobrevive, hay XSS almacenado en artículos y páginas.
VECTORES = [
    ('<a href="javascript:alert(1)">x</a>', "javascript:"),
    ('<a href="JaVaScRiPt:alert(1)">x</a>', "javascript:"),
    ('<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>', "data:"),
    ('<a href="vbscript:msgbox(1)">x</a>', "vbscript:"),
    ('<img src="x" onerror="alert(1)">', "onerror"),
    ('<div onmouseover="alert(1)">x</div>', "onmouseover"),
    ('<body onload="alert(1)">', "onload"),
    ('<iframe src="https://evil.example"></iframe>', "<iframe"),
    ("<svg><script>alert(1)</script></svg>", "<script"),
    ("<math><mtext><script>alert(1)</script></mtext></math>", "<script"),
    ('<form action="https://evil.example"><input name="x"></form>', "<form"),
    ("<script>alert(1)</script>", "<script"),
    ('<style>body{background:url("javascript:alert(1)")}</style>', "<style"),
    ('<object data="evil.swf"></object>', "<object"),
    ('<embed src="evil.swf">', "<embed"),
    ('<a href="#" style="position:fixed;inset:0">secuestro</a>', "style="),
]


@pytest.mark.parametrize(("entrada", "prohibido"), VECTORES)
def test_el_saneo_elimina_los_vectores_peligrosos(entrada, prohibido):
    salida = clean_html(entrada)
    assert prohibido.lower() not in salida.lower(), f"sobrevivió {prohibido!r} en {salida!r}"


def test_los_enlaces_legitimos_sobreviven():
    """El saneo no puede ser tan agresivo que rompa el contenido real."""
    salida = clean_html('<p>Ver <a href="https://ejemplo.cl/obra" title="Obra">la obra</a>.</p>')
    assert 'href="https://ejemplo.cl/obra"' in salida
    assert "<p>" in salida and "</p>" in salida


def test_los_esquemas_permitidos_son_explicitos():
    """Fijados a mano y no heredados: el default de nh3 admite 25 esquemas —ssh, magnet,
    bitcoin, sms, wtai…— que este sitio no necesita, y podría cambiar entre versiones."""
    assert ALLOWED_URL_SCHEMES == {"http", "https", "mailto"}


@pytest.mark.parametrize("esquema", ["ssh://host/x", "magnet:?xt=urn:btih:abc", "sms:+56900000"])
def test_los_esquemas_exoticos_se_descartan(esquema):
    salida = clean_html(f'<a href="{esquema}">x</a>')
    assert "x</a>" in salida  # control: el enlace queda, sin su destino
    assert "href=" not in salida


def test_mailto_links_are_allowed():
    salida = clean_html('<a href="mailto:hola@ejemplo.cl">escríbenos</a>')
    assert "mailto:hola@ejemplo.cl" in salida


def test_el_saneo_es_idempotente():
    sucio = '<p>Hola<script>alert(1)</script> <a href="https://x">y</a></p>'
    una = clean_html(sucio)
    assert clean_html(una) == una


def test_los_enlaces_salen_con_rel_defensivo():
    salida = clean_html('<a href="https://externo.example">x</a>')
    for token in ("nofollow", "noopener", "noreferrer"):
        assert token in salida


@pytest.mark.django_db
@pytest.mark.parametrize("model", ["article", "page"])
def test_what_the_panel_saves_comes_out_clean(client, editor, model):
    """Lo que un editor guarda desde el panel, en un texto o en una página, queda saneado: el
    texto permitido sigue y el guion, con lo que traía, no."""
    from apps.content.models import Page

    if model == "article":
        item = make_article(slug="desde-el-panel")
    else:
        item = Page.objects.create(slug="desde-el-panel", title="Desde el panel", body="<p>x</p>")
    url = reverse(f"admin:content_{model}_change", args=[item.pk])
    client.force_login(editor)
    data = admin_form_fields(client.get(url).content, f"{model}_form")
    data["body"] = "<p>ok</p><script>alert(1)</script>"
    assert client.post(url, data).status_code == 302, "control: el panel guardó"
    item.refresh_from_db()
    assert "<p>ok</p>" in item.body
    assert "<script" not in item.body and "alert" not in item.body


@pytest.mark.django_db
def test_el_saneo_se_aplica_al_guardar_el_modelo():
    """El modelo sanea el cuerpo al guardarlo, aunque se escriba por fuera del formulario."""
    from apps.content.models import Article

    art = Article.objects.create(
        slug="directo", title="Directo", body="<p>a</p><script>alert(1)</script>"
    )
    art.refresh_from_db()
    assert "<p>a</p>" in art.body  # control: el texto permitido queda
    assert "<script" not in art.body
    assert "alert" not in art.body  # el contenido del script también se elimina


@pytest.mark.django_db
def test_sanitizer_keeps_allowed_formatting():
    article = make_article(
        body='<p><strong>Negrita</strong> y <a href="https://x.cl">enlace</a>.</p>'
    )
    assert "<strong>Negrita</strong>" in article.body
    assert 'href="https://x.cl"' in article.body


def test_clean_html_passes_through_empty_input():
    """clean_html devuelve la entrada tal cual cuando es vacía o None (no llama a nh3)."""
    assert clean_html("") == ""
    assert clean_html(None) is None
