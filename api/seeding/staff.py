"""Admin roles and one account for each.

superadmin   everything
content      the catalogue and content, full access
support      subscribers and what they did, read-only
finance      billing, read-only
"""

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import transaction

from api.common.models import CatalogueItem
from api.users.models import Subscriber

ALL = ("add", "change", "delete", "view")
VIEW = ("view",)

SUPPORT_MODELS = [
    "users.Subscriber",
    "billing.Wallet",
    "billing.Transaction",
    "billing.TopUp",
    "billing.SavedCard",
    "billing.SavedAkart",
    "billing.SteamAccount",
    "billing.SteamTopUp",
    "tariffs.SubscriberTariff",
    "packs.PackActivation",
    "kredit.CreditDebt",
    "sim.SimProfile",
    "sim.ServiceSubscription",
    "content.Notification",
    "content.StoryView",
    "content.AppRating",
    "referral.ReferralProfile",
    "assistant.Conversation",
    "assistant.Message",
    "usage.DailyUsage",
    "usage.AppUsage",
    "usage.PersonalOffer",
    "usage.SubscriberInsight",
]

FINANCE_MODELS = [
    "billing.Wallet",
    "billing.Transaction",
    "billing.TopUp",
    "billing.SavedCard",
    "billing.SavedAkart",
    "billing.SteamAccount",
    "billing.SteamTopUp",
    "billing.IdempotencyKey",
]


def catalogue_models() -> list[str]:
    """Everything editors manage: the catalogue rows and the notifications."""
    labels = [model._meta.label for model in apps.get_models() if issubclass(model, CatalogueItem)]
    return [*labels, "content.Notification"]


def roles() -> dict[str, tuple[list[str], tuple[str, ...]]]:
    """Group name -> (models, actions)."""
    return {
        "Content manager": (catalogue_models(), ALL),
        "Support": (SUPPORT_MODELS, VIEW),
        "Finance": (FINANCE_MODELS, VIEW),
    }


ACCOUNTS = {
    # login: (display name, group or None for the superuser)
    "superadmin": ("Super Admin", None),
    "content": ("Content Manager", "Content manager"),
    "support": ("Support Agent", "Support"),
    "finance": ("Finance Analyst", "Finance"),
}


def _permissions(labels, actions):
    wanted = []
    for label in labels:
        model = apps.get_model(label)
        wanted += [f"{action}_{model._meta.model_name}" for action in actions]
    app_labels = {label.split(".")[0] for label in labels}
    found = Permission.objects.filter(content_type__app_label__in=app_labels, codename__in=wanted)
    # A codename alone is not unique across apps; keep only the models asked for.
    names = {label.lower() for label in labels}
    return [
        permission
        for permission in found.select_related("content_type")
        if f"{permission.content_type.app_label}.{permission.content_type.model}" in names
    ]


@transaction.atomic
def seed_staff() -> list[Subscriber]:
    """Create or refresh the role groups and their accounts."""
    groups = {}
    for name, (labels, actions) in roles().items():
        group, _created = Group.objects.get_or_create(name=name)
        group.permissions.set(_permissions(labels, actions))
        groups[name] = group

    accounts = []
    for login, (display_name, group_name) in ACCOUNTS.items():
        account, created = Subscriber.objects.get_or_create(
            msisdn=login, defaults={"display_name": display_name}
        )
        if created:
            # Only a new account gets the seed password: a changed one is kept.
            account.set_password(settings.SEED_STAFF_PASSWORD)
        account.is_staff = True
        account.is_active = True
        account.is_superuser = group_name is None
        account.save()
        account.groups.set([groups[group_name]] if group_name else [])
        accounts.append(account)
    return accounts
