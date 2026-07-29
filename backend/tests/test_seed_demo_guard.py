"""`seed_demo` no debe poder correr contra producción (hallazgo S-03).

El comando crea contenido ficticio y, sobre todo, CUENTAS DE STAFF. Antes no
comprobaba `DEBUG` y fijaba la contraseña `demo12345`, publicada en el repositorio:
dos cuentas de panel utilizables por cualquiera que leyese el código. Como `editora`
pertenece al grupo `editor`, encadenaba con S-01 hasta superusuario, y django-axes no
aportaba defensa alguna porque la contraseña era *conocida* (basta un intento).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

pytestmark = pytest.mark.django_db


@override_settings(DEBUG=False)
def test_seed_demo_se_niega_a_correr_con_debug_apagado():
    with pytest.raises(CommandError, match="producción"):
        call_command("seed_demo")
    assert not get_user_model().objects.filter(username="editora").exists()


@override_settings(DEBUG=False)
def test_seed_demo_exige_force_explicito_y_no_deja_contrasena_conocida():
    """Con --force sí corre (entornos de staging), pero sin contraseña fija."""
    call_command("seed_demo", "--force", verbosity=0)
    editora = get_user_model().objects.get(username="editora")
    assert editora.is_staff
    assert not editora.check_password("demo12345"), "la contraseña publicada sigue activa"


@override_settings(DEBUG=False)
def test_las_cuentas_demo_no_son_superusuarias():
    call_command("seed_demo", "--force", verbosity=0)
    usuarios = get_user_model().objects.filter(username__in=["editora", "autor1"])
    assert usuarios.count() == 2
    assert not any(u.is_superuser for u in usuarios)


@override_settings(DEBUG=False)
def test_seed_demo_corre_sobre_base_limpia_y_es_idempotente():
    """Regresión: el comando llevaba roto desde la migración media.0004 —`get_or_create`
    insertaba el registro de audio con file='' y embed_url='', violando la restricción
    `recording_file_or_embed`—. No lo cubría ninguna prueba porque nada lo ejecutaba.
    Se afirma además la idempotencia que el comando promete en su ayuda."""
    from apps.media.models import Recording

    call_command("seed_demo", "--force", verbosity=0)
    call_command("seed_demo", "--force", verbosity=0)

    audio = Recording.objects.get(slug="umbral-lectura")
    assert audio.file, "el registro de audio quedó sin archivo"
    assert Recording.objects.filter(slug="umbral-lectura").count() == 1
    assert get_user_model().objects.filter(username="editora").count() == 1
