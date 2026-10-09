from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.billing.idempotency import idempotent
from api.billing.presenters import transaction_brief
from api.common.docs import doc
from api.common.http import iso, money, validated_query
from api.common.routing import route
from api.sim import catalogue as sim_catalogue

from . import offers, recommendations, services, taxonomy, texts

TAG = "usage"
MB_PER_GB = services.MB_PER_GB


def _gb(data_mb):
    return f"{data_mb / MB_PER_GB:.2f}"


# --- summary ------------------------------------------------------------------


class SummaryQuery(serializers.Serializer):
    days = serializers.IntegerField(
        required=False, default=services.DEFAULT_DAYS, min_value=1, max_value=90
    )


def headline(profile):
    return _("%(gb)s GB, %(minutes)s min. and %(sms)s SMS in %(days)s days; %(paid)s ₼ paid") % {
        "gb": f"{profile.data_mb / MB_PER_GB:.1f}",
        "minutes": profile.minutes,
        "sms": profile.sms,
        "days": profile.days,
        "paid": money(profile.spend.total),
    }


def profile_json(profile):
    spend = profile.spend
    service_names = {item["id"]: item["name"] for item in sim_catalogue.services()}
    ran_out = profile.ran_out
    return {
        "window": {
            "days": profile.days,
            "from": profile.start.isoformat(),
            "to": profile.end.isoformat(),
        },
        "segment": {"key": profile.segment, "label": texts.SEGMENT_LABELS[profile.segment]},
        "headline": headline(profile),
        "totals": {
            "data_mb": profile.data_mb,
            "data_gb": _gb(profile.data_mb),
            "minutes": profile.minutes,
            "sms": profile.sms,
            "roaming_data_mb": profile.roaming_data_mb,
            "roaming_minutes": profile.roaming_minutes,
            "roaming_days": profile.roaming_days,
        },
        "daily_average": {
            "data_mb": round(profile.data_mb / profile.days),
            "minutes": round(profile.minutes / profile.days, 1),
            "sms": round(profile.sms / profile.days, 1),
        },
        "data_by_category": [
            {
                "key": category,
                "label": taxonomy.CATEGORY_LABELS[category],
                "data_mb": data_mb,
                "share": profile.share(data_mb),
            }
            for category, data_mb in profile.by_category
        ],
        "data_by_app": [
            {
                "key": app,
                "label": taxonomy.APP_LABELS[app],
                "category": taxonomy.category_of(app),
                "data_mb": data_mb,
                "share": profile.share(data_mb),
            }
            for app, data_mb in profile.by_app
        ],
        "data_ran_out": ran_out
        and {
            "day": ran_out.day,
            "date": ran_out.date.isoformat(),
            "period_days": ran_out.period_days,
        },
        "spend": {
            "tariff_fee": money(spend.tariff_fee),
            "addon_packs": {"count": spend.addon_count, "amount": money(spend.addon_amount)},
            "roaming": {"count": spend.roaming_count, "amount": money(spend.roaming_amount)},
            "other": money(spend.other),
            "total": money(spend.total),
        },
        "services": [
            {"id": slug, "name": service_names.get(slug, slug)} for slug in profile.services
        ],
    }


@doc("30-day usage profile", query=SummaryQuery, errors=(400,))
def summary(request):
    """What the subscriber used and paid in the last `days` days (30 unless given, 1 to 90).

    Usage by category and by app with shares, the day included data ran out
    (or null), spend by kind and a segment label. In this prototype the usage
    rows come from seed data, not from a network feed.
    """
    days = validated_query(SummaryQuery, request)["days"]
    return profile_json(services.profile(request.user, days))


# --- recommendations ----------------------------------------------------------


def recommendation_json(item):
    body = {
        "kind": item.kind,
        "target_id": item.target_id,
        "title": item.title,
        "current_monthly_cost": money(item.current),
        "projected_monthly_cost": money(item.projected),
        "saving": money(item.saving),
        "evidence": list(item.evidence),
        "action": item.action,
    }
    if item.plan_id:
        body["plan_id"] = item.plan_id
    if item.values:
        body["values"] = item.values
    if item.quantity > 1:
        body["quantity"] = item.quantity
    return body


