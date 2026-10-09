from celery import shared_task

from . import services


@shared_task
def expire_activations() -> int:
    """Switch off packs whose time has run out."""
    return services.expire_activations()
