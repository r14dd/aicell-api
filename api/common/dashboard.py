"""Figures on the admin's first page.

Each figure is shown only to staff who may view the data behind it, so a
content manager does not see money and a finance analyst does not see content.
"""

from datetime import datetime, time
from decimal import Decimal

from django.apps import apps
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from api.billing.models import TopUp, Transaction
from api.common.models import CatalogueItem
from api.packs.models import PackActivation
from api.users.models import Subscriber

from .admin import manat, signed_manat


def today_start() -> datetime:
    """Midnight in Asia/Baku."""
    now = timezone.localtime()
    return datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)


def _subscribers():
    total = Subscriber.objects.filter(is_staff=False).count()
    new = Subscriber.objects.filter(is_staff=False, created_at__gte=today_start()).count()
    return {
        "title": "Subscribers",
        "value": total,
        "note": f"{new} joined today",
        "icon": "group",
        "link": reverse("admin:users_subscriber_changelist"),
    }


def _transactions():
    today = Transaction.objects.filter(created_at__gte=today_start())
    topped_up = TopUp.objects.filter(created_at__gte=today_start(), status="completed").aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    return {
        "title": "Transactions today",
        "value": today.count(),
        "note": f"{manat(topped_up)} topped up",
        "icon": "receipt_long",
        "link": reverse("admin:billing_transaction_changelist"),
    }


def _active_packs():
    active = PackActivation.objects.filter(status="active", expires_at__gt=timezone.now())
    renewing = active.filter(auto_renew=True).count()
    return {
        "title": "Active packs",
        "value": active.count(),
        "note": f"{renewing} renew automatically",
        "icon": "inventory_2",
        "link": reverse("admin:packs_packactivation_changelist") + "?status=active",
    }


def _catalogue():
    models = [model for model in apps.get_models() if issubclass(model, CatalogueItem)]
    live = sum(model.objects.filter(is_active=True).count() for model in models)
    hidden = sum(model.objects.filter(is_active=False).count() for model in models)
    return {
        "title": "Catalogue items live",
        "value": live,
        "note": f"{hidden} switched off",
        "icon": "category",
        "link": reverse("admin:tariffs_tariffplan_changelist"),
    }


CARDS = [
    ("users.view_subscriber", _subscribers),
    ("billing.view_transaction", _transactions),
    ("packs.view_packactivation", _active_packs),
    ("tariffs.view_tariffplan", _catalogue),
]


def _recent_transactions():
    rows = Transaction.objects.select_related("subscriber").order_by("-created_at", "-id")[:8]
    return {
        "headers": ["When", "Subscriber", "Kind", "Title", "Amount"],
        "rows": [
            [
                timezone.localtime(tx.created_at).strftime("%d.%m.%Y %H:%M"),
                tx.subscriber.msisdn,
                tx.get_kind_display(),
                tx.title,
                signed_manat(tx.amount),
            ]
            for tx in rows
        ],
    }


def dashboard(request, context):
    user = request.user
    context["cards"] = [build() for permission, build in CARDS if user.has_perm(permission)]
    if user.has_perm("billing.view_transaction"):
        context["recent_transactions"] = _recent_transactions()
    return context
