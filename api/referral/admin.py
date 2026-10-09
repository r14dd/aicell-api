from django.contrib import admin
from unfold.contrib.filters.admin import RangeNumericFilter
from unfold.decorators import display

from api.common.admin import BaseAdmin, CatalogueAdmin, manat

from .models import ReferralProfile, ReferralStep


@admin.register(ReferralProfile)
class ReferralProfileAdmin(BaseAdmin):
    list_display = ("code", "subscriber", "earned_display")
    list_filter = (("earned", RangeNumericFilter),)
    search_fields = ("code", "subscriber__msisdn", "subscriber__display_name")
    ordering = ("-earned", "-id")
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("earned",)
    fieldsets = ((None, {"fields": ("subscriber", "code", "earned")}),)

    @display(description="Earned", ordering="earned")
    def earned_display(self, obj):
        return manat(obj.earned)


@admin.register(ReferralStep)
class ReferralStepAdmin(CatalogueAdmin):
    """The rules shown on the "Invite & earn" page, in order."""

    translated = ("title", "body")
    list_display = ("title", "order", "is_active")
    search_fields = ("title", "body")
