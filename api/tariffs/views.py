from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.http import iso_local, media, money, validated_query
from api.common.routing import Todo, route

from . import catalogue, services, texts

TAG = "tariffs"


# --- catalogue --------------------------------------------------------------


def family_json(family, plan_id=None):
    plan = services.plan(family, plan_id)
    body = {key: value for key, value in family.items() if key != "default_plan"}
    body.update(
        selected_plan=plan["id"],
        total_price=catalogue.price_groups(),
        note=texts.NOTE,
        cta=_("Subscribe for %(price)s ₼") % {"price": plan["price"]},
    )
    return body


@doc("All tariff families with their plans")
def families(request):
    """Feeds the Change tariff screen and the catalogue pages."""
    return {"results": [family_json(family) for family in catalogue.families()]}


class FamilyQuery(serializers.Serializer):
    plan = serializers.CharField(required=False, help_text="Plan to select, e.g. `digimax-25`")


@doc("One tariff family", query=FamilyQuery, path={"family": "digimax"}, errors=(400, 404))
def family(request, family):
    """`?plan=` selects the chip; without it the family's default plan is selected."""
    plan_id = validated_query(FamilyQuery, request).get("plan")
    return family_json(services.family(family), plan_id)


@doc("Hot offers on tariffs")
def hot(request):
    """Cards of the Products screen, in shelf order."""
    return {"results": catalogue.hot()}


@doc("Change tariff groups and cards")
def change(request):
    """`family_id` is set on cards that open a catalogue page."""
    return {"results": catalogue.change_groups()}


@doc("Premium benefits")
def premium(request):
    """Logo, benefit list and the note under it."""
    return {
        "logo": media(request, "premium-logo.png"),
        "benefits": catalogue.premium_benefits(),
        "note": texts.PREMIUM_NOTE,
    }


# --- my tariff --------------------------------------------------------------


def usage_rows(tariff):
    return [
        {
            "kind": "internet",
            "label": _("Internet"),
            "remaining": money(tariff.data_remaining_gb),
            "remaining_unit": _("GB"),
            "total": str(tariff.data_total_gb),
            "total_unit": _("GB"),
            "ratio": round(float(tariff.data_remaining_gb) / tariff.data_total_gb, 2),
        },
        {
            "kind": "messaging",
            "label": _("Messaging"),
            "remaining": str(tariff.messaging_remaining_mb),
            "remaining_unit": _("MB"),
            "total": str(tariff.messaging_total_gb),
            "total_unit": _("GB"),
            "ratio": round(tariff.messaging_remaining_mb / (tariff.messaging_total_gb * 1024), 2),
        },
        {
            "kind": "calls",
            "label": _("Local calls"),
            "remaining": str(tariff.minutes_remaining),
            "remaining_unit": _("MIN."),
            "total": str(tariff.minutes_total),
            "total_unit": _("MIN."),
            "ratio": round(tariff.minutes_remaining / tariff.minutes_total, 2),
        },
    ]


def _monthly(amount):
    return _("%(amount)s ₼/month") % {"amount": money(amount)}


@doc("My tariff", errors=(404,))
def my(request):
    """Header, usage, payment details, total price, banner and the renew sheet copy."""
    tariff = services.tariff_of(request.user)
    line_type = _("PREPAID") if request.user.line_type == "prepaid" else _("POSTPAID")
    return {
        "family": tariff.family,
        "title": tariff.title,
        "pills": [_("CURRENT TARIFF"), line_type],
        "lines": [
            {"label": _("Current tariff"), "value": _monthly(tariff.price)},
            {"label": _("Next renewal"), "value": _monthly(services.estimate(tariff.redesign))},
        ],
        "usage": usage_rows(tariff),
        "payment_details": [
            {
                "label": _("Validity period"),
                "value": _("%(days)s d.") % {"days": tariff.validity_days},
            },
            {"label": _("Activation date"), "value": iso_local(tariff.activated_at)},
            {"label": _("Last payment date"), "value": iso_local(tariff.last_payment_at)},
            {"label": _("Next payment date"), "value": iso_local(tariff.next_payment_at)},
            {"label": _("Payment amount"), "value": money(tariff.price)},
        ],
        "total_price": catalogue.price_groups(),
        "charging_note": texts.CHARGING_NOTE,
        "banner": {
            "image": media(request, "banner-want-more.png"),
            "alt": texts.BANNER_ALT,
            "deep_link": "/internet-packs",
        },
        "renew": texts.RENEW,
    }


@doc("Remaining balance of my tariff", errors=(404,))
def usage(request):
    """Home card, Remaining balance page and the aggregation sheet copy."""
    tariff = services.tariff_of(request.user)
    left = services.period_left(tariff)
    renews_at = timezone.localtime(tariff.next_payment_at)
    return {
        "tariff": tariff.title,
        "renewal_label": _("Renews %(day)s, %(time)s")
        % {"day": services.renewal_day(tariff), "time": f"{renews_at:%H:%M}"},
        "period_left": {"days": left.days, "hours": left.seconds // 3600},
        "remaining": {
            "data_gb": money(tariff.data_remaining_gb),
            "data_total_gb": str(tariff.data_total_gb),
            "minutes": tariff.minutes_remaining,
            "minutes_total": tariff.minutes_total,
        },
        "rows": usage_rows(tariff),
        "aggregation": texts.AGGREGATION,
    }


@doc("Redesign sliders and current estimate", errors=(404,))
def redesign(request):
    """The client computes the live estimate with `pricing`."""
    tariff = services.tariff_of(request.user)
    return {
        "sliders": [
            {**slider, "value": tariff.redesign.get(slider["key"], slider["min"])}
            for slider in catalogue.sliders()
        ],
        "pricing": services.REDESIGN_PRICING,
        "estimate": money(services.estimate(tariff.redesign)),
    }


# --- routes -----------------------------------------------------------------

catalogue_view = route(TAG, get=families)
catalogue_family_view = route(TAG, get=family)
hot_view = route(TAG, get=hot)
subscribe_view = route(
    TAG,
    post=Todo(
        _("Tariff subscription is not part of this prototype yet"),
        "Subscribe to a tariff plan",
    ),
)
my_view = route(TAG, get=my)
usage_view = route(TAG, get=usage)
renew_view = route(
    TAG, post=Todo(_("Tariff renewal is not part of this prototype yet"), "Renew my tariff")
)
redesign_view = route(
    TAG,
    get=redesign,
    post=Todo(
        _("Saving a redesigned tariff is not part of this prototype yet"),
        "Save a redesigned tariff",
    ),
)
change_view = route(
    TAG,
    get=change,
    post=Todo(_("Changing tariff is not part of this prototype yet"), "Change tariff"),
)
premium_view = route(TAG, get=premium)
premium_activate_view = route(
    TAG,
    post=Todo(_("Premium activation is not part of this prototype yet"), "Activate Premium"),
)
