from django.conf import settings
from django.db import models
from django.utils import timezone

from api.billing.models import Transaction
from api.common.models import ActiveQuerySet, CatalogueItem


class PackActivation(models.Model):
    KINDS = [
        ("internet", "Internet"),
        ("social", "Social"),
        ("roaming", "Roaming"),
        ("kredit", "Kredit"),
    ]

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pack_activations"
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pack_activation",
    )
    kind = models.CharField(max_length=10, choices=KINDS)
    pack_id = models.CharField(max_length=60)
    label = models.CharField(max_length=120)
    STATUSES = [("active", "Active"), ("expired", "Expired"), ("cancelled", "Cancelled")]

    status = models.CharField(max_length=12, choices=STATUSES, default="active")
    auto_renew = models.BooleanField(default=False)
    activated_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"#{self.pk} {self.label}"


class PackCategory(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=40)

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        verbose_name_plural = "pack categories"

    def __str__(self):
        return self.label


class InternetPack(CatalogueItem):
    category = models.ForeignKey(PackCategory, on_delete=models.PROTECT, related_name="packs")
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=40)
    sub = models.CharField(max_length=80)
    label = models.CharField(max_length=80, help_text="Shown on the activation and the receipt")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    renews = models.BooleanField(default=False)
    hours = models.PositiveIntegerField(help_text="Lifetime of an activation")
    top_position = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Position in "TOP internet packs"; empty hides it'
    )

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.label


class SocialPack(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=60)
    subtitle = models.CharField(max_length=160)
    app = models.CharField(max_length=20, help_text="Icon key in the mobile app")
    price_range = models.CharField(max_length=20)
    special = models.BooleanField(default=False)
    volume = models.CharField(max_length=40)
    periods = models.JSONField(default=list)
    cta = models.CharField(max_length=40)
    auto_renew = models.BooleanField(default=False)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class SocialPlan(CatalogueItem):
    pack = models.ForeignKey(SocialPack, on_delete=models.CASCADE, related_name="plans")
    slug = models.SlugField(max_length=20)
    title = models.CharField(max_length=40)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    validity = models.CharField(max_length=20)
    days = models.PositiveSmallIntegerField(help_text="Lifetime of an activation")

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        unique_together = [("pack", "slug")]

    def __str__(self):
        return f"{self.pack.title} {self.title}"


class RoamingPack(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=40)
    sub = models.CharField(max_length=40)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    days = models.PositiveSmallIntegerField(help_text="Lifetime of an activation")

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.name
