"""Pack catalogue content.

Mirrors the internet / social / roaming pack data of the mobile app. Entries
the API docs abbreviate are placeholders in the documented shape. `hours` and
`days` are server-side only (they set `expires_at`) and are not returned.
"""

CATEGORIES = [
    {"id": "unlimited", "label": "Unlimited"},
    {"id": "high-volume", "label": "High-volume"},
    {"id": "weekly", "label": "Weekly"},
    {"id": "daily", "label": "Daily"},
    {"id": "social", "label": "Social"},
]


def _pack(id, name, sub, price, label, hours, renews=False):
    return {
        "id": id,
        "name": name,
        "sub": sub,
        "price": price,
        "renews": renews,
        "label": label,
        "hours": hours,
    }


PACKS = {
    "unlimited": [
        _pack("unlimited-1h", "1 hour", "Unlimited speed", "0.99", "Unlimited 1 hour", 1),
        _pack("unlimited-3h", "3 hours", "Unlimited speed", "1.99", "Unlimited 3 hours", 3),
        _pack("unlimited-1d", "1 day", "Unlimited speed", "2.99", "Unlimited 1 day", 24),
    ],
    "high-volume": [
        _pack("hv-20gb", "20 GB", "30 days", "15.00", "High-volume 20 GB", 30 * 24, renews=True),
        _pack("hv-50gb", "50 GB", "30 days", "25.00", "High-volume 50 GB", 30 * 24, renews=True),
        _pack("hv-100gb", "100 GB", "30 days", "35.00", "High-volume 100 GB", 30 * 24, renews=True),
    ],
    "weekly": [
        _pack("weekly-2gb", "2 GB", "7 days", "3.00", "Weekly 2 GB", 7 * 24),
        _pack("weekly-5gb", "5 GB", "7 days", "5.00", "Weekly 5 GB", 7 * 24),
    ],
    "daily": [
        _pack("daily-500mb", "500 MB", "1 day", "0.50", "Daily 500 MB", 24),
        _pack("daily-1gb", "1 GB", "1 day", "1.00", "Daily 1 GB", 24),
    ],
}

TOP = ["unlimited-1h", "hv-20gb", "weekly-5gb"]


SOCIAL = {
    "tehsil": {
        "id": "tehsil",
        "title": "Tehsil",
        "subtitle": "Join online classes with ease via Microsoft Teams.",
        "app": "teams",
        "range": "0.7-9.9",
        "special": False,
        "volume": "10-100 GB",
        "periods": ["Daily", "Monthly"],
        "cta": "Subscribe",
        "auto_renew": True,
        "plans": [
            {"id": "10gb", "title": "10 GB", "price": "0.70", "validity": "1 d.", "days": 1},
            {"id": "100gb", "title": "100 GB", "price": "9.90", "validity": "30 d.", "days": 30},
        ],
    },
    "instagram-facebook": {
        "id": "instagram-facebook",
        "title": "Instagram & Facebook",
        "subtitle": "Scroll, post and watch stories without counting megabytes.",
        "app": "instagram",
        "range": "1-3",
        "special": True,
        "volume": "1-5 GB",
        "periods": ["Daily", "Monthly"],
        "cta": "Activate",
        "auto_renew": False,
        "plans": [
            {"id": "1gb", "title": "1 GB", "price": "1.00", "validity": "1 d.", "days": 1},
            {"id": "5gb", "title": "5 GB", "price": "3.00", "validity": "30 d.", "days": 30},
        ],
    },
    "tiktok": {
        "id": "tiktok",
        "title": "TikTok",
        "subtitle": "Watch and share videos on TikTok all day long.",
        "app": "tiktok",
        "range": "1-4",
        "special": False,
        "volume": "2-10 GB",
        "periods": ["Daily", "Monthly"],
        "cta": "Activate",
        "auto_renew": False,
        "plans": [
            {"id": "2gb", "title": "2 GB", "price": "1.00", "validity": "1 d.", "days": 1},
            {"id": "10gb", "title": "10 GB", "price": "4.00", "validity": "30 d.", "days": 30},
        ],
    },
    "youtube": {
        "id": "youtube",
        "title": "YouTube",
        "subtitle": "Stream your favourite channels in high quality.",
        "app": "youtube",
        "range": "1-4",
        "special": False,
        "volume": "2-10 GB",
        "periods": ["Daily", "Monthly"],
        "cta": "Activate",
        "auto_renew": False,
        "plans": [
            {"id": "2gb", "title": "2 GB", "price": "1.00", "validity": "1 d.", "days": 1},
            {"id": "10gb", "title": "10 GB", "price": "4.00", "validity": "30 d.", "days": 30},
        ],
    },
}

ROAMING = [
    {"id": "r-500mb", "name": "500 MB", "sub": "3 days", "price": "10.00", "days": 3},
    {"id": "r-2gb", "name": "2 GB", "sub": "10 days", "price": "25.00", "days": 10},
    {"id": "r-5gb", "name": "5 GB", "sub": "30 days", "price": "45.00", "days": 30},
]

# Traffic of each pack in MB, for cost projection. Packs left out are unlimited.
INTERNET_MB = {
    "hv-20gb": 20 * 1024,
    "hv-50gb": 50 * 1024,
    "hv-100gb": 100 * 1024,
    "weekly-2gb": 2 * 1024,
    "weekly-5gb": 5 * 1024,
    "daily-500mb": 500,
    "daily-1gb": 1024,
}
SOCIAL_MB = {"1gb": 1024, "2gb": 2 * 1024, "5gb": 5 * 1024, "10gb": 10 * 1024, "100gb": 100 * 1024}
ROAMING_MB = {"r-500mb": 500, "r-2gb": 2 * 1024, "r-5gb": 5 * 1024}
