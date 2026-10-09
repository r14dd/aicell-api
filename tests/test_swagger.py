"""The OpenAPI schema describes every endpoint, and describes it truthfully."""

import io
import json

import pytest
from django.core.management import call_command

from api.common import schema
from api.common.management.commands.record_examples import call, ready_endpoints
from api.common.routing import Todo

from .test_docs_conformance import ROWS

PUBLIC = {"/api/users/otp/send/", "/api/users/otp/verify/", "/api/users/token/refresh/"}
MONEY = {
    "/api/billing/top-up/card/",
    "/api/billing/top-up/akart/",
    "/api/billing/top-up/google-pay/",
    "/api/billing/steam/top-up/",
    "/api/packs/internet/purchase/",
    "/api/packs/social/{slug}/activate/",
    "/api/packs/roaming/purchase/",
    "/api/sim/services/{slug}/subscribe/",
    "/api/usage/offers/{id}/accept/",
    "/api/tariffs/subscribe/",
    "/api/tariffs/change/",
    "/api/tariffs/my/renew/",
}


@pytest.fixture(scope="module")
def spec(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        out = io.StringIO()
        call_command("spectacular", "--format", "openapi-json", stdout=out)
    return json.loads(out.getvalue())


def operations(spec):
    return [
        (path, method, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
    ]


def test_schema_is_valid_and_free_of_warnings(db):
    """The same check as `manage.py spectacular --validate --fail-on-warn`."""
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=io.StringIO())


def test_every_endpoint_of_the_docs_is_in_the_schema(spec):
    assert len(operations(spec)) == 129  # the 127 documented paths x methods + 2 health probes
    assert {tag for _, _, operation in operations(spec) for tag in operation["tags"]} == {
        "users", "billing", "tariffs", "packs", "kredit", "sim", "content", "referral",
        "assistant", "usage", "laya", "insights", "health",
    }  # fmt: skip


def test_every_operation_is_described(spec):
    ids = [operation["operationId"] for _, _, operation in operations(spec)]
    assert len(ids) == len(set(ids))
    for path, method, operation in operations(spec):
        where = f"{method.upper()} {path}"
        assert len(operation["tags"]) == 1, where
        assert operation.get("summary"), where
        assert operation.get("description"), where


def test_language_header_is_a_choice_on_every_api_operation(spec):
    for path, method, operation in operations(spec):
        if path.startswith("/api/health/"):
            continue
        header = next(
            (p for p in operation.get("parameters", []) if p["name"] == "Accept-Language"), None
        )
        assert header, f"{method.upper()} {path}"
        assert header["in"] == "header"
        assert sorted(header["schema"]["enum"]) == ["az", "en"]


def test_idempotency_key_is_required_exactly_on_money_posts(spec):
    with_key = set()
    for path, _method, operation in operations(spec):
        header = next(
            (p for p in operation.get("parameters", []) if p["name"] == "Idempotency-Key"), None
        )
        if header:
            assert header["in"] == "header" and header["required"] is True
            assert header["schema"] == {"type": "string", "format": "uuid"}
            with_key.add(path)
    assert with_key == MONEY


def test_error_responses_are_documented(spec):
    for path, method, operation in operations(spec):
        where = f"{method.upper()} {path}"
        responses = operation["responses"]
        if path.startswith("/api/health/"):
            continue
        assert ("401" in responses) == (path not in PUBLIC), where
        if ":todo" in operation["summary"]:
            assert "501" in responses, where
        if path in MONEY and method == "post":
            assert {"400", "429"} <= set(responses), where
    purchase = spec["paths"]["/api/packs/internet/purchase/"]["post"]["responses"]
    assert set(purchase) == {"201", "400", "401", "402", "429"}
    subscribe = spec["paths"]["/api/sim/services/{slug}/subscribe/"]["post"]["responses"]
    assert {"402", "404", "409"} <= set(subscribe)
    # every code the API can answer is used somewhere
    used = {code for _, _, operation in operations(spec) for code in operation["responses"]}
    assert {"400", "401", "402", "404", "409", "429", "501"} <= used


def test_error_bodies_use_the_shared_shape(spec):
    error = spec["components"]["schemas"]["Error"]
    assert set(error["properties"]) == {"code", "detail"}
    assert "errors" in spec["components"]["schemas"]["ValidationError"]["properties"]


def test_inputs_are_typed(spec):
    components = spec["components"]["schemas"]
    card = components["CardTopUpInputRequest"]
    assert set(card["required"]) == {"card_bin", "amount"}
    assert card["properties"]["card_bin"]["pattern"] == r"^\d{6}$"

    body = spec["paths"]["/api/billing/top-up/card/"]["post"]["requestBody"]["content"]
    assert body["application/json"]["examples"]["Example"]["value"] == {
        "card_bin": "416300",
        "amount": "25.00",
    }

    top_ups = spec["paths"]["/api/billing/top-ups/"]["get"]["parameters"]
    query = {p["name"]: p["schema"] for p in top_ups if p["in"] == "query"}
    assert query["from"] == {"type": "string", "format": "date"}
    assert query["limit"]["type"] == "integer"

    placement = next(
        p
        for p in spec["paths"]["/api/content/banners/"]["get"]["parameters"]
        if p["name"] == "placement"
    )
    assert sorted(placement["schema"]["enum"]) == ["benefits", "home", "partners", "products"]

    slug = next(
        p
        for p in spec["paths"]["/api/packs/social/{slug}/"]["get"]["parameters"]
        if p["name"] == "slug"
    )
    assert slug["in"] == "path" and slug["required"] is True
    assert slug["examples"]["Tehsil"]["value"] == "tehsil"


def test_authorize_button_uses_bearer_tokens(spec, anon):
    assert spec["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    me = spec["paths"]["/api/users/me/"]["get"]
    assert {"bearerAuth": []} in me["security"]
    assert "security" not in spec["paths"]["/api/users/otp/send/"]["post"]
    assert anon.get("/api/swagger/").status_code == 200
    assert anon.get("/api/schema/").status_code == 200


# --- recorded examples ------------------------------------------------------


def shape(value):
    """Structure without values: keys of objects, the type of everything else."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return "null" if value is None else type(value).__name__


def same_shape(live, recorded, where=""):
    if "null" in (live, recorded) or [] in (live, recorded):
        return  # a value that may be empty tells nothing about the other side
    if isinstance(recorded, dict):
        assert isinstance(live, dict) and set(live) == set(recorded), where
        for key in recorded:
            same_shape(live[key], recorded[key], f"{where}.{key}")
    elif isinstance(recorded, list):
        same_shape(live[0], recorded[0], f"{where}[]")
    else:
        assert live == recorded, where


def test_every_ready_endpoint_has_a_recorded_example():
    recorded = schema.examples()
    expected = {schema.example_key(method, handler) for method, _, handler in ready_endpoints()}
    assert set(recorded) == expected, "run `manage.py record_examples`"


def test_recorded_examples_match_what_the_server_answers(client):
    """Swagger's response schemas come from the recordings; they must not drift."""
    recorded = schema.examples()
    for method, path, handler in ready_endpoints():
        response = call(client, method, path, handler)
        key = schema.example_key(method, handler)
        same_shape(shape(response.json()), shape(recorded[key]), key)


def test_response_schemas_come_from_the_examples(spec):
    balance = spec["paths"]["/api/billing/balance/"]["get"]["responses"]["200"]
    body = balance["content"]["application/json"]["schema"]
    assert body["properties"]["balance"] == {"type": "string"}
    assert body["example"]["currency"] == "AZN"

    stream = spec["paths"]["/api/assistant/conversations/{id}/messages/"]["post"]["responses"]
    assert "text/event-stream" in stream["200"]["content"]
    assert "application/json" in stream["201"]["content"]


def test_todo_handlers_are_marked(spec):
    todo = [o for _, _, o in operations(spec) if ":todo" in o["summary"]]
    documented = [row for row in ROWS if row[2] == ":todo"]
    # `GET games/?q=` is :todo in the docs but shares its operation with `GET games/`.
    assert len(todo) == len(documented) - 1
    assert all(isinstance(handler, Todo) is False for _, _, handler in ready_endpoints())
