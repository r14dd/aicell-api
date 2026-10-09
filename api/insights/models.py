from django.conf import settings
from django.db import models
from django.utils import timezone

KINDS = [
    ("video_heavy", "Video heavy"),
    ("repeat_packs", "Repeat packs"),
    ("overage", "Out of package"),
    ("forecast_gap", "Forecast gap"),
    ("social_heavy", "Social heavy"),
    ("underused", "Underused"),
    ("roaming", "Roaming"),
    ("renewal_shortfall", "Renewal shortfall"),
]
SEVERITIES = [("info", "Info"), ("urgent", "Urgent")]


class Insight(models.Model):
    """Something the subscriber's own numbers show, with what the catalogue offers for it.

    A detector writes the facts (`evidence`) and the priced answers (`offers`).
    No sentence is stored: wording belongs to the assistant that reads this.
    """

    STATUSES = [
        ("new", "New"),
        ("seen", "Seen"),
        ("accepted", "Accepted"),
        ("dismissed", "Dismissed"),
        ("expired", "Expired"),
        ("resolved", "Resolved"),
    ]
    OPEN = ("new", "seen")

    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="insights"
    )
    kind = models.CharField(max_length=20, choices=KINDS)
    severity = models.CharField(max_length=10, choices=SEVERITIES, default="info")
    evidence = models.JSONField(default=dict, help_text="The figures the detector found")
    offers = models.JSONField(default=list, help_text="Priced catalogue answers, best first")
    recommended = models.PositiveSmallIntegerField(default=0, help_text="Index into offers")
    status = models.CharField(max_length=10, choices=STATUSES, default="new")
    accepted_offer = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    delivered_at = models.DateTimeField(
        null=True, blank=True, help_text="When the app was first given it"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(
        null=True, blank=True, help_text="No insight of this kind is written before this"
    )

    class Meta:
        indexes = [models.Index(fields=["subscriber", "status"], name="insight_subscriber_status")]

    def __str__(self):
        return f"#{self.pk} {self.kind} ({self.status})"
