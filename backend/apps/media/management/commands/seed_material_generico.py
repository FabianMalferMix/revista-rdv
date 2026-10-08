"""Material visual GENÉRICO para desarrollo: retratos, afiches, fotos de lectura, cubiertas,
carátulas de registro, logos, imágenes de texto y foto de grupo, dibujados con Pillow en la
paleta risográfica del colectivo. Son marcadores de posición con proporciones reales, para
que el diseño pueda evaluarse antes de que llegue el material verdadero.

Idempotente: cada pieza es un MediaAsset identificado por su `alt_text` (todos contienen la
palabra «provisional») y se genera una sola vez. Solo se asigna donde el campo está vacío o
donde lo que hay es otro marcador (crédito con «Placeholder» o «provisional»): nunca pisa
material real. Para reemplazar una pieza basta subir el archivo real en el panel
(Medios → Recursos) y seleccionarlo en el campo correspondiente; ver docs/contenido-visual.md.
"""

import random
from functools import partial
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageChops, ImageDraw, ImageFont

from apps.agenda.models import Event, EventPhoto
from apps.content.models import Article
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.reviews.models import Work
from apps.showcase.models import Partner, PressMention, Publication, SiteProfile

CREDITO = "Material genérico provisional (reemplazar por el real)"
MARCADORES = ("placeholder", "provisional")

PAPEL = (217, 232, 247)
TINTA = (18, 24, 35)
MAGENTA = (184, 8, 107)
AZUL = (31, 115, 199)
AMARILLO = (252, 228, 60)
BLANCO = (255, 255, 255)

MANIFIESTO_GENERICO = (
    "Repitentes del Verso es un colectivo de poesía que se reúne para leer en voz alta, "
    "escribir en compañía y llevar los poemas a lugares donde no suelen llegar: salas de "
    "clases, ferias, plazas, bibliotecas y escenarios compartidos con otras disciplinas. "
    "Trabajamos la escritura como un oficio que se afina en público: lo que resiste la "
    "lectura colectiva se publica, lo demás vuelve al taller. Guardamos registro de cada "
    "encuentro porque la memoria de un colectivo también se escribe entre todos."
)

PIES_DE_FOTO = (
    "Apertura de la lectura",
    "Público en la sala",
    "Lectura en el escenario",
    "Mesa de publicaciones",
    "Conversación tras la lectura",
    "Cierre colectivo",
)


# ── Dibujo ────────────────────────────────────────────────────────────────


def _fuente(tamano, peso=500):
    """La Syne del sitio (autoalojada, variable 400–800): tiene tildes y eñes, que a la
    fuente empaquetada de Pillow le faltan. Si no se puede leer, cae a la de Pillow."""
    ruta = settings.BASE_DIR / "static" / "fonts" / "syne.woff2"
    try:
        fuente = ImageFont.truetype(str(ruta), tamano)
        try:
            fuente.set_variation_by_axes([peso])
        except (OSError, AttributeError):
            pass
        return fuente
    except OSError:
        return ImageFont.load_default(size=tamano)


def _may(texto):
    """Mayúsculas solo para texto ASCII: la fuente empaquetada no trae Í ni Ñ en caja alta."""
    return texto.upper() if texto.isascii() else texto


def _tinta(img, dibujar, color, desregistro=(0, 0)):
    """Sobreimprime una «tinta»: dibuja en una capa blanca y la multiplica sobre la imagen,
    con un desregistro de unos píxeles, que es lo que delata una risografía real."""
    capa = Image.new("RGB", img.size, BLANCO)
    dibujar(ImageDraw.Draw(capa), color)
    dx, dy = desregistro
    if (dx, dy) != (0, 0):
        # `offset` envuelve: lo que sale por un borde entra por el opuesto. Se blanquean
        # esas franjas para que no aparezca un fragmento espurio al otro lado.
        capa = ImageChops.offset(capa, dx, dy)
        w, h = capa.size
        d = ImageDraw.Draw(capa)
        if dx > 0:
            d.rectangle((0, 0, dx - 1, h), fill=BLANCO)
        elif dx < 0:
            d.rectangle((w + dx, 0, w, h), fill=BLANCO)
        if dy > 0:
            d.rectangle((0, 0, w, dy - 1), fill=BLANCO)
        elif dy < 0:
            d.rectangle((0, h + dy, w, h), fill=BLANCO)
    return ImageChops.multiply(img, capa)


