"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import ReferralStep


@register(ReferralStep)
class ReferralStepTranslation(TranslationOptions):
    fields = ("title", "body")
