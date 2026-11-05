"""`seed_demo` no puede dejar cuentas del panel que un tercero sepa abrir.

El comando crea contenido ficticio y dos CUENTAS DE STAFF; `editora` pertenece al grupo
`editor`. Con una contraseña conocida serían dos puertas al panel, y django-axes no frena a
quien acierta al primer intento. Por eso cada corrida les da una contraseña aleatoria, y el
comando, como todos los de desarrollo, solo corre con DEBUG y fuera de producción
(tests/test_dev_tools.py lo prueba para los cuatro).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_seed_demo_se_niega_a_correr_con_debug_apagado(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG está apagado"):
        call_command("seed_demo")
    assert not get_user_model().objects.filter(username="editora").exists()


def test_seed_demo_no_deja_una_contrasena_conocida(settings):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)
    editora = get_user_model().objects.get(username="editora")
    assert editora.is_staff
    assert not editora.check_password("demo12345"), "la contraseña publicada sigue activa"


def test_las_cuentas_demo_no_son_superusuarias(settings):
    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)
    usuarios = get_user_model().objects.filter(username__in=["editora", "autor1"])
    assert usuarios.count() == 2
    assert not any(u.is_superuser for u in usuarios)


def test_seed_demo_corre_sobre_base_limpia_y_es_idempotente(settings):
    """Regresión: el comando llevaba roto desde la migración media.0004 —`get_or_create`
    insertaba el registro de audio con file='' y embed_url='', violando la restricción
    `recording_file_or_embed`—. No lo cubría ninguna prueba porque nada lo ejecutaba.
    Se afirma además la idempotencia que el comando promete en su ayuda."""
    from apps.media.models import Recording

    settings.DEBUG = True
    call_command("seed_demo", verbosity=0)
    call_command("seed_demo", verbosity=0)

    audio = Recording.objects.get(slug="umbral-lectura")
    assert audio.file, "el registro de audio quedó sin archivo"
    assert Recording.objects.filter(slug="umbral-lectura").count() == 1
    assert get_user_model().objects.filter(username="editora").count() == 1
