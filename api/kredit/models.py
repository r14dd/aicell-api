from django.conf import settings
from django.db import models
from django.utils import timezone

from api.common.models import ActiveQuerySet, CatalogueItem


class CreditDebt(models.Model):
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_debts"
    )
    product = models.CharField(max_length=40)
    name = models.CharField(max_length=60)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    repaid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"#{self.pk} {self.name} {self.amount} ₼"


class KreditProduct(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=60)
    subtitle = models.CharField(max_length=160)
    chip = models.CharField(max_length=20)
    chip_icon = models.CharField(max_length=20)
    price_label = models.CharField(max_length=20, blank=True, help_text='e.g. "2 ₼"; optional')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    options = models.JSONField(default=list, blank=True, help_text="Selectable amounts, if any")
    amount_mb = models.PositiveIntegerField(null=True, blank=True)
    validity_days = models.PositiveSmallIntegerField(null=True, blank=True)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.name
