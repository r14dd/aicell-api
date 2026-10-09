from django.conf import settings
from django.db import models
from django.utils import timezone

from api.common.models import ActiveQuerySet, CatalogueItem
from api.packs.models import PackActivation

SUBSCRIBER = settings.AUTH_USER_MODEL

SEGMENTS = [
    ("heavy_data", "Heavy data"),
    ("voice_only", "Voice only"),
    ("roamer", "Roamer"),
    ("balanced", "Balanced"),
    ("low_usage", "Low usage"),
]

TARGET_KINDS = [
    ("internet_pack", "Internet pack"),
    ("social_pack", "Social pack plan"),
    ("roaming_pack", "Roaming pack"),
    ("tariff_plan", "Tariff plan"),
]


class DailyUsage(models.Model):
    """What a subscriber used on one day."""

    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="daily_usage")
    day = models.DateField()
    data_mb = models.PositiveIntegerField(default=0, help_text="Mobile data at home")
    call_minutes = models.PositiveIntegerField(default=0)
    sms = models.PositiveIntegerField(default=0)
    roaming_data_mb = models.PositiveIntegerField(default=0)
    roaming_minutes = models.PositiveIntegerField(default=0)
    overage_mb = models.PositiveIntegerField(
        default=0, help_text="Part of the data that was outside every package"
    )
    overage_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0, help_text="What that part cost"
    )

    class Meta:
        unique_together = [("subscriber", "day")]
        # Statistics read a range of days across all subscribers.
        indexes = [models.Index(fields=["day"], name="usage_daily_day")]
        verbose_name_plural = "daily usage"

    def __str__(self):
        return f"{self.subscriber} · {self.day}"


class AppUsage(models.Model):
    """Mobile data one app used on one day. The category comes from `taxonomy`."""

    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="app_usage")
    day = models.DateField()
    app = models.CharField(max_length=30)
    data_mb = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("subscriber", "day", "app")]
        indexes = [models.Index(fields=["day", "app"], name="usage_app_day_app")]
        verbose_name_plural = "app usage"

    def __str__(self):
        return f"{self.subscriber} · {self.day} · {self.app}"


class OfferRule(CatalogueItem):
    """Who gets which personal offer: a segment, a catalogue item and its offer price."""

    segment = models.CharField(max_length=20, choices=SEGMENTS)
    target_kind = models.CharField(max_length=20, choices=TARGET_KINDS)
    target_id = models.CharField(
        max_length=80, help_text='Catalogue slug; for a social pack "<pack>:<plan>"'
    )
    offer_price = models.DecimalField(max_digits=8, decimal_places=2)
    valid_days = models.PositiveSmallIntegerField(default=14)
    reason = models.CharField(max_length=200, help_text="Shown to the subscriber with the offer")

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return f"{self.get_segment_display()} → {self.target_id} at {self.offer_price} ₼"


class PersonalOffer(models.Model):
    STATUSES = [
        ("new", "New"),
        ("shown", "Shown"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("expired", "Expired"),
    ]
    OPEN = ("new", "shown")

    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="offers")
    rule = models.ForeignKey(
        OfferRule, on_delete=models.SET_NULL, null=True, blank=True, related_name="offers"
    )
    target_kind = models.CharField(max_length=20, choices=TARGET_KINDS)
    target_id = models.CharField(max_length=80)
    normal_price = models.DecimalField(max_digits=8, decimal_places=2)
    offer_price = models.DecimalField(max_digits=8, decimal_places=2)
    reason = models.CharField(max_length=200, blank=True, help_text="Used when there is no rule")
    status = models.CharField(max_length=10, choices=STATUSES, default="new")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    activation = models.OneToOneField(
        PackActivation, on_delete=models.SET_NULL, null=True, blank=True, related_name="offer"
    )

    def __str__(self):
        return f"#{self.pk} {self.target_id} at {self.offer_price} ₼ ({self.status})"


class SubscriberInsight(models.Model):
    """What the last 30 days say about a subscriber, stored so it can be counted.

    A segment and a recommendation take a profile to work out; `insights.refresh`
    does that for everyone on a schedule, and statistics aggregate these rows.
    """

    subscriber = models.OneToOneField(SUBSCRIBER, on_delete=models.CASCADE, related_name="insight")
    segment = models.CharField(max_length=20, choices=SEGMENTS, db_index=True)
    data_mb = models.PositiveIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saving = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text="Of the top recommendation, per month"
    )
    recommendation = models.CharField(max_length=160, blank=True)
    refreshed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.subscriber} · {self.segment}"
