"""OpenAPI: turns what a handler says about itself (`@doc`) into its Swagger entry."""

import json
import re
from functools import cache
from pathlib import Path

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from drf_spectacular.openapi import AutoSchema as SpectacularAutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers

EXAMPLES_FILE = Path(__file__).parent / "examples.json"
SSE = "text/event-stream"

ERROR_NOTES = {
    400: "`validation_error` — the input is wrong; `errors` lists the fields",
    401: "`not_authenticated` or `token_expired`",
    402: "`insufficient_balance` — the wallet cannot cover the charge",
    403: "`forbidden`",
    404: "`not_found`",
    409: "`already_active` — the pack or service is already on; `offer_closed` / `insight_closed` — it was already decided",
    429: "`rate_limited` — see the `Retry-After` header",
    501: "`not_implemented` — `detail` is the app's notice text",
    502: "`laya_unavailable` — the model failed or gave an answer that was rejected",
}
ERROR_EXAMPLES = {
    400: {
        "code": "validation_error",
        "detail": "This field is required.",
        "errors": {"amount": ["This field is required."]},
    },
    401: {"code": "not_authenticated", "detail": "Authentication required"},
    402: {"code": "insufficient_balance", "detail": "Not enough balance for this pack"},
    403: {"code": "forbidden", "detail": "You do not have permission to perform this action."},
    404: {"code": "not_found", "detail": "Not found."},
    409: {"code": "already_active", "detail": "This service is already active"},
    429: {"code": "rate_limited", "detail": "Too many requests, try again in 42 seconds"},
    501: {"code": "not_implemented", "detail": "This is not part of this prototype yet"},
    502: {"code": "laya_unavailable", "detail": "Laya is not available right now"},
}


class ErrorSerializer(serializers.Serializer):
    """The one error shape of the API."""

    code = serializers.CharField(help_text="Stable, machine-readable; branch on this")
    detail = serializers.CharField(help_text="For people, in the language of `Accept-Language`")


class ValidationErrorSerializer(ErrorSerializer):
    errors = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False,
        help_text="Messages per field, when the body or query failed validation",
    )


class BearerScheme(SimpleJWTScheme):
    """Makes Swagger's Authorize button send `Authorization: Bearer <access-jwt>`."""

    target_class = "api.common.auth.BearerAuthentication"
    name = "bearerAuth"


ACCEPT_LANGUAGE = OpenApiParameter(
    "Accept-Language",
    location=OpenApiParameter.HEADER,
    enum=["az", "ru", "en"],
    default="en",
    description="Language of the copy in the answer. Unsupported or missing: `en`.",
)
IDEMPOTENCY_KEY = OpenApiParameter(
    "Idempotency-Key",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.HEADER,
    required=True,
    description="A UUID per attempt. Repeating a request with the same key returns "
    "the first answer and moves no money.",
)


class AutoSchema(SpectacularAutoSchema):
    def get_operation_id(self):
        """`<method>_<path>`: unique by construction, readable in generated clients."""
        path = re.sub(r"[{}]", "", self.path).strip("/").removeprefix("api/")
        return "_".join([*re.split(r"[/\-]", path), self.method.lower()])


# --- response schemas from recorded examples --------------------------------


@cache
def examples() -> dict:
    """Recorded answers of every ready endpoint, keyed by `"<METHOD> <operation>"`."""
    return json.loads(EXAMPLES_FILE.read_text()) if EXAMPLES_FILE.exists() else {}


def infer(value) -> dict:
    """The JSON schema of a recorded answer."""
    if isinstance(value, dict):
        return {"type": "object", "properties": {key: infer(item) for key, item in value.items()}}
    if isinstance(value, list):
        return {"type": "array", "items": infer(value[0]) if value else {}}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if value is None:
        return {"type": "string", "nullable": True}
    return {"type": "string"}


def example_key(method: str, handler) -> str:
    return f"{method.upper()} {handler.__module__.split('.')[1]}.{handler.__name__}"


def _success(method, handler):
    recorded = examples().get(example_key(method, handler))
    if recorded is None:
        return OpenApiTypes.OBJECT
    return {**infer(recorded), "example": recorded}


def _error(status):
    serializer = ValidationErrorSerializer if status == 400 else ErrorSerializer
    return OpenApiResponse(
        serializer,
        description=ERROR_NOTES[status],
        examples=[
            OpenApiExample(
                str(status), value=ERROR_EXAMPLES[status], response_only=True, status_codes=[status]
            )
        ],
    )


def describe(tag, method, handler, *, public=False, otp=False):
    """The `extend_schema` decorator for one HTTP method of a route."""
    from .routing import Todo  # routing imports this module

    todo = isinstance(handler, Todo)
    info = None if todo else handler.doc
    money = getattr(handler, "idempotent", False)

    errors = set(handler.errors if todo else info.errors)
    if not public:
        errors.add(401)
    if money:
        errors |= {400, 429}
    if otp:
        errors.add(429)
    if todo:
        errors.add(501)

    parameters = [ACCEPT_LANGUAGE]
    if money:
        parameters.append(IDEMPOTENCY_KEY)

    if todo:
        return extend_schema(
            tags=[tag],
            summary=f"{handler.summary} · :todo",
            description="Routed at its final path. Answers `501 not_implemented`; "
            "`detail` carries the app's notice text.",
            request=handler.body,
            parameters=parameters,
            responses={status: _error(status) for status in sorted(errors)},
            auth=[] if public else None,
        )

    if info.query:
        parameters.append(info.query)
    parameters += [
        OpenApiParameter(
            name,
            type=int if isinstance(sample, int) else str,
            location=OpenApiParameter.PATH,
            examples=[OpenApiExample(str(sample), value=sample)],
        )
        for name, sample in info.path.items()
    ]

    responses = {status: _error(status) for status in sorted(errors)}
    if info.streams:
        responses[(200, SSE)] = OpenApiResponse(
            OpenApiTypes.STR,
            description="Server-Sent Events: `message`, text chunks, `action`, `log`, `done`",
        )
        responses[(201, "application/json")] = _success(method, handler)
    else:
        responses[info.status] = _success(method, handler)

    request_examples = []
    if info.example is not None:
        request_examples.append(OpenApiExample("Example", value=info.example, request_only=True))

    return extend_schema(
        tags=[tag],
        summary=info.summary,
        description=_description(handler),
        request=info.body,
        parameters=parameters,
        responses=responses,
        examples=request_examples,
        auth=[] if public else None,
    )


def _description(handler) -> str:
    lines = [line.strip() for line in (handler.__doc__ or "").strip().splitlines()]
    return "\n".join(lines)
