from django.contrib import admin
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
    RangeNumericFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, BaseAdmin, ReadOnlyAdmin, manat, signed_manat

from .models import (
    IdempotencyKey,
    SavedAkart,
    SavedCard,
    SteamAccount,
    SteamTopUp,
    TopUp,
    Transaction,
    Wallet,
)

SUBSCRIBER_SEARCH = ("subscriber__msisdn", "subscriber__display_name")


@admin.register(Wallet)
class WalletAdmin(ReadOnlyAdmin):
    """Balances change only through transactions, so wallets are read-only here."""

    list_display = ("subscriber", "holder", "balance_display")
    list_filter = (("balance", RangeNumericFilter),)
    search_fields = SUBSCRIBER_SEARCH
    ordering = ("-balance",)
    list_select_related = ("subscriber",)

    @display(description="Name", ordering="subscriber__display_name")
    def holder(self, obj):
        return obj.subscriber.display_name or "—"

    @display(description="Balance", ordering="balance")
    def balance_display(self, obj):
        return manat(obj.balance)


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdmin):
    list_display = ("id", "subscriber", "kind_badge", "title", "amount_display", "created_at")
    list_filter = (
        ("kind", ChoicesDropdownFilter),
        ("created_at", RangeDateFilter),
        ("amount", RangeNumericFilter),
        ("subscriber", AutocompleteSelectFilter),
    )
    search_fields = ("=id", "title", *SUBSCRIBER_SEARCH)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber",)
    fieldsets = (
        (None, {"fields": ("id", "subscriber", "kind", "title")}),
        ("Money", {"fields": ("amount", "created_at")}),
    )

    @display(
        description="Kind",
        ordering="kind",
        label={"top_up": "success", "purchase": "info", "payment": "warning", "credit": "danger"},
    )
    def kind_badge(self, obj):
        return obj.kind

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return signed_manat(obj.amount)


@admin.register(TopUp)
class TopUpAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "subscriber",
        "method_badge",
        "amount_display",
        "status_badge",
        "created_at",
    )
    list_filter = (
        ("method", ChoicesDropdownFilter),
        ("status", ChoicesDropdownFilter),
        ("created_at", RangeDateFilter),
        ("amount", RangeNumericFilter),
    )
    search_fields = ("=id", "=transaction__id", *SUBSCRIBER_SEARCH)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber", "transaction")
    fieldsets = (
        (None, {"fields": ("id", "subscriber", "method", "status")}),
        ("Money", {"fields": ("amount", "transaction", "created_at")}),
    )

    @display(description="Method", ordering="method", label=True)
    def method_badge(self, obj):
        return obj.get_method_display()

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return manat(obj.amount)


@admin.register(SavedCard)
class SavedCardAdmin(BaseAdmin):
    list_display = ("subscriber", "brand", "masked", "expiry", "is_default")
    list_filter = ("brand", ("is_default", BooleanRadioFilter))
    search_fields = ("last4", *SUBSCRIBER_SEARCH)
    ordering = ("-id",)
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    fieldsets = (
        (None, {"fields": ("subscriber",)}),
        ("Card", {"fields": ("brand", "last4", "expiry", "is_default")}),
    )

    @display(description="Number", ordering="last4")
    def masked(self, obj):
        return f"•••• {obj.last4}"


@admin.register(SavedAkart)
class SavedAkartAdmin(BaseAdmin):
    list_display = ("id", "subscriber", "msisdn")
    list_filter = (("subscriber", AutocompleteSelectFilter),)
    search_fields = ("msisdn", *SUBSCRIBER_SEARCH)
    ordering = ("-id",)
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)


@admin.register(SteamAccount)
class SteamAccountAdmin(BaseAdmin):
    list_display = ("name", "subscriber", "last_amount_display", "last_topped_at")
    list_filter = (("last_topped_at", RangeDateFilter),)
    search_fields = ("name", *SUBSCRIBER_SEARCH)
    date_hierarchy = "last_topped_at"
    ordering = ("-last_topped_at", "-id")
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("last_amount", "last_topped_at")
    fieldsets = (
        (None, {"fields": ("subscriber", "name")}),
        ("Last top-up", {"fields": ("last_amount", "last_topped_at")}),
    )

    @display(description="Last amount", ordering="last_amount")
    def last_amount_display(self, obj):
        return manat(obj.last_amount)


@admin.register(SteamTopUp)
class SteamTopUpAdmin(ReadOnlyAdmin):
    list_display = ("id", "subscriber", "account", "amount_display", "created_at")
    list_filter = (("created_at", RangeDateFilter), ("amount", RangeNumericFilter))
    search_fields = ("=id", "account", "=transaction__id", *SUBSCRIBER_SEARCH)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber", "transaction")

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return manat(obj.amount)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(ReadOnlyAdmin):
    list_display = ("key", "subscriber", "path", "status_badge", "created_at")
    list_filter = (("created_at", RangeDateFilter), "status")
    search_fields = ("=key", "path", *SUBSCRIBER_SEARCH)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber",)

    @display(description="Answer", ordering="status", label={201: "success", 200: "success"})
    def status_badge(self, obj):
        return obj.status
