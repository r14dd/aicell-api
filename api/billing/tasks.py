from celery import shared_task
from django.conf import settings

from . import services


@shared_task
def purge_idempotency_keys() -> int:
    """Forget stored replies of money requests that are too old to be retried."""
    return services.purge_idempotency_keys(settings.IDEMPOTENCY_KEY_DAYS)
