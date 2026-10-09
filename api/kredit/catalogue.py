"""Read side of the credit products: models to the documented JSON shapes."""

from api.common.cache import cached
from api.common.formatting import money

from .models import KreditProduct


@cached("kredit.products")
def products() -> list[dict]:
    """Products with every field the list and the detail page need."""
    return [
        {
            "id": product.slug,
            "name": product.name,
            "subtitle": product.subtitle,
            "chip": product.chip,
            "chip_icon": product.chip_icon,
            "price": product.price_label,
            "amount": money(product.amount),
            "fee": money(product.fee),
            "options": product.options,
            "amount_mb": product.amount_mb,
            "validity_days": product.validity_days,
        }
        for product in KreditProduct.objects.active()
    ]
