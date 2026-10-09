from django.urls import path

from . import views

urlpatterns = [
    path("catalogue/", views.catalogue_view),
    path("catalogue/<slug:family>/", views.catalogue_family_view),
    path("hot/", views.hot_view),
    path("subscribe/", views.subscribe_view),
    path("my/", views.my_view),
    path("my/usage/", views.usage_view),
    path("my/renew/", views.renew_view),
    path("my/redesign/", views.redesign_view),
    path("change/", views.change_view),
    path("premium/", views.premium_view),
    path("premium/activate/", views.premium_activate_view),
]
