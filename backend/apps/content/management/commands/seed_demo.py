"""Carga datos de demostración para desarrollo. Idempotente: se puede repetir.

docker compose exec web python manage.py seed_demo
"""

from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.agenda.models import Event, EventPhoto, Milestone
from apps.community.models import Comment, NewsletterSubscriber
from apps.content.models import (
    Article,
    ArticleContributor,
    ArticleType,
    Collection,
    CollectionArticle,
    CollectionPoem,
    EditorialStatus,
    Page,
    Poem,
    PoemContributor,
    PublishStatus,
    ReviewedWork,
    Section,
    Tag,
)
from apps.media.models import MediaAsset, Recording
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
from apps.showcase.models import (
    Partner,
    PressMention,
    Publication,
    SiteProfile,
    SiteSocialLink,
    WhereToBuy,
)
from apps.submissions.models import Call, Submission

P = "<p>{}</p>"


def body(*paras):
    return "\n".join(P.format(p) for p in paras)


class Command(BaseCommand):
    help = "Carga datos de demostración (idempotente)."

    def handle(self, *args, **options):
        User = get_user_model()
        now = timezone.now()

        # ── Usuarios con rol ─────────────────────────────────
        editora = self._user(User, "editora", "editor")
        autor_user = self._user(User, "autor1", "autor")

        # ── Taxonomía ────────────────────────────────────────
        sections = {}
        for i, name in enumerate(["Reseñas", "Ensayos", "Entrevistas", "Poesía", "Crónica"]):
            sections[name], _ = Section.objects.get_or_create(
                slug=slugify(name), defaults={"name": name, "position": i}
            )

        tags = {}
        for name in ["poesía", "narrativa", "ensayo", "novedad", "entrevista", "traducción"]:
            tags[name], _ = Tag.objects.get_or_create(slug=slugify(name), defaults={"name": name})

        # ── Catálogo de reseñas ──────────────────────────────
        publishers = {}
        for name in ["Alquimia Ediciones", "Overol", "Hueders", "Ediciones UDP", "Laurel"]:
            publishers[name], _ = Publisher.objects.get_or_create(
                slug=slugify(name), defaults={"name": name, "country": "Chile"}
            )

        book_authors = {}
        for name in [
            "Valentina Aguirre",
            "Ignacio Bravo",
            "Camila Reyes",
            "Tomás Vergara",
            "Josefa Lillo",
        ]:
            book_authors[name], _ = BookAuthor.objects.get_or_create(
                slug=slugify(name), defaults={"name": name}
            )

        works = {}
        works_data = [
            (
                "El invierno de las cosas",
                Work.Kind.POEMARIO,
                "Alquimia Ediciones",
                2023,
                "Valentina Aguirre",
            ),
            ("Territorio en fuga", Work.Kind.LIBRO, "Overol", 2022, "Ignacio Bravo"),
            ("Cuadernos del sur", Work.Kind.ENSAYO, "Hueders", 2024, "Camila Reyes"),
            ("La casa vacía", Work.Kind.LIBRO, "Ediciones UDP", 2021, "Tomás Vergara"),
            ("Antología del margen", Work.Kind.ANTOLOGIA, "Laurel", 2023, "Josefa Lillo"),
        ]
        for title, kind, pub, year, author in works_data:
            w, _ = Work.objects.get_or_create(
                slug=slugify(title),
                defaults={
                    "title": title,
                    "kind": kind,
                    "publisher": publishers[pub],
                    "publication_year": year,
                },
            )
            w.authors.add(book_authors[author])
            works[title] = w

        # ── Colaboradores de la revista ──────────────────────
        contributors = {}
        for name, bio in [
            ("Fernanda Soto", "Crítica literaria y editora."),
            ("Andrés Cáceres", "Escribe sobre narrativa y poesía chilena."),
            ("Paula Miranda", "Ensayista y traductora."),
            ("Diego Salinas", "Periodista cultural."),
        ]:
            contributors[name], _ = Contributor.objects.get_or_create(
                slug=slugify(name), defaults={"display_name": name, "bio": bio}
            )
        # El colaborador Andrés Cáceres tiene cuenta en el sistema.
        if contributors["Andrés Cáceres"].user_id is None:
            contributors["Andrés Cáceres"].user = autor_user
            contributors["Andrés Cáceres"].save(update_fields=["user"])

        # ── Integrantes del colectivo ────────────────────────
        # Diego Salinas queda como colaborador externo (sin membresía).
        members_extra = {
            "Fernanda Soto": {
                "role": "Fundadora · edición",
                "member_since": 2019,
                "position": 0,
                "short_bio": "Poeta y editora. Coordina las publicaciones del colectivo.",
                "poetics": "Escribo para afinar el oído: el poema como temperatura del habla.",
                "photo_file": "member-fernanda.jpg",
            },
            "Andrés Cáceres": {
                "member_since": 2021,
                "position": 1,
                "short_bio": "Poeta. Escribe sobre narrativa y poesía chilena.",
                "poetics": "Busco el verso que camina: ritmo antes que ornamento.",
                "photo_file": "member-andres.jpg",
            },
            "Paula Miranda": {
                "role": "Fundadora",
                "member_since": 2019,
                "position": 2,
                "short_bio": "Poeta, ensayista y traductora.",
                "poetics": "Traducir y escribir son la misma operación: escuchar dos veces.",
                "photo_file": "member-paula.jpg",
            },
        }
        for name, extra in members_extra.items():
            photo = self._photo(f"Retrato de {name}", extra.pop("photo_file"))
            Contributor.objects.filter(pk=contributors[name].pk).update(
                is_member=True, active=True, photo=photo, **extra
            )

        # ── Artículos en varios estados ──────────────────────
        articles = {}
        for spec in self._articles(now):
            articles[spec["slug"]] = self._make_article(
                spec, sections, tags, contributors, works, editora, autor_user
            )

        # ── Colección con artículos publicados ───────────────
        collection, _ = Collection.objects.get_or_create(
            slug="nuevas-voces",
            defaults={
                "title": "Nuevas voces",
                "description": "Un recorrido por la narrativa y poesía chilena reciente.",
                "intro": "Cinco lecturas para entrar al año literario.",
                "status": PublishStatus.PUBLISHED,
                "published_at": now - timedelta(days=1),
            },
        )
        for i, slug in enumerate(
            [
                "resena-el-invierno-de-las-cosas",
                "resena-territorio-en-fuga",
                "resena-cuadernos-del-sur",
            ]
        ):
            if slug in articles:
                CollectionArticle.objects.get_or_create(
                    collection=collection, article=articles[slug], defaults={"position": i}
                )

        # ── Comentarios (moderación) ─────────────────────────
        art = articles.get("resena-el-invierno-de-las-cosas")
        if art:
            Comment.objects.get_or_create(
                article=art,
                guest_name="Lector Anónimo",
                defaults={
                    "guest_email": "lector@example.com",
                    "body": "Gran lectura del poemario. Gracias por la reseña.",
                    "status": Comment.Status.APPROVED,
                },
            )
            Comment.objects.get_or_create(
                article=art,
                guest_name="Comentario Pendiente",
                defaults={
                    "guest_email": "otro@example.com",
                    "body": "¿Dónde se consigue el libro?",
                    "status": Comment.Status.PENDING,
                },
            )

        # ── Newsletter ───────────────────────────────────────
        NewsletterSubscriber.objects.get_or_create(
            email="suscriptor@example.com",
            defaults={
                "status": NewsletterSubscriber.Status.CONFIRMED,
                "confirmed_at": now - timedelta(days=10),
            },
        )
        NewsletterSubscriber.objects.get_or_create(
            email="pendiente@example.com",
            defaults={"status": NewsletterSubscriber.Status.PENDING, "token": "demo-token"},
        )

        # ── Convocatoria + envío ─────────────────────────────
        call, _ = Call.objects.get_or_create(
            slug="convocatoria-invierno",
            defaults={
                "title": "Convocatoria de invierno",
                "description": "Recibimos reseñas y ensayos hasta fin de mes.",
                "opens_at": now - timedelta(days=5),
                "closes_at": now + timedelta(days=30),
            },
        )
        Submission.objects.get_or_create(
            title="Propuesta: reseña de un debut narrativo",
            author_email="colaborador.externo@example.com",
            defaults={
                "author_name": "Colaborador Externo",
                "type": "reseña",
                "body": "Adjunto una propuesta de reseña para su evaluación.",
                "status": Submission.Status.RECEIVED,
                "call": call,
            },
        )

        # ── Páginas estáticas ────────────────────────────────
        for slug, title, html in [
            (
                "quienes-somos",
                "Quiénes somos",
                "<p>Somos un colectivo de poesía dedicado a difundir la obra de sus "
                "integrantes: poemas, reseñas y ensayos, además de los recitales, "
                "talleres y publicaciones que realizamos como grupo.</p>",
            ),
            (
                "bases",
                "Bases de colaboración",
                "<p>Cuando abrimos convocatorias recibimos textos inéditos. Envía tu "
                "propuesta desde la página de convocatorias y el equipo editorial "
                "te responderá.</p>",
            ),
        ]:
            Page.objects.get_or_create(
                slug=slug,
                defaults={"title": title, "body": html, "status": PublishStatus.PUBLISHED},
            )

        # ── Identidad del colectivo (SiteProfile singleton) ──
        profile = SiteProfile.load()
        if profile.name in ("", "Colectivo"):
            profile.name = "Reseñas"
            profile.tagline = "Colectivo de poesía · crítica y difusión literaria."
            profile.manifesto = (
                "Somos un colectivo dedicado a difundir el trabajo literario de sus integrantes: "
                "poemas, reseñas y ensayos, además de los recitales y publicaciones que hacemos."
            )
            profile.founded_year = 2019
            profile.location = "Santiago, Chile"
            profile.general_email = "hola@resenas.cl"
            profile.booking_email = "gestion@resenas.cl"
            profile.save()
        for i, (platform, url) in enumerate(
            [("Instagram", "https://instagram.com/"), ("YouTube", "https://youtube.com/")]
        ):
            SiteSocialLink.objects.get_or_create(
                profile=profile, platform=platform, defaults={"url": url, "position": i}
            )

        # ── Registro destacado (embed de ejemplo) ────────────
        recording, _ = Recording.objects.get_or_create(
            slug="recital-nuevas-voces",
            defaults={
                "title": "Recital «Nuevas voces» (registro)",
                "kind": Recording.Kind.VIDEO,
                "embed_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "description": "Lectura colectiva de apertura del año.",
                "featured": True,
                "published": True,
                "published_at": now - timedelta(days=1),
            },
        )
        if profile.featured_recording_id is None:
            profile.featured_recording = recording
            profile.save(update_fields=["featured_recording"])
        recording.participants.add(contributors["Fernanda Soto"], contributors["Paula Miranda"])

        # ── Poemas (obra propia: texto plano, versos y sangrías) ──
        poems_data = [
            {
                "slug": "umbral",
                "title": "Umbral",
                "author": "Fernanda Soto",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=3),
                "featured": True,
                "epigraph": "a los que llegan tarde",
                "body": (
                    "La casa guarda un idioma\n"
                    "que nadie termina de hablar:\n"
                    "\n"
                    "    la llave que gira,\n"
                    "    el agua que sube,\n"
                    "    la luz que se apaga sola.\n"
                    "\n"
                    "Entrar es aprender de nuevo\n"
                    "dónde duelen las paredes."
                ),
            },
            {
                "slug": "oficio-de-la-lluvia",
                "title": "Oficio de la lluvia",
                "author": "Paula Miranda",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=7),
                "body": (
                    "Llueve como corrige un editor:\n"
                    "sin apuro,\n"
                    "        tachando lo que sobra,\n"
                    "dejando en pie\n"
                    "lo que de verdad moja."
                ),
            },
            {
                "slug": "borrador-de-invierno",
                "title": "Borrador de invierno",
                "author": "Andrés Cáceres",
                "status": EditorialStatus.DRAFT,
                "published": None,
                "body": "Primer verso en frío.\n(aún en trabajo)",
            },
        ]
        poems = {}
        for spec in poems_data:
            poem, _ = Poem.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "epigraph": spec.get("epigraph", ""),
                    "body": spec["body"],
                    "status": spec["status"],
                    "featured": spec.get("featured", False),
                    "owner": autor_user,
                    "published_at": spec["published"],
                },
            )
            PoemContributor.objects.get_or_create(
                poem=poem, contributor=contributors[spec["author"]], defaults={"position": 0}
            )
            poems[spec["slug"]] = poem

        # El destacado lleva el registro del recital, entra a la colección y a la portada.
        umbral = poems["umbral"]
        if umbral.recording_id is None:
            umbral.recording = recording
            umbral.save(update_fields=["recording"])
        CollectionPoem.objects.get_or_create(
            collection=collection, poem=umbral, defaults={"position": 3}
        )
        if profile.featured_poem_id is None:
            profile.featured_poem = umbral
            profile.save(update_fields=["featured_poem"])

        # ── Agenda y trayectoria (eventos, galería, hitos) ───
        events_data = [
            {
                "slug": "recital-nuevas-voces-lanzamiento",
                "title": "Recital «Nuevas voces»",
                "type": Event.Type.RECITAL,
                "starts_at": now - timedelta(days=90),
                "venue_name": "Casa del Libro",
                "city": "Santiago",
                "description": "Lectura colectiva de apertura del año, con invitados.",
                "participants": ["Fernanda Soto", "Paula Miranda", "Andrés Cáceres"],
                "photos": [
                    ("Lectura de apertura", "event-apertura.jpg"),
                    ("Público en la sala", "event-publico.jpg"),
                    ("Cierre colectivo", "event-cierre.jpg"),
                ],
            },
            {
                "slug": "lectura-festival-poesia-joven",
                "title": "Lectura en Festival de Poesía Joven",
                "type": Event.Type.FESTIVAL,
                "starts_at": now - timedelta(days=300),
                "city": "Valparaíso",
                "is_external": True,
                "host": "Festival de Poesía Joven",
                "participants": ["Fernanda Soto", "Andrés Cáceres"],
            },
            {
                "slug": "taller-el-verso-vivo",
                "title": "Taller de escritura: el verso vivo",
                "type": Event.Type.TALLER,
                "starts_at": now + timedelta(days=20),
                "venue_name": "Biblioteca de Santiago",
                "city": "Santiago",
                "description": "Taller abierto de escritura poética, cupos limitados.",
                "registration_url": "https://example.com/inscripcion",
                "featured": True,
                "participants": ["Paula Miranda"],
            },
            {
                "slug": "recital-de-invierno",
                "title": "Recital de invierno",
                "type": Event.Type.RECITAL,
                "starts_at": now + timedelta(days=45),
                "venue_name": "Café Literario",
                "city": "Santiago",
                "participants": ["Fernanda Soto", "Paula Miranda", "Andrés Cáceres"],
            },
        ]
        events = {}
        for spec in events_data:
            event, _ = Event.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "type": spec["type"],
                    "starts_at": spec["starts_at"],
                    "venue_name": spec.get("venue_name", ""),
                    "city": spec.get("city", ""),
                    "description": spec.get("description", ""),
                    "is_external": spec.get("is_external", False),
                    "host": spec.get("host", ""),
                    "registration_url": spec.get("registration_url", ""),
                    "featured": spec.get("featured", False),
                    "published": True,
                },
            )
            event.participants.add(*[contributors[n] for n in spec.get("participants", [])])
            for i, (caption, filename) in enumerate(spec.get("photos", [])):
                EventPhoto.objects.get_or_create(
                    event=event,
                    asset=self._photo(f"{spec['title']} — {caption}", filename),
                    defaults={"caption": caption, "position": i},
                )
            events[spec["slug"]] = event

        # El registro del recital queda ligado a su evento.
        if recording.event_id is None:
            recording.event = events["recital-nuevas-voces-lanzamiento"]
            recording.save(update_fields=["event"])

        for year, title, desc in [
            (2019, "Fundación del colectivo", "Primera lectura conjunta y manifiesto."),
            (2022, "Primera plaquette colectiva", "Edición artesanal de 200 ejemplares."),
        ]:
            Milestone.objects.get_or_create(year=year, title=title, defaults={"description": desc})

        # ── Registro de audio (alimenta el feed podcast) ─────
        audio, audio_created = Recording.objects.get_or_create(
            slug="umbral-lectura",
            defaults={
                "title": "«Umbral» — lectura de la autora",
                "kind": Recording.Kind.AUDIO,
                "description": "Lectura del poema «Umbral», registrada en el recital.",
                "published": True,
                "published_at": now - timedelta(days=2),
                "event": events["recital-nuevas-voces-lanzamiento"],
                "position": 1,
            },
        )
        if audio_created:
            from django.core.files.base import ContentFile

            audio.file.save("umbral-lectura.wav", ContentFile(self._audio_bytes()), save=True)
        audio.participants.add(contributors["Fernanda Soto"])

        # ── Catálogo de publicaciones (vitrina, sin pagos) ───
        pubs_data = [
            {
                "slug": "umbral-y-otras-salidas",
                "title": "Umbral y otras salidas",
                "kind": Publication.Kind.PLAQUETTE,
                "year": 2022,
                "synopsis": "Plaquette colectiva: nueve poemas sobre casas, puertas y regresos. "
                "Edición artesanal cosida a mano.",
                "participants": ["Fernanda Soto", "Paula Miranda", "Andrés Cáceres"],
                "cover_file": "cover-umbral.jpg",
                "featured": True,
                "with_pdf": True,
                "stores": [("Feria del Libro Independiente", "https://example.com/feria")],
            },
            {
                "slug": "cuadernos-del-ruido",
                "title": "Cuadernos del ruido",
                "kind": Publication.Kind.LIBRO,
                "year": 2024,
                "publisher": "Overol",
                "synopsis": "Primer libro individual de Fernanda Soto, escrito dentro del taller "
                "del colectivo.",
                "participants": ["Fernanda Soto"],
                "cover_file": "cover-cuadernos.jpg",
                "stores": [("Editorial Overol", "https://example.com/overol")],
            },
            {
                "slug": "correspondencias",
                "title": "Correspondencias",
                "kind": Publication.Kind.FANZINE,
                "year": 2023,
                "synopsis": "Fanzine de poemas cruzados entre integrantes: cada texto responde "
                "al anterior. Descarga gratuita.",
                "participants": ["Paula Miranda", "Andrés Cáceres"],
                "cover_file": "cover-correspondencias.jpg",
                "with_pdf": True,
            },
        ]
        for spec in pubs_data:
            pub, pub_created = Publication.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "kind": spec["kind"],
                    "year": spec["year"],
                    "publisher": publishers.get(spec.get("publisher")),
                    "synopsis": spec["synopsis"],
                    "cover": self._photo(f"Portada — {spec['title']}", spec["cover_file"]),
                    "featured": spec.get("featured", False),
                    "published": True,
                },
            )
            pub.participants.add(*[contributors[n] for n in spec.get("participants", [])])
            if pub_created and spec.get("with_pdf"):
                from django.core.files.base import ContentFile

                pub.pdf.save(f"{spec['slug']}.pdf", ContentFile(self._pdf_bytes()), save=True)
            for i, (label, url) in enumerate(spec.get("stores", [])):
                WhereToBuy.objects.get_or_create(
                    publication=pub, label=label, defaults={"url": url, "position": i}
                )

        # ── Prensa y aliados ─────────────────────────────────
        for spec in [
            {
                "title": "«La poesía vuelve a los recitales»",
                "outlet": "El Mercurio de Valparaíso",
                "kind": PressMention.Kind.NOTA,
                "published_on": (now - timedelta(days=200)).date(),
                "quote": "Uno de los colectivos más activos de la escena joven.",
                "featured": True,
            },
            {
                "title": "Entrevista al colectivo tras su plaquette",
                "outlet": "Radio Universidad",
                "kind": PressMention.Kind.ENTREVISTA,
                "published_on": (now - timedelta(days=120)).date(),
                "quote": "Leen como quien conversa: cerca, sin solemnidad.",
                "author": "M. Torres",
            },
        ]:
            PressMention.objects.get_or_create(
                title=spec["title"],
                outlet=spec["outlet"],
                defaults={
                    "kind": spec["kind"],
                    "published_on": spec["published_on"],
                    "quote": spec["quote"],
                    "author": spec.get("author", ""),
                    "featured": spec.get("featured", False),
                    "published": True,
                },
            )
        for i, (name, kind) in enumerate(
            [
                ("Fondo Nacional de Fomento del Libro", Partner.Kind.FINANCIAMIENTO),
                ("Casa del Libro", Partner.Kind.ESPACIO),
                ("Editorial Overol", Partner.Kind.EDITORIAL),
            ]
        ):
            Partner.objects.get_or_create(name=name, defaults={"kind": kind, "position": i})

        self._summary()

    # ─────────────────────────────────────────────────────────
    ASSETS = Path(__file__).resolve().parent / "seed_assets"

    def _photo(self, alt_text, filename, credit="Placeholder de demo (reemplazable)"):
        """MediaAsset desde una imagen empaquetada en seed_assets/ (placeholder).

        Idempotente: crea el recurso por alt_text y (re)escribe el archivo solo si
        falta o si el nombre difiere — así reemplaza los antiguos colores planos en
        una BD ya sembrada sin duplicar recursos.
        """
        from django.core.files.base import ContentFile

        asset, _ = MediaAsset.objects.get_or_create(alt_text=alt_text, defaults={"credit": credit})
        current = Path(asset.file.name).name if asset.file else ""
        if current != filename:
            data = (self.ASSETS / filename).read_bytes()
            asset.file.save(filename, ContentFile(data), save=True)
        return asset

    def _audio_bytes(self):
        """WAV corto generado (1 s, tono 220 Hz): audio real y liviano para la demo."""
        import math
        import struct
        import wave
        from io import BytesIO

        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(
                b"".join(
                    struct.pack("<h", int(12000 * math.sin(2 * math.pi * 220 * i / 8000)))
                    for i in range(8000)
                )
            )
        return buffer.getvalue()

    def _pdf_bytes(self):
        """PDF mínimo válido (una página en blanco) para descargas de demostración."""
        header = b"%PDF-1.4\n"
        objs = [
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n",
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n",
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\n",
        ]
        out = bytearray(header)
        offsets = []
        for obj in objs:
            offsets.append(len(out))
            out += obj
        xref = len(out)
        out += b"xref\n0 4\n0000000000 65535 f \n"
        for offset in offsets:
            out += f"{offset:010d} 00000 n \n".encode()
        out += b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
        return bytes(out)

    def _user(self, User, username, group_name):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@resenas.cl", "is_staff": True},
        )
        if created:
            user.set_password("demo12345")
            user.save()
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        return user

    def _articles(self, now):
        return [
            {
                "slug": "resena-el-invierno-de-las-cosas",
                "title": "El invierno de las cosas: una poética de la intemperie",
                "subtitle": "El debut de Valentina Aguirre convierte el frío en método.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=2),
                "featured": True,
                "author": "Fernanda Soto",
                "work": "El invierno de las cosas",
                "tags": ["poesía", "novedad"],
                "body": body(
                    "Hay libros que se leen y libros que se habitan. El invierno de las cosas "
                    "pertenece al segundo grupo: un poemario que hace del frío una manera de mirar.",
                    "Aguirre trabaja con una economía de medios notable. Cada poema es una "
                    "estancia despojada donde el lenguaje se vuelve, por fin, temperatura.",
                ),
            },
            {
                "slug": "resena-territorio-en-fuga",
                "title": "Territorio en fuga, o la novela como mapa roto",
                "subtitle": "Ignacio Bravo escribe una geografía de la pérdida.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=6),
                "featured": False,
                "author": "Andrés Cáceres",
                "work": "Territorio en fuga",
                "tags": ["narrativa"],
                "body": body(
                    "La primera novela de Bravo avanza como quien huye: sin mirar atrás, "
                    "pero cargando todo el paisaje en la espalda.",
                    "El resultado es una prosa nerviosa, atenta al detalle, que encuentra en "
                    "la fuga no un tema sino una forma.",
                ),
            },
            {
                "slug": "resena-cuadernos-del-sur",
                "title": "Cuadernos del sur: pensar desde el margen",
                "subtitle": "El ensayo de Camila Reyes reordena nuestra cartografía crítica.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=12),
                "featured": False,
                "author": "Paula Miranda",
                "work": "Cuadernos del sur",
                "tags": ["ensayo"],
                "body": body(
                    "Reyes propone una tesis incómoda y necesaria: el centro también es un "
                    "punto de vista, y por lo tanto puede discutirse.",
                    "Sus Cuadernos son, a la vez, diario y manifiesto.",
                ),
            },
            {
                "slug": "ensayo-sobre-el-oficio-de-la-critica",
                "title": "Sobre el oficio de la crítica",
                "subtitle": "Notas para una reseña que no adula ni destruye.",
                "type": ArticleType.ENSAYO,
                "section": "Ensayos",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=4),
                "featured": True,
                "author": "Paula Miranda",
                "work": None,
                "tags": ["ensayo"],
                "body": body(
                    "Reseñar no es calificar. Es acompañar una lectura con otra lectura, "
                    "más lenta y más honesta.",
                    "La buena crítica deja el libro en mejor estado del que lo encontró: "
                    "más legible, más discutible, más vivo.",
                ),
            },
            {
                "slug": "entrevista-editorial-independiente",
                "title": "Conversación con una editorial independiente",
                "subtitle": "Hablamos sobre catálogos, riesgo y supervivencia.",
                "type": ArticleType.ENTREVISTA,
                "section": "Entrevistas",
                "status": EditorialStatus.PUBLISHED,
                "published": now - timedelta(days=8),
                "featured": False,
                "author": "Diego Salinas",
                "work": None,
                "tags": ["entrevista"],
                "body": body(
                    "«Publicar es apostar», nos dice al comenzar. Y en su caso la apuesta "
                    "tiene nombre: un catálogo pequeño y terco.",
                    "Conversamos sobre lo que significa sostener un proyecto editorial fuera "
                    "de las grandes casas.",
                ),
            },
            {
                "slug": "resena-la-casa-vacia",
                "title": "La casa vacía: el regreso como forma del duelo",
                "subtitle": "Programada — se publicará automáticamente en unos minutos.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.SCHEDULED,
                "published": now + timedelta(minutes=2),
                "featured": False,
                "author": "Fernanda Soto",
                "work": "La casa vacía",
                "tags": ["narrativa"],
                "body": body(
                    "Vergara vuelve a la casa de la infancia para comprobar que el duelo, "
                    "como el polvo, se acumula en los rincones.",
                    "Una novela sobre lo que queda cuando ya no queda nadie.",
                ),
            },
            {
                "slug": "resena-antologia-del-margen",
                "title": "Antología del margen (borrador)",
                "subtitle": "En preparación.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.DRAFT,
                "published": None,
                "featured": False,
                "author": "Andrés Cáceres",
                "work": "Antología del margen",
                "tags": ["poesía"],
                "body": body("Borrador de trabajo, aún sin enviar a revisión."),
            },
            {
                "slug": "resena-en-revision",
                "title": "Una reseña en revisión editorial",
                "subtitle": "Enviada, esperando decisión del comité.",
                "type": ArticleType.RESENA,
                "section": "Reseñas",
                "status": EditorialStatus.IN_REVIEW,
                "published": None,
                "featured": False,
                "author": "Andrés Cáceres",
                "work": None,
                "tags": ["narrativa"],
                "body": body("Texto en revisión: el comité editorial decidirá si avanza."),
            },
        ]

    def _make_article(self, spec, sections, tags, contributors, works, editora, autor_user):
        article, created = Article.objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "title": spec["title"],
                "subtitle": spec["subtitle"],
                "body": spec["body"],
                "type": spec["type"],
                "status": spec["status"],
                "featured": spec["featured"],
                "section": sections[spec["section"]],
                "owner": autor_user,
                "published_at": spec["published"],
            },
        )
        # Byline (colaborador), obra reseñada y etiquetas.
        ArticleContributor.objects.get_or_create(
            article=article,
            contributor=contributors[spec["author"]],
            defaults={"position": 0},
        )
        if spec["work"]:
            ReviewedWork.objects.get_or_create(
                article=article, work=works[spec["work"]], defaults={"is_primary": True}
            )
        article.tags.add(*[tags[t] for t in spec["tags"]])
        return article

    def _summary(self):
        pub = Article.objects.filter(status=EditorialStatus.PUBLISHED).count()
        sched = Article.objects.filter(status=EditorialStatus.SCHEDULED).count()
        members = Contributor.objects.filter(is_member=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed listo — {Article.objects.count()} artículos "
                f"({pub} publicados, {sched} programado), "
                f"{Work.objects.count()} obras, {Contributor.objects.count()} colaboradores "
                f"({members} integrantes), {Poem.objects.count()} poemas, "
                f"{Event.objects.count()} eventos, {Publication.objects.count()} publicaciones."
            )
        )
        self.stdout.write(
            "Usuarios demo: editora / autor1 (contraseña: demo12345, solo desarrollo)."
        )
