"""Los roles del panel y qué gestiona cada uno: la matriz de roles, en un solo lugar.

Tres grupos. El admin lo gestiona todo. El editor, todo el contenido, salvo el perfil del sitio y
las cuentas. La autora, sus textos y sus poemas, con sus autorías, sus obras reseñadas y sus
notas, y puede añadir obras al catálogo, pero no editar las que ya existen. Que solo vea sus
piezas, y que solo las edite en borrador o con cambios pedidos, lo deciden el panel y
`apps/content/permissions.py` sobre estos permisos.

Cada modelo del proyecto está aquí de forma explícita, en EDITOR_PERMISSIONS o en ADMIN_ONLY:
tests/test_roles.py falla si aparece uno sin clasificar. `setup_groups` reparte estos permisos
en cada release, sin restaurar los que el operador retiró a mano.
"""

from django.contrib.auth.models import Permission
from django.db.models import Q

# Los nombres de los grupos.
ADMIN = "admin"
EDITOR = "editor"
AUTHOR = "autor"

ALL = frozenset({"add", "change", "delete", "view"})
READ = frozenset({"view"})

# Lo que solo gestiona el admin (además de las cuentas, que no son de ninguna app del proyecto).
ADMIN_ONLY = frozenset(
    {
        "showcase.SiteProfile",
        "showcase.SiteSocialLink",
        # El registro de lo que repartió setup_groups.
        "people.RoleGrant",
        # La marca de una base de desarrollo.
        "devtools.DevelopmentMarker",
    }
)

EDITOR_PERMISSIONS = {
    "media.MediaAsset": ALL,
    "media.Recording": ALL,
    "people.Contributor": ALL,
    "people.SocialLink": ALL,
    "reviews.Publisher": ALL,
    "reviews.BookAuthor": ALL,
    "reviews.Work": ALL,
    "content.Section": ALL,
    "content.Tag": ALL,
    "content.Article": ALL,
    "content.ArticleContributor": ALL,
    "content.ReviewedWork": ALL,
    "content.Poem": ALL,
    "content.PoemContributor": ALL,
    "content.Collection": ALL,
    "content.CollectionArticle": ALL,
    "content.CollectionPoem": ALL,
    "content.Page": ALL,
    # La bitácora no se corrige a mano: cada movimiento la escribe perform_transition.
    "content.EditorialTransition": READ,
    "content.EditorialNote": ALL,
    "showcase.Publication": ALL,
    "showcase.WhereToBuy": ALL,
    "showcase.PressMention": ALL,
    "showcase.Partner": ALL,
    "agenda.Event": ALL,
    "agenda.EventPhoto": ALL,
    "agenda.Milestone": ALL,
    "community.NewsletterSubscriber": ALL,
    "submissions.Call": ALL,
    "submissions.Submission": ALL,
}

AUTHOR_PERMISSIONS = {
    "content.Article": frozenset({"add", "change", "view"}),
    "content.Poem": frozenset({"add", "change", "view"}),
    "content.ArticleContributor": ALL,
    "content.PoemContributor": ALL,
    "content.ReviewedWork": ALL,
    "content.EditorialNote": frozenset({"add", "view"}),
    "content.EditorialTransition": READ,
    "content.Section": READ,
    "content.Tag": READ,
    "reviews.Work": frozenset({"add", "view"}),
    "reviews.Publisher": frozenset({"add", "view"}),
    "reviews.BookAuthor": frozenset({"add", "view"}),
    "media.MediaAsset": frozenset({"add", "view"}),
    # Para enlazar un poema con su registro y nombrar las autorías.
    "media.Recording": READ,
    "people.Contributor": READ,
}

MATRIX = {EDITOR: EDITOR_PERMISSIONS, AUTHOR: AUTHOR_PERMISSIONS}


def permissions_for(role):
    """Los permisos de Django que la matriz da a un rol. El admin los tiene todos."""
    if role == ADMIN:
        return Permission.objects.all()
    wanted = Q(pk__in=[])
    for label, actions in MATRIX[role].items():
        app_label, model = label.lower().split(".")
        wanted |= Q(
            content_type__app_label=app_label,
            codename__in=[f"{action}_{model}" for action in actions],
        )
    return Permission.objects.filter(wanted)
