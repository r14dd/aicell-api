"""One-click admin sign-in for demos: on only when switched on, only for seeded staff."""

import pytest
from django.test import Client
from django.urls import reverse

from api.seeding import seed_staff

LOGIN = "/admin/login/"


@pytest.fixture
def staff(db):
    return seed_staff()


@pytest.fixture
def browser():
    return Client(enforce_csrf_checks=True)


def sign_in(browser, account, **data):
    browser.get(LOGIN)
    token = browser.cookies["csrftoken"].value  # kept from an earlier visit too
    return browser.post(
        reverse("admin-demo-login", args=[account]), {"csrfmiddlewaretoken": token, **data}
    )


def test_buttons_appear_only_when_switched_on(staff, browser, settings):
    assert 'data-test="demo-logins"' not in browser.get(LOGIN).content.decode()
    settings.DEMO_ADMIN_LOGIN = True
    html = browser.get(LOGIN).content.decode()
    assert 'data-test="demo-logins"' in html
    for account in ("superadmin", "content", "support", "finance"):
        assert reverse("admin-demo-login", args=[account]) in html


@pytest.mark.parametrize(
    "account,allowed,forbidden",
    [
        ("superadmin", "/admin/billing/transaction/", None),
        ("content", "/admin/tariffs/tariffplan/", "/admin/billing/transaction/"),
        ("support", "/admin/users/subscriber/", "/admin/tariffs/tariffplan/"),
        ("finance", "/admin/billing/transaction/", "/admin/users/subscriber/"),
    ],
)
def test_each_button_signs_in_with_that_role(staff, browser, settings, account, allowed, forbidden):
    settings.DEMO_ADMIN_LOGIN = True
    response = sign_in(browser, account)
    assert (response.status_code, response["Location"]) == (302, "/admin/")
    assert browser.get(allowed).status_code == 200
    if forbidden:
        assert browser.get(forbidden).status_code == 403


def test_switched_off_it_does_nothing(staff, browser):
    assert sign_in(browser, "superadmin").status_code == 404
    assert browser.get("/admin/").status_code == 302  # still signed out


def test_only_seeded_staff_and_only_by_post(staff, browser, settings):
    settings.DEMO_ADMIN_LOGIN = True
    assert sign_in(browser, "994516643342").status_code == 404  # a subscriber
    assert sign_in(browser, "nobody").status_code == 404
    assert browser.get(reverse("admin-demo-login", args=["superadmin"])).status_code == 405
    # without the CSRF token a third-party page cannot sign someone in
    assert browser.post(reverse("admin-demo-login", args=["superadmin"])).status_code == 403


def test_next_is_kept_but_only_on_this_site(staff, browser, settings):
    settings.DEMO_ADMIN_LOGIN = True
    assert sign_in(browser, "support", next="/admin/users/subscriber/")["Location"] == (
        "/admin/users/subscriber/"
    )
    assert sign_in(browser, "support", next="https://evil.example/")["Location"] == "/admin/"
