"""La clase base de los comandos de desarrollo, con su única guarda."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# El valor de DJANGO_ENVIRONMENT con que docker-compose.prod.yml declara la producción.
PRODUCTION = "production"


class DevelopmentCommand(BaseCommand):
    """Un comando que siembra contenido ficticio, copia la base o rehace archivos del repositorio
    desde sus fuentes: solo corre en desarrollo.

    La guarda está en `execute`, por donde pasan `manage.py` y `call_command` antes de llegar a
    `handle`: exige DEBUG y un entorno que no se declare de producción. Ninguna opción la salta.
    """

    def create_parser(self, prog_name, subcommand, **kwargs):
        # argparse acepta un prefijo de una opción larga como la opción entera: sin esto,
        # `--force` valdría por `--force-color` y el comando correría.
        kwargs.setdefault("allow_abbrev", False)
        return super().create_parser(prog_name, subcommand, **kwargs)

    def execute(self, *args, **options):
        name = type(self).__module__.rsplit(".", 1)[-1]
        if not settings.DEBUG:
            raise CommandError(
                f"{name} es una herramienta de desarrollo y aquí DEBUG está apagado: no corre."
            )
        if settings.ENVIRONMENT == PRODUCTION:
            raise CommandError(
                f"{name} es una herramienta de desarrollo y este entorno se declara de producción "
                f"(DJANGO_ENVIRONMENT={PRODUCTION}): no corre, aunque DEBUG esté encendido."
            )
        return super().execute(*args, **options)
