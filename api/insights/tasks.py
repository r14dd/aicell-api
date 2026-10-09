from celery import shared_task

from . import services


@shared_task
def detect_insights() -> int:
    """Run every detector for every subscriber. Returns how many insights are open."""
    return services.refresh_all()
