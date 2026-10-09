from django.urls import path

from . import views

urlpatterns = [
    path("", views.insights_view),
    path("advisor/", views.advisor_view),
    path("<int:id>/seen/", views.seen_view),
    path("<int:id>/accept/", views.accept_view),
    path("<int:id>/dismiss/", views.dismiss_view),
]
