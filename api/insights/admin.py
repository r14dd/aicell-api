from django.contrib import admin
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, ReadOnlyAdmin

from .models import Insight


@admin.register(Insight)
class InsightAdmin(ReadOnlyAdmin):
    """Written by the detectors (`insights.services.refresh`); here they can only be looked at."""

    list_display = (
        "id",
        "subscriber",
        "kind_badge",
        "severity_badge",
        "status_badge",
        "offer_count",
        "created_at",
        "expires_at",
    )
    list_filter = (
        ("kind", ChoicesDropdownFilter),
        ("severity", ChoicesDropdownFilter),
        ("status", ChoicesDropdownFilter),
        ("created_at", RangeDateFilter),
        ("subscriber", AutocompleteSelectFilter),
    )
    search_fields = ("=id", "kind", "subscriber__msisdn", "subscriber__display_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("subscriber",)

    @display(description="Kind", ordering="kind", label=True)
    def kind_badge(self, obj):
        return obj.get_kind_display()

    @display(
        description="Severity", ordering="severity", label={"urgent": "danger", "info": "info"}
    )
    def severity_badge(self, obj):
        return obj.severity

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Offers")
    def offer_count(self, obj):
        return len(obj.offers)
