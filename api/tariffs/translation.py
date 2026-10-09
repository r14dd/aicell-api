"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import (
    ChangeCard,
    ChangeGroup,
    PremiumBenefit,
    PriceGroup,
    RedesignSlider,
    TariffFamily,
    TariffPlan,
)


@register(ChangeCard)
class ChangeCardTranslation(TranslationOptions):
    fields = ("title", "period", "tagline", "features")


@register(ChangeGroup)
class ChangeGroupTranslation(TranslationOptions):
    fields = ("title",)


@register(PremiumBenefit)
class PremiumBenefitTranslation(TranslationOptions):
    fields = ("text",)


@register(PriceGroup)
class PriceGroupTranslation(TranslationOptions):
    fields = ("heading", "rows")


@register(RedesignSlider)
class RedesignSliderTranslation(TranslationOptions):
    fields = ("label",)


@register(TariffFamily)
class TariffFamilyTranslation(TranslationOptions):
    fields = ("name", "subtitle")


@register(TariffPlan)
class TariffPlanTranslation(TranslationOptions):
    fields = ("title", "features", "hot_features")
