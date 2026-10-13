"""Pie de entidad: las salidas al final de cada ficha.

Cada ficha terminaba en seco: leído el poema, la única salida era la navegación de
arriba. El pie ofrece adónde ir después —el índice, quien lo firma, lo que viene antes y
después— como una lista de puertas que la vista arma y la parcial
`content/partials/_pie_de_entidad.html` dibuja.
"""


def puerta(rotulo, texto, url):
    """Una salida: un rótulo que dice qué es («Más de», «Índice») y el destino."""
    return {"rotulo": rotulo, "texto": texto, "url": url}


def firmas(personas):
    """Una puerta por cada persona que firma, hacia su página."""
    return [puerta("Más de", p.display_name, p.get_absolute_url()) for p in personas]


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


def puertas_vecinas(anterior, siguiente, nombre, titulo=lambda o: str(o)):
    """Las puertas «{nombre} anterior» y «{nombre} siguiente», las que haya."""
    puertas = []
    if anterior:
        puertas.append(puerta(f"{nombre} anterior", titulo(anterior), anterior.get_absolute_url()))
    if siguiente:
        puertas.append(
            puerta(f"{nombre} siguiente", titulo(siguiente), siguiente.get_absolute_url())
        )
    return puertas


def vecinos(queryset, objeto, campo="published_at"):
    """(anterior, siguiente) en el orden del índice, que va del más reciente al más antiguo.

    «Siguiente» es el que viene después en la lista, es decir, el anterior en el tiempo.
    El desempate por clave primaria evita saltarse dos piezas con la misma fecha.
    """
    from django.db.models import Q

    valor = getattr(objeto, campo)
    if valor is None:
        return None, None
    antes = Q(**{f"{campo}__lt": valor}) | Q(**{campo: valor, "pk__lt": objeto.pk})
    despues = Q(**{f"{campo}__gt": valor}) | Q(**{campo: valor, "pk__gt": objeto.pk})
    siguiente = queryset.filter(antes).order_by(f"-{campo}", "-pk").first()
    anterior = queryset.filter(despues).order_by(campo, "pk").first()
    return anterior, siguiente
