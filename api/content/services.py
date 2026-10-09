"""Per-subscriber state over the content catalogue: viewed stories, read notifications."""

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from api.common.exceptions import NotFound

from . import catalogue
from .models import AppRating, Notification, StoryView

# --- stories ----------------------------------------------------------------


def shelf(subscriber) -> list[dict]:
    """Chips in shelf order with viewed ones last, the most recently viewed at the end."""
    viewed_at = dict(
        StoryView.objects.filter(subscriber=subscriber).values_list("story_key", "viewed_at")
    )
    chips = [
        {
            "key": story["key"],
            "label": story["label"],
            "image": story["image"],
            "viewed": story["key"] in viewed_at,
            "has_story": bool(story["pages"]),
        }
        for story in catalogue.stories()
    ]
    unviewed = [chip for chip in chips if not chip["viewed"]]
    viewed = sorted(
        (chip for chip in chips if chip["viewed"]), key=lambda chip: viewed_at[chip["key"]]
    )
    return unviewed + viewed


def story(key) -> dict:
    """A story with the keys of its neighbours in shelf order."""
    stories = catalogue.stories()
    keys = [item["key"] for item in stories]
    if key not in keys:
        raise NotFound()
    index = keys.index(key)
    item = stories[index]
    return {
        "key": item["key"],
        "title": item["label"],
        "thumb": item["image"],
        "pages": item["pages"],
        "next_key": keys[index + 1] if index + 1 < len(keys) else None,
        "prev_key": keys[index - 1] if index else None,
    }


def mark_story_viewed(subscriber, key) -> None:
    if key not in {item["key"] for item in catalogue.stories()}:
        raise NotFound()
    StoryView.objects.update_or_create(
        subscriber=subscriber, story_key=key, defaults={"viewed_at": timezone.now()}
    )


# --- notifications ----------------------------------------------------------


def notifications(subscriber, *, query=None, start=None, end=None) -> QuerySet[Notification]:
    """The subscriber's notifications, narrowed by text and by a [start, end) range."""
    queryset = Notification.objects.filter(subscriber=subscriber)
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(body__icontains=query))
    if start:
        queryset = queryset.filter(sent_at__gte=start)
    if end:
        queryset = queryset.filter(sent_at__lt=end)
    return queryset


def unread_count(subscriber) -> int:
    return Notification.objects.filter(subscriber=subscriber, read_at__isnull=True).count()


def read_notification(subscriber, slug) -> Notification:
    notification = Notification.objects.filter(subscriber=subscriber, slug=slug).first()
    if notification is None:
        raise NotFound()
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


# --- app rating -------------------------------------------------------------


def rate_app(subscriber, stars: int) -> str:
    """Store the rating and return the thank-you line for it."""
    AppRating.objects.create(subscriber=subscriber, stars=stars)
    if stars >= 4:
        return _("Thanks! Your rating helps us a lot")
    return _("Thanks for the feedback, we will do better")
