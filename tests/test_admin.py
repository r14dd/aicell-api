"""The admin panel: every model is there, every role sees exactly its share."""

import re

import pytest
from django.apps import apps
from django.contrib import admin
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api.billing.models import SavedCard, Transaction
from api.common.admin import ReadOnlyMixin
from api.common.models import CatalogueItem
from api.packs.models import PackActivation
from api.seeding import seed_staff
from api.seeding.staff import FINANCE_MODELS, SUPPORT_MODELS, catalogue_models
from api.tariffs.models import TariffPlan
from api.users.models import Subscriber

API_APPS = {
    "users",
    "billing",
    "tariffs",
    "packs",
    "kredit",
    "sim",
    "content",
    "referral",
    "assistant",
}
API_MODELS = [model for model in apps.get_models() if model._meta.app_label in API_APPS]
REGISTERED = sorted(admin.site._registry, key=lambda model: model._meta.label)
ROLES = ["superadmin", "content", "support", "finance"]
MONEY_RECORDS = ["billing.Transaction", "billing.TopUp", "billing.IdempotencyKey"]


def url(model, page, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{page}", args=args)


def label(model):
    return model._meta.label


@pytest.fixture
def staff(subscriber, other):
    """The four seeded accounts, with two subscribers' worth of data to look at."""
    return {account.msisdn: account for account in seed_staff()}


@pytest.fixture
def panel(staff):
    """`panel("finance")` is a browser session signed in as that account."""

    def sign_in(login):
        client = Client(raise_request_exception=False)
        client.force_login(staff[login])
        return client

    return sign_in


# --- registration -----------------------------------------------------------


def test_every_model_is_registered():
    missing = [label(model) for model in API_MODELS if model not in admin.site._registry]
    assert not missing


@pytest.mark.parametrize("model", REGISTERED, ids=label)
def test_list_pages_are_set_up(model):
    """Each list has its key columns, a search box, filters and a newest-first order."""
    model_admin = admin.site._registry[model]
    if model._meta.app_label not in API_APPS:
        return
    assert 3 <= len(model_admin.list_display) <= 8, "list_display"
    assert model_admin.search_fields, "search_fields"
    assert model_admin.list_filter or issubclass(model, CatalogueItem), "list_filter"
    assert model_admin.ordering, "ordering"
    dated = [
        f.name
        for f in model._meta.fields
        if f.get_internal_type() in ("DateTimeField", "DateField")
    ]
    if dated:
        assert model_admin.date_hierarchy in dated, "date_hierarchy"


# --- every page opens -------------------------------------------------------


@pytest.mark.parametrize("model", REGISTERED, ids=label)
def test_superadmin_can_open_every_page(panel, model):
    client = panel("superadmin")
    model_admin = admin.site._registry[model]
    assert client.get(url(model, "changelist")).status_code == 200
    assert client.get(url(model, "changelist") + "?q=994").status_code == 200

    add = client.get(url(model, "add"))
    assert add.status_code == (403 if isinstance(model_admin, ReadOnlyMixin) else 200)

    row = model._default_manager.first()
    if row is not None:
        assert client.get(url(model, "change", row.pk)).status_code == 200
        assert client.get(url(model, "history", row.pk)).status_code == 200


@pytest.mark.parametrize("model", REGISTERED, ids=label)
def test_filters_and_sorting_do_not_break_the_list(panel, model):
    client = panel("superadmin")
    model_admin = admin.site._registry[model]
    page = client.get(url(model, "changelist"))
    # follow every filter and sort link the page itself offers
    links = set(re.findall(r'href="(\?[^"#]+)"', page.content.decode()))
    for link in sorted(links)[:40]:
        response = client.get(url(model, "changelist") + link.replace("&amp;", "&"))
        assert response.status_code in (200, 302), f"{label(model)} {link}"
    for index in range(1, len(model_admin.list_display) + 1):
        response = client.get(url(model, "changelist") + f"?o={index}")
        assert response.status_code in (200, 302), f"{label(model)} ?o={index}"


# --- roles ------------------------------------------------------------------


def expected_view(login):
    if login == "superadmin":
        return {label(model) for model in REGISTERED}
    return set(
        {
            "content": catalogue_models(),
            "support": SUPPORT_MODELS,
            "finance": FINANCE_MODELS,
        }[login]
    )


@pytest.mark.parametrize("login", ROLES)
def test_each_role_opens_only_its_own_lists(panel, login):
    client = panel(login)
    allowed = expected_view(login)
    for model in REGISTERED:
        status = client.get(url(model, "changelist")).status_code
        assert status == (200 if label(model) in allowed else 403), f"{login}: {label(model)}"


@pytest.mark.parametrize("login", ROLES)
def test_a_page_without_permission_is_403_never_500(panel, login):
    client = panel(login)
    allowed = expected_view(login)
    for model in REGISTERED:
        if label(model) in allowed:
            continue
        row = model._default_manager.first()
        pages = [url(model, "changelist"), url(model, "add")]
        if row is not None:
            pages += [url(model, "change", row.pk), url(model, "delete", row.pk)]
        for page in pages:
            assert client.get(page).status_code == 403, f"{login}: {page}"
        assert client.post(url(model, "add"), {}).status_code == 403


@pytest.mark.parametrize("login", ROLES)
def test_the_menu_lists_only_what_the_role_may_see(panel, login):
    html = panel(login).get(reverse("admin:index")).content.decode()
    allowed = expected_view(login)
    for model in REGISTERED:
        linked = f'href="{url(model, "changelist")}"' in html
        assert linked == (label(model) in allowed), f"{login}: {label(model)} in menu"


@pytest.mark.parametrize(
    "login,groups",
    [
        ("content", ["Tariff catalogue", "Packs and services", "Content"]),
        ("support", ["Subscribers", "Billing", "Content", "Activity"]),
        ("finance", ["Billing"]),
    ],
)
def test_the_menu_has_no_empty_groups(panel, login, groups):
    request = panel(login).get(reverse("admin:index")).wsgi_request
    from config.unfold import navigation

    shown = [group["title"] for group in navigation(request) if "title" in group]
    assert shown == groups


def test_content_managers_edit_the_catalogue_and_nothing_else(panel):
    client = panel("content")
    plan = TariffPlan.objects.get(slug="digimax-5")
    assert client.get(url(TariffPlan, "add")).status_code == 200
    assert client.get(url(TariffPlan, "change", plan.pk)).status_code == 200
    assert client.get(url(TariffPlan, "delete", plan.pk)).status_code == 200
    assert client.get(url(Subscriber, "changelist")).status_code == 403
    assert client.get(url(Transaction, "changelist")).status_code == 403


def test_support_and_finance_only_look(panel, subscriber):
    card = SavedCard.objects.filter(subscriber=subscriber).first()
    for login, model, row in [
        ("support", Subscriber, subscriber),
        ("support", SavedCard, card),
        ("finance", SavedCard, card),
    ]:
        client = panel(login)
        assert client.get(url(model, "change", row.pk)).status_code == 200  # opens read-only
        assert client.get(url(model, "add")).status_code == 403
        assert client.get(url(model, "delete", row.pk)).status_code == 403
        assert client.post(url(model, "change", row.pk), {"last4": "0000"}).status_code == 403
    card.refresh_from_db()
    assert card.last4 == "4471"
    # finance has no access to subscribers at all
    assert panel("finance").get(url(Subscriber, "changelist")).status_code == 403


@pytest.mark.parametrize("name", MONEY_RECORDS)
def test_money_records_are_read_only_even_for_the_superadmin(panel, client, name):
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "5.00"})
    model = apps.get_model(name)
    row = model.objects.first()
    admin_client = panel("superadmin")
    before = model.objects.count()

    assert admin_client.get(url(model, "change", row.pk)).status_code == 200
    assert admin_client.get(url(model, "add")).status_code == 403
    assert admin_client.post(url(model, "add"), {"amount": "1000"}).status_code == 403
    assert admin_client.post(url(model, "change", row.pk), {"amount": "1000"}).status_code == 403
    assert admin_client.post(url(model, "delete", row.pk), {"post": "yes"}).status_code == 403
    # the bulk "delete selected" action is not offered either
    bulk = {"action": "delete_selected", "_selected_action": [row.pk], "post": "yes"}
    admin_client.post(url(model, "changelist"), bulk)
    assert model.objects.count() == before


