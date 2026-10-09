from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.exceptions import NotImplementedYet
from api.common.http import (
    AmountField,
    DateRangeQuery,
    MsisdnField,
    PageQuery,
    date_range,
    iso,
    media,
    money,
    paginate,
    validated,
    validated_query,
)
from api.common.routing import Todo, route

from . import services
from .idempotency import idempotent
from .models import SavedCard, SteamAccount, TopUp, Transaction
from .presenters import top_up_json, top_up_receipt, transaction_brief, transaction_json

TAG = "billing"

TOP_UP_MIN, TOP_UP_MAX = "1.00", "500.00"
STEAM_MIN, STEAM_MAX = "1.00", "50.00"


# --- reads ------------------------------------------------------------------


@doc("Balance")
def balance(request):
    """Balance and the sum of this month's top-ups (Asia/Baku month)."""
    return {
        "balance": money(services.balance_of(request.user)),
        "currency": "AZN",
        "top_ups_this_month": money(services.top_ups_this_month(request.user)),
        "month": timezone.localtime().strftime("%Y-%m"),
    }


@doc("Recent transactions", query=PageQuery, errors=(400,))
def transactions(request):
    """Every wallet movement, newest first. Feeds Home and the Payments tab."""
    return paginate(request, Transaction.objects.filter(subscriber=request.user), transaction_json)


@doc("Top-up history", query=DateRangeQuery, errors=(400,))
def top_ups(request):
    """Newest first. `from` and `to` are inclusive dates in Asia/Baku."""
    start, end = date_range(validated_query(DateRangeQuery, request))
    queryset = TopUp.objects.filter(subscriber=request.user)
    if start:
        queryset = queryset.filter(created_at__gte=start)
    if end:
        queryset = queryset.filter(created_at__lt=end)
    return paginate(request, queryset, top_up_json)


@doc("Top-up methods")
def methods(request):
    """The list behind "Select a top-up method", with the banner and Google Pay limits."""
    return {
        "banner": {
            "image": media(request, "banner-akart.png"),
            "alt": _("Instant loan with akart! Complete your payments up to 50 ₼ with akart loan"),
            "deep_link": "/kredit/tamamla",
        },
        "methods": [
            {"key": "card", "label": _("Top up from bank card"), "deep_link": "/top-up/card"},
            {"key": "akart", "label": "akart", "deep_link": "/top-up/akart"},
            {"key": "voucher", "label": _("Voucher"), "deep_link": "/top-up/voucher"},
            {"key": "kredit", "label": _("Get Kredit"), "deep_link": "/kredit"},
        ],
        "google_pay": {
            "available": True,
            "min": TOP_UP_MIN,
            "max": TOP_UP_MAX,
            "note": _("We don't charge any fees for Google Pay top-ups"),
        },
    }


@doc("Saved cards")
def cards(request):
    """The subscriber's cards, default first (Payments tab)."""
    rows = SavedCard.objects.filter(subscriber=request.user).order_by("-is_default", "id")
    return {
        "results": [
            {
                "id": card.id,
                "brand": card.brand,
                "last4": card.last4,
                "expiry": card.expiry,
                "is_default": card.is_default,
            }
            for card in rows
        ]
    }


@doc("Saved Steam accounts")
def steam_accounts(request):
    """Accounts with their last top-up, the amount limits and the amount chips."""
    rows = SteamAccount.objects.filter(subscriber=request.user).order_by("-last_topped_at", "-id")
    return {
        "results": [
            {
                "id": account.id,
                "name": account.name,
                "last_amount": None if account.last_amount is None else money(account.last_amount),
                "last_topped_at": iso(account.last_topped_at),
            }
            for account in rows
        ],
        "limits": {"min": STEAM_MIN, "max": STEAM_MAX},
        "chips": ["5", "10", "25", "50"],
    }


# --- top-ups ----------------------------------------------------------------


class CardTopUpInput(serializers.Serializer):
    card_bin = serializers.RegexField(
        r"^\d{6}$",
        error_messages={"invalid": _("Enter the first 6 digits of the card")},
        help_text="First six digits of the card",
    )
    amount = AmountField(TOP_UP_MIN, TOP_UP_MAX, help_text="1.00 to 500.00")


class AkartTopUpInput(serializers.Serializer):
    akart_msisdn = MsisdnField(help_text="akart number as 994XXXXXXXXX")
    amount = AmountField(TOP_UP_MIN, TOP_UP_MAX, help_text="1.00 to 500.00")
    save = serializers.BooleanField(default=False, help_text="Remember the akart number")


class GooglePayInput(serializers.Serializer):
    amount = AmountField(TOP_UP_MIN, TOP_UP_MAX, help_text="1.00 to 500.00")
    payment_token = serializers.CharField(help_text='`"simulated"` completes in the demo')
    card_last4 = serializers.RegexField(r"^\d{4}$", required=False)


