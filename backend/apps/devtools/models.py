"""Lo que solo existe en las bases de desarrollo."""

from django.db import DatabaseError, models


class DevelopmentMarker(models.Model):
    """La marca de que esta base es de desarrollo.

    La crean `datos_de_desarrollo cargar`, `datos_de_desarrollo marcar` y `seed_demo` (solo con
    DEBUG), y `datos_de_desarrollo exportar` se niega a correr sin ella: una copia de producción
    restaurada en local no la tiene, y su contenido no debe acabar en el repositorio público.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "marca de base de desarrollo"
        verbose_name_plural = "marcas de base de desarrollo"

    def __str__(self):
        return f"Base de desarrollo desde el {self.created_at:%Y-%m-%d}"

    @classmethod
    def mark(cls):
        cls.objects.get_or_create(pk=1)

    @classmethod
    def is_marked(cls):
        try:
            return cls.objects.exists()
        except DatabaseError:
            # Sin la tabla, la base viene de otra parte (por ejemplo, de un respaldo).
            return False
