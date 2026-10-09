from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.exceptions import NotImplementedYet
from api.common.http import (
    DateRangeQuery,
    date_range,
    iso,
    paginate,
    validated,
    validated_query,
    with_images,
)
from api.common.routing import Todo, route

from . import catalogue, services
from .models import Banner

TAG = "content"

LOTTERY_STARTS_AT = "2026-10-19"


# --- home and stories -------------------------------------------------------


@doc("Home feed")
def home(request):
    """Story shelf (viewed chips last), quick actions, carousel banners and the lottery banner."""
    return {
        "stories": with_images(request, services.shelf(request.user)),
        "quick_actions": catalogue.quick_actions(),
        "banners": with_images(request, catalogue.banners()["home"]),
        "lottery": {
            "title": _("30 il səninlə"),
            "subtitle": _("Chance collection starts on 19 October 2026"),
            "starts_at": LOTTERY_STARTS_AT,
            "cta": _("Learn more about the lottery"),
            "deep_link": "/lottery-rules",
        },
    }


@doc("Story shelf")
def stories(request):
    """Chips in shelf order with `viewed` flags; viewed chips come last."""
    return {"results": with_images(request, services.shelf(request.user))}


@doc("Story pages", path={"key": "especially"}, errors=(404,))
def story(request, key):
    """The pages of one story and the keys of its neighbours on the shelf."""
    return with_images(request, services.story(key))


@doc("Mark a story viewed", path={"key": "especially"}, errors=(404,))
def story_viewed(request, key):
    """Moves the chip to the end of the shelf."""
    services.mark_story_viewed(request.user, key)
    return {"key": key, "viewed": True}


class BannerQuery(serializers.Serializer):
    placement = serializers.ChoiceField(
        [placement for placement, _label in Banner.PLACEMENTS], required=False, default="home"
    )


@doc("Banners by placement", query=BannerQuery, errors=(400,))
def banners(request):
    """`placement` is `home` when left out."""
    placement = validated_query(BannerQuery, request)["placement"]
    return {"results": with_images(request, catalogue.banners()[placement])}


# --- notifications ----------------------------------------------------------


def notification_json(notification):
    return {
        "id": notification.slug,
        "title": notification.title,
        "body": notification.body,
        "cta": notification.cta,
        "sent_at": iso(notification.sent_at),
        "read": notification.read_at is not None,
    }


class NotificationQuery(DateRangeQuery):
    q = serializers.CharField(required=False, help_text="Text to find in the title or the body")


@doc("Notifications", query=NotificationQuery, errors=(400,))
def notifications(request):
    """Newest first, with text search and an inclusive date range.

    `unread` feeds the bell badge and counts every unread notification, not
    only the ones matching the filter.
    """
    query = validated_query(NotificationQuery, request)
    start, end = date_range(query)
    queryset = services.notifications(request.user, query=query.get("q"), start=start, end=end)
    body = paginate(request, queryset, notification_json)
    body["unread"] = services.unread_count(request.user)
    return body


@doc("Notification detail", path={"id": "wingz"}, errors=(404,))
def notification(request, id):
    """Opening a notification marks it read."""
    return notification_json(services.read_notification(request.user, id))


@doc("Mark a notification read", path={"id": "wingz"}, errors=(404,))
def notification_read(request, id):
    """The "Got it" button."""
    return notification_json(services.read_notification(request.user, id))


# --- lottery, games, offers -------------------------------------------------


@doc("Lottery rules")
def lottery_rules(request):
    """Sections of "Lottery rules & info" as blocks of text and examples."""
    return {"sections": catalogue.lottery_sections(), "terms_url": None}


class GamesQuery(serializers.Serializer):
    q = serializers.CharField(required=False, help_text="Search text; search is `:todo`")


@doc("Games", query=GamesQuery, errors=(501,))
def games(request):
    """Games, reward games and the tournament. With `?q=` it answers `501`: search is `:todo`."""
    if "q" in request.query_params:
        raise NotImplementedYet(_("Game search is not part of this prototype yet"))
    return with_images(request, catalogue.games())


