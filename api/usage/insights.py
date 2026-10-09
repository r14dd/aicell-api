"""The stored 30-day view of each subscriber: segment, totals and top recommendation.

Working these out takes a profile per subscriber, which is too slow to do for
everyone while a page loads. `refresh` does it on a schedule (and at the end of
the seed); statistics then count and sum the stored rows.
"""

from decimal import Decimal

from django.utils import timezone

from api.users.models import Subscriber

from . import recommendations
from .models import SubscriberInsight

FIELDS = ("segment", "data_mb", "minutes", "spend", "saving", "recommendation", "refreshed_at")
ZERO = Decimal("0")


def insight_of(subscriber, now=None) -> SubscriberInsight:
    """The row for one subscriber, computed now and not saved."""
    result = recommendations.recommend(subscriber)
    profile = result.profile
    top = result.recommendations[0] if result.recommendations else None
    return SubscriberInsight(
        subscriber=subscriber,
        segment=profile.segment,
        data_mb=profile.data_mb,
        minutes=profile.minutes,
        spend=profile.spend.total,
        saving=max(top.saving, ZERO) if top else ZERO,
        recommendation=top.title[:160] if top else "",
        refreshed_at=now or timezone.now(),
    )


def refresh(now=None) -> int:
    """Recompute the row of every subscriber. Returns how many."""
    now = now or timezone.now()
    subscribers = Subscriber.objects.filter(is_staff=False, is_active=True)
    rows = [insight_of(subscriber, now) for subscriber in subscribers]
    SubscriberInsight.objects.bulk_create(
        rows, update_conflicts=True, unique_fields=["subscriber"], update_fields=FIELDS
    )
    SubscriberInsight.objects.exclude(subscriber__in=[row.subscriber_id for row in rows]).delete()
    return len(rows)


def last_refreshed():
    """When the stored rows were last recomputed, or None when there are none."""
    return (
        SubscriberInsight.objects.order_by("-refreshed_at")
        .values_list("refreshed_at", flat=True)
        .first()
    )
