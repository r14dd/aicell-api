# API — referral `/api/referral/`

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `me/` | `ready` | Invite & earn page |
| GET | `terms/` | `:todo` | "Terms of Use" |
| POST | `events/` | `:todo` | Service webhook: a friend registered / qualified (`Token <key>`) |

## `GET me/`

```json
← 200 {
  "code": "wa16Kg",
  "share_url": "https://azercell.com/app?ref=wa16Kg",
  "share_message": "Join me on the Azercell app and use my referral code wa16Kg",
  "earned": "0.00",
  "headline": "Share Azercell app and get 3.00 ₼ bonus!",
  "steps": [
    { "title": "Invite a friend who doesn’t have an account on the Azercell app", "body": "Share your invitation link or referral code. The link can be sent an unlimited number of times." },
    { "title": "Your friend registers and easily uses the service.", "body": "Your friend must register for the first time using the link you shared and benefit from the specified paid services. Use of the paid service must be done within 24 hours of registration." },
    { "title": "Earn together with your friend", "body": "Once all eligibility requirements are confirmed, you will receive a bonus of 3.00 ₼. Your friend will also be granted 5GB of free internet." }
  ],
  "terms_url": null
}
```

## `POST events/` `:todo`

```json
→ { "code": "wa16Kg", "invited_msisdn": "9945…", "event": "registered|qualified" }
← 202 {}
```

`qualified` credits 3.00 ₼ to the referrer's wallet (`kind=credit`,
title "Referral bonus") and bumps `earned`.
