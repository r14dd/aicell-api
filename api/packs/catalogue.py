"""Read side of the pack catalogue: models to the documented JSON shapes."""

from api.common.cache import cached
from api.common.formatting import money

from .models import InternetPack, PackCategory, RoamingPack, SocialPack


def _internet_pack(pack) -> dict:
    return {
        "id": pack.slug,
        "name": pack.name,
        "sub": pack.sub,
        "price": money(pack.price),
        "renews": pack.renews,
        "label": pack.label,
    }


@cached("packs.categories")
def categories() -> list[dict]:
    return [
        {"id": category.slug, "label": category.label} for category in PackCategory.objects.active()
    ]


@cached("packs.internet")
def internet_packs() -> dict[str, list[dict]]:
    """Packs grouped by category slug; categories without packs are left out."""
    grouped: dict[str, list[dict]] = {}
    packs = InternetPack.objects.active().filter(category__is_active=True)
    for pack in packs.select_related("category").order_by("category__order", "order", "id"):
        grouped.setdefault(pack.category.slug, []).append(_internet_pack(pack))
    return grouped


@cached("packs.top")
def top() -> list[dict]:
    packs = InternetPack.objects.active().filter(top_position__isnull=False)
    return [_internet_pack(pack) for pack in packs.order_by("top_position", "id")]


@cached("packs.priced")
def priced() -> dict[str, list[dict]]:
    """Packs with their traffic in MB, for cost projection (None = unlimited)."""
    internet = [
        {
            "id": p.slug,
            "title": p.label,
            "price": money(p.price),
            "data_mb": p.data_mb,
            "hours": p.hours,
        }
        for p in InternetPack.objects.active().filter(category__is_active=True)
    ]
    social = [
        {
            "id": pack.slug,
            "plan_id": plan.slug,
            "pack_title": pack.title,
            "title": f"{pack.title} {plan.title}",
            "price": money(plan.price),
            "data_mb": plan.data_mb,
            "days": plan.days,
        }
        for pack in SocialPack.objects.active().prefetch_related("plans")
        for plan in pack.plans.all()
        if plan.is_active
    ]
    roaming = [
        {
            "id": p.slug,
            "title": p.name,
            "price": money(p.price),
            "data_mb": p.data_mb,
            "days": p.days,
        }
        for p in RoamingPack.objects.active()
    ]
    return {"internet": internet, "social": social, "roaming": roaming}


def _social_plans(pack) -> list[dict]:
    return [
        {
            "id": plan.slug,
            "title": plan.title,
            "price": money(plan.price),
            "validity": plan.validity,
        }
        for plan in pack.plans.all()
        if plan.is_active
    ]


@cached("packs.social")
def social_packs() -> list[dict]:
    """Social packs with their plans; the list endpoint drops `plans`."""
    return [
        {
            "id": pack.slug,
            "title": pack.title,
            "subtitle": pack.subtitle,
            "app": pack.app,
            "range": pack.price_range,
            "special": pack.special,
            "volume": pack.volume,
            "periods": pack.periods,
            "cta": pack.cta,
            "auto_renew": pack.auto_renew,
            "plans": _social_plans(pack),
        }
        for pack in SocialPack.objects.active().prefetch_related("plans")
    ]


@cached("packs.roaming")
def roaming() -> list[dict]:
    return [
        {"id": pack.slug, "name": pack.name, "sub": pack.sub, "price": money(pack.price)}
        for pack in RoamingPack.objects.active()
    ]
