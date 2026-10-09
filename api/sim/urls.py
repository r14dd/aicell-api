from django.urls import path

from . import views

urlpatterns = [
    path("", views.overview_view),
    path("line/", views.line_view),
    path("line/internet-settings/", views.internet_settings_view),
    path("line/status/", views.line_status_view),
    path("line/close/", views.line_close_view),
    path("call-forwarding/", views.call_forwarding_view),
    path("roaming/", views.roaming_view),
    path("roaming/countries/", views.roaming_countries_view),
    path("sms/", views.sms_view),
    path("puk/", views.puk_view),
    path("services/", views.services_view),
    path("services/<slug:slug>/", views.service_view),
    path("services/<slug:slug>/subscribe/", views.service_subscribe_view),
    path("services/<slug:slug>/deactivate/", views.service_deactivate_view),
    path("esim/", views.esim_view),
    path("esim/transfer/", views.esim_transfer_view),
    path("esim/recover/", views.esim_recover_view),
]
