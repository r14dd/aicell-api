"""Fixed copy of the usage screens."""

from django.utils.translation import gettext_lazy as _

SEGMENT_LABELS = {
    "heavy_data": _("Heavy internet user"),
    "voice_only": _("Calls only"),
    "roamer": _("Frequent traveller"),
    "balanced": _("Balanced use"),
    "low_usage": _("Light use"),
}

FITS = _("Your current plan fits how you use your number")
