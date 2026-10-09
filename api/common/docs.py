"""What an endpoint tells Swagger about itself.

A handler is described once, next to its code, with `@doc`. `api.common.schema`
turns the description into the OpenAPI operation.
"""

from dataclasses import dataclass, field

from rest_framework import serializers


@dataclass(frozen=True)
class Doc:
    summary: str
    body: type[serializers.Serializer] | None = None
    query: type[serializers.Serializer] | None = None
    example: dict | None = None
    path: dict = field(default_factory=dict)
    errors: tuple[int, ...] = ()
    status: int = 200
    streams: bool = False


def doc(
    summary, *, body=None, query=None, example=None, path=None, errors=(), status=200, streams=False
):
    """Describe a handler for Swagger.

    summary  one line shown in the endpoint list
    body     serializer of the request body
    query    serializer of the query string
    example  a request body that works against the seeded data
    path     sample values of the path parameters, e.g. `{"slug": "tehsil"}`
    errors   status codes the handler can answer besides 401
    status   the success status
    streams  the success answer is a Server-Sent Events stream

    The handler's docstring becomes the longer description.
    """

    def decorator(handler):
        handler.doc = Doc(summary, body, query, example, path or {}, tuple(errors), status, streams)
        return handler

    return decorator
