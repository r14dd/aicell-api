"""Keeping insights: running the detectors, deciding what the app is given, and the answers.

Delivery policy, all decided here so every client behaves the same:

- nothing between 23:00 and 08:00 in Asia/Baku;
- every urgent insight, but at most one new "info" insight per 48 hours;
- an insight lapses seven days after it was written;
- a dismissed kind stays silent for 14 days, an accepted one for two.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from api.common.exceptions import InvalidInput, NotFound
from api.users.models import Subscriber

from . import detectors
from .catalogue import Catalogue
from .detectors import Finding
from .metrics import metrics
from .models import Insight

LIFETIME = timedelta(days=7)
INFO_INTERVAL = timedelta(hours=48)
DISMISS_SNOOZE = timedelta(days=14)
ACCEPT_SNOOZE = timedelta(days=2)


# --- finding and storing ------------------------------------------------------


def findings(subscriber, now=None, catalogue: Catalogue | None = None) -> list[Finding]:
    """What the detectors see for the subscriber right now. Nothing is stored."""
    figures = metrics(subscriber, now)
    if figures is None:
        return []
    return detectors.detect(figures, catalogue or Catalogue.load())


def _silenced(subscriber, now) -> set[str]:
    """Kinds the subscriber answered recently: they are not raised again yet."""
    return set(
        Insight.objects.filter(subscriber=subscriber, snoozed_until__gt=now).values_list(
            "kind", flat=True
        )
    )


def store(subscriber, finding: Finding, now=None, **fields) -> Insight:
    """Write a finding as a new insight."""
    now = now or timezone.now()
    return Insight.objects.create(
        subscriber=subscriber,
        kind=finding.kind,
        severity=finding.severity,
        evidence=finding.evidence,
        offers=finding.offers,
        recommended=finding.recommended,
        created_at=now,
        expires_at=now + LIFETIME,
        **fields,
    )


@transaction.atomic
def refresh(subscriber, now=None, catalogue: Catalogue | None = None) -> list[Insight]:
    """Run the detectors and bring the subscriber's insights up to date.

    There is never a second open insight of a kind: an open one gets the new
    figures instead. Open insights past their time are closed first, and one
    whose condition no longer holds (the balance was topped up, a pack was
    bought) is closed as resolved rather than shown with stale figures.
    """
    now = now or timezone.now()
    Insight.objects.filter(
        subscriber=subscriber, status__in=Insight.OPEN, expires_at__lte=now
    ).update(status="expired")
    open_by_kind = {
        insight.kind: insight
        for insight in Insight.objects.select_for_update().filter(
            subscriber=subscriber, status__in=Insight.OPEN
        )
    }
    silenced = _silenced(subscriber, now)
    current = []
    for finding in findings(subscriber, now, catalogue):
        insight = open_by_kind.get(finding.kind)
        if insight is not None:
            insight.severity = finding.severity
            insight.evidence = finding.evidence
            insight.offers = finding.offers
            insight.recommended = finding.recommended
            insight.save(update_fields=["severity", "evidence", "offers", "recommended"])
        elif finding.kind in silenced:
            continue
        else:
            insight = store(subscriber, finding, now)
        current.append(insight)
    still_true = {insight.id for insight in current}
    Insight.objects.filter(
        id__in=[insight.id for insight in open_by_kind.values() if insight.id not in still_true]
    ).update(status="resolved")
    return current


def refresh_all(now=None) -> int:
    """The nightly run: every subscriber, one catalogue snapshot. Returns insights kept open."""
    now = now or timezone.now()
    catalogue = Catalogue.load()
    subscribers = Subscriber.objects.filter(is_staff=False, is_active=True)
    return sum(len(refresh(subscriber, now, catalogue)) for subscriber in subscribers)


# --- delivery -----------------------------------------------------------------


def is_quiet(now) -> bool:
    """Whether `now` falls in the hours nothing is delivered (Asia/Baku)."""
    hours = settings.INSIGHTS_QUIET_HOURS
    if not hours:
        return False
    start, end = hours
    hour = timezone.localtime(now).hour
    return hour >= start or hour < end


@transaction.atomic
def deliverable(subscriber, now=None) -> list[Insight]:
    """The insights the app may show now, urgent ones first.

    Giving out a new "info" insight starts its 48 hours: until they pass, the
    same one is returned and no other "info" insight joins it.
    """
    now = now or timezone.now()
    if is_quiet(now):
        return []
    open_now = list(
        Insight.objects.select_for_update()
        .filter(subscriber=subscriber, status__in=Insight.OPEN, expires_at__gt=now)
        .order_by("created_at", "id")
    )
    urgent = [insight for insight in open_now if insight.severity == "urgent"]
    info = [insight for insight in open_now if insight.severity == "info"]

    last_delivery = (
        Insight.objects.filter(
            subscriber=subscriber, severity="info", delivered_at__gt=now - INFO_INTERVAL
        )
        .order_by("-delivered_at")
        .first()
    )
    if last_delivery is not None:
        chosen = [insight for insight in info if insight.id == last_delivery.id]
    else:
        chosen = info[:1]
        for insight in chosen:
            insight.delivered_at = now
            insight.save(update_fields=["delivered_at"])
    return urgent + chosen


# --- the subscriber's answer --------------------------------------------------


def _own(subscriber, insight_id) -> Insight:
    """The subscriber's own insight. Someone else's is simply not found."""
    insight = (
        Insight.objects.select_for_update().filter(subscriber=subscriber, id=insight_id).first()
    )
    if insight is None:
        raise NotFound()
    return insight


@transaction.atomic
def mark_seen(subscriber, insight_id) -> Insight:
    insight = _own(subscriber, insight_id)
    if insight.status == "new":
        insight.status = "seen"
        insight.save(update_fields=["status"])
    return insight


@transaction.atomic
def accept(subscriber, insight_id, offer: int | None = None, now=None) -> Insight:
    """Record that the subscriber said yes to an offer (the recommended one by default).

    Nothing is bought here: the offer's task is carried out through the
    endpoint that sells it. Answering an insight twice changes nothing.
    """
    now = now or timezone.now()
    insight = _own(subscriber, insight_id)
    chosen = insight.recommended if offer is None else offer
    if not 0 <= chosen < len(insight.offers):
        raise InvalidInput(errors={"offer": [_("This insight has no such offer")]})
    if insight.status in Insight.OPEN:
        insight.status = "accepted"
        insight.accepted_offer = chosen
        insight.decided_at = now
        insight.snoozed_until = now + ACCEPT_SNOOZE
        insight.save(update_fields=["status", "accepted_offer", "decided_at", "snoozed_until"])
    return insight


@transaction.atomic
def dismiss(subscriber, insight_id, now=None) -> Insight:
    """Record a "no": the kind is not raised again for 14 days."""
    now = now or timezone.now()
    insight = _own(subscriber, insight_id)
    if insight.status in Insight.OPEN:
        insight.status = "dismissed"
        insight.decided_at = now
        insight.snoozed_until = now + DISMISS_SNOOZE
        insight.save(update_fields=["status", "decided_at", "snoozed_until"])
    return insight