def offers(kind, summary, description):
    """A read endpoint for one kind of offer, as `{ "results": [...] }`."""

    def view(request):
        return {"results": with_images(request, catalogue.offers()[kind])}

    view.__name__ = f"{kind}_offers"
    view.__doc__ = description
    return doc(summary)(view)


class RatingInput(serializers.Serializer):
    stars = serializers.IntegerField(min_value=1, max_value=5)


@doc("Rate the app", body=RatingInput, example={"stars": 5}, errors=(400,), status=201)
def app_rating(request):
    """Stores the stars and returns the thank-you line."""
    stars = validated(RatingInput, request)["stars"]
    return {"message": services.rate_app(request.user, stars)}, 201


# --- routes -----------------------------------------------------------------

home_view = route(TAG, get=home)
stories_view = route(TAG, get=stories)
story_view = route(TAG, get=story)
story_viewed_view = route(TAG, post=story_viewed)
banners_view = route(TAG, get=banners)
notifications_view = route(TAG, get=notifications)
notification_view = route(TAG, get=notification)
notification_read_view = route(TAG, post=notification_read)
notification_options_view = route(
    TAG,
    get=Todo(
        _("Notification options are not part of this prototype yet"), "Notification options menu"
    ),
)
lottery_rules_view = route(TAG, get=lottery_rules)
lottery_chances_view = route(
    TAG, get=Todo(_("Lottery chances are not part of this prototype yet"), "My lottery chances")
)
lottery_terms_view = route(
    TAG, get=Todo(_("Lottery terms are not part of this prototype yet"), "Lottery terms")
)
games_view = route(TAG, get=games)
game_launch_view = route(
    TAG, get=Todo(_("Games are not part of this prototype yet"), "Launch a game")
)
tournament_join_view = route(
    TAG, post=Todo(_("The tournament is not part of this prototype yet"), "Join the tournament")
)
tournament_rules_view = route(
    TAG, get=Todo(_("Tournament rules are not part of this prototype yet"), "Tournament rules")
)
app_offers_view = route(
    TAG, get=offers("app", "App offers", "Subscriptions such as Kinon, Yandex Plus and Litres.")
)
app_offer_subscribe_view = route(
    TAG,
    post=Todo(_("App subscriptions are not part of this prototype yet"), "Subscribe to an app"),
)
aztelekom_view = route(
    TAG, get=offers("aztelekom", "Aztelekom offers", "The Fiber Optical home internet card.")
)
aztelekom_order_view = route(
    TAG, post=Todo(_("Aztelekom orders are not part of this prototype yet"), "Order Aztelekom")
)
perks_view = route(TAG, get=offers("perk", "Partner perks", "Perks such as Wingz and Wolt+."))
campaigns_view = route(TAG, get=offers("campaign", "Campaigns", "Current campaigns."))
gift_wheel_view = route(
    TAG, get=Todo(_("Gift Wheel is not part of this prototype yet"), "Gift Wheel state")
)
gift_wheel_spin_view = route(
    TAG, post=Todo(_("Gift Wheel is not part of this prototype yet"), "Spin the Gift Wheel")
)
app_rating_view = route(TAG, post=app_rating)
about_view = route(
    TAG, get=Todo(_("About Azercell is not part of this prototype yet"), "About Azercell")
)
map_view = route(TAG, get=Todo(_("Stores map is not part of this prototype yet"), "Stores map"))
stickers_view = route(
    TAG, get=Todo(_("Stickers are not part of this prototype yet"), "Sticker packs")
)
help_view = route(
    TAG, get=Todo(_("Help & Support is not part of this prototype yet"), "Help & Support")
)
problem_report_view = route(
    TAG,
    post=Todo(_("Problem reports are not part of this prototype yet"), "Report a problem"),
)
