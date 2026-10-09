"""Read side of the content catalogue: models to the documented JSON shapes.

Image values are file names here; views turn them into absolute URLs, so the
cached JSON does not depend on the host of the request.
"""

from api.common.cache import cached
from api.common.formatting import iso, money

from .models import Banner, Game, LotterySection, Offer, QuickAction, Story, Tournament


def _page(page) -> dict:
    cta = None
    if page.cta_label:
        cta = {"label": page.cta_label, "deep_link": page.cta_deep_link or None}
    return {
        "image": page.image,
        "title": page.title,
        "body": page.body,
        "cta": cta,
        "duration_ms": page.duration_ms,
    }


@cached("content.stories")
def stories() -> list[dict]:
    """Stories in shelf order, each with its pages."""
    return [
        {
            "key": story.key,
            "label": story.label,
            "image": story.image,
            "pages": [_page(page) for page in story.pages.all() if page.is_active],
        }
        for story in Story.objects.active().prefetch_related("pages")
    ]


@cached("content.quick_actions")
def quick_actions() -> list[dict]:
    return [
        {"key": action.key, "label": action.label, "deep_link": action.deep_link}
        for action in QuickAction.objects.active()
    ]


@cached("content.banners")
def banners() -> dict[str, list[dict]]:
    """Banners grouped by placement."""
    grouped: dict[str, list[dict]] = {placement: [] for placement, _label in Banner.PLACEMENTS}
    for banner in Banner.objects.active():
        grouped[banner.placement].append(
            {
                "key": banner.key,
                "image": banner.image,
                "alt": banner.alt,
                "deep_link": banner.deep_link or None,
            }
        )
    return grouped


@cached("content.lottery_sections")
def lottery_sections() -> list[dict]:
    return [
        {"icon": section.icon or None, "title": section.title, "blocks": section.blocks}
        for section in LotterySection.objects.active()
    ]


def _game(game) -> dict:
    return {"id": game.slug, "name": game.name, "image": game.image}


@cached("content.games")
def games() -> dict:
    listed = list(Game.objects.active())
    tournament = Tournament.objects.active().select_related("game").first()
    return {
        "games": [_game(game) for game in listed if not game.is_reward],
        "reward_games": [_game(game) for game in listed if game.is_reward],
        "tournament": tournament
        and {
            "title": tournament.title,
            "game": tournament.game.slug,
            "prize": tournament.prize,
            "participants": tournament.participants,
            "ends_at": iso(tournament.ends_at),
            "cta": tournament.cta,
        },
    }


@cached("content.offers")
def offers() -> dict[str, list[dict]]:
    """Offers grouped by kind; `price` appears only on offers that have one."""
    grouped: dict[str, list[dict]] = {kind: [] for kind, _label in Offer.KINDS}
    for offer in Offer.objects.active():
        item = {"id": offer.slug, "name": offer.name, "sub": offer.sub}
        if offer.price is not None:
            item["price"] = money(offer.price)
        item.update(image=offer.image, deep_link=offer.deep_link or None)
        grouped[offer.kind].append(item)
    return grouped
