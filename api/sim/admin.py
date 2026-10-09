from django.contrib import admin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, BaseAdmin, CatalogueAdmin, ReadOnlyAdmin, manat

from .models import ServiceSubscription, SimProfile, SimService


@admin.register(SimProfile)
class SimProfileAdmin(BaseAdmin):
    list_display = (
        "subscriber",
        "status_badge",
        "lte_enabled",
        "mobile_internet",
        "roaming_enabled",
        "sms_language",
        "deactivation_date",
    )
    list_filter = (
        ("line_status", ChoicesDropdownFilter),
        ("lte_enabled", BooleanRadioFilter),
        ("roaming_enabled", BooleanRadioFilter),
        ("deactivation_date", RangeDateFilter),
    )
    search_fields = ("subscriber__msisdn", "subscriber__display_name")
    date_hierarchy = "deactivation_date"
    ordering = ("-id",)
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("roaming_changed_at", "puk1", "puk2")
    fieldsets = (
        (None, {"fields": ("subscriber", "line_status", "lte_enabled")}),
        ("Dates", {"fields": ("one_way_blocking_date", "deactivation_date")}),
        ("Line", {"classes": ["tab"], "fields": ("mobile_internet", "second_line")}),
        (
            "Call forwarding",
            {
                "classes": ["tab"],
                "fields": (
                    "forward_all",
                    "forward_unanswered",
                    "forward_busy",
                    "forward_unreachable",
                ),
            },
        ),
        ("Roaming", {"classes": ["tab"], "fields": ("roaming_enabled", "roaming_changed_at")}),
        (
            "SMS",
            {
                "classes": ["tab"],
                "fields": ("sms_language", "sms_ads", "sms_campaigns", "sms_partners"),
            },
        ),
        ("PUK", {"classes": ["tab"], "fields": ("puk1", "puk2")}),
    )

    @display(description="Line", ordering="line_status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.line_status


@admin.register(ServiceSubscription)
class ServiceSubscriptionAdmin(ReadOnlyAdmin):
    list_display = ("id", "subscriber", "service", "status_badge", "created_at", "next_payment_at")
    list_filter = (
        "service",
        ("status", ChoicesDropdownFilter),
        ("created_at", RangeDateFilter),
        ("next_payment_at", RangeDateFilter),
    )
    search_fields = ("=id", "service", "subscriber__msisdn", "=transaction__id")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber", "transaction")

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status


@admin.register(SimService)
class SimServiceAdmin(CatalogueAdmin):
    general = ("slug", "price", "days", "auto_renew")
    translated = ("name", "sub", "period", "sections")
    list_display = ("name", "slug", "price_display", "days", "auto_renew", "order", "is_active")
    list_filter = (("auto_renew", BooleanRadioFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("slug", "name")

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)
