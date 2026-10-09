from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.billing.idempotency import idempotent
from api.common.docs import doc
from api.common.exceptions import NotFound
from api.common.http import iso, money, validated
from api.common.routing import Todo, route

from . import catalogue, services, texts

TAG = "sim"


@doc("SIM settings overview", errors=(404,))
def overview(request):
    """The 4G badge, the blocking and deactivation dates and the settings rows."""
    sim = services.sim_of(request.user)
    return {
        "msisdn": request.user.msisdn,
        "lte_enabled": sim.lte_enabled,
        "badge": _("4G (LTE) enabled") if sim.lte_enabled else _("4G (LTE) disabled"),
        "details": [
            {"label": _("One-way blocking"), "value": sim.one_way_blocking_date.isoformat()},
            {"label": _("Deactivation date"), "value": sim.deactivation_date.isoformat()},
        ],
        "rows": texts.ROWS,
    }


# --- line -------------------------------------------------------------------


def _status_title(sim):
    status = texts.LINE_STATUS_NAMES.get(sim.line_status, sim.line_status.capitalize())
    return _("Line status: %(status)s") % {"status": status}


def line_json(sim):
    forwarding = any(services.forwarding_of(sim).values())
    return {
        "status": sim.line_status,
        "status_title": _status_title(sim),
        "status_sub": texts.LINE_STATUS_SUB,
        "mobile_internet": sim.mobile_internet,
        "second_line": sim.second_line,
        "call_forwarding_status": _("On") if forwarding else _("Off"),
        "texts": texts.LINE_TEXTS,
    }


@doc("Line settings", errors=(404,))
def line(request):
    """Line status, the two toggles and the call forwarding summary."""
    return line_json(services.sim_of(request.user))


class LineInput(serializers.Serializer):
    mobile_internet = serializers.BooleanField(required=False)
    second_line = serializers.BooleanField(required=False)


@doc(
    "Update line settings",
    body=LineInput,
    example={"mobile_internet": False},
    errors=(400, 404),
)
def line_update(request):
    """Send only the toggles that change."""
    sim = services.sim_of(request.user)
    for field, value in validated(LineInput, request).items():
        setattr(sim, field, value)
    sim.save()
    return line_json(sim)


@doc("Line status page", errors=(404,))
def line_status(request):
    """What closing the line costs and what follows from it."""
    sim = services.sim_of(request.user)
    return {
        "title": _status_title(sim),
        "general": texts.LINE_STATUS_GENERAL,
        "fee": texts.LINE_STATUS_FEE,
        "suspend_until": sim.deactivation_date.isoformat(),
        "consequences": texts.LINE_STATUS_CONSEQUENCES,
        "cta": _("Close line"),
    }


# --- call forwarding --------------------------------------------------------


@doc("Call forwarding toggles", errors=(404,))
def call_forwarding(request):
    """All calls, unanswered, busy and unreachable."""
    return services.forwarding_of(services.sim_of(request.user))


class ForwardingInput(serializers.Serializer):
    all = serializers.BooleanField(required=False)
    unanswered = serializers.BooleanField(required=False)
    busy = serializers.BooleanField(required=False)
    unreachable = serializers.BooleanField(required=False)


@doc(
    "Update call forwarding",
    body=ForwardingInput,
    example={"all": True},
    errors=(400, 404),
)
def call_forwarding_update(request):
    """`all` wins: turning it on resets the other three.

    While it is on, turning one of the three on without turning `all` off
    answers `400 validation_error`.
    """
    sim = services.sim_of(request.user)
    services.update_call_forwarding(sim, dict(validated(ForwardingInput, request)))
    return services.forwarding_of(sim)


# --- roaming ----------------------------------------------------------------


def roaming_json(sim):
    return {
        "enabled": sim.roaming_enabled,
        "changed_at": iso(sim.roaming_changed_at),
        "texts": texts.ROAMING_TEXTS,
    }


@doc("Roaming state", errors=(404,))
def roaming(request):
    """The toggle and the screen's texts. Packs come from `/api/packs/roaming/`."""
    return roaming_json(services.sim_of(request.user))


class RoamingInput(serializers.Serializer):
    enabled = serializers.BooleanField()


@doc("Turn roaming on or off", body=RoamingInput, example={"enabled": True}, errors=(400, 404))
def roaming_update(request):
    """`changed_at` moves only when the state actually changes."""
    enabled = validated(RoamingInput, request)["enabled"]
    return roaming_json(services.set_roaming(services.sim_of(request.user), enabled))


# --- sms --------------------------------------------------------------------


def sms_json(sim):
    return {
        "language": sim.sms_language,
        "languages": texts.SMS_LANGUAGES,
        "toggles": {
            "ads": sim.sms_ads,
            "campaigns": sim.sms_campaigns,
            "partners": sim.sms_partners,
        },
    }


@doc("SMS settings", errors=(404,))
def sms(request):
    """SMS language and the three marketing toggles."""
    return sms_json(services.sim_of(request.user))


class SmsTogglesInput(serializers.Serializer):
    ads = serializers.BooleanField(required=False)
    campaigns = serializers.BooleanField(required=False)
    partners = serializers.BooleanField(required=False)


