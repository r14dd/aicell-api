"""Personal offer rules: which segment is offered which catalogue item at which price."""

OFFER_RULES = [
    {
        "segment": "voice_only",
        "target_kind": "internet_pack",
        "target_id": "weekly-2gb",
        "offer_price": "1.50",
        "valid_days": 14,
        "reason": "You have not used mobile internet yet: try your first pack at half price",
        "is_active": True,
    },
    {
        "segment": "roamer",
        "target_kind": "roaming_pack",
        "target_id": "r-2gb",
        "offer_price": "20.00",
        "valid_days": 14,
        "reason": "You travel often: a bigger roaming pack for less",
        "is_active": True,
    },
    # Switched off: it is not applied to a segment. The seed places one offer
    # from it on the demo subscriber by hand, so the offer screens have content.
    {
        "segment": "balanced",
        "target_kind": "social_pack",
        "target_id": "instagram-facebook:5gb",
        "offer_price": "2.00",
        "valid_days": 14,
        "reason": "Instagram & Facebook is most of your internet: 5 GB for less",
        "is_active": False,
    },
]
