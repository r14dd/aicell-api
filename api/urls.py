from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api.common.exceptions import not_found_view
from api.common.health import LiveView, ReadyView

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("health/", LiveView.as_view(), name="health"),
    path("health/ready/", ReadyView.as_view(), name="health-ready"),
    path("users/", include("api.users.urls")),
    path("billing/", include("api.billing.urls")),
    # Unknown API paths answer in the JSON error shape, in DEBUG too.
    re_path(r"^.*$", not_found_view),
]
