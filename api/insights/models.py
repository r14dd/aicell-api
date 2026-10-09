from django.conf import settings
from django.db import models
from django.utils import timezone

KINDS = [
    ("renewal_shortfall", "Renewal shortfall"),
    ("overage", "Out of data"),
    ("forecast_gap", "Data will run out"),
    ("repeat_packs", "Repeated packs"),
    ("roaming", "Roaming"),
    ("social_heavy", "Social networks"),
    ("underused", "Underused data"),
    ("video_heavy", "Video"),
]


class Insight(models.Model):
    """Something the usage says the subscriber should hear about, with what to do about it.

    One row per subscriber and kind. `GET insights/` recomputes the content of the rows
    that still apply; a row the subscriber accepted or dismissed stays closed for a week.
    """

    STATUSES = [
        ("new", "New"),
        ("seen", "Seen"),
        ("accepted", "Accepted"),
        ("dismissed", "Dismissed"),
    ]
    OPEN = ("new", "seen")

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="usage_insights"
    )
    kind = models.CharField(max_length=20, choices=KINDS)
    status = models.CharField(max_length=10, choices=STATUSES, default="new")
    evidence = models.JSONField(default=dict)
    offers = models.JSONField(default=list)
    recommended = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("subscriber", "kind")]

    def __str__(self):
        return f"#{self.pk} {self.kind} ({self.status})"