class SmsInput(serializers.Serializer):
    language = serializers.ChoiceField(["az", "en", "ru"], required=False)
    toggles = SmsTogglesInput(required=False)


@doc(
    "Update SMS settings",
    body=SmsInput,
    example={"language": "en", "toggles": {"partners": False}},
    errors=(400, 404),
)
def sms_update(request):
    """Send only what changes; toggles that are left out keep their value."""
    sim = services.sim_of(request.user)
    changes = validated(SmsInput, request)
    if "language" in changes:
        sim.sms_language = changes["language"]
    for name, value in changes.get("toggles", {}).items():
        setattr(sim, f"sms_{name}", value)
    sim.save()
    return sms_json(sim)


# --- puk --------------------------------------------------------------------


def _spaced(code):
    return f"{code[:4]} {code[4:]}"


@doc("PUK codes", errors=(404,))
def puk(request):
    """PUK 1 and PUK 2 with the explanation as rich text segments."""
    sim = services.sim_of(request.user)
    return {
        "codes": [
            {"label": "PUK 1", "value": _spaced(sim.puk1)},
            {"label": "PUK 2", "value": _spaced(sim.puk2)},
        ],
        "paragraphs": texts.PUK_PARAGRAPHS,
    }


# --- services ---------------------------------------------------------------


def _badge(item, activated):
    if activated:
        return _("ACTIVATED")
    return _("AUTO-RENEWAL") if item["auto_renew"] else None


def service_row(item, activated):
    return {
        "id": item["id"],
        "name": item["name"],
        "sub": item["sub"],
        "period": item["period"],
        "price": None if activated else item["price"],
        "activated": activated,
        "badge": _badge(item, activated),
    }


@doc("Services")
def service_list(request):
    """`price` is null and the badge reads ACTIVATED once the subscriber has the service."""
    active = services.active_service_ids(request.user)
    return {"results": [service_row(item, item["id"] in active) for item in catalogue.services()]}


@doc("Service detail", path={"slug": "missed-call"}, errors=(404,))
def service_detail(request, slug):
    """`sections` are text, rows or an option; `action` is subscribe or deactivate."""
    item = next((item for item in catalogue.services() if item["id"] == slug), None)
    if item is None:
        raise NotFound()
    activated = slug in services.active_service_ids(request.user)
    action = (
        {"kind": "deactivate", "label": _("Deactivate")}
        if activated
        else {
            "kind": "subscribe",
            "label": _("Subscribe for %(price)s ₼") % {"price": item["price"]},
        }
    )
    return {**service_row(item, activated), "sections": item["sections"], "action": action}


class SubscribeInput(serializers.Serializer):
    options = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="Ids of the service's optional extras",
    )


@doc(
    "Subscribe to a service",
    body=SubscribeInput,
    example={"options": ["xeber-ver"]},
    path={"slug": "missed-call"},
    errors=(400, 402, 404, 409),
    status=201,
)
@idempotent
def service_subscribe(request, slug):
    """Charges the first period. A service that is already active answers `409`."""
    options = validated(SubscribeInput, request)["options"]
    purchase = services.subscribe(request.user, slug, options)
    return {
        "subscription": {
            "id": purchase.subscription.id,
            "service": purchase.subscription.service,
            "status": purchase.subscription.status,
            "next_payment_at": iso(purchase.subscription.next_payment_at),
        },
        "transaction": {
            "title": purchase.transaction.title,
            "amount": money(purchase.transaction.amount),
        },
        "balance": money(purchase.balance),
    }, 201


@doc("eSIM info page")
def esim(request):
    """Benefits, the Asan İmza note and the two actions."""
    return texts.ESIM


# --- routes -----------------------------------------------------------------

overview_view = route(TAG, get=overview)
line_view = route(TAG, get=line, patch=line_update)
internet_settings_view = route(
    TAG,
    post=Todo(
        _("Internet settings will be sent by SMS (prototype)"),
        "Request automatic internet settings",
    ),
)
line_status_view = route(TAG, get=line_status)
line_close_view = route(
    TAG, post=Todo(_("Closing the line is not part of this prototype yet"), "Close the line")
)
call_forwarding_view = route(TAG, get=call_forwarding, patch=call_forwarding_update)
roaming_view = route(TAG, get=roaming, patch=roaming_update)
roaming_countries_view = route(
    TAG,
    get=Todo(_("Country pricing is not part of this prototype yet"), "Search country pricing"),
)
sms_view = route(TAG, get=sms, patch=sms_update)
puk_view = route(TAG, get=puk)
services_view = route(TAG, get=service_list)
service_view = route(TAG, get=service_detail)
service_subscribe_view = route(TAG, post=service_subscribe)
service_deactivate_view = route(
    TAG, post=Todo(_("Deactivation is not part of this prototype yet"), "Deactivate a service")
)
esim_view = route(TAG, get=esim)
esim_transfer_view = route(
    TAG, post=Todo(_("eSIM transfer is not part of this prototype yet"), "Transfer to eSIM")
)
esim_recover_view = route(
    TAG, post=Todo(_("eSIM recovery is not part of this prototype yet"), "Recover an eSIM")
)
