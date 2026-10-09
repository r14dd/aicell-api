"""Fixed copy of the pack screens. Catalogue content lives in the models."""

from django.utils.translation import gettext_lazy as _

PROMO = {
    "title": _("Unlimited entertainment is waiting for you!"),
    "sub": _("For only 0.99 ₼"),
    "gradient": ["#8C80FE", "#4670E2"],
}

NOTE = _(
    "The traffic of the pack is used only in the specified application. "
    "After the traffic ends, standard internet pricing of your tariff applies."
)

ROAMING_CONFIRM = {
    "title": _("You are not yet in the roaming area"),
    "body": _(
        "Roaming internet pack is activated immediately after purchasing. "
        "Are you sure you want to proceed?"
    ),
    "decline": _("No, thanks"),
    "confirm": _("Yes, activate the pack"),
}
