from django.urls import path

from . import views

urlpatterns = [
    path("plan/", views.plan_view),
    path("narrate/", views.narrate_view),
]
