"""Newsletter con doble opt-in + baja, y el formulario de alta."""

from unittest import mock

import pytest
from bs4 import BeautifulSoup
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.community.forms import SubscribeForm
from apps.community.models import NewsletterSubscriber
from apps.community.tasks import send_confirmation_email
from apps.community.views import ALTA_NEUTRA

pytestmark = pytest.mark.django_db
S = NewsletterSubscriber.Status
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_subscribe_sends_confirmation_with_link(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("community:subscribe"), {"email": "nuevo@example.com", "apodo": ""}
        )
    assert resp.status_code == 302
    sub = NewsletterSubscriber.objects.get(email="nuevo@example.com")
    # Dos tokens de vida distinta: el de baja es permanente, el de confirmación caduca.
    assert sub.status == S.PENDING and sub.token and sub.confirm_token
    assert len(mail.outbox) == 1
    assert reverse("community:confirm", args=[sub.confirm_token]) in mail.outbox[0].body
    assert reverse("community:unsubscribe", args=[sub.token]) in mail.outbox[0].body


def test_confirm_sets_confirmed(client):
    # La confirmación muta por POST; el GET solo muestra el botón.
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


@override_settings(EMAIL_BACKEND=LOCMEM)
def test_already_confirmed_not_reconfirmed(client, django_capture_on_commit_callbacks):
    NewsletterSubscriber.objects.create(email="z@example.com", status=S.CONFIRMED, token="t")
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("community:subscribe"), {"email": "z@example.com", "apodo": ""}, follow=True
        )
    assert ALTA_NEUTRA in resp.content.decode()  # control: la respuesta es la de siempre
    assert len(mail.outbox) == 0  # no reenvía a quien ya confirmó


def test_subscribe_long_email_rejected_cleanly_not_500(client):
    """Un correo con formato válido pero de >254 caracteres se rechaza con error de
    validación, no revienta en un HTTP 500 (DataError) al insertarse."""
    long_email = "a" * 250 + "@example.com"  # 262 caracteres, formato válido
    resp = client.post(reverse("community:subscribe"), {"email": long_email, "apodo": ""})
    assert resp.status_code == 200  # no 500
    assert not NewsletterSubscriber.objects.filter(email=long_email).exists()
    campo = BeautifulSoup(resp.content, "html.parser").select_one("#news-email")
    assert campo["aria-invalid"] == "true"


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
@pytest.mark.parametrize("nxt", ["agenda", "//evil.com", "https://evil.example/phish", "feed", ""])
def test_subscribe_with_a_bogus_next_returns_home(client, nxt):
    """Todo lo que no es una ruta local lleva a la portada, también una palabra suelta, que
    `redirect()` tomaría por un nombre de vista («agenda» daría un 500 y «feed» llevaría a
    /feed/). El control de que una ruta local sí se respeta es la prueba anterior."""
    resp = client.post(
        reverse("community:subscribe"), {"email": "valido@example.com", "apodo": "", "next": nxt}
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("site:home")


@pytest.mark.parametrize("nxt", ["agenda", "//evil.com", "feed", ""])
def test_the_newsletter_page_also_sends_a_bogus_next_home(client, nxt):
    """Con un correo que no sirve, la página del boletín guarda adónde volver tras corregirlo:
    la misma regla, a la portada."""
    resp = client.post(
        reverse("community:subscribe"), {"email": "no-es-un-correo", "apodo": "", "next": nxt}
    )
    assert resp.status_code == 200
    volver = BeautifulSoup(resp.content, "html.parser").select_one('main input[name="next"]')
    assert volver["value"] == reverse("site:home")


def test_subscribe_degrades_gracefully_when_broker_is_down(client):
    """Si el broker está caído al encolar el correo, el alta NO revienta con 500: el
    suscriptor queda guardado y el fallo se registra."""
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


def test_the_confirmation_task_receives_only_the_subscriber_id(client, editor):
    """El correo y los tokens no viajan por el broker ni quedan en los argumentos que Celery
    escribe en el log: la tarea recibe el id, se encole desde el sitio o desde el panel (el alta
    a mano y el reenvío)."""
    panel = reverse("admin:community_newslettersubscriber_changelist")
    with mock.patch.object(send_confirmation_email, "delay_on_commit") as enqueue:
        client.post(reverse("community:subscribe"), {"email": "ana@example.com", "apodo": ""})
        client.force_login(editor)
        client.post(
            reverse("admin:community_newslettersubscriber_add"), {"email": "berta@example.com"}
        )
        ana = NewsletterSubscriber.objects.get(email="ana@example.com")
        client.post(panel, {"action": "do_resend", "_selected_action": [ana.pk]})
    berta = NewsletterSubscriber.objects.get(email="berta@example.com")
    assert enqueue.call_args_list == [mock.call(ana.pk), mock.call(berta.pk), mock.call(ana.pk)]


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
    """Un correo que no sirve vuelve a su campo: responde la página del boletín, con el mismo
    formulario en el contenido, lo escrito, el error junto al campo y el foco en él, y sin un
    aviso arriba de la página, que quedaría lejos del campo y que «Saltar al contenido» se
    saltaría."""
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
