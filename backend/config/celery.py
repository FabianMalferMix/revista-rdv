import os

from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("resenas")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@setup_logging.connect
def use_django_logging(**kwargs):
    """Worker y beat escriben con el LOGGING de Django: JSON y redacción en producción.

    Sin un receptor de esta señal, Celery vacía los handlers del logger raíz y pone los
    suyos, en texto plano y sin el filtro que redacta los tokens.
    """
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
