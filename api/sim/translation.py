"""Fields stored once per language (az, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import SimService


@register(SimService)
class SimServiceTranslation(TranslationOptions):
    fields = ("name", "sub", "period", "sections")
