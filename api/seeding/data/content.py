"""Home, stories, lottery, games and offers content.

Mirrors `src/data/stories.ts` and `src/data/mock.ts` of the mobile app.
Entries the API docs abbreviate — three story chips, the story pages, eight
banners, most lottery sections, seven games and the offer lists — are
placeholders in the documented shape. Image values are file names under
`media/content/`; views turn them into absolute URLs.
"""


def _page(image, title, body, cta=None):
    return {"image": image, "title": title, "body": body, "cta": cta, "duration_ms": 5000}


# Shelf order. `pages` follows the app's `StoryPage` shape.
STORIES = [
    {
        "key": "gift-wheel",
        "label": "Gift Wheel",
        "image": "chip-gift-wheel.png",
        "pages": [
            _page(
                "story-gift-wheel-1.png",
                "Spin the Gift Wheel!",
                "A new gift is waiting for you every day.",
            ),
            _page(
                "story-gift-wheel-2.png",
                "Internet, minutes and more",
                "Spin once a day and collect your prize.",
            ),
        ],
    },
    {
        "key": "roaming",
        "label": "Roaming",
        "image": "chip-roaming.png",
        "pages": [
            _page(
                "story-roaming-1.png",
                "Stay online abroad",
                "Roaming internet packs from 10 ₼.",
                {"label": "Roaming packs", "deep_link": "/sim/roaming"},
            ),
        ],
    },
    {
        "key": "especially",
        "label": "Especially for you",
        "image": "chip-especially.png",
        "pages": [
            _page(
                "story-especially-1.png",
                "Especially for you",
                "Offers picked for the way you use your number.",
            ),
            _page(
                "story-especially-2.png",
                "Unlimited 1 hour",
                "Unlimited speed for only 0.99 ₼.",
                {"label": "Buy internet", "deep_link": "/internet-packs"},
            ),
        ],
    },
    {
        "key": "applications",
        "label": "Applications",
        "image": "chip-applications.png",
        "pages": [
            _page(
                "story-applications-1.png",
                "Apps you will love",
                "Kinon, Yandex Plus and Litres with your balance.",
            ),
        ],
    },
    {
        "key": "tariffs",
        "label": "Tariffs",
        "image": "chip-tariffs.png",
        "pages": [
            _page(
                "story-tariffs-1.png",
                "DigiMax",
                "Internet, calls and social networks in one tariff.",
                {"label": "See tariffs", "deep_link": "/tariffs/digimax"},
            ),
        ],
    },
    {
        "key": "kredit",
        "label": "Kredit",
        "image": "chip-kredit.png",
        "pages": [
            _page(
                "story-kredit-1.png",
                "Out of balance?",
                "Get now and pay back at the next top-up.",
                {"label": "Get Kredit", "deep_link": "/kredit"},
            ),
        ],
    },
    {
        "key": "lottery",
        "label": "30 il səninlə",
        "image": "chip-lottery.png",
        "pages": [
            _page(
                "story-lottery-1.png",
                "30 il səninlə",
                "Chance collection starts on 19 October 2026.",
                {"label": "Learn more", "deep_link": "/lottery-rules"},
            ),
        ],
    },
]

QUICK_ACTIONS = [
    {"key": "simkredit", "label": "SimKredit", "deep_link": "/kredit"},
    {"key": "buy-internet", "label": "Buy internet", "deep_link": "/internet-packs"},
    {"key": "sim-settings", "label": "SIM settings", "deep_link": "/sim-settings"},
]

AKART_ALT = "Instant loan with akart! Complete your payments up to 50 ₼ with akart loan"


def _banner(key, alt, deep_link=None):
    return {"key": key, "image": f"banner-{key}.png", "alt": alt, "deep_link": deep_link}


BANNERS = {
    "home": [
        _banner("akart", AKART_ALT, "/kredit/tamamla"),
        _banner("spin", "Spin the Gift Wheel! A new gift every day"),
        _banner("unlimited", "Unlimited entertainment is waiting for you!", "/internet-packs"),
        _banner("lottery", "30 il səninlə: collect chances and win", "/lottery-rules"),
        _banner("digimax", "DigiMax: everything in one tariff"),
        _banner("roaming", "Stay online abroad with roaming packs", "/sim/roaming"),
        _banner("esim", "Switch to eSIM in a few minutes", "/esim"),
        _banner("steam", "Top up Steam with your balance"),
        _banner("referral", "Share Azercell app and get 3.00 ₼ bonus!"),
        _banner("premium", "Premium: a personal curator for all your needs"),
    ],
    "products": [
        _banner("want-more", "All you need and more!", "/internet-packs"),
        _banner("digimax", "DigiMax: everything in one tariff"),
    ],
    "benefits": [
        _banner("spin", "Spin the Gift Wheel! A new gift every day"),
        _banner("referral", "Share Azercell app and get 3.00 ₼ bonus!"),
    ],
    "partners": [
        _banner("wingz", "Activate Wingz scooter with your Azercell balance!"),
        _banner("wolt", "Wolt+ with your Azercell number"),
    ],
}


