from django.contrib import admin
from unfold.admin import TabularInline
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, CatalogueAdmin, ReadOnlyAdmin, manat

from .models import InternetPack, PackActivation, PackCategory, RoamingPack, SocialPack, SocialPlan


@admin.register(PackActivation)
class PackActivationAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "subscriber",
        "label",
        "kind_badge",
        "status_badge",
        "auto_renew",
        "activated_at",
        "expires_at",
    )
    list_filter = (
        ("kind", ChoicesDropdownFilter),
        ("status", ChoicesDropdownFilter),
        ("auto_renew", BooleanRadioFilter),
        ("activated_at", RangeDateFilter),
        ("subscriber", AutocompleteSelectFilter),
    )
    search_fields = ("=id", "pack_id", "label", "subscriber__msisdn", "=transaction__id")
    date_hierarchy = "activated_at"
    ordering = ("-activated_at", "-id")
    list_select_related = ("subscriber", "transaction")
    fieldsets = (
        (None, {"fields": ("id", "subscriber", "kind", "pack_id", "label")}),
        ("State", {"fields": ("status", "auto_renew", "activated_at", "expires_at")}),
        ("Payment", {"fields": ("transaction",)}),
    )

    @display(description="Kind", ordering="kind", label=True)
    def kind_badge(self, obj):
        return obj.get_kind_display()

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status


@admin.register(PackCategory)
class PackCategoryAdmin(CatalogueAdmin):
    general = ("slug",)
    translated = ("label",)
    list_display = ("label", "slug", "pack_count", "order", "is_active")
    search_fields = ("slug", "label")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("packs")

    @display(description="Packs")
    def pack_count(self, obj):
        return len(obj.packs.all())


@admin.register(InternetPack)
class InternetPackAdmin(CatalogueAdmin):
    general = ("category", "slug", "price", "hours", "renews", "top_position")
    translated = ("name", "sub", "label")
    list_display = (
        "label",
        "category",
        "price_display",
        "lifetime",
        "renews",
        "top_position",
        "is_active",
    )
    list_filter = (
        ("category", RelatedDropdownFilter),
        ("renews", BooleanRadioFilter),
        ("is_active", BooleanRadioFilter),
    )
    search_fields = ("slug", "name", "label")
    list_select_related = ("category",)
    autocomplete_fields = ("category",)

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)

    @display(description="Lasts", ordering="hours")
    def lifetime(self, obj):
        days, hours = divmod(obj.hours, 24)
        return f"{days} d" if days and not hours else f"{obj.hours} h"


class SocialPlanInline(TabularInline):
    model = SocialPlan
    extra = 0
    show_change_link = True
    fields = ("slug", "title_en", "price", "validity_en", "days", "order", "is_active")


@admin.register(SocialPack)
class SocialPackAdmin(CatalogueAdmin):
    general = ("slug", "app", "price_range", ("special", "auto_renew"))
    translated = ("title", "subtitle", "volume", "periods", "cta")
    list_display = ("title", "app", "price_range", "special", "auto_renew", "order", "is_active")
    list_filter = (
        ("special", BooleanRadioFilter),
        ("auto_renew", BooleanRadioFilter),
        ("is_active", BooleanRadioFilter),
    )
    search_fields = ("slug", "title")
    inlines = (SocialPlanInline,)


@admin.register(SocialPlan)
class SocialPlanAdmin(CatalogueAdmin):
    general = ("pack", "slug", "price", "days")
    translated = ("title", "validity")
    list_display = ("title", "pack", "price_display", "days", "order", "is_active")
    list_filter = (("pack", RelatedDropdownFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("slug", "title", "pack__title")
    list_select_related = ("pack",)
    autocomplete_fields = ("pack",)

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)


@admin.register(RoamingPack)
class RoamingPackAdmin(CatalogueAdmin):
    general = ("slug", "price", "days")
    translated = ("name", "sub")
    list_display = ("name", "slug", "price_display", "days", "order", "is_active")
    search_fields = ("slug", "name")

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)
