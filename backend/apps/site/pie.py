"""Pie de entidad: las vecinas de cada ficha, lo que viene antes y después en su índice.

Las salidas al final de una ficha —el índice, quien la firma, lo que viene antes y después—
salen de dos sitios: la vista busca aquí las vecinas, que son consultas, y se las pasa a la
plantilla; las etiquetas de `templatetags/pie.py` arman las puertas con sus rótulos, y las
dibuja la parcial `partials/_pie_de_entidad.html`.
"""

from django.db.models import Q


def vecinos_en_lista(queryset, objeto):
    """(anterior, siguiente) en el orden de un índice que no va por fecha: el colectivo,
    el catálogo, los registros. Son listas cortas: se leen las claves en orden (una
    consulta) y se traen los dos vecinos (otra)."""
    claves = list(queryset.values_list("pk", flat=True))
    if objeto.pk not in claves:
        return None, None
    i = claves.index(objeto.pk)
    anterior = claves[i - 1] if i > 0 else None
    siguiente = claves[i + 1] if i + 1 < len(claves) else None
    encontrados = queryset.model.objects.in_bulk([k for k in (anterior, siguiente) if k])
    return encontrados.get(anterior), encontrados.get(siguiente)


def vecinos(queryset, objeto, campo="published_at"):
    """(anterior, siguiente) en el orden del índice, que va del más reciente al más antiguo.

    «Siguiente» es el que viene después en la lista, es decir, el anterior en el tiempo.
    El desempate por clave primaria evita saltarse dos piezas con la misma fecha.
    """
    valor = getattr(objeto, campo)
    if valor is None:
        return None, None
    antes = Q(**{f"{campo}__lt": valor}) | Q(**{campo: valor, "pk__lt": objeto.pk})
    despues = Q(**{f"{campo}__gt": valor}) | Q(**{campo: valor, "pk__gt": objeto.pk})
    siguiente = queryset.filter(antes).order_by(f"-{campo}", "-pk").first()
    anterior = queryset.filter(despues).order_by(campo, "pk").first()
    return anterior, siguiente
