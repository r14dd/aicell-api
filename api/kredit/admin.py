from django.contrib import admin
from unfold.contrib.filters.admin import BooleanRadioFilter, RangeDateFilter
from unfold.decorators import display

from api.common.admin import BaseAdmin, CatalogueAdmin, manat

from .models import CreditDebt, KreditProduct


@admin.register(CreditDebt)
class CreditDebtAdmin(BaseAdmin):
    list_display = (
        "id",
        "subscriber",
        "name",
        "amount_display",
        "fee_display",
        "repaid",
        "created_at",
    )
    list_filter = ("product", ("created_at", RangeDateFilter), ("repaid_at", RangeDateFilter))
    search_fields = ("=id", "name", "subscriber__msisdn", "subscriber__display_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("subscriber", "product", "name")}),
        ("Money", {"fields": ("amount", "fee")}),
        ("Dates", {"fields": ("created_at", "repaid_at")}),
    )

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return manat(obj.amount)

    @display(description="Fee", ordering="fee")
    def fee_display(self, obj):
        return manat(obj.fee)

    @display(description="Repaid", boolean=True, ordering="repaid_at")
    def repaid(self, obj):
        return obj.repaid_at is not None


@admin.register(KreditProduct)
class KreditProductAdmin(CatalogueAdmin):
    general = (
        "slug",
        "name",
        ("amount", "fee"),
        "options",
        ("amount_mb", "validity_days"),
        ("chip_icon", "price_label"),
    )
    translated = ("subtitle", "chip")
    list_display = ("name", "slug", "amount_display", "fee_display", "chip", "order", "is_active")
    list_filter = (("is_active", BooleanRadioFilter),)
    search_fields = ("slug", "name")

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return manat(obj.amount)

    @display(description="Fee", ordering="fee")
    def fee_display(self, obj):
        return manat(obj.fee)
