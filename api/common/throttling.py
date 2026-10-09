"""Request limits, counted in the cache (Redis in Docker).

Rates come from `settings.THROTTLE_RATES` at request time, so they can be set
per environment and switched off: a scope without a rate is not limited.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class SettingsRateThrottle(SimpleRateThrottle):
    def get_rate(self):
        return settings.THROTTLE_RATES.get(self.scope)

    def key(self, ident) -> str:
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SubscriberThrottle(SettingsRateThrottle):
    """The wide limit on everything a subscriber does."""

    scope = "subscriber"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.key(request.user.pk)
        return self.key(self.get_ident(request))


class MoneyThrottle(SettingsRateThrottle):
    """A tighter limit on the POSTs that move money."""

    scope = "money"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.key(request.user.pk)
        return None


class OtpIpThrottle(SettingsRateThrottle):
    """Sign-in attempts from one address."""

    scope = "otp_ip"

    def get_cache_key(self, request, view):
        return self.key(self.get_ident(request))


class OtpPhoneThrottle(SettingsRateThrottle):
    """Sign-in attempts for one number, wherever they come from."""

    scope = "otp_phone"

    def get_cache_key(self, request, view):
        data = request.data if isinstance(request.data, dict) else {}
        target = data.get("msisdn") or data.get("request_id")
        return self.key(str(target)[:64]) if target else None


SUBSCRIBER = (SubscriberThrottle,)
MONEY = (SubscriberThrottle, MoneyThrottle)
OTP = (OtpIpThrottle, OtpPhoneThrottle)
