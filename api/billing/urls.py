from django.urls import path

from . import views

urlpatterns = [
    path("balance/", views.balance_view),
    path("transactions/", views.transactions_view),
    path("top-ups/", views.top_ups_view),
    path("top-up/methods/", views.methods_view),
    path("top-up/card/", views.top_up_card_view),
    path("top-up/akart/", views.top_up_akart_view),
    path("top-up/voucher/", views.top_up_voucher_view),
    path("top-up/google-pay/", views.top_up_google_pay_view),
    path("akart/", views.akart_view),
    path("cards/", views.cards_view),
    path("cards/<int:id>/", views.card_view),
    path("payments/", views.payments_view),
    path("pay/number/", views.pay_number_view),
    path("pay/aztelekom/", views.pay_aztelekom_view),
    path("pay/utilities/", views.pay_utilities_view),
    path("steam/accounts/", views.steam_accounts_view),
    path("steam/top-up/", views.steam_top_up_view),
    path("steam/accounts/<int:id>/", views.steam_account_view),
]
