from django.urls import path

from . import views

urlpatterns = [
    path("otp/send/", views.otp_send),
    path("otp/verify/", views.otp_verify),
    path("token/refresh/", views.token_refresh),
    path("logout/", views.logout),
    path("me/", views.me_view),
    path("me/app-settings/", views.app_settings),
    path("devices/", views.devices),
]
