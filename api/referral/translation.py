"""Fields stored once per language (az, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import ReferralStep


@register(ReferralStep)
class ReferralStepTranslation(TranslationOptions):
    fields = ("title", "body")
