from django.conf import settings
from django.db import models
from django.utils import timezone

from api.common.models import ActiveQuerySet, CatalogueItem

SUBSCRIBER = settings.AUTH_USER_MODEL


class StoryView(models.Model):
    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="story_views")
    story_key = models.CharField(max_length=40)
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("subscriber", "story_key")]

    def __str__(self):
        return f"{self.subscriber} viewed {self.story_key}"


class Notification(models.Model):
    subscriber = models.ForeignKey(
        SUBSCRIBER, on_delete=models.CASCADE, related_name="notifications"
    )
    slug = models.SlugField(max_length=60)  # the public `id`
    title = models.CharField(max_length=200)
    body = models.TextField()
    cta = models.JSONField(null=True, blank=True)  # { "label", "deep_link" }
    sent_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("subscriber", "slug")]

    def __str__(self):
        return self.title


class AppRating(models.Model):
    subscriber = models.ForeignKey(SUBSCRIBER, on_delete=models.CASCADE, related_name="app_ratings")
    stars = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.stars}★ by {self.subscriber}"


class Story(CatalogueItem):
    key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=60)
    image = models.CharField(max_length=120, help_text="File name under media/content/")

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        verbose_name_plural = "stories"

    def __str__(self):
        return self.label


class StoryPage(CatalogueItem):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="pages")
    image = models.CharField(max_length=120, help_text="File name under media/content/")
    title = models.CharField(max_length=120)
    body = models.TextField()
    cta_label = models.CharField(max_length=60, blank=True)
    cta_deep_link = models.CharField(max_length=120, blank=True)
    duration_ms = models.PositiveIntegerField(default=5000)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class QuickAction(CatalogueItem):
    key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=60)
    deep_link = models.CharField(max_length=120)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.label


class Banner(CatalogueItem):
    PLACEMENTS = [
        ("home", "Home"),
        ("products", "Products"),
        ("benefits", "Benefits"),
        ("partners", "Partners"),
    ]

    placement = models.CharField(max_length=12, choices=PLACEMENTS)
    key = models.SlugField(max_length=40)
    image = models.CharField(max_length=120, help_text="File name under media/content/")
    alt = models.CharField(max_length=200)
    deep_link = models.CharField(max_length=120, blank=True)

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        unique_together = [("placement", "key")]

    def __str__(self):
        return f"{self.placement}: {self.key}"


class LotterySection(CatalogueItem):
    icon = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=120)
    blocks = models.JSONField(
        default=list,
        help_text='Each item is {"kind": "p", "text", "num"?, "bold"?} or {"kind": "example", "items"}',
    )

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class Game(CatalogueItem):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    image = models.CharField(max_length=120, help_text="File name under media/content/")
    is_reward = models.BooleanField(default=False, help_text="Listed under reward games")

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.name


class Tournament(CatalogueItem):
    title = models.CharField(max_length=80)
    game = models.ForeignKey(Game, on_delete=models.PROTECT, related_name="tournaments")
    prize = models.CharField(max_length=40)
    participants = models.PositiveIntegerField(default=0)
    ends_at = models.DateTimeField()
    cta = models.CharField(max_length=80)

    objects = ActiveQuerySet.as_manager()

    def __str__(self):
        return self.title


class Offer(CatalogueItem):
    """Partner cards: app subscriptions, Aztelekom, perks and campaigns."""

    KINDS = [
        ("app", "App offer"),
        ("aztelekom", "Aztelekom"),
        ("perk", "Partner perk"),
        ("campaign", "Campaign"),
    ]

    kind = models.CharField(max_length=12, choices=KINDS)
    slug = models.SlugField(max_length=40)
    name = models.CharField(max_length=80)
    sub = models.CharField(max_length=160)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    image = models.CharField(max_length=120, help_text="File name under media/content/")
    deep_link = models.CharField(max_length=120, blank=True)

    objects = ActiveQuerySet.as_manager()

    class Meta(CatalogueItem.Meta):
        unique_together = [("kind", "slug")]

    def __str__(self):
        return self.name
