"""Building views from plain handler functions.

    balance_view = route("billing", get=balance)
    cards_view = route("billing", get=cards, post=Todo(notice, "Add a card"))

A handler takes `(request, **url_kwargs)` and returns a body, a
`(body, status)` pair or a ready response. Authentication, permissions,
throttling, the error shape and the Swagger entry are the same for all of them
and live here, so a handler holds nothing but its own endpoint.
"""

from django.http.response import HttpResponseBase
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import schema, throttling
from .exceptions import NotImplementedYet


class Todo:
    """A `:todo` method: answers `501 not_implemented` with the app's notice text.

    `detail` is the notice, or a function `(request, **url_kwargs)` returning it.
    """

    def __init__(self, detail, summary, *, body=None, errors=()):
        self.detail = detail
        self.summary = summary
        self.body = body
        self.errors = tuple(errors)

    def text(self, request, **kwargs):
        return self.detail(request, **kwargs) if callable(self.detail) else self.detail


class IgnoreAccept(BaseContentNegotiation):
    """Always render JSON, whatever `Accept` says (used by the SSE endpoint)."""

    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class RouteView(APIView):
    handlers: dict = {}
    otp = False

    def get_throttles(self):
        handler = self.handlers.get(self.request.method.lower())
        if self.otp:
            classes = throttling.OTP
        elif getattr(handler, "idempotent", False):
            classes = throttling.MONEY
        else:
            classes = throttling.SUBSCRIBER
        return [throttle() for throttle in classes]


def route(tag, *, public=False, accept_any=False, throttle=None, parsers=None, **handlers):
    """Build a view from per-method handlers, e.g. `route("sim", get=line, patch=line_update)`.

    public      no credentials needed (the sign-in endpoints)
    accept_any  do not reject on the `Accept` header
    throttle    `"otp"` applies the sign-in limits instead of the subscriber ones
    parsers     request parsers instead of the JSON default (file uploads)
    """
    attrs = {
        "handlers": handlers,
        "otp": throttle == "otp",
        "permission_classes": [AllowAny] if public else [IsAuthenticated],
    }
    if parsers:
        attrs["parser_classes"] = parsers
    if public:
        attrs["authentication_classes"] = []
    if accept_any:
        attrs["content_negotiation_class"] = IgnoreAccept
    for method, handler in handlers.items():
        view = _todo(handler) if isinstance(handler, Todo) else _ready(handler)
        attrs[method] = schema.describe(tag, method, handler, public=public, otp=throttle == "otp")(
            view
        )
    return type("RouteView", (RouteView,), attrs).as_view()


def _todo(handler):
    def view(self, request, **kwargs):
        raise NotImplementedYet(handler.text(request, **kwargs))

    return view


def _ready(handler):
    def view(self, request, **kwargs):
        result = handler(request, **kwargs)
        if isinstance(result, HttpResponseBase):
            return result
        if isinstance(result, tuple):
            body, status = result
            return Response(body, status=status)
        return Response(result)

    return view
