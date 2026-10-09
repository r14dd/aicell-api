from decimal import Decimal

from django.conf import settings
from django.db import models

from api.common.models import ActiveQuerySet, CatalogueItem


def default_redesign():
    return {"internet": 16, "calls": 30, "instagramFb": 0, "youtube": 0, "tiktok": 0}


class SubscriberTariff(models.Model):
    subscriber = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tariff"
    )
    family = models.CharField(max_length=40, default="istesen")
    plan_slug = models.CharField(
        max_length=40, blank=True, help_text="Catalogue plan this tariff is, if it is one"
    )
    title = models.CharField(max_length=60, default="IsteSen")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("19.10"))
    validity_days = models.PositiveSmallIntegerField(default=30)
    activated_at = models.DateTimeField()
    last_payment_at = models.DateTimeField()
    next_payment_at = models.DateTimeField()

    data_remaining_gb = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("7.20"))
    data_total_gb = models.PositiveSmallIntegerField(default=16)
    messaging_remaining_mb = models.PositiveIntegerField(default=1003)
    messaging_total_gb = models.PositiveSmallIntegerField(default=1)
    minutes_remaining = models.PositiveIntegerField(default=30)
    minutes_total = models.PositiveIntegerField(default=30)

    redesign = models.JSONField(default=default_redesign)

    def __str__(self):
        return f"{self.subscriber} · {self.title}"


class TariffFamily(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=60)
    subtitle = models.CharField(max_length=160, blank=True)
    badges = models.JSONField(default=list, blank=True)  # e.g. ["PREPAID"]
    is_premium = models.BooleanField(default=False)

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        verbose_name_plural = "tariff families"

    def __str__(self):
        return self.name


class TariffPlan(CatalogueItem):
    family = models.ForeignKey(TariffFamily, on_delete=models.CASCADE, related_name="plans")
    slug = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    hot = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False, help_text="Selected when no ?plan= is given")
    features = models.JSONField(default=list, help_text='[{"kind", "label", "value", "socials"?}]')

    # What the plan includes, as numbers (the features above are display text).
    data_mb = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    sms = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    roaming_mb = models.PositiveIntegerField(default=0)

    # "Hot offers on tariffs" card; empty position means the plan is not on the shelf.
    hot_position = models.PositiveSmallIntegerField(null=True, blank=True)
    hot_socials = models.JSONField(default=list, blank=True)
    hot_features = models.JSONField(default=list, blank=True, help_text='[{"kind", "value"}]')

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class PriceGroup(CatalogueItem):
    """A block of the "Total price" table: what usage costs outside the package."""

    TONES = [("secondary", "Secondary"), ("red", "Red")]

    heading = models.CharField(max_length=120)
    tone = models.CharField(max_length=12, choices=TONES, default="secondary")
    rows = models.JSONField(default=list, help_text='[{"label", "price"}]')

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.heading


class ChangeGroup(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=60)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class ChangeCard(CatalogueItem):
    group = models.ForeignKey(ChangeGroup, on_delete=models.CASCADE, related_name="cards")
    slug = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=60)
    price = models.CharField(max_length=20, help_text='A price or a range, e.g. "12-30"')
    period = models.CharField(max_length=40)
    tagline = models.CharField(max_length=160)
    is_new = models.BooleanField(default=False)
    socials = models.JSONField(default=list, blank=True)
    features = models.JSONField(default=list, help_text='[{"kind", "value"}]')
    family = models.ForeignKey(
        TariffFamily,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_cards",
        help_text="Set when the card opens a catalogue page",
    )

    # A card without a page is chosen directly, so it says what it includes itself.
    data_mb = models.PositiveIntegerField(null=True, blank=True)
    minutes = models.PositiveIntegerField(null=True, blank=True)
    validity_days = models.PositiveSmallIntegerField(default=28)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class PremiumBenefit(CatalogueItem):
    key = models.SlugField(max_length=40, unique=True)
    text = models.CharField(max_length=160)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.text


class RedesignSlider(CatalogueItem):
    key = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=60)
    minimum = models.PositiveSmallIntegerField()
    maximum = models.PositiveSmallIntegerField()
    step = models.PositiveSmallIntegerField(default=1)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.label
