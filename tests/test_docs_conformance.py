"""Every row of the endpoint tables in docs/api/*.md is checked against the server.

`:todo` rows must answer 501 `not_implemented`; `ready` / `:dummy` GET rows
must answer 200. Writes that are `ready` have their own tests per domain.
"""

import re
from pathlib import Path

import pytest

from api.seeding import DEMO_CONVERSATION_ID, DEMO_INSIGHT_ID, DEMO_OFFER_ID

DOCS = Path(__file__).resolve().parent.parent / "docs" / "api"
ROW = re.compile(r"^\| (GET|POST|PATCH|DELETE) \| `([^`]*)`[^|]*\| `([^`]+)` \|")

# Sample values for the path parameters, per domain.
PARAMS = {
    "billing": {"<id>": "1"},
    "tariffs": {"<family>": "digimax"},
    "packs": {"<slug>": "tehsil"},
    "kredit": {"<slug>": "simtaksit"},
    "sim": {"<slug>": "missed-call"},
    "content": {"<key>": "especially", "<id>": "wingz", "<slug>": "ninja-saga-2"},
    "assistant": {"<id>": str(DEMO_CONVERSATION_ID)},
    "usage": {"<id>": str(DEMO_OFFER_ID)},
    "insights": {"<id>": str(DEMO_INSIGHT_ID)},
}


def rows():
    found = []
    for page in sorted(DOCS.glob("*.md")):
        domain = page.stem
        for line in page.read_text().splitlines():
            match = ROW.match(line)
            if not match:
                continue
            method, path, status = match.groups()
            path, _, query = path.partition("?")
            for placeholder, value in PARAMS.get(domain, {}).items():
                path = path.replace(placeholder, value)
            if path == "offers/apps/wingz/subscribe/":
                path = "offers/apps/kinon/subscribe/"
            # `GET games/?q=` is :todo while `GET games/` is ready.
            suffix = (
                "?q=test"
                if status == ":todo" and query.startswith("q=") and domain == "content"
                else ""
            )
            found.append((method, f"/api/{domain}/{path}{suffix}", status))
    return found


ROWS = rows()


def test_docs_tables_were_parsed():
    assert len(ROWS) == 126  # every endpoint row in docs/api/*.md
    assert {status for _, _, status in ROWS} == {"ready", ":todo", ":dummy"}


@pytest.mark.parametrize("method,path,status", [row for row in ROWS if row[2] == ":todo"])
def test_todo_endpoints_answer_501(client, method, path, status):
    response = client.generic(method, path, "{}", content_type="application/json")
    assert response.status_code == 501, response.content
    body = response.json()
    assert body["code"] == "not_implemented"
    assert body["detail"]


@pytest.mark.parametrize(
    "method,path,status", [row for row in ROWS if row[0] == "GET" and row[2] != ":todo"]
)
def test_ready_reads_answer_200(client, method, path, status):
    response = client.get(path)
    assert response.status_code == 200, response.content
    assert isinstance(response.json(), dict)


@pytest.mark.parametrize(
    "method,path,status", [row for row in ROWS if row[0] != "GET" and row[2] != ":todo"]
)
def test_ready_writes_are_routed(client, method, path, status):
    """An empty body may fail validation, but the route exists and is implemented."""
    response = client.generic(method, path, "{}", content_type="application/json")
    assert response.status_code not in (404, 405, 500, 501), response.content