def _grano(img, sigma=26):
    ruido = Image.effect_noise(img.size, sigma).convert("RGB")
    claro = ImageChops.lighter(ruido, Image.new("RGB", img.size, (205, 205, 205)))
    return ImageChops.multiply(img, claro)


def _ajustar(texto, fuente, ancho_max, draw):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _escribir(img, xy, texto, tamano, color, ancho_max=None, interlinea=1.08, peso=500):
    draw = ImageDraw.Draw(img)
    fuente = _fuente(tamano, peso)
    lineas = _ajustar(texto, fuente, ancho_max, draw) if ancho_max else [texto]
    x, y = xy
    for linea in lineas:
        draw.text((x, y), linea, font=fuente, fill=color)
        y += int(tamano * interlinea)
    return y


def _etiqueta(img, texto, color=TINTA, posicion=None):
    """Rótulo pequeño (abajo a la izquierda salvo que se indique): la pieza es provisional."""
    w, h = img.size
    tamano = max(18, w // 60)
    xy = posicion or (w // 25, h - tamano - h // 25)
    _escribir(img, xy, _may(texto), tamano, color)


def _silueta(draw, color, cx, cy, escala):
    """Busto esquemático: cabeza + hombros."""
    r = int(230 * escala)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    ancho, alto = int(520 * escala), int(600 * escala)
    y0 = cy + int(260 * escala)
    draw.rounded_rectangle(
        (cx - ancho, y0, cx + ancho, y0 + alto), radius=int(200 * escala), fill=color
    )


def _retrato(nombre, semilla):
    rng = random.Random(f"retrato:{semilla}")
    fondo, tinta, segunda = rng.choice(
        ((PAPEL, MAGENTA, AZUL), (AMARILLO, AZUL, MAGENTA), (PAPEL, AZUL, MAGENTA))
    )
    img = Image.new("RGB", (1200, 1500), fondo)
    r = rng.randint(380, 520)
    cx, cy = rng.randint(650, 820), rng.randint(520, 700)
    img = _tinta(
        img, lambda d, c: d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c), segunda, (14, -10)
    )
    img = _tinta(img, lambda d, c: _silueta(d, c, 600, 560, 1.0), tinta)
    img = _grano(img)
    _escribir(img, (60, 1290), nombre, 56, TINTA, ancho_max=1080, peso=700)
    _etiqueta(img, "retrato provisional · reemplazar")
    return img, "JPEG"


def _foto_lectura(titulo, n, semilla):
    rng = random.Random(f"foto:{semilla}:{n}")
    img = Image.new("RGB", (2400, 1600), PAPEL)
    tinta = rng.choice((AZUL, MAGENTA))

    def luces(d, c):
        for _ in range(rng.randint(3, 5)):
            r = rng.randint(180, 420)
            x, y = rng.randint(200, 2200), rng.randint(150, 700)
            d.ellipse((x - r, y - r, x + r, y + r), fill=c)

    def sala(d, c):
        d.rectangle((0, 1020, 2400, 1600), fill=c)
        for _ in range(rng.randint(5, 9)):
            x, w = rng.randint(100, 2200), rng.randint(90, 160)
            d.rounded_rectangle((x, rng.randint(620, 760), x + w, 1040), radius=60, fill=c)

    img = _tinta(img, luces, tinta, (10, 8))
    img = _tinta(img, sala, TINTA)
    img = _grano(img, sigma=34)
    _etiqueta(img, f"foto provisional {n} · {titulo}", posicion=(60, 60))
    return img, "JPEG"


def _afiche(evento, semilla):
    rng = random.Random(f"afiche:{semilla}")
    img = Image.new("RGB", (1200, 1600), AMARILLO)
    r = rng.randint(380, 520)
    cx, cy = rng.randint(700, 900), rng.randint(900, 1100)
    img = _tinta(
        img, lambda d, c: d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c), MAGENTA, (12, -8)
    )
    img = _tinta(img, lambda d, c: d.rectangle((0, 0, 1200, 90), fill=c), TINTA)
    _escribir(img, (70, 150), _may(evento.get_type_display()), 40, TINTA)
    y = _escribir(
        img, (70, 230), evento.title, 112, TINTA, ancho_max=1060, interlinea=1.0, peso=700
    )
    fecha = evento.starts_at.strftime("%d · %m · %Y") if evento.starts_at else ""
    lugar = " · ".join(p for p in (evento.venue_name, evento.city) if p)
    _escribir(
        img, (70, y + 40), " ".join(p for p in (fecha, lugar) if p), 44, TINTA, ancho_max=1060
    )
    _etiqueta(img, "afiche provisional · reemplazar")
    return img, "JPEG"


