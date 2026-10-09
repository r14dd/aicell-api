from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.exceptions import NotFound
from api.common.http import iso, media, money
from api.common.routing import Todo, route

from . import catalogue
from .models import CreditDebt

TAG = "kredit"
AKART_URL = "https://links.akart.az/app/"


def _product(slug) -> dict:
    found = next((product for product in catalogue.products() if product["id"] == slug), None)
    if found is None:
        raise NotFound()
    return found


@doc("Get Kredit page")
def overview(request):
    """The subscriber's open debt and the credit products."""
    debts = list(
        CreditDebt.objects.filter(subscriber=request.user, repaid_at__isnull=True).order_by("id")
    )
    total = sum((debt.amount + debt.fee for debt in debts), Decimal("0"))
    cards = []
    for product in catalogue.products():
        card = {key: product[key] for key in ("id", "name", "subtitle", "chip", "chip_icon")}
        if product["price"]:
            card["price"] = product["price"]
        card["deep_link"] = f"/kredit/{product['id']}"
        cards.append(card)
    return {
        "debt": {
            "amount": money(total),
            "note": _("%(count)s items") % {"count": len(debts)} if debts else _("no items"),
            "items": [
                {
                    "id": debt.id,
                    "product": debt.product,
                    "name": debt.name,
                    "amount": money(debt.amount + debt.fee),
                    "created_at": iso(debt.created_at),
                }
                for debt in debts
            ],
        },
        "products": cards,
    }


@doc("Credit product detail", path={"slug": "simtaksit"}, errors=(404,))
def product(request, slug):
    """`options`, `amount_mb` and `validity_days` appear only on products that have them."""
    item = _product(slug)
    body = {
        "id": item["id"],
        "name": item["name"],
        "amount": item["amount"],
        "fee": item["fee"],
        "unit": "₼",
    }
    if item["options"]:
        body["options"] = item["options"]
    if item["amount_mb"]:
        body["amount_mb"] = item["amount_mb"]
        body["validity_days"] = item["validity_days"]
    body["cta"] = _("Get %(name)s %(amount)s ₼") % {"name": item["name"], "amount": item["amount"]}
    return body


class TakeInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)


def take_notice(request, slug):
    """The app's toast for "Get <product> X ₼", echoing the requested amount.

    When built: create CreditDebt and credit the wallet (kind=credit, title
    "<name> credit") or, for a data product, a PackActivation.
    """
    item = _product(slug)
    if item["amount_mb"]:
        return _("%(name)s %(mb)s MB will be added to your number (prototype)") % {
            "name": item["name"],
            "mb": item["amount_mb"],
        }
    amount = item["amount"]
    # An unusable amount keeps the product's default in the notice.
    data = request.data if isinstance(request.data, dict) else {}
    form = TakeInput(data=data)
    if form.is_valid() and "amount" in form.validated_data:
        amount = money(form.validated_data["amount"])
    return _("%(name)s %(amount)s ₼ will be added to your balance (prototype)") % {
        "name": item["name"],
        "amount": amount,
    }


@doc("Tamamla page")
def tamamla(request):
    """Banner, the three steps and the akart link."""
    return {
        "banner": {
            "image": media(request, "tamamla-hero.png"),
            "alt": _("Instant loan with akart! Complete your payments up to 50 ₼ with akart loan"),
        },
        "steps": [
            _("Apply for akart with ease: download the akart app and register"),
            _("Give permission to borrow up to 50.00 ₼ when your balance is not enough"),
            _("Activate Tamamla & Cover unexpected expenses!"),
        ],
        "cta": {"label": _("Get now!"), "url": AKART_URL},
    }


overview_view = route(TAG, get=overview)
product_view = route(TAG, get=product)
take_view = route(TAG, post=Todo(take_notice, "Take a credit", body=TakeInput, errors=(404,)))
tamamla_view = route(TAG, get=tamamla)
