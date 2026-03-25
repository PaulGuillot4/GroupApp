"""
Root URL configuration for GroupsApp.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # API routes
    path("api/auth/", include("apps.authentication.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/groups/", include("apps.groups.urls")),
    path("api/messages/", include("apps.chat_messages.urls")),
    path("api/files/", include("apps.files.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
