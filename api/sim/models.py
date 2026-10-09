from django.conf import settings
from django.db import models
from django.utils import timezone

from api.billing.models import Transaction
from api.common.models import ActiveQuerySet, CatalogueItem


class SimProfile(models.Model):
    subscriber = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sim"
    )
    lte_enabled = models.BooleanField(default=True)
    one_way_blocking_date = models.DateField()
    deactivation_date = models.DateField()
    LINE_STATUSES = [("open", "Open"), ("suspended", "Suspended"), ("closed", "Closed")]

    line_status = models.CharField(max_length=10, choices=LINE_STATUSES, default="open")

    mobile_internet = models.BooleanField(default=True)
    second_line = models.BooleanField(default=True)

    forward_all = models.BooleanField(default=False)
    forward_unanswered = models.BooleanField(default=False)
    forward_busy = models.BooleanField(default=False)
    forward_unreachable = models.BooleanField(default=False)

    roaming_enabled = models.BooleanField(default=False)
    roaming_changed_at = models.DateTimeField(null=True, blank=True)

    sms_language = models.CharField(max_length=2, default="az")
    sms_ads = models.BooleanField(default=True)
    sms_campaigns = models.BooleanField(default=True)
    sms_partners = models.BooleanField(default=True)

    puk1 = models.CharField(max_length=8)
    puk2 = models.CharField(max_length=8)

    def __str__(self):
        return f"SIM of {self.subscriber}"


class ServiceSubscription(models.Model):
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_subscriptions"
    )
    transaction = models.OneToOneField(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    service = models.CharField(max_length=40)
    STATUSES = [("active", "Active"), ("cancelled", "Cancelled")]

    status = models.CharField(max_length=12, choices=STATUSES, default="active")
    options = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    next_payment_at = models.DateTimeField()

    def __str__(self):
        return f"#{self.pk} {self.service}"


class SimService(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    sub = models.CharField(max_length=160)
    period = models.CharField(max_length=40)
    days = models.PositiveSmallIntegerField(help_text="Days until the next payment")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    auto_renew = models.BooleanField(default=True)
    sections = models.JSONField(
        default=list,
        help_text='Each item is {"text"}, {"rows": [{"label", "value"}]} or {"option"}',
    )

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.name
