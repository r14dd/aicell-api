from django.urls import path

from . import views

urlpatterns = [
    path("summary/", views.summary_view),
    path("recommendations/", views.recommendations_view),
    path("offers/<int:id>/accept/", views.offer_accept_view),
    path("offers/<int:id>/decline/", views.offer_decline_view),
]