@doc(
    "Top up from a bank card",
    body=CardTopUpInput,
    example={"card_bin": "416300", "amount": "25.00"},
    errors=(400,),
    status=201,
)
@idempotent
def top_up_card(request):
    """Adds the amount to the balance and records the top-up and its transaction."""
    data = validated(CardTopUpInput, request)
    return top_up_receipt(*services.top_up(request.user, "card", data["amount"])), 201


@doc(
    "Top up with akart",
    body=AkartTopUpInput,
    example={"akart_msisdn": "994516643342", "amount": "20.00", "save": True},
    errors=(400,),
    status=201,
)
@idempotent
def top_up_akart(request):
    """Same as a card top-up; `save` also stores the akart number (`saved_akart`)."""
    data = validated(AkartTopUpInput, request)
    body = top_up_receipt(*services.top_up(request.user, "akart", data["amount"]))
    body["saved_akart"] = None
    if data["save"]:
        saved = services.save_akart(request.user, data["akart_msisdn"])
        body["saved_akart"] = {"id": saved.id, "msisdn": saved.msisdn}
    return body, 201


@doc(
    "Top up with Google Pay",
    body=GooglePayInput,
    example={"amount": "20.00", "payment_token": "simulated", "card_last4": "4471"},
    errors=(400, 501),
    status=201,
)
@idempotent
def top_up_google_pay(request):
    """A `simulated` token completes immediately while `GOOGLE_PAY_SIMULATED` is on.

    A real token answers `501`: verifying it with the acquirer is not built yet.
    """
    data = validated(GooglePayInput, request)
    if not (settings.GOOGLE_PAY_SIMULATED and data["payment_token"] == "simulated"):
        # TODO(acquirer): verify the real Google Pay token with the acquirer.
        raise NotImplementedYet(
            _("Google Pay token verification is not part of this prototype yet")
        )
    return top_up_receipt(*services.top_up(request.user, "google_pay", data["amount"])), 201


# --- steam ------------------------------------------------------------------


class SteamTopUpInput(serializers.Serializer):
    account = serializers.CharField(max_length=64, help_text="Steam account name")
    amount = AmountField(STEAM_MIN, STEAM_MAX, help_text="1.00 to 50.00")
    save = serializers.BooleanField(default=False, help_text="Remember the account")


@doc(
    "Top up a Steam account",
    body=SteamTopUpInput,
    example={"account": "gamer_01", "amount": "10.00", "save": True},
    errors=(400, 402),
    status=201,
)
@idempotent
def steam_top_up(request):
    """Pays the Steam account from the balance."""
    data = validated(SteamTopUpInput, request)
    steam, new_balance = services.steam_top_up(
        request.user, data["account"], data["amount"], save=data["save"]
    )
    return {
        "steam_top_up": {"id": steam.id, "account": steam.account, "amount": money(steam.amount)},
        "transaction": transaction_brief(steam.transaction),
        "balance": money(new_balance),
    }, 201


# --- routes -----------------------------------------------------------------

balance_view = route(TAG, get=balance)
transactions_view = route(TAG, get=transactions)
top_ups_view = route(TAG, get=top_ups)
methods_view = route(TAG, get=methods)
top_up_card_view = route(TAG, post=top_up_card)
top_up_akart_view = route(TAG, post=top_up_akart)
top_up_voucher_view = route(
    TAG,
    post=Todo(
        _("Voucher redemption is not part of this prototype yet"), "Redeem a 13-digit voucher"
    ),
)
top_up_google_pay_view = route(TAG, post=top_up_google_pay)
akart_view = route(
    TAG,
    get=Todo(_("Saved akart numbers are not part of this prototype yet"), "Saved akart numbers"),
)
cards_view = route(
    TAG,
    get=cards,
    post=Todo(_("Adding a card is not part of this prototype yet"), "Add a card"),
)
card_view = route(
    TAG, delete=Todo(_("Card settings are not part of this prototype yet"), "Remove a card")
)
payments_view = route(
    TAG, get=Todo(_("Payment history is not part of this prototype yet"), "Payment history")
)
pay_number_view = route(
    TAG,
    post=Todo(
        _("Paying for another number is not part of this prototype yet"),
        "Top up another Azercell number",
    ),
)
pay_aztelekom_view = route(
    TAG,
    post=Todo(
        _("Aztelekom payments are not part of this prototype yet"),
        "Pay for Aztelekom home internet",
    ),
)
pay_utilities_view = route(
    TAG,
    post=Todo(
        _("Utility payments are not part of this prototype yet"),
        "Pay for electricity, gas or water",
    ),
)
steam_accounts_view = route(TAG, get=steam_accounts)
steam_top_up_view = route(TAG, post=steam_top_up)
steam_account_view = route(
    TAG,
    delete=Todo(
        _("Removing a Steam account is not part of this prototype yet"),
        "Remove a saved Steam account",
    ),
)
