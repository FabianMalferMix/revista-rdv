"""Newsletter con doble opt-in + baja, y páginas legales (Lote F1-E)."""

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community.forms import SubscribeForm
from apps.community.models import NewsletterSubscriber
from apps.community.views import ALTA_NEUTRA

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _pending(email="a@example.com"):
    """Una suscripción pendiente de confirmar, con sus dos tokens."""
    return NewsletterSubscriber.objects.create(
        email=email, token="tok-baja", confirm_token="tok-confirma", confirm_token_at=timezone.now()
    )


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_sends_confirmation_with_link(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("community:subscribe"), {"email": "nuevo@example.com", "apodo": ""})
    sub = NewsletterSubscriber.objects.get(email="nuevo@example.com")
    # Dos tokens de vida distinta: el de baja es permanente, el de confirmación caduca.
    assert sub.status == S.PENDING and sub.token and sub.confirm_token
    assert len(mail.outbox) == 1
    assert reverse("community:confirm", args=[sub.confirm_token]) in mail.outbox[0].body
    assert reverse("community:unsubscribe", args=[sub.token]) in mail.outbox[0].body


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_confirmation_email_carries_list_unsubscribe_header():
    """El correo lleva la cabecera List-Unsubscribe (RFC 8058) con el enlace de baja,
    para que el cliente de correo ofrezca un botón de darse de baja."""
    from apps.community.tasks import send_confirmation_email

    sub = _pending()
    send_confirmation_email(sub.pk)
    unsub_url = f"{settings.SITE_URL}{reverse('community:unsubscribe', args=[sub.token])}"
    assert mail.outbox[0].extra_headers["List-Unsubscribe"] == f"<{unsub_url}>"


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_confirmation_email_task_sends_message():
    # El envío vive en una tarea Celery (fuera del hilo de la petición, con reintento).
    from apps.community.tasks import send_confirmation_email

    sub = _pending()
    send_confirmation_email(sub.pk)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["a@example.com"]
    confirm_url = f"{settings.SITE_URL}{reverse('community:confirm', args=[sub.confirm_token])}"
    assert confirm_url in mail.outbox[0].body


def test_confirm_sets_confirmed(client):
    # La confirmación muta por POST (S-16); el GET solo muestra el botón.
    NewsletterSubscriber.objects.create(
        email="x@example.com",
        token="tok-baja",
        confirm_token="tok-confirm",
        confirm_token_at=timezone.now(),
    )
    resp = client.post(reverse("community:confirm", args=["tok-confirm"]))
    assert resp.status_code == 200
    sub = NewsletterSubscriber.objects.get(email="x@example.com")
    assert sub.status == S.CONFIRMED and sub.confirmed_at is not None


def test_unsubscribe_sets_unsubscribed(client):
    NewsletterSubscriber.objects.create(email="y@example.com", token="tok-baja", status=S.CONFIRMED)
    resp = client.post(reverse("community:unsubscribe", args=["tok-baja"]))
    assert resp.status_code == 200
    sub = NewsletterSubscriber.objects.get(email="y@example.com")
    assert sub.status == S.UNSUBSCRIBED


def test_one_click_unsubscribe_skips_csrf():
    """Gmail y Outlook envían el POST de RFC 8058 sin sesión ni token CSRF: si la vista
    dejara de estar exenta, su botón de baja recibiría un 403. El cliente de pruebas no
    exige CSRF salvo que se le pida, y aquí se le pide."""
    NewsletterSubscriber.objects.create(
        email="w@example.com", token="tok-1clic", status=S.CONFIRMED
    )
    csrf_client = Client(enforce_csrf_checks=True)
    resp = csrf_client.post(
        reverse("community:unsubscribe", args=["tok-1clic"]),
        data="List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code == 200
    assert NewsletterSubscriber.objects.get(email="w@example.com").status == S.UNSUBSCRIBED
    # Control: el mismo cliente sí choca con el CSRF en un formulario que lo exige.
    resp = csrf_client.post(reverse("community:subscribe"), {"email": "v@example.com", "apodo": ""})
    assert resp.status_code == 403
    assert b"CSRF" in resp.content


def test_confirm_bad_token_404(client):
    assert client.get(reverse("community:confirm", args=["no-existe"])).status_code == 404


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_already_confirmed_not_reconfirmed(client, django_capture_on_commit_callbacks):
    NewsletterSubscriber.objects.create(email="z@example.com", status=S.CONFIRMED, token="t")
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("community:subscribe"), {"email": "z@example.com", "apodo": ""}, follow=True
        )
    assert ALTA_NEUTRA in resp.content.decode()  # control: la respuesta es la de siempre
    assert len(mail.outbox) == 0  # no reenvía a quien ya confirmó


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_honeypot_sends_no_mail(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("community:subscribe"), {"email": "bot@spam.com", "apodo": "bot"}, follow=True
        )
    assert ALTA_NEUTRA in resp.content.decode()  # control: el bot recibe la respuesta de siempre
    assert not NewsletterSubscriber.objects.filter(email="bot@spam.com").exists()
    assert len(mail.outbox) == 0


