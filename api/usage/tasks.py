from celery import shared_task

from . import insights, offers


@shared_task
def refresh_offers() -> dict[str, int]:
    """Expire old personal offers and create the ones the rules call for."""
    return offers.refresh()


@shared_task
def refresh_insights() -> int:
    """Recompute every subscriber's segment, totals and top recommendation."""
    return insights.refresh()
