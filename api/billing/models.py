from decimal import Decimal

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

SUBSCRIBER = settings.AUTH_USER_MODEL


class Wallet(models.Model):
    subscriber = models.OneToOneField(SUBSCRIBER, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"{self.subscriber} · {self.balance} ₼"


class Transaction(models.Model):
    KINDS = [
        ("top_up", "Top-up"),
        ("purchase", "Purchase"),
        ("payment", "Payment"),
        ("credit", "Credit"),
    ]

    subscriber = models.ForeignKey(
        SUBSCRIBER, on_delete=models.CASCADE, related_name="transactions"
    )
    kind = models.CharField(max_length=10, choices=KINDS)
    title = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # signed
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"#{self.pk} {self.title} ({self.amount} ₼)"


class TopUp(models.Model):
    METHODS = [
        ("card", "Card"),
        ("akart", "akart"),
        ("voucher", "Voucher"),
        ("google_pay", "Google Pay"),
    ]

    STATUSES = [("completed", "Completed"), ("pending", "Pending"), ("failed", "Failed")]

    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="top_ups")
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="top_up")
    method = models.CharField(max_length=12, choices=METHODS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=12, choices=STATUSES, default="completed")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"#{self.pk} {self.amount} ₼ via {self.method}"


class SavedCard(models.Model):
    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="cards")
    brand = models.CharField(max_length=20)
    last4 = models.CharField(max_length=4)
    expiry = models.CharField(max_length=5)  # MM/YY
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.brand} •••• {self.last4}"


class SavedAkart(models.Model):
    subscriber = models.ForeignKey(
        SUBSCRIBER, on_delete=models.CASCADE, related_name="akart_numbers"
    )
    msisdn = models.CharField(max_length=12)

    class Meta:
        unique_together = [("subscriber", "msisdn")]

    def __str__(self):
        return self.msisdn


class SteamAccount(models.Model):
    subscriber = models.ForeignKey(
        SUBSCRIBER, on_delete=models.CASCADE, related_name="steam_accounts"
    )
    name = models.CharField(max_length=64)
    last_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_topped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("subscriber", "name")]

    def __str__(self):
        return self.name


class SteamTopUp(models.Model):
    subscriber = models.ForeignKey(
        SUBSCRIBER, on_delete=models.CASCADE, related_name="steam_top_ups"
    )
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="steam_top_up"
    )
    account = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"#{self.pk} {self.account} {self.amount} ₼"


class IdempotencyKey(models.Model):
    """Stored response of a money-moving POST, replayed when the key is seen again."""

    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="+")
    key = models.UUIDField()
    path = models.CharField(max_length=255)
    status = models.PositiveSmallIntegerField()
    body = models.JSONField(encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("subscriber", "key")]

    def __str__(self):
        return str(self.key)
