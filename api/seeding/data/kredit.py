"""Kredit products.

Only SimTaksit's amount and fee are documented; the other fees and two of the
three Tamamla steps are placeholders in the documented shape.
"""

NEXT_TOPUP = "Get now! Pay back at the next topup"

PRODUCTS = [
    {
        "id": "simkredit",
        "name": "SimKredit",
        "subtitle": NEXT_TOPUP,
        "chip": "1-3 ₼",
        "chip_icon": "coins",
        "deep_link": "/kredit/simkredit",
    },
    {
        "id": "simtaksit",
        "name": "SimTaksit",
        "subtitle": "Get now! Pay back within 32 days by 0.08 ₼",
        "chip": "2 ₼",
        "chip_icon": "coins",
        "deep_link": "/kredit/simtaksit",
    },
    {
        "id": "internetkredit",
        "name": "InternetKredit",
        "subtitle": NEXT_TOPUP,
        "chip": "300 MB",
        "chip_icon": "broadcast",
        "price": "2 ₼",
        "deep_link": "/kredit/internetkredit",
    },
    {
        "id": "ekstrakredit",
        "name": "EkstraKredit",
        "subtitle": NEXT_TOPUP,
        "chip": "1 ₼",
        "chip_icon": "coins",
        "deep_link": "/kredit/ekstrakredit",
    },
]

DETAILS = {
    "simkredit": {"amount": "1.00", "fee": "0.20", "options": ["1", "2", "3"]},
    "simtaksit": {"amount": "2.00", "fee": "0.60"},
    "internetkredit": {"amount": "2.00", "fee": "0.00", "amount_mb": 300, "validity_days": 7},
    "ekstrakredit": {"amount": "1.00", "fee": "0.25"},
}
