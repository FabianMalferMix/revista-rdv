from .models import Section


def nav(request):
    """Secciones para el menú de navegación, disponibles en todas las plantillas."""
    return {"nav_sections": Section.objects.all()}
