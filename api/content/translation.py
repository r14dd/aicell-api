"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import (
    Banner,
    LotterySection,
    Notification,
    Offer,
    QuickAction,
    Story,
    StoryPage,
    Tournament,
)


@register(Banner)
class BannerTranslation(TranslationOptions):
    fields = ("alt",)


@register(LotterySection)
class LotterySectionTranslation(TranslationOptions):
    fields = ("title", "blocks")


@register(Notification)
class NotificationTranslation(TranslationOptions):
    fields = ("title", "body", "cta")


@register(Offer)
class OfferTranslation(TranslationOptions):
    fields = ("sub",)


@register(QuickAction)
class QuickActionTranslation(TranslationOptions):
    fields = ("label",)


@register(Story)
class StoryTranslation(TranslationOptions):
    fields = ("label",)


@register(StoryPage)
class StoryPageTranslation(TranslationOptions):
    fields = ("title", "body", "cta_label")


@register(Tournament)
class TournamentTranslation(TranslationOptions):
    fields = ("title", "prize", "cta")
