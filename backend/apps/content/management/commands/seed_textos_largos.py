"""Textos y poemas largos, cercanos a los reales, para probar las vistas de lectura.

Seis textos y cinco poemas, con libros y autores inventados:

- una reseña larga, con subtítulos, citas de poemas y una nota al pie;
- un ensayo muy largo a dos firmas, con subtítulos de dos niveles, listas, una partitura
  preformateada, una figura con imagen del sitio, código y notas con direcciones larguísimas;
- una entrevista de preguntas y respuestas;
- una crónica con el programa de la lectura y una cita;
- una crítica con los casos límite: un título de 190 letras, una bajada larga, cuatro firmas,
  ocho etiquetas, palabras de más de treinta letras, una dirección web de doscientos
  caracteres sin espacios, un correo larguísimo, un bloque preformateado ancho y una cita con
  una lista dentro;
- una reseña breve de dos libros, con títulos y editoriales largos;
- una letanía de unos 110 versos con epígrafe, un poema en prosa a cuatro manos, una oda de
  versos que no caben en una línea, un poema escalonado con sangrías y uno breve de título
  larguísimo.

Todo lo que crea lleva el prefijo `zz-largo-` en el slug, para encontrarlo y borrarlo:

    python manage.py seed_textos_largos            # siembra (o pone al día) los once
    python manage.py seed_textos_largos --borrar   # los borra, con lo que creó para ellos

Las firmas son integrantes del colectivo si existen (por su slug); si no, firmas invitadas que
el comando crea y después borra. Las fechas de publicación son recientes, así que los textos y
los poemas aparecen arriba en los índices y en la portada. Con DEBUG=0 exige --force: es
contenido de prueba.
"""

import re
import unicodedata
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.agenda.models import EventPhoto
from apps.content.models import (
    Article,
    ArticleContributor,
    ArticleType,
    EditorialStatus,
    Poem,
    PoemContributor,
    ReviewedWork,
    Section,
    Tag,
)
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work

DIRECTORIO = Path(__file__).resolve().parent / "textos_largos"
PREFIJO = "zz-largo-"

# Firmas: el slug de una integrante y el nombre con que se crea si no existe.
FERNANDA = ("fernanda-soto", "Fernanda Soto")
ANDRES = ("andres-caceres", "Andrés Cáceres")
PAULA = ("paula-miranda", "Paula Miranda")
CAMILA = ("relleno-0", "Camila Reyes")
TOMAS = ("relleno-1", "Tomás Figueroa")
JAVIERA = ("relleno-2", "Javiera Núñez")
MATIAS = ("relleno-3", "Matías Olivares")
ANTONIA = ("relleno-4", "Antonia Vergara")
ROCIO = ("relleno-6", "Rocío Carrasco")
FELIPE = ("relleno-7", "Felipe Astorga")
VALENTINA = ("relleno-8", "Valentina Aguirre")

