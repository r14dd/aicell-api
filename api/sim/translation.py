"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import SimService


@register(SimService)
class SimServiceTranslation(TranslationOptions):
    fields = ("name", "sub", "period", "sections")