def offer_json(offer):
    target = offers.resolve(offer.target_kind, offer.target_id)
    return {
        "id": offer.id,
        "kind": offer.target_kind,
        "target_id": offer.target_id,
        "title": target.title if target else offer.target_id,
        "normal_price": money(offer.normal_price),
        "offer_price": money(offer.offer_price),
        "reason": offers.reason_of(offer),
        "status": offer.status,
        "expires_at": iso(offer.expires_at),
        "action": {"action": "navigate", "to": f"/offers/{offer.id}", "label": _("See the offer")},
    }


def message_for(result):
    """One sentence that states the outcome with its numbers."""
    if result.fits:
        return texts.FITS
    top = result.recommendations[0]
    return _(
        "You paid %(current)s ₼ in the last 30 days; with %(title)s it would have been %(projected)s ₼"
    ) % {
        "current": money(top.current),
        "title": top.title,
        "projected": money(top.projected),
    }


def result_json(result, offer):
    return {
        "window_days": result.profile.days,
        "segment": {
            "key": result.profile.segment,
            "label": texts.SEGMENT_LABELS[result.profile.segment],
        },
        "current_monthly_cost": money(result.current),
        "fits": result.fits,
        "message": message_for(result),
        "recommendations": [recommendation_json(item) for item in result.recommendations],
        "insights": [
            {
                "category": insight.category,
                "share": insight.share,
                "text": insight.text,
                "sells": list(insight.sells),
            }
            for insight in result.insights
        ],
        "offer": offer and offer_json(offer),
    }


@doc("Recommendations and the open personal offer")
def recommend(request):
    """Tariffs and packs that would have cost less over the last 30 days, best saving first.

    Each carries the current and projected monthly cost and the facts behind
    it. `fits: true` with no recommendations means nothing in the catalogue
    beats the current setup. `insights` name the biggest category of data and
    what is sold for it, which may be nothing. `offer` is the subscriber's open
    personal offer or null; returning it marks it shown.
    """
    result = recommendations.recommend(request.user)
    offer = offers.open_offer(request.user)
    if offer:
        offers.mark_shown(offer)
    return result_json(result, offer)


# --- offers -------------------------------------------------------------------


@doc("Accept a personal offer", path={"id": 9001}, errors=(402, 404, 409), status=201)
@idempotent
def offer_accept(request, id):
    """Buys the offered pack at the offer price and activates it, like a normal purchase.

    A closed offer (accepted, declined or expired) answers `409 offer_closed`.
    A tariff offer buys nothing, since a tariff at an offer price is not built: it
    answers `200` with the way to the tariff's page and stays open.
    """
    accepted = offers.accept(request.user, id)
    body = {"offer": offer_json(accepted.offer)}
    if accepted.purchase is None:
        target = offers.resolve(accepted.offer.target_kind, accepted.offer.target_id)
        body["action"] = {
            "action": "navigate",
            "to": f"/tariffs/{target.family_id}?plan={accepted.offer.target_id}",
            "label": _("See the tariff"),
        }
        return body, 200
    activation = accepted.purchase.activation
    body.update(
        activation={
            "id": activation.id,
            "pack_id": activation.pack_id,
            "label": activation.label,
            "status": activation.status,
            "activated_at": iso(activation.activated_at),
            "expires_at": iso(activation.expires_at),
            "auto_renew": activation.auto_renew,
        },
        transaction=transaction_brief(accepted.purchase.transaction),
        balance=money(accepted.purchase.balance),
    )
    return body, 201


@doc("Decline a personal offer", path={"id": 9001}, errors=(404, 409))
def offer_decline(request, id):
    """Closes the offer. No new offer is made for 7 days."""
    return {"offer": offer_json(offers.decline(request.user, id))}


# --- routes -------------------------------------------------------------------

summary_view = route(TAG, get=summary)
recommendations_view = route(TAG, get=recommend)
offer_accept_view = route(TAG, post=offer_accept)
offer_decline_view = route(TAG, post=offer_decline)