def test_subscribe_long_email_rejected_cleanly_not_500(client):
    """Un correo con formato válido pero de >254 caracteres se rechaza con error de
    validación, no revienta en un HTTP 500 (DataError) al insertarse (hallazgo #03)."""
    long_email = "a" * 250 + "@example.com"  # 262 caracteres, formato válido
    resp = client.post(reverse("community:subscribe"), {"email": long_email, "apodo": ""})
    assert resp.status_code == 200  # no 500
    assert not NewsletterSubscriber.objects.filter(email=long_email).exists()
    campo = BeautifulSoup(resp.content, "html.parser").select_one("#news-email")
    assert campo["aria-invalid"] == "true"


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_next_open_redirect_is_blocked(client):
    """Un `next` hacia un host externo se ignora: la redirección se queda en el
    sitio (evita el open redirect CWE-601, hallazgo #07)."""
    resp = client.post(
        reverse("community:subscribe"),
        {"email": "safe@example.com", "apodo": "", "next": "https://evil.example/phish"},
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp["Location"]
    assert resp["Location"] == reverse("content:home")


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_next_same_site_is_honored(client):
    """Un `next` a una ruta del propio sitio sí se respeta."""
    resp = client.post(
        reverse("community:subscribe"),
        {"email": "safe2@example.com", "apodo": "", "next": "/textos/"},
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/textos/"


@override_settings(EMAIL_BACKEND=LOCMEM)
@pytest.mark.parametrize("nxt", ["agenda", "//evil.com", "feed", ""])
def test_subscribe_with_a_bogus_next_returns_home(client, nxt):
    """Una palabra suelta en `next` era un nombre de vista para `redirect()`: «agenda» daba
    un 500 y «feed» llevaba a /feed/. Ahora todo lo que no es una ruta local lleva a la
    portada; el control de que una ruta local sí se respeta es la prueba anterior."""
    resp = client.post(
        reverse("community:subscribe"), {"email": "valido@example.com", "apodo": "", "next": nxt}
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("content:home")


@pytest.mark.parametrize("nxt", ["agenda", "//evil.com", "feed", ""])
def test_the_newsletter_page_also_sends_a_bogus_next_home(client, nxt):
    """Con un correo que no sirve, la página del boletín guarda adónde volver tras corregirlo:
    la misma regla, a la portada."""
    resp = client.post(
        reverse("community:subscribe"), {"email": "no-es-un-correo", "apodo": "", "next": nxt}
    )
    assert resp.status_code == 200
    volver = BeautifulSoup(resp.content, "html.parser").select_one('main input[name="next"]')
    assert volver["value"] == reverse("content:home")


def test_subscribe_degrades_gracefully_when_broker_is_down(client):
    """Si el broker está caído al encolar el correo, el alta NO revienta con 500: el
    suscriptor queda guardado y el fallo se registra (hallazgo: degradación Celery)."""
    from unittest import mock

    from kombu.exceptions import OperationalError

    from apps.community import views

    def enqueue_fail(*a, **k):
        raise OperationalError("broker inaccesible")

    with mock.patch.object(views.send_confirmation_email, "delay_on_commit", enqueue_fail):
        resp = client.post(
            reverse("community:subscribe"), {"email": "broker@example.com", "apodo": ""}
        )
    assert resp.status_code == 302  # redirección normal, no 500
    assert NewsletterSubscriber.objects.filter(email="broker@example.com").exists()


def test_email_task_declares_retry_policy():
    """La tarea de correo reintenta ante fallos transitorios de SMTP/red (política)."""
    import smtplib

    from apps.community.tasks import send_confirmation_email

    # SMTPException hereda de OSError: lo transitorio se reintenta, lo permanente no.
    assert issubclass(smtplib.SMTPException, OSError)
    assert OSError in send_confirmation_email.autoretry_for
    assert smtplib.SMTPRecipientsRefused in send_confirmation_email.dont_autoretry_for
    assert send_confirmation_email.retry_kwargs["max_retries"] == 8


def test_email_task_does_not_swallow_smtp_errors(monkeypatch):
    """Sin fail_silently: un fallo definitivo de SMTP se propaga (sube a Sentry) en vez
    de tragarse en silencio."""
    import smtplib

    from django.core.mail import EmailMessage

    from apps.community import tasks

    def boom(self, *a, **k):
        raise smtplib.SMTPException("smtp caído")

    monkeypatch.setattr(EmailMessage, "send", boom)
    with pytest.raises(smtplib.SMTPException):
        tasks.send_confirmation_email(_pending().pk)


def test_legal_pages_published(legal_pages):
    from django.test import Client

    c = Client()
    for slug in ["privacidad", "cookies", "terminos"]:
        assert c.get(reverse("content:page_detail", args=[slug])).status_code == 200


def test_footer_has_legal_links_and_consent(client):
    content = client.get(reverse("content:home")).content
    assert reverse("content:page_detail", args=["privacidad"]).encode() in content
    assert reverse("content:page_detail", args=["cookies"]).encode() in content
    assert b"pol\xc3\xadtica de privacidad" in content  # nota de consentimiento del form


def test_privacy_page_cites_ley_21719(client, legal_pages):
    # La política actualizada cita la Ley 21.719 (además de la 19.628).
    resp = client.get(reverse("content:page_detail", args=["privacidad"]))
    assert resp.status_code == 200
    assert b"21.719" in resp.content
    assert b"19.628" in resp.content


# ── El formulario, desde SubscribeForm: en el pie y en la página del boletín ────────


def test_the_footer_paints_the_subscribe_form(client):
    """El pie se pinta desde SubscribeForm: sus campos, el correo con su propósito declarado
    (`autocomplete`, WCAG 1.3.5) y descrito por el texto de consentimiento."""
    sopa = BeautifulSoup(client.get(reverse("content:text_archive")).content, "html.parser")
    form = sopa.select_one("footer form.newsletter")
    assert form["action"] == reverse("community:subscribe")
    nombres = {campo["name"] for campo in form.select("input")}
    assert nombres == {"csrfmiddlewaretoken", "next", *SubscribeForm().fields}
    correo = form.select_one('input[name="email"]')
    assert correo["type"] == "email" and correo["autocomplete"] == "email"
    etiqueta = form.select_one(f'label[for="{correo["id"]}"]')
    assert etiqueta.get_text() == "Novedades para prensa y gestores:"
    assert "política de privacidad" in form.select_one(f"#{correo['aria-describedby']}").get_text()
    trampa = form.select_one('input[name="apodo"]')
    assert trampa["type"] == "text" and "hp" in trampa["class"]
    assert trampa["tabindex"] == "-1" and trampa["aria-hidden"] == "true"


def test_an_invalid_email_comes_back_to_its_field_with_the_error(client):
    """El aviso arriba de la página de vuelta quedaba lejos del campo, «Saltar al contenido» se
    lo saltaba y lo escrito se perdía. Responde la página del boletín: el mismo formulario,
    en el contenido, con lo escrito, el error junto al campo y el foco en él."""
    resp = client.post(
        reverse("community:subscribe"), {"email": "ana@correo", "apodo": "", "next": "/textos/"}
    )
    assert resp.status_code == 200
    sopa = BeautifulSoup(resp.content, "html.parser")
    campos = sopa.select("#news-email")
    assert len(campos) == 1, "el pie repite el formulario"
    correo = campos[0]
    assert correo.find_parent("main") is not None
    assert correo["value"] == "ana@correo" and correo["aria-invalid"] == "true"
    assert correo.has_attr("autofocus")
    error, consentimiento = (sopa.select_one(f"#{i}") for i in correo["aria-describedby"].split())
    assert error.find_parent("form") is correo.find_parent("form")
    assert error.get_text(strip=True) == "Revisa el correo ingresado."
    assert "política de privacidad" in consentimiento.get_text()
    assert sopa.select_one('main input[name="next"]')["value"] == "/textos/"
    assert not sopa.select(".mensajes")
    assert not NewsletterSubscriber.objects.exists()
