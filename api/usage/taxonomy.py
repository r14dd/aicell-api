"""Apps, their categories, and what can be sold for each category.

This is the one place that knows them. A usage row stores only the app key;
the category is looked up here, so regrouping apps needs no migration.
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

# Every app belongs to exactly one category.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "video": ("youtube", "kinon"),
    "social": ("instagram_facebook", "tiktok"),
    "messaging": ("whatsapp", "telegram"),
    "games": ("games", "steam"),
    "other": ("teams", "other"),
}

APP_CATEGORY: dict[str, str] = {
    app: category for category, apps in CATEGORIES.items() for app in apps
}
APPS: tuple[str, ...] = tuple(APP_CATEGORY)

CATEGORY_LABELS = {
    "video": _("Video"),
    "social": _("Social networks"),
    "messaging": _("Messaging"),
    "games": _("Games"),
    "other": _("Other"),
}

# Brand names read the same in every language; only the generic ones are translated.
APP_LABELS = {
    "youtube": "YouTube",
    "kinon": "Kinon",
    "instagram_facebook": "Instagram & Facebook",
    "tiktok": "TikTok",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "games": _("Games"),
    "steam": "Steam",
    "teams": "Microsoft Teams",
    "other": _("Other"),
}


@dataclass(frozen=True)
class Sells:
    """Something in the catalogue that answers a category's usage."""

    kind: str  # social_pack | app_offer | redesign | tariff_messaging
    target_id: str = ""


# What can be sold for a category. An empty tuple means nothing yet: such a
# category is reported as an insight only, never with an invented product.
SELLS: dict[str, tuple[Sells, ...]] = {
    "video": (Sells("social_pack", "youtube"), Sells("app_offer", "kinon")),
    "social": (
        Sells("social_pack", "instagram-facebook"),
        Sells("social_pack", "tiktok"),
        Sells("redesign"),
    ),
    "messaging": (Sells("tariff_messaging"),),
    "games": (),
    "other": (),
}

# Social pack slug -> the app whose traffic it covers.
SOCIAL_PACK_APP = {
    "youtube": "youtube",
    "instagram-facebook": "instagram_facebook",
    "tiktok": "tiktok",
}

# IsteSen redesign slider -> the app whose traffic it covers.
SLIDER_APP = {"instagramFb": "instagram_facebook", "youtube": "youtube", "tiktok": "tiktok"}


class UnknownApp(ValueError):
    """An app key that is not in `CATEGORIES`."""


def category_of(app: str) -> str:
    try:
        return APP_CATEGORY[app]
    except KeyError:
        raise UnknownApp(app) from None
