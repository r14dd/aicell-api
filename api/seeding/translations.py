"""Stores seeded text in every language.

The seed data is written in English. `localized` expands each translated field
of a model into its `_en`, `_az` and `_ru` columns, looking the Azerbaijani and
Russian text up in `data/translations.py`. A text with no translation stops the
seed, so a catalogue row can never be saved half-translated.
"""

import re

from modeltranslation.translator import NotRegistered, translator

from .data.translations import SAME, TEXTS, UNITS

LANGUAGES = ("az", "ru")
INDEX = {"az": 0, "ru": 1}

# Keys of JSON content whose string values are shown to the subscriber.
TEXT_KEYS = {"label", "value", "text", "bold", "title", "body", "sub", "heading"}

NUMBER = re.compile(r"^[\d.,\-–+]+$")


class MissingTranslation(KeyError):
    pass


def _quantity(text: str, language: str) -> str | None:
    """Translate `5-25 GB`, `30 days`, `1-3 ₼`: numbers stay, units are looked up."""
    words = text.split(" ")
    if not all(NUMBER.match(word) or word in UNITS for word in words):
        return None
    return " ".join(UNITS[word][INDEX[language]] if word in UNITS else word for word in words)


def translate(text: str, language: str) -> str:
    if not text or text in SAME:
        return text
    if text in TEXTS:
        return TEXTS[text][INDEX[language]]
    quantity = _quantity(text, language)
    if quantity is not None:
        return quantity
    raise MissingTranslation(text)


def translate_json(value, language: str, key: str | None = None):
    """Translate the subscriber-facing strings inside JSON content."""
    if isinstance(value, dict):
        return {name: translate_json(item, language, name) for name, item in value.items()}
    if isinstance(value, list):
        # A list of plain strings under a text field (e.g. periods) is all text.
        return [translate_json(item, language, key) for item in value]
    if isinstance(value, str) and (key is None or key in TEXT_KEYS):
        return translate(value, language)
    return value


def localized(model, values: dict) -> dict:
    """Field values for `model`, with every translated field set in all languages."""
    try:
        translated = translator.get_options_for_model(model).get_field_names()
    except NotRegistered:
        return values
    result = dict(values)
    for name, value in values.items():
        if name not in translated:
            continue
        result[f"{name}_en"] = value
        for language in LANGUAGES:
            result[f"{name}_{language}"] = (
                translate(value, language)
                if isinstance(value, str)
                else translate_json(value, language)
            )
    return result