def test_subscribers_cannot_enter_the_admin(subscriber):
    client = Client()
    client.force_login(subscriber)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 302 and "/admin/login/" in response["Location"]
    assert Client().get(reverse("admin:index")).status_code == 302


def test_seeded_accounts_can_sign_in_with_the_seed_password(staff, settings):
    for login in ROLES:
        client = Client()
        assert client.login(username=login, password=settings.SEED_STAFF_PASSWORD), login
        assert client.get(reverse("admin:index")).status_code == 200


def test_seeding_staff_twice_keeps_one_account_per_role(staff):
    seed_staff()
    assert Subscriber.objects.filter(is_staff=True).count() == 4
    assert Subscriber.objects.get(msisdn="superadmin").is_superuser
    assert not Subscriber.objects.get(msisdn="finance").is_superuser


# --- dashboard --------------------------------------------------------------


@pytest.mark.parametrize(
    "login,titles",
    [
        (
            "superadmin",
            ["Subscribers", "Transactions today", "Active packs", "Catalogue items live"],
        ),
        ("support", ["Subscribers", "Transactions today", "Active packs"]),
        ("finance", ["Transactions today"]),
        ("content", ["Catalogue items live"]),
    ],
)
def test_dashboard_shows_each_role_its_own_figures(panel, login, titles):
    response = panel(login).get(reverse("admin:index"))
    assert response.status_code == 200
    assert [card["title"] for card in response.context["cards"]] == titles
    assert ("recent_transactions" in response.context) == (login != "content")


