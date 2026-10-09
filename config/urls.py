from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from api.common.demo_login import demo_login

urlpatterns = [
    path("admin/demo-login/<str:account>/", demo_login, name="admin-demo-login"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "api.common.exceptions.not_found_view"
handler500 = "api.common.exceptions.server_error_view"