TEXTOS = (
    {
        "slug": "la-casa-como-lengua-extranjera",
        "archivo": "resena-inventario.html",
        "titulo": "La casa como lengua extranjera",
        "bajada": "Inventario de lo que no se dijo, el primer libro de Marta Ilabaca, convierte "
        "una mudanza familiar en una gramática del silencio. Una lectura lenta de sus cinco "
        "secciones.",
        "tipo": ArticleType.RESENA,
        "seccion": "resenas",
        "etiquetas": ("poesía chilena", "memoria", "primeros libros"),
        "firmas": (FERNANDA,),
        "obras": (
            {
                "titulo": "Inventario de lo que no se dijo",
                "autores": ("Marta Ilabaca",),
                "editorial": "Ediciones Pájaro de Cemento",
                "anio": 2025,
            },
        ),
        "horas": 50,
    },
    {
        "slug": "repetir-el-verso",
        "archivo": "ensayo-repetir.html",
        "titulo": "Repetir el verso: notas sobre la lectura en voz alta, la memoria y el error",
        "bajada": "Un colectivo que se llama Repitentes del Verso tendría que explicar alguna "
        "vez por qué repetir no es fracasar. Este ensayo lo intenta en siete movimientos y una "
        "partitura.",
        "tipo": ArticleType.ENSAYO,
        "seccion": "ensayos",
        "etiquetas": ("lectura en voz alta", "oralidad", "memoria", "colectivos"),
        "firmas": (ANDRES, PAULA),
        "imagen_de_portada": 0,
        "horas": 26,
    },
    {
        "slug": "escribir-es-volver-a-oir",
        "archivo": "entrevista-bravo.html",
        "titulo": "«Escribir es volver a oír»: conversación con Ignacio Bravo",
        "bajada": "Llegó al colectivo por una puerta equivocada y hoy coordina el taller de los "
        "jueves y la gestión. Hablamos de talleres, de fondos públicos, de su padre electricista "
        "y de las salas donde se lee.",
        "tipo": ArticleType.ENTREVISTA,
        "seccion": "entrevistas",
        "etiquetas": ("talleres", "gestión cultural"),
        "firmas": (VALENTINA,),
        "horas": 74,
    },
    {
        "slug": "doce-sillas-y-un-paraguas",
        "archivo": "cronica-yungay.html",
        "titulo": "Doce sillas y un paraguas: crónica de una lectura bajo la lluvia en el "
        "Barrio Yungay",
        "bajada": "Treinta y dos personas bajo un alero, un micrófono que funcionaba a ratos y "
        "un poema cuya última estrofa la escribió la lluvia.",
        "tipo": ArticleType.NOTA,
        "seccion": "cronica",
        "etiquetas": ("crónica", "lecturas"),
        "firmas": (FELIPE,),
        "imagen_de_portada": 1,
        "horas": 98,
    },
    {
        "slug": "contra-la-lectura-apurada",
        "archivo": "critica-relectura.html",
        "titulo": "Contra la lectura apurada, a favor de la relectura obstinada: once "
        "objeciones (y una concesión) a la costumbre de juzgar un libro de poemas por su primer "
        "verso, su contratapa y su número de seguidores",
        "bajada": "Una discusión del taller de los jueves que duró más de lo razonable, escrita "
        "a ocho manos: por qué el primer verso dice menos de lo que creemos, por qué la "
        "relectura es donde ocurre la poesía, y una concesión para quien abandona libros "
        "sin culpa.",
        "tipo": ArticleType.CRITICA,
        "seccion": "ensayos",
        "etiquetas": (
            "relectura",
            "redes sociales",
            "mercado editorial",
            "oficio",
            "polémica",
            "poesía contemporánea",
            "talleres",
            "lecturas",
        ),
        "firmas": (ROCIO, MATIAS, ANTONIA, TOMAS),
        "horas": 2,
    },
    {
        "slug": "dos-libros-sobre-el-agua",
        "archivo": "resena-dos-libros.html",
        "titulo": "Dos libros sobre el agua que ya no está",
        "bajada": "Un manual para cruzar ríos secos y un registro de lluvias recordadas forman, "
        "leídos el mismo día, una conversación involuntaria sobre la sequía.",
        "tipo": ArticleType.RESENA,
        "seccion": "resenas",
        "etiquetas": ("sequía", "paisaje"),
        "firmas": (CAMILA,),
        "obras": (
            {
                "titulo": "Manual para cruzar ríos que ya no existen",
                "autores": ("Héctor Quilodrán",),
                "editorial": "Editorial Barco de Papel Mojado y Sus Amigos",
                "anio": 2026,
            },
            {
                "titulo": "Aguacero",
                "autores": ("Lucía Painemal Ortúzar",),
                "editorial": "Ediciones Cuaderno de Campo del Sur Austral",
                "anio": 2026,
            },
        ),
        "horas": 122,
    },
)

POEMAS = (
    {
        "slug": "sobre-la-imposibilidad-de-terminar-un-poema",
        "archivo": "trompeta.txt",
        "titulo": "Sobre la imposibilidad de terminar un poema cuando afuera alguien está "
        "aprendiendo a tocar la trompeta con la ventana abierta",
        "firmas": (ANTONIA,),
        "horas": 3,
    },
    {
        "slug": "escalera",
        "archivo": "escalera.txt",
        "titulo": "Escalera",
        "firmas": (MATIAS,),
        "horas": 27,
    },
    {
        "slug": "oda-a-los-que-llegan-tarde",
        "archivo": "oda-tarde.txt",
        "titulo": "Oda a los que llegan tarde a la lectura",
        "epigrafe": "Para quienes llegaron a la lectura de otoño cuando ya estábamos en el "
        "tercer poema, empapados, pidiendo disculpas con la mirada, y se quedaron de pie junto "
        "a la puerta hasta el final.",
        "firmas": (JAVIERA,),
        "horas": 51,
    },
    {
        "slug": "inventario-del-patio",
        "archivo": "inventario-patio.txt",
        "titulo": "Inventario del patio",
        "firmas": (TOMAS, ROCIO),
        "horas": 75,
    },
    {
        "slug": "letania-para-una-casa-que-se-vende",
        "archivo": "letania-casa.txt",
        "titulo": "Letanía para una casa que se vende",
        "epigrafe": "Toda casa es un idioma que se olvida al mudarse. (Lo decía mi abuela.)",
        "firmas": (CAMILA,),
        "horas": 99,
    },
)


