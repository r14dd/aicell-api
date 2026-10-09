"""Cache for catalogue reads.

Catalogue content is the same for every subscriber, so the built JSON is cached
per language. Saving or deleting any catalogue row bumps a version number,
which orphans every cached entry at once; nothing subscriber-specific is ever
cached here.
"""

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils import translation

from .models import CatalogueItem

VERSION_KEY = "catalogue:version"


def _version() -> int:
    return cache.get_or_set(VERSION_KEY, 1, timeout=None)


def invalidate(**kwargs) -> None:
    """Orphan every cached catalogue entry."""
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # the version key was evicted or never set
        cache.set(VERSION_KEY, 1, timeout=None)


def cached(name: str):
    """Cache a no-argument catalogue reader per language until the catalogue changes."""

    def decorator(reader):
        @wraps(reader)
        def wrapper():
            language = translation.get_language() or settings.LANGUAGE_CODE
            key = f"catalogue:{_version()}:{name}:{language}"
            return cache.get_or_set(key, reader, timeout=settings.CATALOGUE_CACHE_SECONDS)

        return wrapper

    return decorator


def _on_change(sender, **kwargs):
    if issubclass(sender, CatalogueItem):
        invalidate()


post_save.connect(_on_change, dispatch_uid="catalogue-cache-save")
post_delete.connect(_on_change, dispatch_uid="catalogue-cache-delete")
