"""Read side of the SIM services: models to the documented JSON shapes."""

from api.common.cache import cached
from api.common.formatting import money

from .models import SimService


@cached("sim.services")
def services() -> list[dict]:
    return [
        {
            "id": service.slug,
            "name": service.name,
            "sub": service.sub,
            "period": service.period,
            "price": money(service.price),
            "auto_renew": service.auto_renew,
            "sections": service.sections,
        }
        for service in SimService.objects.active()
    ]