def _cubierta(titulo, autor, pie, semilla, fondo=None):
    rng = random.Random(f"cubierta:{semilla}")
    fondo = fondo or rng.choice((PAPEL, BLANCO, AMARILLO))
    img = Image.new("RGB", (1000, 1400), fondo)
    r = rng.randint(220, 320)
    cx, cy = rng.randint(520, 700), rng.randint(760, 920)
    img = _tinta(img, lambda d, c: d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c), AZUL)
    img = _tinta(
        img,
        lambda d, c: d.ellipse((cx - r - 150, cy - r + 90, cx + r - 150, cy + r + 90), fill=c),
        MAGENTA,
        (8, 6),
    )
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 959, 1359), outline=TINTA, width=3)
    y = _escribir(img, (90, 120), titulo, 92, TINTA, ancho_max=820, interlinea=1.0, peso=700)
    _escribir(img, (90, y + 30), autor, 40, TINTA, ancho_max=820)
    _escribir(img, (90, 1230), _may(pie), 30, TINTA)
    _etiqueta(img, "cubierta provisional · reemplazar", posicion=(90, 1300))
    return img, "JPEG"


def _caratula_registro(registro, semilla):
    rng = random.Random(f"caratula:{semilla}")
    img = Image.new("RGB", (1920, 1080), TINTA)
    capa = Image.new("RGB", img.size, TINTA)
    d = ImageDraw.Draw(capa)
    r = rng.randint(380, 520)
    cx, cy = rng.randint(1350, 1550), rng.randint(420, 660)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AZUL)
    d.ellipse((cx - r + 60, cy - r + 40, cx + r + 60, cy + r + 40), fill=MAGENTA)
    img = ImageChops.lighter(
        img, ImageChops.darker(capa, Image.new("RGB", img.size, (210, 210, 210)))
    )
    _escribir(img, (100, 120), f"REGISTRO · {_may(registro.get_kind_display())}", 40, PAPEL)
    _escribir(img, (100, 220), registro.title, 96, PAPEL, ancho_max=1100, interlinea=1.0, peso=700)
    _etiqueta(img, "carátula provisional · reemplazar", color=PAPEL)
    return img, "JPEG"


def _logo(nombre, semilla):
    rng = random.Random(f"logo:{semilla}")
    img = Image.new("RGB", (600, 300), BLANCO)
    a, b = rng.choice(((MAGENTA, AZUL), (AZUL, MAGENTA), (TINTA, MAGENTA)))
    img = _tinta(img, lambda d, c: d.ellipse((40, 70, 200, 230), fill=c), a)
    img = _tinta(img, lambda d, c: d.ellipse((110, 70, 270, 230), fill=c), b, (4, 3))
    _escribir(img, (300, 90), nombre, 40, TINTA, ancho_max=270, interlinea=1.05)
    _etiqueta(img, "logo provisional")
    return img, "PNG"


