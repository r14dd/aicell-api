"""What the live catalogue can answer an insight with, ranked by price per gigabyte.

Nothing here is a fixed list: packs and plans are read from their tables, so a
pack added or repriced in the admin is chosen (or not) by the same rules.
"""

from dataclasses import dataclass
from decimal import Decimal

from api.packs.models import InternetPack, RoamingPack, SocialPlan
from api.tariffs import catalogue as tariffs_catalogue
from api.tariffs.models import TariffPlan
from api.usage import taxonomy

MB_PER_GB = 1024
CENT = Decimal("0.01")
HOURS_PER_DAY = 24
WEEK_HOURS = 7 * HOURS_PER_DAY


@dataclass(frozen=True)
class Option:
    """One thing that can be bought, with what it holds."""

    kind: str  # internet_pack | social_pack | roaming_pack | tariff_plan
    target_id: str  # the slug the purchase endpoints take; "<pack>:<plan>" for a social pack
    price: Decimal
    data_mb: int | None  # None = unlimited
    hours: int  # how long it lasts
    app: str | None = None  # the only app a social pack's traffic is for
    minutes: int | None = None  # tariff plans only; None = unlimited

    @property
    def ref(self) -> str:
        prefix = {
            "internet_pack": "internet",
            "social_pack": "social",
            "roaming_pack": "roaming",
            "tariff_plan": "tariff",
        }[self.kind]
        return f"{prefix}:{self.target_id}"

    @property
    def per_gb(self) -> Decimal | None:
        """Price of one gigabyte; None for an unlimited option."""
        if not self.data_mb:
            return None
        return (self.price * MB_PER_GB / self.data_mb).quantize(CENT)

    def covers(self, need_mb: float) -> bool:
        return self.data_mb is None or self.data_mb >= need_mb


def per_gb_order(option: Option):
    """Cheapest gigabyte first; unlimited options last, then the cheaper one."""
    return (option.per_gb is None, option.per_gb or 0, option.price)


@dataclass(frozen=True)
class Catalogue:
    """A snapshot of the catalogue, read once for a run of the detectors."""

    internet: tuple[Option, ...]  # every internet pack, also switched-off ones (for history)
    social: tuple[Option, ...]
    roaming: tuple[Option, ...]
    plans: tuple[Option, ...]
    on_sale: frozenset[str]  # refs that can be bought now
    overage_per_mb: Decimal

    def sold(self, options) -> list[Option]:
        return [option for option in options if option.ref in self.on_sale]

    def sized_internet(self) -> list[Option]:
        """Internet packs on sale that hold a fixed amount, cheapest first."""
        return sorted(
            (option for option in self.sold(self.internet) if option.data_mb),
            key=lambda option: (option.price, -option.data_mb),
        )

    def pack(self, slug: str) -> Option | None:
        return next((option for option in self.internet if option.target_id == slug), None)

    def for_app(self, app: str) -> list[Option]:
        """Social plans whose traffic is for this app, cheapest gigabyte first."""
        return sorted(
            (option for option in self.sold(self.social) if option.app == app), key=per_gb_order
        )

    def plan_for(self, app: str, need_mb: float) -> Option | None:
        """The cheapest plan of the app that holds `need_mb`; the biggest one if none does.

        Plans that last less than a week are left out when longer ones exist:
        the need is a month's habit, not one evening.
        """
        plans = self.for_app(app)
        plans = [plan for plan in plans if plan.hours >= WEEK_HOURS] or plans
        enough = [plan for plan in plans if plan.covers(need_mb)]
        if enough:
            return min(enough, key=lambda plan: plan.price)
        return max(plans, key=lambda plan: plan.data_mb, default=None)

    @classmethod
    def load(cls) -> "Catalogue":
        internet = tuple(
            Option("internet_pack", pack.slug, pack.price, pack.data_mb, pack.hours)
            for pack in InternetPack.objects.all()
        )
        social = tuple(
            Option(
                "social_pack",
                f"{plan.pack.slug}:{plan.slug}",
                plan.price,
                plan.data_mb,
                plan.days * HOURS_PER_DAY,
                app=taxonomy.SOCIAL_PACK_APP.get(plan.pack.slug),
            )
            for plan in SocialPlan.objects.select_related("pack")
            if plan.data_mb
        )
        roaming = tuple(
            Option("roaming_pack", pack.slug, pack.price, pack.data_mb, pack.days * HOURS_PER_DAY)
            for pack in RoamingPack.objects.all()
            if pack.data_mb
        )
        plans = tuple(
            Option(
                "tariff_plan",
                plan["id"],
                Decimal(plan["price"]),
                plan["data_mb"],
                0,
                minutes=plan["minutes"],
            )
            for plan in tariffs_catalogue.plans()
        )
        on_sale = (
            {f"internet:{slug}" for slug in _active(InternetPack)}
            | {
                f"social:{plan.pack.slug}:{plan.slug}"
                for plan in SocialPlan.objects.active()
                .filter(pack__is_active=True)
                .select_related("pack")
            }
            | {f"roaming:{slug}" for slug in _active(RoamingPack)}
            | {f"tariff:{slug}" for slug in _active(TariffPlan)}
        )
        rate = Decimal(tariffs_catalogue.overage_rates().get("data_mb", "0"))
        return cls(internet, social, roaming, plans, frozenset(on_sale), rate)


def _active(model) -> list[str]:
    return list(model.objects.active().values_list("slug", flat=True))
