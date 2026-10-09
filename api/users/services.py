"""Signing in with a one-time code.

There is no SMS provider yet: every code is `settings.OTP_TEST_CODE`, so any
seeded subscriber signs in with the number alone. A request lives in the cache
for `OTP_TTL` seconds and allows `OTP_ATTEMPTS` wrong codes.
"""

import math
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.common.exceptions import ApiError, NotFound, RateLimited

from .models import Subscriber


class InvalidCode(ApiError):
    status_code = 400
    code = "invalid_code"


class InvalidToken(ApiError):
    status_code = 400
    code = "invalid_token"


def _request_key(request_id):
    return f"otp:request:{request_id}"


def _sent_key(msisdn):
    return f"otp:sent:{msisdn}"


def send(msisdn):
    """Start a sign-in for an existing subscriber; one per number per `OTP_RESEND_AFTER`."""
    if not Subscriber.objects.filter(msisdn=msisdn, is_active=True, is_staff=False).exists():
        raise NotFound(_("No subscriber with this number"))
    sent_at = cache.get(_sent_key(msisdn))
    if sent_at is not None:
        wait = math.ceil(sent_at + settings.OTP_RESEND_AFTER - time.time())
        if wait > 0:
            raise RateLimited(_("Try again in %(wait)d seconds") % {"wait": wait})
    cache.set(_sent_key(msisdn), time.time(), settings.OTP_RESEND_AFTER)
    return {
        "request_id": start(msisdn),
        "ttl": settings.OTP_TTL,
        "resend_after": settings.OTP_RESEND_AFTER,
    }


def start(msisdn):
    """A new sign-in request for `msisdn`, without the checks `send` makes; its id."""
    request_id = secrets.token_hex(16)
    cache.set(
        _request_key(request_id),
        {"msisdn": msisdn, "attempts_left": settings.OTP_ATTEMPTS},
        settings.OTP_TTL,
    )
    return request_id


def verify(request_id, code):
    """The subscriber and a fresh token pair, or `InvalidCode` with the attempts left."""
    key = _request_key(request_id)
    pending = cache.get(key)
    if pending is None:
        raise InvalidCode(_("The code has expired, request a new one"), attempts_left=0)
    if not secrets.compare_digest(code, settings.OTP_TEST_CODE):
        left = pending["attempts_left"] - 1
        if left > 0:
            cache.set(key, {**pending, "attempts_left": left}, settings.OTP_TTL)
        else:
            cache.delete(key)
        raise InvalidCode(_("Wrong code"), attempts_left=left)
    cache.delete(key)
    subscriber = Subscriber.objects.filter(
        msisdn=pending["msisdn"], is_active=True, is_staff=False
    ).first()
    if subscriber is None:
        raise InvalidCode(_("The code has expired, request a new one"), attempts_left=0)
    refresh = RefreshToken.for_user(subscriber)
    return subscriber, {"access": str(refresh.access_token), "refresh": str(refresh)}


def refresh(token):
    """A new access token for a valid refresh token."""
    try:
        return {"access": str(RefreshToken(token).access_token)}
    except TokenError:
        raise InvalidToken(_("The refresh token is invalid or has expired")) from None
