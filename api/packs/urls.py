from django.urls import path

from . import views

urlpatterns = [
    path("internet/", views.internet_view),
    path("internet/top/", views.internet_top_view),
    path("internet/purchase/", views.internet_purchase_view),
    path("social/<slug:slug>/", views.social_view),
    path("social/<slug:slug>/activate/", views.social_activate_view),
    path("roaming/", views.roaming_view),
    path("roaming/purchase/", views.roaming_purchase_view),
    path("active/", views.active_view),
]
