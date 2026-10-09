"""The layering rules of README "Architecture", checked on the import graph.

    urls -> views -> services  -> models
                 \\-> catalogue -> models
                 \\-> texts

A rule that is only written down erodes; these fail the build instead.
"""

import ast
from pathlib import Path

import pytest

API = Path(__file__).resolve().parent.parent / "api"
DOMAINS = sorted(path.name for path in API.iterdir() if (path / "urls.py").exists())
HTTP_MODULES = (
    "rest_framework",
    "django.http",
    "django.shortcuts",
    "api.common.http",
    "api.common.routing",
    "api.common.schema",
    "api.common.docs",
)
BELOW_VIEWS = ("services.py", "catalogue.py", "models.py", "texts.py", "tasks.py", "responder.py")


def imports(path: Path) -> set[str]:
    """Absolute module names imported by a file inside `api/<domain>/`."""
    package = ".".join(path.relative_to(API.parent).with_suffix("").parts[:-1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package if node.level else ""
            module = ".".join(part for part in (base, node.module) if part)
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def test_every_domain_was_found():
    assert DOMAINS == [
        "assistant",
        "billing",
        "content",
        "kredit",
        "packs",
        "referral",
        "sim",
        "tariffs",
        "users",
    ]


@pytest.mark.parametrize("domain", DOMAINS)
def test_business_rules_do_not_depend_on_http(domain):
    """Everything below the views knows nothing about requests, responses or views."""
    for layer in BELOW_VIEWS:
        path = API / domain / layer
        if not path.exists():
            continue
        for module in imports(path):
            assert not module.startswith(HTTP_MODULES), f"{domain}/{layer} imports {module}"
            assert ".views" not in module and ".urls" not in module, (
                f"{domain}/{layer} imports {module}"
            )


@pytest.mark.parametrize("domain", DOMAINS)
def test_domains_do_not_reach_into_each_others_views(domain):
    for path in (API / domain).glob("*.py"):
        for module in imports(path):
            other = module.removeprefix("api.").split(".")[0]
            if module.startswith("api.") and other in DOMAINS and other != domain:
                assert ".views" not in module, f"{domain}/{path.name} imports {module}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_views_do_not_write_to_the_wallet_directly(domain):
    """Money moves only through billing.services, so every change is recorded."""
    views = API / domain / "views.py"
    assert "Wallet" not in views.read_text(), f"{domain}/views.py touches Wallet"


@pytest.mark.parametrize("domain", DOMAINS)
def test_seed_data_is_used_only_for_seeding(domain):
    """The API reads the catalogue from the database, never from the seed files."""
    for path in (API / domain).glob("*.py"):
        for module in imports(path):
            assert not module.startswith("api.seeding"), f"{domain}/{path.name} imports {module}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_admin_code_stays_out_of_the_api(domain):
    for path in (API / domain).glob("*.py"):
        if path.name == "admin.py":
            continue
        for module in imports(path):
            assert not module.endswith(".admin") and "unfold" not in module, (
                f"{domain}/{path.name} imports {module}"
            )
