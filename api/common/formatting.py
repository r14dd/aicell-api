"""The API's wire formats for money and time (docs/api/overview.md, "Shapes")."""

from datetime import UTC, datetime
from decimal import Decimal

from django.utils import timezone


def money(value) -> str:
    """Decimal string with two decimals: `16.21`."""
    return f"{Decimal(value):.2f}"


def iso(value: datetime | None) -> str | None:
    """ISO 8601 UTC: `2026-10-02T12:39:00Z`."""
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_local(value: datetime) -> str:
    """ISO 8601 with the Asia/Baku offset: `2026-10-25T08:00:00+04:00`."""
    return timezone.localtime(value).isoformat(timespec="seconds")
