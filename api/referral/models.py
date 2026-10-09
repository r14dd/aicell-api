from decimal import Decimal

from django.conf import settings
from django.db import models

from api.common.models import ActiveQuerySet, CatalogueItem


class ReferralProfile(models.Model):
    subscriber = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral"
    )
    code = models.CharField(max_length=12, unique=True)
    earned = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return self.code


class ReferralStep(CatalogueItem):
    """One step of the "Invite & earn" rules."""

    title = models.CharField(max_length=160)
    body = models.TextField()

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title
