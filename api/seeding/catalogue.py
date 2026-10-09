"""Load the initial catalogue from `api/seeding/data/` into the models.

Rows are matched on their slug (or position, where there is none). A row that
already exists is left alone, so the seed can run on every start without
undoing what editors changed in the admin; `refresh=True` puts the seeded rows
back to their initial content. Rows editors added are never touched.
"""

from datetime import datetime
from decimal import Decimal

from django.db import transaction

from api.content.models import (
    Banner,
    Game,
    LotterySection,
    Offer,
    QuickAction,
    Story,
    StoryPage,
    Tournament,
)
from api.kredit.models import KreditProduct
from api.packs.models import InternetPack, PackCategory, RoamingPack, SocialPack, SocialPlan
from api.referral.models import ReferralStep
from api.sim.models import SimService
from api.tariffs.models import (
    ChangeCard,
    ChangeGroup,
    PremiumBenefit,
    PriceGroup,
    RedesignSlider,
    TariffFamily,
    TariffPlan,
)

from .data import content, kredit, packs, referral, sim, tariffs
from .translations import localized


class Loader:
    """Writes catalogue rows; text fields are stored in every language."""

    def __init__(self, refresh: bool):
        self.refresh = refresh

    def __call__(self, model, lookup: dict, **values):
        defaults = localized(model, values)
        if self.refresh:
            row, _created = model.objects.update_or_create(**lookup, defaults=defaults)
        else:
            row, _created = model.objects.get_or_create(**lookup, defaults=defaults)
        return row


def _tariffs(load):
    hot = {card["id"]: (position, card) for position, card in enumerate(tariffs.HOT, start=1)}
    families = {}
    plan_order = 0
    for order, family in enumerate(tariffs.FAMILIES.values()):
        families[family["id"]] = row = load(
            TariffFamily,
            {"slug": family["id"]},
            order=order,
            name=family["name"],
            subtitle=family["subtitle"] or "",
            badges=family["badges"],
            is_premium=family["is_premium"],
        )
        for plan in family["plans"]:
            position, card = hot.get(plan["id"], (None, None))
            load(
                TariffPlan,
                {"slug": plan["id"]},
                family=row,
                order=plan_order,
                title=plan["title"],
                price=Decimal(plan["price"]),
                hot=plan["hot"],
                is_default=plan["id"] == family["default_plan"],
                features=plan["features"],
                hot_position=position,
                hot_socials=card["socials"] if card else [],
                hot_features=card["features"] if card else [],
            )
            plan_order += 1

    for order, group in enumerate(tariffs.TOTAL_PRICE):
        load(
            PriceGroup,
            {"order": order},
            heading=group["heading"],
            tone=group["tone"],
            rows=group["rows"],
        )

    card_order = 0
    for order, group in enumerate(tariffs.CHANGE_GROUPS):
        row = load(ChangeGroup, {"slug": group["id"]}, order=order, title=group["title"])
        for card in group["cards"]:
            load(
                ChangeCard,
                {"slug": card["id"]},
                group=row,
                order=card_order,
                title=card["title"],
                price=card["price"],
                period=card["period"],
                tagline=card["tagline"],
                is_new=card["is_new"],
                socials=card["socials"],
                features=card["features"],
                family=families.get(card["family_id"]),
            )
            card_order += 1

    for order, benefit in enumerate(tariffs.PREMIUM["benefits"]):
        load(PremiumBenefit, {"key": benefit["key"]}, order=order, text=benefit["text"])

    for order, slider in enumerate(tariffs.REDESIGN_SLIDERS):
        load(
            RedesignSlider,
            {"key": slider["key"]},
            order=order,
            label=slider["label"],
            minimum=slider["min"],
            maximum=slider["max"],
            step=slider["step"],
        )


def _packs(load):
    categories = {}
    for order, category in enumerate(packs.CATEGORIES):
        categories[category["id"]] = load(
            PackCategory, {"slug": category["id"]}, order=order, label=category["label"]
        )

    order = 0
    for category, items in packs.PACKS.items():
        for pack in items:
            load(
                InternetPack,
                {"slug": pack["id"]},
                category=categories[category],
                order=order,
                name=pack["name"],
                sub=pack["sub"],
                label=pack["label"],
                price=Decimal(pack["price"]),
                renews=pack["renews"],
                hours=pack["hours"],
                top_position=packs.TOP.index(pack["id"]) + 1 if pack["id"] in packs.TOP else None,
            )
            order += 1

    for order, pack in enumerate(packs.SOCIAL.values()):
        row = load(
            SocialPack,
            {"slug": pack["id"]},
            order=order,
            title=pack["title"],
            subtitle=pack["subtitle"],
            app=pack["app"],
            price_range=pack["range"],
            special=pack["special"],
            volume=pack["volume"],
            periods=pack["periods"],
            cta=pack["cta"],
            auto_renew=pack["auto_renew"],
        )
        for plan_order, plan in enumerate(pack["plans"]):
            load(
                SocialPlan,
                {"pack": row, "slug": plan["id"]},
                order=plan_order,
                title=plan["title"],
                price=Decimal(plan["price"]),
                validity=plan["validity"],
                days=plan["days"],
            )

    for order, pack in enumerate(packs.ROAMING):
        load(
            RoamingPack,
            {"slug": pack["id"]},
            order=order,
            name=pack["name"],
            sub=pack["sub"],
            price=Decimal(pack["price"]),
            days=pack["days"],
        )


