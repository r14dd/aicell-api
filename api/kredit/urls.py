from django.urls import path

from . import views

urlpatterns = [
    path("", views.overview_view),
    path("products/<slug:slug>/", views.product_view),
    path("products/<slug:slug>/take/", views.take_view),
    path("tamamla/", views.tamamla_view),
]
