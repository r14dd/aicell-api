"""Shared pieces of the admin: base classes, language tabs and display helpers."""

from modeltranslation.admin import TranslationAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import BooleanRadioFilter

LANGUAGE_TABS = (("az", "Azərbaycan"), ("en", "English"))

# Colours of status badges, by value.
STATUS_COLOURS = {
    "active": "success",
    "completed": "success",
    "open": "success",
    "pending": "warning",
    "suspended": "warning",
    "expired": "danger",
    "failed": "danger",
    "cancelled": "danger",
    "closed": "info",
    "new": "info",
    "shown": "warning",
    "accepted": "success",
    "declined": "danger",
    "seen": "warning",
    "dismissed": "danger",
    "resolved": "info",
}


def manat(amount) -> str:
    """An amount with its currency, e.g. `16.21 ₼`."""
    return "—" if amount is None else f"{amount:.2f} ₼"


def signed_manat(amount) -> str:
    """A wallet movement: `+15.00 ₼` or `-0.99 ₼`."""
    return f"{amount:+.2f} ₼"


def language_tabs(*translated: str) -> list[tuple]:
    """One tab per language holding that language's version of the given fields."""
    return [
        (label, {"classes": ["tab"], "fields": [f"{name}_{code}" for name in translated]})
        for code, label in LANGUAGE_TABS
    ]


class BaseAdmin(ModelAdmin):
    list_per_page = 50
    list_filter_submit = True
    list_fullwidth = True
    compressed_fields = True
    warn_unsaved_form = True
    show_full_result_count = False


class ReadOnlyMixin:
    """Rows that record what happened: they can be looked at, never edited."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAdmin(ReadOnlyMixin, BaseAdmin):
    pass


class CatalogueAdmin(BaseAdmin, TranslationAdmin):
    """Editable catalogue content with one tab per language.

    Subclasses name their own fields in `general` and `translated`; the
    fieldsets, the position block and the active filter are the same for all.
    """

    general: tuple = ()
    translated: tuple = ()
    ordering = ("order", "id")
    list_filter = (("is_active", BooleanRadioFilter),)

    def get_fieldsets(self, request, obj=None):
        return [
            (None, {"fields": self.general}),
            *language_tabs(*self.translated),
            ("Placement", {"fields": ("order", "is_active")}),
        ]


class ReadOnlyInline(ReadOnlyMixin, TabularInline):
    """Related records listed on a parent page, with a link to each."""

    extra = 0
    can_delete = False
    show_change_link = True
    tab = True
    per_page = 10