def _kredit(load):
    for order, product in enumerate(kredit.PRODUCTS):
        detail = kredit.DETAILS[product["id"]]
        load(
            KreditProduct,
            {"slug": product["id"]},
            order=order,
            name=product["name"],
            subtitle=product["subtitle"],
            chip=product["chip"],
            chip_icon=product["chip_icon"],
            price_label=product.get("price", ""),
            amount=Decimal(detail["amount"]),
            fee=Decimal(detail["fee"]),
            options=detail.get("options", []),
            amount_mb=detail.get("amount_mb"),
            validity_days=detail.get("validity_days"),
        )


def _sim(load):
    for order, service in enumerate(sim.SERVICES.values()):
        load(
            SimService,
            {"slug": service["id"]},
            order=order,
            name=service["name"],
            sub=service["sub"],
            period=service["period"],
            days=service["days"],
            price=Decimal(service["price"]),
            auto_renew=service["auto_renew"],
            sections=service["sections"],
        )


def _content(load):
    for order, story in enumerate(content.STORIES):
        row = load(
            Story, {"key": story["key"]}, order=order, label=story["label"], image=story["image"]
        )
        for page_order, page in enumerate(story["pages"]):
            cta = page["cta"] or {}
            load(
                StoryPage,
                {"story": row, "order": page_order},
                image=page["image"],
                title=page["title"],
                body=page["body"],
                cta_label=cta.get("label", ""),
                cta_deep_link=cta.get("deep_link") or "",
                duration_ms=page["duration_ms"],
            )

    for order, action in enumerate(content.QUICK_ACTIONS):
        load(
            QuickAction,
            {"key": action["key"]},
            order=order,
            label=action["label"],
            deep_link=action["deep_link"],
        )

    for placement, banners in content.BANNERS.items():
        for order, banner in enumerate(banners):
            load(
                Banner,
                {"placement": placement, "key": banner["key"]},
                order=order,
                image=banner["image"],
                alt=banner["alt"],
                deep_link=banner["deep_link"] or "",
            )

    for order, section in enumerate(content.LOTTERY_RULES["sections"]):
        load(
            LotterySection,
            {"order": order},
            icon=section["icon"] or "",
            title=section["title"],
            blocks=section["blocks"],
        )

    games = {}
    listed = [(game, False) for game in content.GAMES["games"]]
    listed += [(game, True) for game in content.GAMES["reward_games"]]
    for order, (game, is_reward) in enumerate(listed):
        games[game["id"]] = load(
            Game,
            {"slug": game["id"]},
            order=order,
            name=game["name"],
            image=game["image"],
            is_reward=is_reward,
        )
    tournament = content.GAMES["tournament"]
    load(
        Tournament,
        {"order": 0},
        title=tournament["title"],
        game=games[tournament["game"]],
        prize=tournament["prize"],
        participants=tournament["participants"],
        ends_at=datetime.fromisoformat(tournament["ends_at"]),
        cta=tournament["cta"],
    )

    offers = {
        "app": content.APP_OFFERS,
        "aztelekom": content.AZTELEKOM,
        "perk": content.PERKS,
        "campaign": content.CAMPAIGNS,
    }
    for kind, items in offers.items():
        for order, offer in enumerate(items):
            load(
                Offer,
                {"kind": kind, "slug": offer["id"]},
                order=order,
                name=offer["name"],
                sub=offer["sub"],
                price=Decimal(offer["price"]) if offer.get("price") else None,
                image=offer["image"],
                deep_link=offer["deep_link"] or "",
            )


def _referral(load):
    for order, step in enumerate(referral.STEPS):
        load(ReferralStep, {"order": order}, title=step["title"], body=step["body"])


@transaction.atomic
def seed_catalogue(refresh: bool = False) -> None:
    """Create the catalogue rows that are missing; with `refresh`, reset the seeded ones too."""
    load = Loader(refresh)
    for section in (_tariffs, _packs, _kredit, _sim, _content, _referral):
        section(load)
