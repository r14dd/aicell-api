"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import InternetPack, PackCategory, RoamingPack, SocialPack, SocialPlan


@register(InternetPack)
class InternetPackTranslation(TranslationOptions):
    fields = ("name", "sub", "label")


@register(PackCategory)
class PackCategoryTranslation(TranslationOptions):
    fields = ("label",)


@register(RoamingPack)
class RoamingPackTranslation(TranslationOptions):
    fields = ("name", "sub")


@register(SocialPack)
class SocialPackTranslation(TranslationOptions):
    fields = ("title", "subtitle", "volume", "periods", "cta")


@register(SocialPlan)
class SocialPlanTranslation(TranslationOptions):
    fields = ("title", "validity")
