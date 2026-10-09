import math

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, JsonResponse
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.response import Response


class ApiError(exceptions.APIException):
    """Renders as `{ "code": ..., "detail": ..., **extra }`."""

    status_code = 400
    code = "error"

    def __init__(self, detail=None, **extra):
        super().__init__(detail or self.default_detail)
        self.extra = extra


class InvalidInput(ApiError):
    status_code = 400
    code = "validation_error"
    default_detail = _("Invalid input")


class NotFound(ApiError):
    status_code = 404
    code = "not_found"
    default_detail = _("Not found.")


class InsufficientBalance(ApiError):
    status_code = 402
    code = "insufficient_balance"
    default_detail = _("Not enough balance")


class AlreadyActive(ApiError):
    status_code = 409
    code = "already_active"
    default_detail = _("Already active")


class OfferClosed(ApiError):
    status_code = 409
    code = "offer_closed"
    default_detail = _("This offer is no longer available")


class InsightClosed(ApiError):
    status_code = 409
    code = "insight_closed"
    default_detail = _("This insight is already closed")


class RateLimited(ApiError):
    status_code = 429
    code = "rate_limited"
    default_detail = _("Too many requests")


class NotImplementedYet(ApiError):
    status_code = 501
    code = "not_implemented"
    default_detail = _("This is not part of this prototype yet")


class TokenExpired(exceptions.AuthenticationFailed):
    """The bearer token was valid once; the client should refresh it."""


CODES = {
    exceptions.ParseError: "validation_error",
    exceptions.PermissionDenied: "forbidden",
    exceptions.NotFound: "not_found",
}


def _first_message(detail):
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), "Invalid input")
        return _first_message(detail)
    if isinstance(detail, (list, tuple)):
        return _first_message(detail[0]) if detail else "Invalid input"
    return str(detail)


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    if not isinstance(exc, exceptions.APIException):
        return None

    headers = {}
    if getattr(exc, "auth_header", None):
        headers["WWW-Authenticate"] = exc.auth_header

    if isinstance(exc, ApiError):
        body = {"code": exc.code, "detail": str(exc.detail), **exc.extra}
    elif isinstance(exc, exceptions.ValidationError):
        body = {
            "code": "validation_error",
            "detail": _first_message(exc.detail),
            "errors": exc.detail,
        }
    elif isinstance(exc, TokenExpired):
        body = {"code": "token_expired", "detail": str(_("Token expired"))}
    elif isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        body = {"code": "not_authenticated", "detail": str(_("Authentication required"))}
    elif isinstance(exc, exceptions.Throttled):
        headers["Retry-After"] = str(math.ceil(exc.wait or 0))
        body = {
            "code": "rate_limited",
            "detail": _("Too many requests, try again in %(seconds)s seconds")
            % {"seconds": headers["Retry-After"]},
        }
    else:
        body = {"code": CODES.get(type(exc), exc.default_code), "detail": str(exc.detail)}

    # Imported here: rest_framework.views loads the authentication classes,
    # which import this module.
    from rest_framework.views import set_rollback

    set_rollback()
    return Response(body, status=exc.status_code, headers=headers)


def not_found_view(request, exception=None):
    return JsonResponse({"code": "not_found", "detail": str(_("Not found."))}, status=404)


def server_error_view(request):
    return JsonResponse({"code": "server_error", "detail": str(_("Server error"))}, status=500)