def test_dashboard_figures_are_right(panel, client):
    client.pay("/api/billing/top-up/card/", {"card_bin": "416300", "amount": "5.00"})
    client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    client.pay("/api/packs/social/tehsil/activate/", {"plan_id": "10gb"})

    cards = {card["title"]: card for card in panel("superadmin").get("/admin/").context["cards"]}
    assert cards["Subscribers"]["value"] == 2  # the staff accounts are not counted
    assert cards["Transactions today"]["value"] == 3
    assert cards["Transactions today"]["note"] == "5.00 ₼ topped up"
    assert cards["Active packs"]["value"] == 2
    assert cards["Active packs"]["note"] == "1 renew automatically"


# --- forms ------------------------------------------------------------------


def test_translated_fields_sit_in_one_tab_per_language(panel):
    plan = TariffPlan.objects.get(slug="digimax-5")
    response = panel("superadmin").get(url(TariffPlan, "change", plan.pk))
    html = response.content.decode()
    for tab in ("Azərbaycan", "Русский", "English"):
        assert tab in html
    for field in ("title_az", "title_ru", "title_en", "features_az", "features_ru", "features_en"):
        assert f'name="{field}"' in html
    assert 'name="title"' not in html  # only the per-language fields are edited
    fieldsets = response.context["adminform"].fieldsets
    assert [name for name, _ in fieldsets] == [
        None, "Azərbaycan", "Русский", "English", "Hot offers shelf", "Placement",
    ]  # fmt: skip


def test_an_edit_in_the_admin_reaches_the_api(panel, client):
    """Saving a translation in the form changes what the app gets, cache included."""
    path = "/api/tariffs/premium/"
    assert (
        client.get(path, HTTP_ACCEPT_LANGUAGE="az")
        .json()["benefits"][0]["text"]
        .startswith("Bütün")
    )

    from api.tariffs.models import PremiumBenefit

    benefit = PremiumBenefit.objects.get(key="curator")
    response = panel("content").post(
        url(PremiumBenefit, "change", benefit.pk),
        {
            "key": "curator",
            "text_az": "Yeni mətn",
            "text_ru": benefit.text_ru,
            "text_en": benefit.text_en,
            "order": 0,
            "is_active": "on",
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert client.get(path, HTTP_ACCEPT_LANGUAGE="az").json()["benefits"][0]["text"] == "Yeni mətn"
    assert client.get(path).json()["benefits"][0]["text"] == benefit.text_en


def test_a_subscribers_page_lists_only_their_own_records(
    panel, subscriber, other, client, other_client
):
    client.pay("/api/packs/internet/purchase/", {"pack_id": "unlimited-1h"})
    other_client.pay("/api/packs/roaming/purchase/", {"pack_id": "r-500mb"})

    html = panel("superadmin").get(url(Subscriber, "change", subscriber.pk)).content.decode()
    assert "4471" in html and "9999" not in html  # cards
    assert "Unlimited 1 hour" in html and "Roaming 500 MB" not in html  # packs and transactions

    theirs = panel("superadmin").get(url(Subscriber, "change", other.pk)).content.decode()
    assert "9999" in theirs and "4471" not in theirs
    assert "Roaming 500 MB" in theirs and "Unlimited 1 hour" not in theirs


def test_system_fields_are_read_only(panel, subscriber):
    form = panel("superadmin").get(url(Subscriber, "change", subscriber.pk)).context["adminform"]
    assert {"id", "balance", "created_at", "last_login"} <= set(form.readonly_fields)
    assert "balance" not in form.form.fields


def test_related_rows_are_picked_with_autocomplete(panel):
    client = panel("superadmin")
    found = client.get(
        "/admin/autocomplete/",
        {
            "app_label": "billing",
            "model_name": "savedcard",
            "field_name": "subscriber",
            "term": "99450",
        },
    )
    assert found.status_code == 200
    assert [row["text"] for row in found.json()["results"]] == ["994500000002"]


# --- performance ------------------------------------------------------------


@pytest.mark.parametrize("model", [Transaction, PackActivation, Subscriber], ids=label)
def test_lists_do_not_run_a_query_per_row(panel, client, other_client, model):
    """The query count of a list page is the same for few rows and for many."""
    admin_client = panel("superadmin")

    def queries():
        with CaptureQueriesContext(connection) as captured:
            assert admin_client.get(url(model, "changelist")).status_code == 200
        return len(captured)

    for buyer in (client, other_client):
        buyer.pay("/api/packs/internet/purchase/", {"pack_id": "daily-500mb"})
    few = queries()

    for index in range(15):
        buyer = client if index % 2 else other_client
        buyer.pay("/api/packs/internet/purchase/", {"pack_id": "daily-500mb"})
        Subscriber.objects.create_user(f"9947000000{index:02d}")
    assert queries() == few
