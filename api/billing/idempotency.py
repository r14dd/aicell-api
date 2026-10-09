import uuid
from functools import wraps

from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _
from rest_framework.response import Response

from api.common.exceptions import InvalidInput

from .models import IdempotencyKey


def idempotent(handler):
    """Require `Idempotency-Key` (UUID) and replay the stored response on a repeat.

    The handler runs in one database transaction together with the key, so a
    request either moves money and is remembered, or does neither. Only
    successful responses are stored: a failed attempt moved nothing, so
    retrying it with the same key simply runs again.
    """

    @wraps(handler)
    def wrapper(request, **kwargs):
        raw = request.headers.get("Idempotency-Key")
        if not raw:
            raise InvalidInput(_("Idempotency-Key header is required"))
        try:
            key = uuid.UUID(raw)
        except ValueError:
            raise InvalidInput(_("Idempotency-Key must be a UUID")) from None

        def replay():
            record = IdempotencyKey.objects.filter(subscriber=request.user, key=key).first()
            if record is None:
                return None
            if record.path != request.path:
                raise InvalidInput(_("Idempotency-Key was already used for another request"))
            return Response(record.body, status=record.status)

        stored = replay()
        if stored is not None:
            return stored
        try:
            with transaction.atomic():
                body, status = handler(request, **kwargs)
                IdempotencyKey.objects.create(
                    subscriber=request.user, key=key, path=request.path, status=status, body=body
                )
        except IntegrityError:
            # A concurrent request with the same key won; its rollback undid ours.
            stored = replay()
            if stored is None:
                raise
            return stored
        return Response(body, status=status)

    wrapper.idempotent = True
    return wrapper
