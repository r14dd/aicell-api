from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.me_view),
    path("terms/", views.terms_view),
    path("events/", views.events_view),
]
