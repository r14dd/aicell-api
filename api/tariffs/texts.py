"""Fixed copy of the tariff screens. Catalogue content lives in the models."""

from django.utils.translation import gettext_lazy as _

NOTE = _(
    "When the subscription fee of the tariff is paid, the line of the number "
    "will remain bilaterally active for 28 days."
)
CHARGING_NOTE = _("Charging interval: 1 minute for calls")
BANNER_ALT = _("All you need and more!")
PREMIUM_NOTE = _("To access the Premium theme you must log in with Premium number as main account")

AGGREGATION = [
    {
        "title": _("For internet"),
        "body": _(
            "The total shows the sum of the internet in your tariff and in all "
            "of your active internet packs."
        ),
    },
    {
        "title": _("For calls"),
        "body": _(
            "The total shows the sum of the local minutes in your tariff and in "
            "all of your active packs."
        ),
    },
]

RENEW = {
    "title": _("Renew tariff"),
    "body": _(
        "By renewing tariff, the remaining balance will be annulled but the "
        "existing old internet packs will still stay active."
    ),
}
