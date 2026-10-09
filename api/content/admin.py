from django.contrib import admin
from modeltranslation.admin import TranslationAdmin
from unfold.admin import TabularInline
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import display

from api.common.admin import BaseAdmin, CatalogueAdmin, ReadOnlyAdmin, language_tabs, manat

from .models import (
    AppRating,
    Banner,
    Game,
    LotterySection,
    Notification,
    Offer,
    QuickAction,
    Story,
    StoryPage,
    StoryView,
    Tournament,
)

SUBSCRIBER_SEARCH = ("subscriber__msisdn", "subscriber__display_name")


# --- per-subscriber ---------------------------------------------------------


@admin.register(Notification)
class NotificationAdmin(BaseAdmin, TranslationAdmin):
    list_display = ("title", "subscriber", "slug", "is_read", "sent_at")
    list_filter = (("sent_at", RangeDateFilter), ("read_at", RangeDateFilter))
    search_fields = ("slug", "title", *SUBSCRIBER_SEARCH)
    date_hierarchy = "sent_at"
    ordering = ("-sent_at", "-id")
    list_select_related = ("subscriber",)
    autocomplete_fields = ("subscriber",)
    readonly_fields = ("read_at",)
    fieldsets = (
        (None, {"fields": ("subscriber", "slug")}),
        *language_tabs("title", "body", "cta"),
        ("Dates", {"fields": ("sent_at", "read_at")}),
    )

    @display(description="Read", boolean=True, ordering="read_at")
    def is_read(self, obj):
        return obj.read_at is not None


@admin.register(StoryView)
class StoryViewAdmin(ReadOnlyAdmin):
    list_display = ("subscriber", "story_key", "viewed_at")
    list_filter = ("story_key", ("viewed_at", RangeDateFilter))
    search_fields = ("story_key", *SUBSCRIBER_SEARCH)
    date_hierarchy = "viewed_at"
    ordering = ("-viewed_at",)
    list_select_related = ("subscriber",)


@admin.register(AppRating)
class AppRatingAdmin(ReadOnlyAdmin):
    list_display = ("subscriber", "stars_display", "created_at")
    list_filter = ("stars", ("created_at", RangeDateFilter))
    search_fields = SUBSCRIBER_SEARCH
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("subscriber",)

    @display(description="Stars", ordering="stars")
    def stars_display(self, obj):
        return "★" * obj.stars + "☆" * (5 - obj.stars)


# --- catalogue --------------------------------------------------------------


class StoryPageInline(TabularInline):
    model = StoryPage
    extra = 0
    show_change_link = True
    fields = ("title_en", "image", "cta_deep_link", "duration_ms", "order", "is_active")


@admin.register(Story)
class StoryAdmin(CatalogueAdmin):
    general = ("key", "image")
    translated = ("label",)
    list_display = ("label", "key", "image", "page_count", "order", "is_active")
    search_fields = ("key", "label")
    inlines = (StoryPageInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("pages")

    @display(description="Pages")
    def page_count(self, obj):
        return len(obj.pages.all())


@admin.register(StoryPage)
class StoryPageAdmin(CatalogueAdmin):
    general = ("story", "image", "cta_deep_link", "duration_ms")
    translated = ("title", "body", "cta_label")
    list_display = ("title", "story", "image", "cta_deep_link", "duration_ms", "order", "is_active")
    list_filter = (("story", RelatedDropdownFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("title", "body", "story__key")
    list_select_related = ("story",)
    autocomplete_fields = ("story",)


@admin.register(QuickAction)
class QuickActionAdmin(CatalogueAdmin):
    general = ("key", "deep_link")
    translated = ("label",)
    list_display = ("label", "key", "deep_link", "order", "is_active")
    search_fields = ("key", "label")


@admin.register(Banner)
class BannerAdmin(CatalogueAdmin):
    general = ("placement", "key", "image", "deep_link")
    translated = ("alt",)
    list_display = ("key", "placement_badge", "alt", "deep_link", "order", "is_active")
    list_filter = (("placement", ChoicesDropdownFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("key", "alt")
    ordering = ("placement", "order", "id")

    @display(description="Placement", ordering="placement", label=True)
    def placement_badge(self, obj):
        return obj.get_placement_display()


@admin.register(LotterySection)
class LotterySectionAdmin(CatalogueAdmin):
    general = ("icon",)
    translated = ("title", "blocks")
    list_display = ("title", "icon", "block_count", "order", "is_active")
    search_fields = ("title",)

    @display(description="Blocks")
    def block_count(self, obj):
        return len(obj.blocks)


@admin.register(Game)
class GameAdmin(BaseAdmin):
    list_display = ("name", "slug", "image", "is_reward", "order", "is_active")
    list_filter = (("is_reward", BooleanRadioFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("slug", "name")
    ordering = ("order", "id")
    fieldsets = (
        (None, {"fields": ("slug", "name", "image", "is_reward")}),
        ("Placement", {"fields": ("order", "is_active")}),
    )


@admin.register(Tournament)
class TournamentAdmin(CatalogueAdmin):
    general = ("game", "participants", "ends_at")
    translated = ("title", "prize", "cta")
    list_display = ("title", "game", "prize", "participants", "ends_at", "is_active")
    list_filter = (("ends_at", RangeDateFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("title", "game__name")
    date_hierarchy = "ends_at"
    list_select_related = ("game",)
    autocomplete_fields = ("game",)


@admin.register(Offer)
class OfferAdmin(CatalogueAdmin):
    general = ("kind", "slug", "name", "price", "image", "deep_link")
    translated = ("sub",)
    list_display = ("name", "kind_badge", "slug", "price_display", "order", "is_active")
    list_filter = (("kind", ChoicesDropdownFilter), ("is_active", BooleanRadioFilter))
    search_fields = ("slug", "name")
    ordering = ("kind", "order", "id")

    @display(description="Kind", ordering="kind", label=True)
    def kind_badge(self, obj):
        return obj.get_kind_display()

    @display(description="Price", ordering="price")
    def price_display(self, obj):
        return manat(obj.price)
