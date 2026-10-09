from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    subscriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    STATUSES = [("open", "Open"), ("closed", "Closed")]

    status = models.CharField(max_length=10, choices=STATUSES, default="open")
    source = models.CharField(max_length=20, default="mobile")
    unread = models.BooleanField(default=False)
    stars = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_message_at = models.DateTimeField(default=timezone.now)

    @property
    def external_id(self):
        return f"#{self.id}"

    def __str__(self):
        return self.external_id


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    ROLES = [("user", "Subscriber"), ("assistant", "Assistant")]

    role = models.CharField(max_length=10, choices=ROLES)
    content = models.TextField()
    route = models.CharField(max_length=30, blank=True)
    action = models.JSONField(null=True, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
