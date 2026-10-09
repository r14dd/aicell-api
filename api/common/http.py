import base64
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .exceptions import InvalidInput
from .formatting import iso, iso_local, money

__all__ = ["iso", "iso_local", "money"]  # re-exported for views

IMAGE_KEYS = {"image", "thumb", "logo"}


# --- images ----------------------------------------------------------------


def media(request, name):
    return request.build_absolute_uri(f"{settings.MEDIA_URL}content/{name}")


def with_images(request, data):
    """Copy `data`, turning image file names into absolute URLs."""
    if isinstance(data, dict):
        return {
            key: media(request, value)
            if key in IMAGE_KEYS and isinstance(value, str) and "://" not in value
            else with_images(request, value)
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [with_images(request, item) for item in data]
    return data


# --- input ------------------------------------------------------------------


def validated(serializer_class, request):
    """The request body, validated."""
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def validated_query(serializer_class, request):
    """The query string, validated."""
    serializer = serializer_class(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class AmountField(serializers.DecimalField):
    def __init__(self, min_amount, max_amount, **kwargs):
        self.min_amount = Decimal(min_amount)
        self.max_amount = Decimal(max_amount)
        super().__init__(max_digits=9, decimal_places=2, **kwargs)

    def to_internal_value(self, data):
        message = _("Enter an amount between %(min)s and %(max)s ₼") % {
            "min": f"{self.min_amount:.2f}",
            "max": f"{self.max_amount:.2f}",
        }
        try:
            value = super().to_internal_value(data)
        except serializers.ValidationError:
            raise serializers.ValidationError(message) from None
        if not self.min_amount <= value <= self.max_amount:
            raise serializers.ValidationError(message)
        return value


class MsisdnField(serializers.RegexField):
    def __init__(self, **kwargs):
        super().__init__(
            r"^994\d{9}$",
            error_messages={"invalid": _("Enter a number as 994XXXXXXXXX")},
            **kwargs,
        )


class PageQuery(serializers.Serializer):
    cursor = serializers.CharField(required=False, help_text="`next` of the previous page")
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=200, help_text="Page size, 50 by default"
    )


class DateRangeQuery(PageQuery):
    """`from` and `to` are inclusive dates in Asia/Baku."""

    to = serializers.DateField(required=False, help_text="Last day, `YYYY-MM-DD`")

    def get_fields(self):
        fields = super().get_fields()
        # `from` is a Python keyword, so it cannot be declared as a class attribute.
        fields["from"] = serializers.DateField(required=False, help_text="First day, `YYYY-MM-DD`")
        return fields


def date_range(query):
    """Validated `from` / `to` as an aware [start, end) pair in Asia/Baku; either may be None."""
    tz = timezone.get_current_timezone()
    start, end = query.get("from"), query.get("to")
    # The first and last days bound nothing, and overflow once shifted to UTC or by a day.
    if start == date.min:
        start = None
    if end == date.max:
        end = None
    return (
        datetime.combine(start, time.min, tzinfo=tz) if start else None,
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz) if end else None,
    )


def paginate(request, queryset, serialize, ascending=False):
    """Cursor pagination on `id`: `{ "results": [...], "next": "<cursor>|null" }`."""
    query = validated_query(PageQuery, request)
    limit = query.get("limit", 50)
    try:
        cursor = query.get("cursor")
        after = int(base64.urlsafe_b64decode(cursor.encode()).decode()) if cursor else None
    except ValueError:
        raise InvalidInput(_("Invalid cursor")) from None
    if after is not None:
        queryset = queryset.filter(id__gt=after) if ascending else queryset.filter(id__lt=after)
    rows = list(queryset.order_by("id" if ascending else "-id")[: limit + 1])
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = base64.urlsafe_b64encode(str(rows[-1].id).encode()).decode()
    return {"results": [serialize(row) for row in rows], "next": next_cursor}
