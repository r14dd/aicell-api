"""Read side of the tariff catalogue: models to the documented JSON shapes."""

from api.common.cache import cached
from api.common.formatting import money

from .models import (
    ChangeGroup,
    PremiumBenefit,
    PriceGroup,
    RedesignSlider,
    TariffFamily,
    TariffPlan,
)


def _family(family) -> dict:
    plans = [plan for plan in family.plans.all() if plan.is_active]
    default = next((plan for plan in plans if plan.is_default), plans[0] if plans else None)
    return {
        "id": family.slug,
        "name": family.name,
        "subtitle": family.subtitle or None,
        "badges": family.badges,
        "is_premium": family.is_premium,
        "default_plan": default.slug if default else None,
        "plans": [
            {
                "id": plan.slug,
                "title": plan.title,
                "price": money(plan.price),
                "hot": plan.hot,
                "features": plan.features,
            }
            for plan in plans
        ],
    }


@cached("tariffs.families")
def families() -> list[dict]:
    queryset = TariffFamily.objects.active().prefetch_related("plans")
    return [_family(family) for family in queryset]


@cached("tariffs.price_groups")
def price_groups() -> list[dict]:
    return [
        {
            "heading": group.heading,
            "tone": group.tone,
            "rows": [{"label": row["label"], "price": row["price"]} for row in group.rows],
        }
        for group in PriceGroup.objects.active()
    ]


@cached("tariffs.overage_rates")
def overage_rates() -> dict[str, str]:
    """Out-of-package prices by row key (`data_mb`, `minute`, `sms`), from the first price group."""
    group = PriceGroup.objects.active().first()
    return {row["key"]: row["price"] for row in (group.rows if group else []) if "key" in row}


@cached("tariffs.plans")
def plans() -> list[dict]:
    """Every active plan with what it includes as numbers (None = unlimited)."""
    queryset = TariffPlan.objects.active().filter(family__is_active=True).select_related("family")
    return [
        {
            "id": plan.slug,
            "family_id": plan.family.slug,
            "title": plan.title,
            "price": money(plan.price),
            "data_mb": plan.data_mb,
            "minutes": plan.minutes,
            "sms": plan.sms,
            "roaming_mb": plan.roaming_mb,
        }
        for plan in queryset
    ]


@cached("tariffs.hot")
def hot() -> list[dict]:
    plans = (
        TariffPlan.objects.active()
        .filter(hot_position__isnull=False, family__is_active=True)
        .select_related("family")
        .order_by("hot_position", "id")
    )
    return [
        {
            "id": plan.slug,
            "family_id": plan.family.slug,
            "title": plan.title,
            "price": money(plan.price),
            "socials": plan.hot_socials,
            "features": plan.hot_features,
        }
        for plan in plans
    ]


@cached("tariffs.change_groups")
def change_groups() -> list[dict]:
    groups = ChangeGroup.objects.active().prefetch_related("cards__family")
    return [
        {
            "id": group.slug,
            "title": group.title,
            "cards": [
                {
                    "id": card.slug,
                    "title": card.title,
                    "price": card.price,
                    "period": card.period,
                    "tagline": card.tagline,
                    "is_new": card.is_new,
                    "socials": card.socials,
                    "features": card.features,
                    "family_id": card.family.slug if card.family else None,
                }
                for card in group.cards.all()
                if card.is_active
            ],
        }
        for group in groups
    ]


@cached("tariffs.premium_benefits")
def premium_benefits() -> list[dict]:
    return [
        {"key": benefit.key, "text": benefit.text} for benefit in PremiumBenefit.objects.active()
    ]


@cached("tariffs.sliders")
def sliders() -> list[dict]:
    return [
        {
            "key": slider.key,
            "label": slider.label,
            "min": slider.minimum,
            "max": slider.maximum,
            "step": slider.step,
        }
        for slider in RedesignSlider.objects.active()
    ]