def _imagen_texto(titulo, cejilla, semilla):
    rng = random.Random(f"texto:{semilla}")
    img = Image.new("RGB", (1800, 1200), rng.choice((PAPEL, AMARILLO, BLANCO)))
    tinta = rng.choice((MAGENTA, AZUL))

    def formas(d, c):
        x = rng.randint(900, 1300)
        d.pieslice((x - 500, 150, x + 500, 1150), 180, 360, fill=c)
        d.rectangle((rng.randint(120, 400), 700, rng.randint(900, 1200), 780), fill=c)

    img = _tinta(img, formas, tinta, (10, -8))
    img = _grano(img)
    _escribir(img, (90, 110), _may(cejilla), 36, TINTA)
    _escribir(img, (90, 190), titulo, 80, TINTA, ancho_max=1000, interlinea=1.0, peso=700)
    _etiqueta(img, "imagen provisional · reemplazar")
    return img, "JPEG"


def _foto_grupo(nombres):
    img = Image.new("RGB", (2400, 1260), PAPEL)
    n = max(1, len(nombres))
    paso = 2400 / (n + 1)

    def siluetas(d, c, paridad):
        for i, _ in enumerate(nombres):
            if i % 2 != paridad:
                continue
            _silueta(d, c, int(paso * (i + 1)), 880 + (50 if i % 3 else 0), 0.32)

    img = _tinta(img, lambda d, c: siluetas(d, c, 0), MAGENTA, (10, 6))
    img = _tinta(img, lambda d, c: siluetas(d, c, 1), AZUL)
    img = _grano(img)
    _escribir(
        img,
        (110, 110),
        "Repitentes del Verso",
        150,
        TINTA,
        ancho_max=2100,
        interlinea=1.0,
        peso=800,
    )
    _escribir(img, (110, 300), "Colectivo de poesía · Chile", 56, TINTA)
    _etiqueta(img, "foto de grupo provisional · reemplazar", posicion=(110, 400))
    return img, "JPEG"


