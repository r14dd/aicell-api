from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import ExpiredTokenError, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .exceptions import TokenExpired


class BearerAuthentication(JWTAuthentication):
    """`Authorization: Bearer <access-jwt>`.

    Tells an expired token apart from an invalid one by its error type, not by
    its message, so the `token_expired` code does not depend on the language.
    """

    def get_validated_token(self, raw_token):
        try:
            return AccessToken(raw_token)
        except ExpiredTokenError as error:
            raise TokenExpired() from error
        except TokenError:
            return super().get_validated_token(raw_token)


class DemoAuthentication(BaseAuthentication):
    """Acts as the seeded demo subscriber when no Authorization header is sent.

    Only active while `settings.DEMO_AUTH` is on; the app has no login screen
    yet, so this is what lets it call the `ready` endpoints.
    """

    def authenticate(self, request):
        if not settings.DEMO_AUTH or request.META.get("HTTP_AUTHORIZATION"):
            return None
        user = get_user_model().objects.filter(msisdn=settings.DEMO_MSISDN, is_active=True).first()
        return (user, None) if user else None
