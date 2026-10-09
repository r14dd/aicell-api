"""Fixed copy of the SIM screens. The service catalogue lives in the models."""

from django.utils.translation import gettext_lazy as _

ROWS = [
    {"key": "line", "label": _("Line settings"), "deep_link": "/sim/line"},
    {"key": "roaming", "label": _("Roaming settings"), "deep_link": "/sim/roaming"},
    {"key": "esim", "label": _("eSIM"), "deep_link": "/esim"},
    {"key": "sms", "label": _("SMS settings"), "deep_link": "/sim/sms"},
    {"key": "puk", "label": _("PUK codes"), "deep_link": "/sim/puk"},
    {"key": "services", "label": _("Services"), "deep_link": "/sim/services"},
]

LINE_STATUS_SUB = _("Line activation/suspension at subscriber’s request")
LINE_TEXTS = {
    "second_line_sub": _(
        "With call holding you can hold the first caller on the line and answer the second call"
    ),
    "internet_settings_link": _("Request automatic internet settings"),
}

LINE_STATUS_NAMES = {"open": _("Open"), "closed": _("Closed"), "suspended": _("Suspended")}
LINE_STATUS_FEE = "20.00"
LINE_STATUS_GENERAL = _(
    "You can activate or suspend your line upon request. "
    "The line can be closed for a maximum of 90 days"
)
LINE_STATUS_CONSEQUENCES = [
    _("Your agreement will be automatically terminated"),
    _("Your line will be completely deactivated"),
    _("Remaining balance will be lost"),
    _("The number may be reassigned to another person"),
]

ROAMING_TEXTS = {
    "search_title": _("Search for country pricing"),
    "search_placeholder": _("Explore countries and tariffs"),
    "packs_title": _("Roaming packs"),
}

SMS_LANGUAGES = [
    {"id": "az", "name": _("Azerbaijani")},
    {"id": "en", "name": _("English")},
    {"id": "ru", "name": _("Russian")},
]

# Rich text: a paragraph is a list of segments, some of them bold.
PUK_PARAGRAPHS = [
    [
        {"text": _("After 3 incorrect entries of PIN 1 and PIN 2, the codes ")},
        {"text": _("will be blocked"), "bold": True},
        {"text": _(". Use the matching PUK code to unblock them.")},
    ],
    [
        {"text": _("After 10 incorrect entries of a PUK code, the SIM card ")},
        {"text": _("is blocked permanently"), "bold": True},
        {"text": _(" and has to be replaced.")},
    ],
]

ESIM = {
    "benefits": [
        {
            "key": "safe",
            "title": _("Safe & Reliable"),
            "body": _("Your eSIM stays secure, no physical card to lose or damage"),
        },
        {
            "key": "flexible",
            "title": _("Flexible"),
            "body": _("Keep several numbers on one device and switch between them"),
        },
        {
            "key": "eco",
            "title": _("Eco-friendly"),
            "body": _("No plastic card and no packaging"),
        },
    ],
    "asan_note": _(
        "The use of the obtained eSIM “Asan İmza” service is possible only "
        "after the “Asan İmza” certificates are renewed."
    ),
    "actions": [
        {"key": "transfer", "label": _("Transfer to eSIM")},
        {"key": "recover", "label": _("Recover eSIM"), "deep_link": "/esim/recover"},
    ],
}
