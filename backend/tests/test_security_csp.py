"""Auto-hospedaje de dependencias JS + CSP restrictiva (Lote F2-1)."""

import re

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.content.models import EditorialStatus
from config.csp import ContentSecurityPolicyMiddleware

CSP = "Content-Security-Policy"
CSP_RO = "Content-Security-Policy-Report-Only"


# ── Middleware (unitario, sin BD) ─────────────────────────────


def _mw(get_response=None):
    return ContentSecurityPolicyMiddleware(get_response or (lambda r: HttpResponse("ok")))


def test_sets_enforcing_header_by_default():
    resp = _mw()(RequestFactory().get("/"))
    assert CSP in resp and CSP_RO not in resp
    policy = resp[CSP]
    for directive in [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "frame-src 'self' https://www.youtube-nocookie.com https://player.vimeo.com",
    ]:
        assert directive in policy


def test_no_nonce_when_template_does_not_use_it():
    # Sin acceder a request.csp_nonce, la directiva no incluye nonce alguno.
    assert "'nonce-" not in _mw()(RequestFactory().get("/"))[CSP]


def test_nonce_appears_in_header_when_used_and_matches():
    holder = {}

    def get_response(request):
        holder["nonce"] = str(request.csp_nonce)  # simula el uso en plantilla
        return HttpResponse("ok")

    resp = _mw(get_response)(RequestFactory().get("/"))
    assert f"script-src 'self' 'nonce-{holder['nonce']}'" in resp[CSP]


def test_same_nonce_is_stable_within_request():
    seen = []

    def get_response(request):
        seen.append(str(request.csp_nonce))
        seen.append(str(request.csp_nonce))
        return HttpResponse("ok")

    _mw(get_response)(RequestFactory().get("/"))
    assert seen[0] == seen[1]


@override_settings(CSP_REPORT_ONLY=True)
def test_report_only_mode_uses_report_header():
    resp = _mw()(RequestFactory().get("/"))
    assert CSP_RO in resp and CSP not in resp


def test_does_not_override_upstream_policy():
    def get_response(request):
        r = HttpResponse("ok")
        r[CSP] = "default-src 'none'"
        return r

    assert _mw(get_response)(RequestFactory().get("/"))[CSP] == "default-src 'none'"


# ── Integración: self-host y cabecera en páginas reales ───────

pytestmark = pytest.mark.django_db


def test_home_carries_csp_and_selfhosts_htmx(client):
    resp = client.get(reverse("content:home"))
    assert resp.status_code == 200
    assert CSP in resp
    assert b"unpkg.com" not in resp.content
    assert b"cdn.jsdelivr" not in resp.content
    assert b"vendor/htmx/htmx.min.js" in resp.content


def test_article_detail_jsonld_carries_matching_nonce(client, make_article):
    article = make_article(slug="csp-art", title="Artículo CSP")
    article.status = EditorialStatus.PUBLISHED
    article.published_at = timezone.now()
    article.save()

    resp = client.get(reverse("content:article_detail", args=[article.slug]))
    assert resp.status_code == 200
    body = resp.content.decode()
    match = re.search(r'application/ld\+json" nonce="([^"]+)"', body)
    assert match, "el JSON-LD debe llevar nonce"
    assert f"'nonce-{match.group(1)}'" in resp[CSP]


def test_admin_article_add_selfhosts_tinymce(admin_client):
    resp = admin_client.get(reverse("admin:content_article_add"))
    assert resp.status_code == 200
    assert b"vendor/tinymce/tinymce.min.js" in resp.content
    assert b"cdn.jsdelivr" not in resp.content
    assert CSP in resp  # el panel editorial también va protegido


def test_permissions_policy_header_is_restrictive(client):
    """Se emite una Permissions-Policy restrictiva en las respuestas (hallazgo #16)."""
    resp = client.get(reverse("content:home"))
    pp = resp.get("Permissions-Policy", "")
    assert "geolocation=()" in pp
    assert "camera=()" in pp
    assert "microphone=()" in pp
    assert "payment=()" in pp
