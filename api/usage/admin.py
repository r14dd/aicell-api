from django.contrib import admin
from django.urls import path
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, CatalogueAdmin, ReadOnlyAdmin, manat

from . import taxonomy
from .models import AppUsage, DailyUsage, OfferRule, PersonalOffer, SubscriberInsight
from .statistics_admin import StatisticsView

SUBSCRIBER_SEARCH = ("subscriber__msisdn", "subscriber__display_name")


@admin.register(DailyUsage)
class DailyUsageAdmin(ReadOnlyAdmin):
    """Usage arrives through `usage.services.record_usage`; here it can only be looked at."""

    list_display = (
        "subscriber",
        "day",
        "data_mb",
        "call_minutes",
        "sms",
        "roaming_data_mb",
        "roaming_minutes",
    )
    list_filter = (("day", RangeDateFilter), ("subscriber", AutocompleteSelectFilter))
    search_fields = SUBSCRIBER_SEARCH
    date_hierarchy = "day"
    ordering = ("-day", "subscriber")
    list_select_related = ("subscriber",)

    def get_urls(self):
        """The statistics page lives beside the rows it is computed from."""
        statistics = self.admin_site.admin_view(StatisticsView.as_view(model_admin=self))
        return [path("statistics/", statistics, name="usage_statistics"), *super().get_urls()]


@admin.register(AppUsage)
class AppUsageAdmin(ReadOnlyAdmin):
    list_display = ("subscriber", "day", "app", "category", "data_mb")
    list_filter = ("app", ("day", RangeDateFilter), ("subscriber", AutocompleteSelectFilter))
    search_fields = ("app", *SUBSCRIBER_SEARCH)
    date_hierarchy = "day"
    ordering = ("-day", "subscriber", "-data_mb")
    list_select_related = ("subscriber",)

    @display(description="Category", label=True)
    def category(self, obj):
        return taxonomy.APP_CATEGORY.get(obj.app, "?")


@admin.register(OfferRule)
class OfferRuleAdmin(CatalogueAdmin):
    """A rule gives every subscriber of a segment one offer; `refresh_offers` applies it."""

    general = ("segment", ("target_kind", "target_id"), ("offer_price", "valid_days"))
    translated = ("reason",)
    list_display = (
        "segment_badge",
        "target_kind",
        "target_id",
        "price_display",
        "valid_days",
        "order",
        "is_active",
    )
    list_filter = (
        ("segment", ChoicesDropdownFilter),
        ("target_kind", ChoicesDropdownFilter),
        ("is_active", BooleanRadioFilter),
    )
    search_fields = ("target_id", "reason")

    @display(description="Segment", ordering="segment", label=True)
    def segment_badge(self, obj):
        return obj.get_segment_display()

    @display(description="Offer price", ordering="offer_price")
    def price_display(self, obj):
        return manat(obj.offer_price)


@admin.register(PersonalOffer)
class PersonalOfferAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "subscriber",
        "target_id",
        "prices",
        "status_badge",
        "created_at",
        "expires_at",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("target_kind", ChoicesDropdownFilter),
        ("created_at", RangeDateFilter),
        ("subscriber", AutocompleteSelectFilter),
    )
    search_fields = ("=id", "target_id", *SUBSCRIBER_SEARCH)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber", "rule")

    @display(description="Offer / normal", ordering="offer_price")
    def prices(self, obj):
        return f"{manat(obj.offer_price)} / {manat(obj.normal_price)}"

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status


@admin.register(SubscriberInsight)
class SubscriberInsightAdmin(ReadOnlyAdmin):
    """Written by `usage.insights.refresh` every hour; the statistics page counts these rows."""

    list_display = (
        "subscriber",
        "segment_badge",
        "data_mb",
        "minutes",
        "spend_display",
        "saving_display",
        "recommendation",
        "refreshed_at",
    )
    list_filter = (
        ("segment", ChoicesDropdownFilter),
        ("refreshed_at", RangeDateFilter),
        ("subscriber", AutocompleteSelectFilter),
    )
    search_fields = ("recommendation", *SUBSCRIBER_SEARCH)
    date_hierarchy = "refreshed_at"
    ordering = ("-saving", "subscriber")
    list_select_related = ("subscriber",)

    @display(description="Segment", ordering="segment", label=True)
    def segment_badge(self, obj):
        return obj.get_segment_display()

    @display(description="Paid in 30 days", ordering="spend")
    def spend_display(self, obj):
        return manat(obj.spend)

    @display(description="Could save", ordering="saving")
    def saving_display(self, obj):
        return manat(obj.saving)
