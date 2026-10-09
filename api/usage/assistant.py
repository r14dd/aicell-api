"""What the assistant needs to know about a subscriber, in one compact dict.

A model-backed responder puts `context()` into its prompt. It holds only
numbers this backend computed, so the model explains them and does not have to
work anything out. Kept small on purpose: well under 1,500 tokens.
"""

from api.common.formatting import money

from . import offers, recommendations, taxonomy
from .services import MB_PER_GB

TOP_APPS = 3


def _gb(data_mb: int) -> float:
    return round(data_mb / MB_PER_GB, 1)


def context(subscriber) -> dict:
    """Profile, top recommendations and the open offer as JSON-serialisable data."""
    result = recommendations.recommend(subscriber)
    profile = result.profile
    spend = profile.spend
    offer = offers.open_offer(subscriber)
    target = offer and offers.resolve(offer.target_kind, offer.target_id)
    return {
        "window_days": profile.days,
        "segment": profile.segment,
        "tariff": profile.tariff
        and {"title": profile.tariff.title, "monthly_fee": money(profile.tariff.price)},
        "usage": {
            "data_gb": _gb(profile.data_mb),
            "included_data_gb": profile.tariff.data_total_gb if profile.tariff else None,
            "minutes": profile.minutes,
            "sms": profile.sms,
            "roaming_gb": _gb(profile.roaming_data_mb),
            "roaming_days": profile.roaming_days,
            "top_apps": [
                {"app": str(taxonomy.APP_LABELS[app]), "share": profile.share(data_mb)}
                for app, data_mb in profile.by_app[:TOP_APPS]
            ],
            "data_ran_out_on_day": profile.ran_out.day if profile.ran_out else None,
        },
        "spend": {
            "tariff_fee": money(spend.tariff_fee),
            "addon_packs": {"count": spend.addon_count, "amount": money(spend.addon_amount)},
            "roaming": {"count": spend.roaming_count, "amount": money(spend.roaming_amount)},
            "other": money(spend.other),
        },
        "services": list(profile.services),
        "current_monthly_cost": money(result.current),
        "plan_fits": result.fits,
        "recommendations": [
            {
                "kind": item.kind,
                "target_id": item.target_id,
                "title": str(item.title),
                "projected_monthly_cost": money(item.projected),
                "saving": money(item.saving),
                "evidence": [str(fact) for fact in item.evidence],
                "navigate_to": item.action["to"],
            }
            for item in result.recommendations
        ],
        "insights": [str(insight.text) for insight in result.insights],
        "offer": offer
        and {
            "id": offer.id,
            "title": str(target.title) if target else offer.target_id,
            "normal_price": money(offer.normal_price),
            "offer_price": money(offer.offer_price),
            "reason": str(offers.reason_of(offer)),
            "expires_at": offer.expires_at.isoformat(timespec="seconds"),
        },
    }
