"""Carga datos de demostración para desarrollo. Idempotente: se puede repetir.

docker compose exec web python manage.py seed_demo
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.community.models import Comment, NewsletterSubscriber
from apps.content.models import (
    Article,
    ArticleContributor,
    ArticleStatus,
    ArticleType,
    Dossier,
    DossierArticle,
    DossierStatus,
    Page,
    ReviewedWork,
    Section,
    Tag,
)
from apps.people.models import Contributor
from apps.reviews.models import BookAuthor, Publisher, Work
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

        # ── Artículos en varios estados ──────────────────────
        articles = {}
        for spec in self._articles(now):
            articles[spec["slug"]] = self._make_article(
                spec, sections, tags, contributors, works, editora, autor_user
            )

        # ── Dosier con artículos publicados ──────────────────
        dossier, _ = Dossier.objects.get_or_create(
            slug="nuevas-voces",
            defaults={
                "title": "Nuevas voces",
                "description": "Un recorrido por la narrativa y poesía chilena reciente.",
                "intro": "Cinco lecturas para entrar al año literario.",
                "status": DossierStatus.PUBLISHED,
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
                DossierArticle.objects.get_or_create(
                    dossier=dossier, article=articles[slug], defaults={"position": i}
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
                "<p>Reseñas es una revista literaria dedicada a la crítica de libros. "
                "Publicamos reseñas, ensayos y entrevistas sobre narrativa y poesía "
                "contemporáneas.</p>",
            ),
            (
                "bases",
                "Bases de colaboración",
                "<p>Recibimos reseñas inéditas de entre 4.000 y 8.000 caracteres. "
                "Envía tu propuesta desde la página de colaboraciones y el comité "
                "editorial te responderá.</p>",
            ),
        ]:
            Page.objects.get_or_create(
                slug=slug,
                defaults={"title": title, "body": html, "status": DossierStatus.PUBLISHED},
            )

        self._summary()

    # ─────────────────────────────────────────────────────────
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
                "status": ArticleStatus.PUBLISHED,
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
                "status": ArticleStatus.PUBLISHED,
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
                "status": ArticleStatus.PUBLISHED,
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
                "status": ArticleStatus.PUBLISHED,
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
                "status": ArticleStatus.PUBLISHED,
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
                "status": ArticleStatus.SCHEDULED,
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
                "status": ArticleStatus.DRAFT,
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
                "status": ArticleStatus.IN_REVIEW,
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
        pub = Article.objects.filter(status=ArticleStatus.PUBLISHED).count()
        sched = Article.objects.filter(status=ArticleStatus.SCHEDULED).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed listo — {Article.objects.count()} artículos "
                f"({pub} publicados, {sched} programado), "
                f"{Work.objects.count()} obras, {Contributor.objects.count()} colaboradores."
            )
        )
        self.stdout.write(
            "Usuarios demo: editora / autor1 (contraseña: demo12345, solo desarrollo)."
        )
