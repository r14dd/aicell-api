"""Fields stored once per language (az, ru, en) by django-modeltranslation."""

from modeltranslation.translator import TranslationOptions, register

from .models import KreditProduct


@register(KreditProduct)
class KreditProductTranslation(TranslationOptions):
    fields = ("subtitle", "chip")
