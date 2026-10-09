"""SIM settings content.

Mirrors `src/data/simServices.ts` and the SIM screens of the mobile app.
Entries the API docs abbreviate (the service list, the second PUK paragraph,
two eSIM benefits) are placeholders in the documented shape.
"""

SERVICES = {
    "missed-call": {
        "id": "missed-call",
        "name": "Buraxılmış zəng",
        "sub": "Find out who called while you were unreachable",
        "period": "30 days",
        "days": 30,
        "price": "0.90",
        "auto_renew": True,
        "sections": [
            {
                "text": "You receive an SMS about every call you missed while your "
                "phone was switched off or out of coverage."
            },
            {
                "rows": [
                    {"label": "Price", "value": "0.90 ₼"},
                    {"label": "Validity period", "value": "30 days"},
                    {"label": "Renews", "value": "Automatically"},
                ]
            },
            {
                "option": {
                    "id": "xeber-ver",
                    "label": "Xəbər ver",
                    "sub": "Let the caller know when you are back in the network",
                }
            },
        ],
    },
    "whos-calling": {
        "id": "whos-calling",
        "name": "Who is calling",
        "sub": "See the name of unknown callers",
        "period": "30 days",
        "days": 30,
        "price": "1.00",
        "auto_renew": True,
        "sections": [
            {
                "text": "The name of the caller is shown on the screen even when the "
                "number is not in your contacts."
            },
            {
                "rows": [
                    {"label": "Price", "value": "1.00 ₼"},
                    {"label": "Validity period", "value": "30 days"},
                    {"label": "Renews", "value": "Automatically"},
                ]
            },
        ],
    },
    "ringback-tone": {
        "id": "ringback-tone",
        "name": "Ringback tone",
        "sub": "Callers hear music instead of the standard tone",
        "period": "30 days",
        "days": 30,
        "price": "1.50",
        "auto_renew": True,
        "sections": [
            {"text": "Choose a melody that callers hear while they wait for you to answer."},
            {
                "rows": [
                    {"label": "Price", "value": "1.50 ₼"},
                    {"label": "Validity period", "value": "30 days"},
                    {"label": "Renews", "value": "Automatically"},
                ]
            },
        ],
    },
}
