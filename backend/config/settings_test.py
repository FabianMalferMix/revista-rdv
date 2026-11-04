"""Los ajustes de la suite: los de settings.py, con lo que las pruebas fijan a propósito."""

from django.template import TemplateSyntaxError

from .settings import *  # noqa: F403
from .settings import TEMPLATES

# Las pruebas entran con force_login; la del bloqueo del panel lo activa a propósito.
AXES_ENABLED = False
# Las tareas corren en el acto, y la excepción de una tarea llega a la prueba que la encoló.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True


class _FailOnInvalidVariable(str):
    """Una variable que no existe hace fallar la plantilla que la pinta: en producción se pinta
    vacía y en silencio."""

    def __mod__(self, variable):
        raise TemplateSyntaxError(f"La plantilla pinta una variable que no existe: «{variable}»")


TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = _FailOnInvalidVariable("%s")
