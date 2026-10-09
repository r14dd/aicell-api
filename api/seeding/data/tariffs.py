"""Tariff catalogue content.

Mirrors `src/data/tariffs.ts`, `src/data/myTariff.ts` and `hotTariffs` in
`src/data/mock.ts` of the mobile app. Entries the API docs abbreviate are
placeholders in the documented shape — replace them with the app's data.
"""

TOTAL_PRICE = [
    {
        "heading": "When you use all package, prices will be next:",
        "tone": "secondary",
        "rows": [
            {"key": "data_mb", "label": "Internet - 1MB", "price": "0.05"},
            {"key": "minute", "label": "Local calls - 1 min.", "price": "0.06"},
            {"key": "sms", "label": "SMS - 1 pcs.", "price": "0.05"},
            {"key": "intl_sms", "label": "International SMS - 1 pcs.", "price": "0.20"},
        ],
    },
    {
        "heading": "If monthly fee is not paid:",
        "tone": "red",
        "rows": [
            {"key": "data_mb", "label": "Internet - 1MB", "price": "0.10"},
            {"key": "minute", "label": "Local calls - 1 min.", "price": "0.10"},
            {"key": "sms", "label": "SMS - 1 pcs.", "price": "0.06"},
            {"key": "intl_sms", "label": "International SMS - 1 pcs.", "price": "0.25"},
        ],
    },
]

# What each plan includes, as numbers. None means unlimited.
INCLUDED = {
    "digimax-5": {"data_mb": 5 * 1024, "minutes": 100, "sms": 50, "roaming_mb": 0},
    "digimax-10": {"data_mb": 10 * 1024, "minutes": 200, "sms": 100, "roaming_mb": 0},
    "digimax-25": {"data_mb": 25 * 1024, "minutes": 500, "sms": 200, "roaming_mb": 0},
    "premium-60": {"data_mb": 60 * 1024, "minutes": None, "sms": 500, "roaming_mb": 1024},
    "premium-100": {"data_mb": 100 * 1024, "minutes": None, "sms": None, "roaming_mb": 3 * 1024},
}


def _features(internet, minutes, sms, socials=None, roaming=None):
    features = [
        {"kind": "internet", "label": "Internet", "value": internet},
        {"kind": "calls", "label": "Local calls", "value": minutes},
        {"kind": "sms", "label": "SMS", "value": sms},
    ]
    if socials:
        features.append(
            {"kind": "social", "label": "Social networks", "value": "Unlimited", "socials": socials}
        )
    if roaming:
        features.append({"kind": "roaming", "label": "Roaming internet", "value": roaming})
    features.append({"kind": "validity", "label": "Validity period", "value": "28 d."})
    return features


FAMILIES = {
    "digimax": {
        "id": "digimax",
        "name": "DigiMax",
        "subtitle": None,
        "badges": ["PREPAID"],
        "is_premium": False,
        "default_plan": "digimax-10",
        "plans": [
            {
                "id": "digimax-5",
                "title": "DigiMax 5GB",
                "price": "12.00",
                "hot": False,
                "features": _features("5 GB", "100 min.", "50 SMS"),
            },
            {
                "id": "digimax-10",
                "title": "DigiMax 10GB",
                "price": "18.00",
                "hot": True,
                "features": _features("10 GB", "200 min.", "100 SMS", ["whatsapp", "telegram"]),
            },
            {
                "id": "digimax-25",
                "title": "DigiMax 25GB",
                "price": "30.00",
                "hot": True,
                "features": _features(
                    "25 GB", "500 min.", "200 SMS", ["whatsapp", "telegram", "instagram"]
                ),
            },
        ],
    },
    "premium-plus": {
        "id": "premium-plus",
        "name": "Premium+",
        "subtitle": "For those who expect more",
        "badges": ["POSTPAID"],
        "is_premium": True,
        "default_plan": "premium-60",
        "plans": [
            {
                "id": "premium-60",
                "title": "Premium+ 60GB",
                "price": "60.00",
                "hot": True,
                "features": _features(
                    "60 GB",
                    "Unlimited",
                    "500 SMS",
                    ["whatsapp", "telegram", "instagram", "youtube"],
                    "1 GB",
                ),
            },
            {
                "id": "premium-100",
                "title": "Premium+ 100GB",
                "price": "90.00",
                "hot": False,
                "features": _features(
                    "100 GB",
                    "Unlimited",
                    "Unlimited",
                    ["whatsapp", "telegram", "instagram", "youtube"],
                    "3 GB",
                ),
            },
        ],
    },
}

