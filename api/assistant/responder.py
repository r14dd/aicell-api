"""The `:dummy` responder: keyword routing over the subscriber's own data.

`settings.ASSISTANT_RESPONDER` names the callable used, so a model-backed
responder with the same signature can replace this one without touching the
views: `respond(subscriber, text) -> Reply`.
"""

from dataclasses import dataclass

from django.utils import translation

from api.billing.services import balance_of
from api.common.formatting import money
from api.tariffs.models import SubscriberTariff
from api.tariffs.services import renewal_day
from api.usage import offers, recommendations


@dataclass
class Reply:
    text: str
    route: str
    action: dict | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0


def _navigate(to, label):
    return {"action": "navigate", "to": to, "label": label}


def _usage(subscriber):
    tariff = SubscriberTariff.objects.filter(subscriber=subscriber).first()
    if tariff is None:
        return Reply("I could not find an active tariff on your number.", "usage")
    return Reply(
        f"You have {money(tariff.data_remaining_gb)} GB left until {renewal_day(tariff)}.",
        "usage",
        _navigate("/remaining-balance", "Open remaining balance"),
    )


def _balance(subscriber):
    return Reply(
        f"Your balance is {money(balance_of(subscriber))} ₼.",
        "balance",
        _navigate("/top-up", "Top up balance"),
    )


def _tariff(subscriber):
    tariff = SubscriberTariff.objects.filter(subscriber=subscriber).first()
    if tariff is None:
        return Reply("I could not find an active tariff on your number.", "tariff")
    return Reply(
        f"Your tariff is {tariff.title} for {money(tariff.price)} ₼ a month. "
        f"It renews on {renewal_day(tariff)}.",
        "tariff",
        _navigate("/my-tariff", "Open my tariff"),
    )


def _packs(subscriber):
    return Reply(
        "Internet packs start from 0.50 ₼, and Unlimited 1 hour costs 0.99 ₼.",
        "packs",
        _navigate("/internet-packs", "Open internet packs"),
    )


def _roaming(subscriber):
    return Reply(
        "Roaming internet packs start from 10.00 ₼ for 500 MB. "
        "You can turn roaming on in SIM settings.",
        "roaming",
        _navigate("/sim/roaming", "Open roaming settings"),
    )


def _kredit(subscriber):
    return Reply(
        "With SimKredit you can get 1-3 ₼ now and pay back at the next top-up.",
        "kredit",
        _navigate("/kredit", "Open Get Kredit"),
    )


def _recommendation(subscriber):
    """What fits this subscriber, from the numbers `api.usage` computed."""
    with translation.override("en"):  # this responder answers in English only
        result = recommendations.recommend(subscriber)
        offer = offers.open_offer(subscriber)
        paid = money(result.current)
        if not result.fits:
            top = result.recommendations[0]
            text = (
                f"In the last 30 days you paid {paid} ₼. With {top.title} it would have "
                f"been {money(top.projected)} ₼, which is {money(top.saving)} ₼ less. "
                f"Why: {'; '.join(top.evidence)}."
            )
            return Reply(text, "recommendation", top.action)
        text = (
            f"Your current plan fits how you use your number: you paid {paid} ₼ in the "
            "last 30 days and nothing in the catalogue would have cost less."
        )
        if offer is None:
            return Reply(text, "recommendation")
        target = offers.resolve(offer.target_kind, offer.target_id)
        text += (
            f" There is a personal offer for you: {target.title} for "
            f"{money(offer.offer_price)} ₼ instead of {money(offer.normal_price)} ₼."
        )
        action = _navigate(f"/offers/{offer.id}", "See the offer")
        return Reply(text, "recommendation", action)


# First match wins, so the specific topics come before the generic ones.
ROUTES = [
    (
        ("suits me", "suit me", "recommend", "cheaper", "best for me", "save money")
        + ("uyğun", "tövsiy", "məsləhət", "sərfəli")
        + ("подход", "посовет", "рекоменд", "выгодн"),
        _recommendation,
    ),
    (("roaming", "rouminq", "роуминг", "abroad"), _roaming),
    (("kredit", "credit", "loan", "borc", "кредит"), _kredit),
    (("pack", "paket", "пакет"), _packs),
    # "qalı" covers qalıq / qalığım (the q softens to ğ before a suffix).
    (("internet", "qalı", "qali", "left", "remaining", "остал", "интернет"), _usage),
    (("balance", "balans", "баланс", "top up", "top-up", "money"), _balance),
    (("tariff", "tarif", "тариф", "renew"), _tariff),
]

FALLBACK = (
    "I can help with your balance, remaining internet, tariff, internet packs, "
    "roaming and Kredit. What would you like to know?"
)


def respond(subscriber, text):
    # str.lower() turns the Azerbaijani "İ" into "i" + a combining dot.
    lowered = text.replace("İ", "i").lower()
    for keywords, handler in ROUTES:
        if any(keyword in lowered for keyword in keywords):
            return handler(subscriber)
    return Reply(FALLBACK, "fallback")