def _p(text, num=None, bold=None):
    block = {"kind": "p", "text": text}
    if num:
        block["num"] = num
    if bold:
        block["bold"] = bold
    return block


LOTTERY_RULES = {
    "sections": [
        {
            "icon": None,
            "title": "About the lottery",
            "blocks": [
                _p(
                    "We are launching the “30 il səninlə” lottery to celebrate 30 years together "
                    "with our subscribers."
                ),
                _p("Collect chances from 19 October 2026 and take part in the draws."),
            ],
        },
        {
            "icon": "Diamond",
            "title": "How to earn chances?",
            "blocks": [
                _p(
                    "and get 1 chance for every 5 AZN.",
                    num="1.",
                    bold="Top up your balance with 5 AZN or more",
                ),
                {
                    "kind": "example",
                    "items": [
                        {"label": "Top-up of 5 AZN", "value": "1 chance"},
                        {"label": "Top-up of 12 AZN", "value": "2 chances"},
                    ],
                },
                _p(
                    "and get 2 chances for each purchase.",
                    num="2.",
                    bold="Buy an internet pack in the app",
                ),
            ],
        },
        {
            "icon": "Gift",
            "title": "Prizes",
            "blocks": [
                _p(
                    "Smartphones, internet packs and the main prize are drawn among all participants."
                ),
            ],
        },
        {
            "icon": "Calendar",
            "title": "Draw dates",
            "blocks": [
                _p("Draws are held weekly while the campaign lasts."),
            ],
        },
        {
            "icon": "Users",
            "title": "Who can participate?",
            "blocks": [
                _p("All individual prepaid and postpaid subscribers aged 18 and over."),
            ],
        },
        {
            "icon": "Megaphone",
            "title": "How are winners announced?",
            "blocks": [
                _p("Winners are contacted by phone and listed on the official website."),
            ],
        },
        {
            "icon": "Info",
            "title": "Important notes",
            "blocks": [
                _p("Chances are not transferable and cannot be exchanged for money."),
            ],
        },
    ],
    "terms_url": None,
}


def _game(id, name):
    return {"id": id, "name": name, "image": f"game-{id}.png"}


GAMES = {
    "games": [
        _game("ninja-saga-2", "Ninja Saga 2"),
        _game("fruit-slice", "Fruit Slice"),
        _game("road-rush", "Road Rush"),
        _game("penalty-kings", "Penalty Kings"),
        _game("block-puzzle", "Block Puzzle"),
        _game("space-miner", "Space Miner"),
        _game("jungle-run", "Jungle Run"),
        _game("chess-master", "Chess Master"),
    ],
    "reward_games": [_game("battle-for-gb", "Battle for GB")],
    "tournament": {
        "title": "Tournament",
        "game": "ninja-saga-2",
        "prize": "5 GB",
        "participants": 6708,
        "ends_at": "2026-10-08T15:17:02Z",
        "cta": "Participate in the tournament",
    },
}

APP_OFFERS = [
    {
        "id": "kinon",
        "name": "Kinon",
        "sub": "Films and series online",
        "price": "4.99",
        "image": "offer-kinon.png",
        "deep_link": None,
    },
    {
        "id": "yandex-plus",
        "name": "Yandex Plus",
        "sub": "Music, films and cashback",
        "price": "5.90",
        "image": "offer-yandex-plus.png",
        "deep_link": None,
    },
    {
        "id": "litres",
        "name": "Litres",
        "sub": "E-books and audiobooks",
        "price": "3.99",
        "image": "offer-litres.png",
        "deep_link": None,
    },
]

AZTELEKOM = [
    {
        "id": "fiber-optical",
        "name": "Fiber Optical",
        "sub": "Home internet from Aztelekom",
        "image": "offer-aztelekom.png",
        "deep_link": None,
    },
]

PERKS = [
    {
        "id": "wingz",
        "name": "Wingz",
        "sub": "15 minutes of free scooter time",
        "image": "perk-wingz.png",
        "deep_link": None,
    },
    {
        "id": "wolt-plus",
        "name": "Wolt+",
        "sub": "Free delivery with your Azercell number",
        "image": "perk-wolt-plus.png",
        "deep_link": None,
    },
]

CAMPAIGNS = [
    {
        "id": "azercellim",
        "name": "Azercellim.com",
        "sub": "Order a new number online",
        "image": "campaign-azercellim.png",
        "deep_link": None,
    },
]
