"""Backends de correo para las pruebas, en un módulo propio: Django los importa por su ruta,
y así el estado que fija la prueba es el mismo que ve el envío."""

from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend

# Los errores de los próximos envíos, uno por envío y en orden; con la lista vacía, entrega.
failures = []


class FlakyBackend(BaseEmailBackend):
    calls = 0

    def send_messages(self, messages):
        FlakyBackend.calls += 1
        if failures:
            raise failures.pop(0)
        mail.outbox.extend(messages)
        return len(messages)