def _slug(texto):
    """«Ediciones Pájaro de Cemento» → «zz-largo-ediciones-pajaro-de-cemento»."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return PREFIJO + re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")[:200]


class Command(BaseCommand):
    help = "Siembra textos y poemas largos de prueba (prefijo zz-largo-), o los borra."

    def add_arguments(self, parser):
        parser.add_argument("--borrar", action="store_true", help="Borra lo que sembró.")
        parser.add_argument("--force", action="store_true", help="Permite correrlo con DEBUG=0.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_textos_largos crea contenido de prueba publicado: no se corre en "
                "producción. Con DEBUG=0 exige --force explícito."
            )
        with transaction.atomic():
            if options["borrar"]:
                self._borrar()
            else:
                self._sembrar()

    # ── Sembrar ──────────────────────────────────────────────────────────

    def _firma(self, slug, nombre):
        contribuidor = Contributor.objects.filter(slug=slug).first()
        if contribuidor:
            return contribuidor
        invitada, _ = Contributor.objects.get_or_create(
            slug=PREFIJO + slug, defaults={"display_name": nombre}
        )
        return invitada

    def _etiqueta(self, nombre):
        etiqueta, _ = Tag.objects.get_or_create(slug=_slug(nombre), defaults={"name": nombre})
        return etiqueta

    def _obra(self, datos):
        editorial, _ = Publisher.objects.get_or_create(
            slug=_slug(datos["editorial"]), defaults={"name": datos["editorial"]}
        )
        obra, _ = Work.objects.update_or_create(
            slug=_slug(datos["titulo"]),
            defaults={
                "title": datos["titulo"],
                "publisher": editorial,
                "publication_year": datos["anio"],
            },
        )
        obra.authors.set(
            BookAuthor.objects.get_or_create(slug=_slug(nombre), defaults={"name": nombre})[0]
            for nombre in datos["autores"]
        )
        return obra

    def _sembrar(self):
        ahora = timezone.now()
        # Las imágenes salen del material que ya hay: las fotos de las lecturas.
        fotos = [f.asset for f in EventPhoto.objects.select_related("asset").order_by("pk")[:4]]
        for datos in TEXTOS:
            cuerpo = (DIRECTORIO / datos["archivo"]).read_text(encoding="utf-8")
            if "{{imagen}}" in cuerpo:
                if len(fotos) > 2:
                    foto = fotos[2]
                    cuerpo = cuerpo.replace("{{imagen}}", foto.file.url).replace(
                        'width="1200" height="800"', f'width="{foto.width}" height="{foto.height}"'
                    )
                else:
                    cuerpo = re.sub(r"<figure>.*?</figure>", "", cuerpo, flags=re.S)
            indice = datos.get("imagen_de_portada")
            articulo, _ = Article.objects.update_or_create(
                slug=PREFIJO + datos["slug"],
                defaults={
                    "title": datos["titulo"],
                    "subtitle": datos["bajada"],
                    "body": cuerpo,
                    "type": datos["tipo"],
                    "section": Section.objects.filter(slug=datos["seccion"]).first(),
                    "status": EditorialStatus.PUBLISHED,
                    "published_at": ahora - timedelta(hours=datos["horas"]),
                    "cover_image": fotos[indice]
                    if indice is not None and len(fotos) > indice
                    else None,
                },
            )
            ArticleContributor.objects.filter(article=articulo).delete()
            for posicion, (slug, nombre) in enumerate(datos["firmas"]):
                ArticleContributor.objects.create(
                    article=articulo, contributor=self._firma(slug, nombre), position=posicion
                )
            articulo.tags.set(self._etiqueta(nombre) for nombre in datos["etiquetas"])
            ReviewedWork.objects.filter(article=articulo).delete()
            for obra in datos.get("obras", ()):
                ReviewedWork.objects.create(article=articulo, work=self._obra(obra))
            self.stdout.write(f"texto: {articulo.get_absolute_url()}")
        for datos in POEMAS:
            poema, _ = Poem.objects.update_or_create(
                slug=PREFIJO + datos["slug"],
                defaults={
                    "title": datos["titulo"],
                    "epigraph": datos.get("epigrafe", ""),
                    "body": (DIRECTORIO / datos["archivo"]).read_text(encoding="utf-8"),
                    "status": EditorialStatus.PUBLISHED,
                    "published_at": ahora - timedelta(hours=datos["horas"]),
                },
            )
            PoemContributor.objects.filter(poem=poema).delete()
            for posicion, (slug, nombre) in enumerate(datos["firmas"]):
                PoemContributor.objects.create(
                    poem=poema, contributor=self._firma(slug, nombre), position=posicion
                )
            self.stdout.write(f"poema: {poema.get_absolute_url()}")

    # ── Borrar ───────────────────────────────────────────────────────────

    def _borrar(self):
        def borrar(modelo):
            # Solo las filas del modelo: `delete()` cuenta también las que caen en cascada.
            return (
                modelo.objects.filter(slug__startswith=PREFIJO)
                .delete()[1]
                .get(modelo._meta.label, 0)
            )

        borrados = {
            "textos": borrar(Article),
            "poemas": borrar(Poem),
            "obras": borrar(Work),
            "editoriales": borrar(Publisher),
            "autores": borrar(BookAuthor),
            "etiquetas": borrar(Tag),
            "firmas invitadas": borrar(Contributor),
        }
        self.stdout.write("borrado: " + ", ".join(f"{k} {v}" for k, v in borrados.items()))
