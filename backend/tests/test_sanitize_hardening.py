"""Contrato del saneo de HTML autoral (hallazgo S-31 de XSS).

`clean_html` es lo único que separa el HTML que escribe un editor del `|safe` de las
plantillas de artículo y página. Funcionaba, pero NINGÚN test lo afirmaba: la protección
dependía por completo de los valores por defecto de nh3, que podrían cambiar con una
actualización sin que nada avisara. Estos tests fijan el contrato.
"""

import pytest

from apps.content.sanitize import ALLOWED_URL_SCHEMES, clean_html

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
    assert "href=" not in salida


def test_mailto_sigue_permitido():
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
def test_el_formulario_del_panel_tambien_sanea():
    """Defensa en profundidad: el saneo real vive en Model.save(), pero repetirlo en el
    formulario hace que el editor vea el resultado ya depurado al guardar."""
    from apps.content.admin import ArticleAdminForm

    form = ArticleAdminForm(
        data={
            "slug": "prueba",
            "title": "Prueba",
            "type": "resena",
            "status": "draft",
            "body": "<p>ok</p><script>alert(1)</script>",
        }
    )
    form.is_valid()  # dispara clean_body aunque otros campos falten
    assert "<script" not in form.cleaned_data.get("body", "")


@pytest.mark.django_db
def test_el_saneo_se_aplica_al_guardar_el_modelo():
    """La garantía de fondo: aunque se escriba por fuera del formulario."""
    from apps.content.models import Article

    art = Article.objects.create(
        slug="directo", title="Directo", body="<p>a</p><script>alert(1)</script>"
    )
    art.refresh_from_db()
    assert "<script" not in art.body
