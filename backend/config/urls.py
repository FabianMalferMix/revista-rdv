from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.content.feeds import LatestArticlesFeed
from apps.content.sitemaps import SITEMAPS
from apps.content.views import healthz, robots
from apps.media.feeds import RecordingsFeed

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("feed/", LatestArticlesFeed(), name="feed"),
    path("feed/registros/", RecordingsFeed(), name="recordings_feed"),
    path("robots.txt", robots, name="robots"),
    path("", include("apps.people.urls")),
    path("", include("apps.media.urls")),
    path("", include("apps.agenda.urls")),
    path("", include("apps.showcase.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.submissions.urls")),
    path("", include("apps.content.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Títulos del panel editorial
admin.site.site_header = "Reseñas — Panel editorial"
admin.site.site_title = "Reseñas"
admin.site.index_title = "Administración"
