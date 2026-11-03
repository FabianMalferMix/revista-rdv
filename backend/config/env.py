"""Lectura de las variables de entorno con un solo criterio.

Todas las lecturas de `settings.py` pasan por aquí. Un valor que no se entiende detiene
el arranque con un error que nombra la variable, en vez de convertirse en silencio en
otro valor: antes, `AXES_ENABLED=true` apagaba el bloqueo del panel porque solo «1»
contaba como verdadero.

Una variable vacía (`EMAIL_PORT=`, como las deja la plantilla) vale lo mismo que una
ausente: se usa el valor por defecto.
"""

import os

from django.core.exceptions import ImproperlyConfigured

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _raw(name, environ):
    """El valor de la variable, o None si falta o está vacía."""
    value = (os.environ if environ is None else environ).get(name)
    if value is None or not value.strip():
        return None
    return value


def env_str(name, default="", environ=None):
    """Texto tal cual (sin recortar: puede ser una contraseña)."""
    value = _raw(name, environ)
    return default if value is None else value


def env_bool(name, default, environ=None):
    """1, true, yes u on y 0, false, no u off, sin distinguir mayúsculas."""
    value = _raw(name, environ)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(
        f"{name}={value!r} no es un valor de sí o no: usa 1 o 0, true o false, yes o no, on u off."
    )


def env_int(name, default, environ=None):
    value = _raw(name, environ)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        raise ImproperlyConfigured(f"{name}={value!r} no es un número entero.") from None


def env_float(name, default, environ=None):
    value = _raw(name, environ)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        raise ImproperlyConfigured(f"{name}={value!r} no es un número.") from None


def env_list(name, default="", environ=None):
    """Lista separada por comas, sin espacios alrededor ni elementos vacíos. El valor por
    defecto se escribe como se escribiría la variable."""
    value = _raw(name, environ)
    raw = default if value is None else value
    return [item.strip() for item in raw.split(",") if item.strip()]