# ── Comando ───────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Genera material visual genérico (marcadores con proporciones reales). Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Permite correrlo con DEBUG=0.")
        parser.add_argument(
            "--fotos-por-evento", type=int, default=6, help="Fotos de lectura por evento (6)."
        )
        parser.add_argument(
            "--regenerar",
            action="store_true",
            help="Vuelve a dibujar los marcadores ya existentes (mismos recursos, archivo nuevo).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_material_generico crea contenido ficticio: no debe correr en producción. "
                "Con DEBUG=0 exige --force explícito."
            )
        self.creados = 0
        self.regenerar = options["regenerar"]
        fotos_por_evento = max(0, options["fotos_por_evento"])

        # Integrantes: retrato 4:5.
        for m in Contributor.members():
            asset = self._asset(
                f"Retrato provisional de {m.display_name}",
                f"retrato-{m.slug}",
                partial(_retrato, m.display_name, m.slug),
            )
            self._asignar(m, "photo", asset)

        # Eventos: afiche 3:4 y fotos de lectura 3:2.
        for e in Event.objects.all():
            afiche = self._asset(
                f"Afiche provisional · {e.title}", f"afiche-{e.slug}", partial(_afiche, e, e.slug)
            )
            self._asignar(e, "poster", afiche)
            for n in range(1, fotos_por_evento + 1):
                foto = self._asset(
                    f"Foto provisional {n} · {e.title}",
                    f"foto-{e.slug}-{n}",
                    partial(_foto_lectura, e.title, n, e.slug),
                )
                EventPhoto.objects.get_or_create(
                    event=e,
                    asset=foto,
                    defaults={"caption": PIES_DE_FOTO[(n - 1) % len(PIES_DE_FOTO)], "position": n},
                )

        # Publicaciones propias: cubierta 5:7.
        for p in Publication.objects.all():
            pie = " · ".join(x for x in (p.get_kind_display(), str(p.year or "")) if x)
            asset = self._asset(
                f"Cubierta provisional · {p.title}",
                f"cubierta-{p.slug}",
                partial(_cubierta, p.title, "Repitentes del Verso", pie, p.slug),
            )
            self._asignar(p, "cover", asset)

        # Registros: carátula 16:9.
        for r in Recording.objects.all():
            asset = self._asset(
                f"Carátula provisional · {r.title}",
                f"caratula-{r.slug}",
                partial(_caratula_registro, r, r.slug),
            )
            self._asignar(r, "poster", asset)

        # Aliados y medios: logo.
        for a in Partner.objects.all():
            asset = self._asset(
                f"Logo provisional · {a.name}",
                f"logo-aliado-{a.pk}",
                partial(_logo, a.name, f"aliado:{a.pk}"),
            )
            self._asignar(a, "logo", asset)
        for pm in PressMention.objects.all():
            asset = self._asset(
                f"Logo provisional · {pm.outlet}",
                f"logo-medio-{pm.pk}",
                partial(_logo, pm.outlet, f"medio:{pm.pk}"),
            )
            self._asignar(pm, "logo", asset)

        # Textos y obras reseñadas.
        for art in Article.objects.all():
            asset = self._asset(
                f"Imagen provisional · {art.title}",
                f"texto-{art.slug}",
                partial(_imagen_texto, art.title, art.get_type_display(), art.slug),
            )
            self._asignar(art, "cover_image", asset)
        for w in Work.objects.all():
            autores = ", ".join(str(a) for a in w.authors.all()) or "Autoría por confirmar"
            pie = " · ".join(x for x in (w.get_kind_display(), str(w.publication_year or "")) if x)
            asset = self._asset(
                f"Cubierta provisional · {w.title}",
                f"obra-{w.slug}",
                partial(_cubierta, w.title, autores, pie, f"obra:{w.slug}", fondo=BLANCO),
            )
            self._asignar(w, "cover_image", asset)

        # Perfil del sitio: foto de grupo (og_image) y manifiesto si aún es el de la siembra.
        perfil = SiteProfile.load()
        nombres = [m.display_name for m in Contributor.members()]
        grupo = self._asset(
            "Foto de grupo provisional · Repitentes del Verso",
            "foto-grupo",
            partial(_foto_grupo, nombres),
        )
        self._asignar(perfil, "og_image", grupo)
        if len(perfil.manifesto.split()) < 40:
            perfil.manifesto = MANIFIESTO_GENERICO
            perfil.save(update_fields=["manifesto"])
            self.stdout.write("manifiesto: texto genérico aplicado (provisional)")

        self.stdout.write(
            self.style.SUCCESS(f"material genérico listo: {self.creados} imágenes nuevas")
        )

    # ── helpers ──

    def _asset(self, alt_text, nombre, generar):
        asset, _ = MediaAsset.objects.get_or_create(alt_text=alt_text, defaults={"credit": CREDITO})
        existe = bool(asset.file) and asset.file.storage.exists(asset.file.name)
        if existe and not self.regenerar:
            return asset
        if existe:
            # Mismo nombre de archivo: hay que borrar el original y sus derivados, o el
            # almacenamiento renombraría el nuevo y los derivados viejos quedarían servidos.
            almacen = asset.file.storage
            for derivado in asset.derivative_names():
                almacen.delete(derivado)
            almacen.delete(asset.file.name)
        img, formato = generar()
        buf = BytesIO()
        if formato == "JPEG":
            img.save(buf, format="JPEG", quality=86, optimize=True)
            ext = "jpg"
        else:
            img.save(buf, format="PNG", optimize=True)
            ext = "png"
        asset.file.save(f"{nombre}.{ext}", ContentFile(buf.getvalue()), save=True)
        self.creados += 1
        return asset

    def _asignar(self, obj, campo, asset):
        """Asigna solo si el campo está vacío o contiene otro marcador. Material real: intacto."""
        actual = getattr(obj, campo)
        if actual is not None and actual.pk == asset.pk:
            return
        if actual is not None and not any(m in (actual.credit or "").lower() for m in MARCADORES):
            return
        setattr(obj, campo, asset)
        obj.save(update_fields=[campo])