HOT = [
    {
        "id": "digimax-10",
        "family_id": "digimax",
        "title": "DigiMax 10GB",
        "price": "18.00",
        "socials": ["whatsapp", "telegram"],
        "features": [
            {"kind": "data", "value": "10 GB"},
            {"kind": "minutes", "value": "200 min."},
            {"kind": "sms", "value": "100 SMS"},
        ],
    },
    {
        "id": "premium-60",
        "family_id": "premium-plus",
        "title": "Premium+ 60GB",
        "price": "60.00",
        "socials": ["whatsapp", "telegram", "instagram", "youtube"],
        "features": [
            {"kind": "data", "value": "60 GB"},
            {"kind": "minutes", "value": "Unlimited"},
            {"kind": "sms", "value": "500 SMS"},
            {"kind": "roaming", "value": "1 GB"},
        ],
    },
    {
        "id": "digimax-25",
        "family_id": "digimax",
        "title": "DigiMax 25GB",
        "price": "30.00",
        "socials": ["whatsapp", "telegram", "instagram"],
        "features": [
            {"kind": "data", "value": "25 GB"},
            {"kind": "minutes", "value": "500 min."},
            {"kind": "sms", "value": "200 SMS"},
        ],
    },
]

CHANGE_GROUPS = [
    {
        "id": "digimax",
        "title": "DigiMax",
        "cards": [
            {
                "id": "digimax",
                "title": "DigiMax",
                "price": "12-30",
                "period": "28 days",
                "tagline": "Internet, calls and social networks in one tariff",
                "is_new": False,
                "socials": ["whatsapp", "telegram", "instagram"],
                "features": [
                    {"kind": "data", "value": "5-25 GB"},
                    {"kind": "minutes", "value": "100-500 min."},
                ],
                "family_id": "digimax",
            },
            {
                "id": "digimax-3gb",
                "title": "DigiMax 3GB",
                "price": "9",
                "period": "28 days",
                "tagline": "The essentials at the lowest price",
                "is_new": True,
                "socials": ["whatsapp"],
                "features": [
                    {"kind": "data", "value": "3 GB"},
                    {"kind": "minutes", "value": "50 min."},
                ],
                "family_id": None,
                "included": {"data_mb": 3 * 1024, "minutes": 50, "validity_days": 28},
            },
        ],
    },
    {
        "id": "premium",
        "title": "Premium",
        "cards": [
            {
                "id": "premium-plus",
                "title": "Premium+",
                "price": "60-90",
                "period": "30 days",
                "tagline": "Unlimited calls and a personal curator",
                "is_new": False,
                "socials": ["whatsapp", "telegram", "instagram", "youtube"],
                "features": [
                    {"kind": "data", "value": "60-100 GB"},
                    {"kind": "minutes", "value": "Unlimited"},
                ],
                "family_id": "premium-plus",
            },
            {
                "id": "premium",
                "title": "Premium",
                "price": "45",
                "period": "30 days",
                "tagline": "Premium service for everyday use",
                "is_new": False,
                "socials": ["whatsapp", "telegram"],
                "features": [
                    {"kind": "data", "value": "40 GB"},
                    {"kind": "minutes", "value": "1000 min."},
                ],
                "family_id": None,
                "included": {"data_mb": 40 * 1024, "minutes": 1000, "validity_days": 30},
            },
        ],
    },
]

PREMIUM = {
    "logo": "premium-logo.png",
    "benefits": [
        {"key": "curator", "text": "Personal curator for all your needs"},
        {"key": "priority", "text": "Priority service in customer care and stores"},
        {"key": "theme", "text": "Exclusive Premium theme in the app"},
        {"key": "roaming", "text": "Special roaming offers"},
        {"key": "lounge", "text": "Access to airport lounges"},
        {"key": "partners", "text": "Discounts from Premium partners"},
        {"key": "number", "text": "Gold number selection"},
        {"key": "events", "text": "Invitations to private events"},
    ],
    "note": "To access the Premium theme you must log in with Premium number as main account",
}

REDESIGN_SLIDERS = [
    {"key": "internet", "label": "Internet GB", "min": 0, "max": 16, "step": 1},
    {"key": "calls", "label": "Local calls min.", "min": 30, "max": 350, "step": 10},
    {"key": "instagramFb", "label": "Instagram & FB GB", "min": 0, "max": 5, "step": 1},
    {"key": "youtube", "label": "YouTube GB", "min": 0, "max": 10, "step": 1},
    {"key": "tiktok", "label": "TikTok GB", "min": 0, "max": 10, "step": 1},
]
