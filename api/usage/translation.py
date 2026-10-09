"""Fields stored once per language (az, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import OfferRule


@register(OfferRule)
class OfferRuleTranslation(TranslationOptions):
    fields = ("reason",)
