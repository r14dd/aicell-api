from django.contrib import admin
from unfold.admin import TabularInline
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import display

from api.common.admin import BaseAdmin, CatalogueAdmin, manat

from .models import (
    ChangeCard,
    ChangeGroup,
    PremiumBenefit,
    PriceGroup,
    RedesignSlider,
    SubscriberTariff,
    TariffFamily,
    TariffPlan,
)


@admin.register(SubscriberTariff)
class SubscriberTariffAdmin(BaseAdmin):
    list_display = (
        "subscriber",
        "title",
        "price_display",
        "data_left",
        "minutes_left",
        "next_payment_at",
    )
    list_filter = ("family", ("next_payment_at", RangeDateFilter))
    search_fields = ("subscriber__msisdn", "subscriber__display_name", "title")
    date_hierarchy = "next_payment_at"
    ordering = ("-next_payment_at",)
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("activated_at", "last_payment_at")
    fieldsets = (
        (None, {"fields": ("subscriber", "family", "title", "price", "validity_days")}),
        ("Payments", {"fields": ("activated_at", "last_payment_at", "next_payment_at")}),
        (
            "Remaining",
            {
                "fields": (
                    ("data_remaining_gb", "data_total_gb"),
                    ("messaging_remaining_mb", "messaging_total_gb"),
                    ("minutes_remaining", "minutes_total"),
                )
            },
        ),
        ("Redesign", {"fields": ("redesign",)}),
    )

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)

    @display(description="Internet left", ordering="data_remaining_gb")
    def data_left(self, obj):
        return f"{obj.data_remaining_gb} / {obj.data_total_gb} GB"

    @display(description="Minutes left", ordering="minutes_remaining")
    def minutes_left(self, obj):
        return f"{obj.minutes_remaining} / {obj.minutes_total}"


class PlanInline(TabularInline):
    model = TariffPlan
    extra = 0
    show_change_link = True
    fields = ("slug", "title_en", "price", "hot", "is_default", "order", "is_active")


@admin.register(TariffFamily)
class TariffFamilyAdmin(CatalogueAdmin):
    general = ("slug", "badges", "is_premium")
    translated = ("name", "subtitle")
    list_display = ("name", "slug", "plan_count", "is_premium", "order", "is_active")
    list_filter = (("is_premium", BooleanRadioFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("slug", "name")
    inlines = (PlanInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("plans")

    @display(description="Plans")
    def plan_count(self, obj):
        return len(obj.plans.all())


@admin.register(TariffPlan)
class TariffPlanAdmin(CatalogueAdmin):
    general = ("family", "slug", "price", ("hot", "is_default"))
    translated = ("title", "features", "hot_features")
    list_display = (
        "title",
        "family",
        "price_display",
        "hot",
        "is_default",
        "hot_position",
        "is_active",
    )
    list_filter = (
        ("family", RelatedDropdownFilter),
        ("hot", BooleanRadioFilter),
        ("is_active", BooleanRadioFilter),
    )
    search_fields = ("slug", "title")
    list_select_related = ("family",)
    autocomplete_fields = ("family",)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        hot_offer = ("Hot offers shelf", {"fields": ("hot_position", "hot_socials")})
        return [*fieldsets[:-1], hot_offer, fieldsets[-1]]

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)


@admin.register(PriceGroup)
class PriceGroupAdmin(CatalogueAdmin):
    general = ("tone",)
    translated = ("heading", "rows")
    list_display = ("heading", "tone_badge", "row_count", "order", "is_active")
    list_filter = (("tone", ChoicesDropdownFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("heading",)

    @display(description="Tone", ordering="tone", label={"secondary": "info", "red": "danger"})
    def tone_badge(self, obj):
        return obj.tone

    @display(description="Rows")
    def row_count(self, obj):
        return len(obj.rows)


class CardInline(TabularInline):
    model = ChangeCard
    extra = 0
    show_change_link = True
    fields = ("slug", "title_en", "price", "is_new", "family", "order", "is_active")
    autocomplete_fields = ("family",)


@admin.register(ChangeGroup)
class ChangeGroupAdmin(CatalogueAdmin):
    general = ("slug",)
    translated = ("title",)
    list_display = ("title", "slug", "card_count", "order", "is_active")
    search_fields = ("slug", "title")
    inlines = (CardInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("cards")

    @display(description="Cards")
    def card_count(self, obj):
        return len(obj.cards.all())


@admin.register(ChangeCard)
class ChangeCardAdmin(CatalogueAdmin):
    general = ("group", "slug", "price", "is_new", "socials", "family")
    translated = ("title", "period", "tagline", "features")
    list_display = ("title", "group", "price", "is_new", "family", "order", "is_active")
    list_filter = (
        ("group", RelatedDropdownFilter),
        ("is_new", BooleanRadioFilter),
        ("is_active", BooleanRadioFilter),
    )
    search_fields = ("slug", "title")
    list_select_related = ("group", "family")
    autocomplete_fields = ("group", "family")


@admin.register(PremiumBenefit)
class PremiumBenefitAdmin(CatalogueAdmin):
    general = ("key",)
    translated = ("text",)
    list_display = ("text", "key", "order", "is_active")
    search_fields = ("key", "text")


@admin.register(RedesignSlider)
class RedesignSliderAdmin(CatalogueAdmin):
    general = ("key", ("minimum", "maximum", "step"))
    translated = ("label",)
    list_display = ("label", "key", "minimum", "maximum", "step", "order", "is_active")
    search_fields = ("key", "label")
