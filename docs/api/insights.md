# API — insights `/api/insights/`

What the last 30 days of usage say the subscriber should do, as cards the app can
show, and a comparison of the current tariff with the ones that would cost less.

Every number is computed by the backend from the usage rows and the catalogue; no
model is involved. An insight appears only when the data shows it. Each offer carries
a Laya task (`task.name`, `task.params`) that the app runs as it is.

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `` (root) | `ready` | Open insights, most urgent first |
| GET | `advisor/` | `ready` | Current tariff against the ones that would cost less |
| POST | `<id>/seen/` | `ready` | Mark an insight as seen |
| POST | `<id>/accept/` | `ready` | Close an insight as accepted |
| POST | `<id>/dismiss/` | `ready` | Close an insight as dismissed |

## `GET` (root)

Recomputes the insights from the usage and returns the ones that apply.

```json
← 200 {
  "insights": [
    {
      "id": 9101,
      "kind": "social_heavy",
      "status": "new",
      "evidence": { "tiktok_gb": 3.1, "instagram_gb": 9.8, "days": 30, "price": "22.10" },
      "offers": [
        { "title": "…", "price": "22.10",
          "task": { "name": "applyRedesign", "params": { "internet": 20, "calls": 30 } } }
      ],
      "recommended": 0,
      "created_at": "2026-10-09T08:00:00Z",
      "decided_at": null
    }
  ]
}
```

- `kind`, most urgent first: `renewal_shortfall`, `overage`, `forecast_gap`,
  `repeat_packs`, `roaming`, `social_heavy`, `underused`, `video_heavy`.
- `evidence` keys depend on the kind; values are JSON numbers or money strings.
- `task.name` is one of `topUp`, `buyPack`, `changeTariff`, `activatePack`,
  `applyRedesign`.
- `recommended` is the index in `offers` to show first.
- An insight the subscriber accepted or dismissed stays out of the list for 7 days.
  One that no longer applies is not listed.

## `GET advisor/`

```json
← 200 {
  "current": { "plan": "istesen", "title": "IsteSen", "monthly_cost": "31.20" },
  "candidates": [
    { "id": "redesign", "title": "…", "monthly_cost": "24.10", "saving_month": "7.10",
      "task": { "name": "applyRedesign", "params": { "internet": 20, "calls": 30 } } }
  ],
  "recommended": "redesign",
  "effective_from": "2026-10-20"
}
```

- `candidates` are the tariffs and the redesign that would have cost less over the last
  30 days. It is empty and `recommended` is `current` when nothing beats the tariff.
- `effective_from` is the next renewal date.

## `POST <id>/seen/`, `POST <id>/accept/`, `POST <id>/dismiss/`

```json
← 200 { "insight": { "id": 9101, "kind": "social_heavy", "status": "seen", … } }
```

- `seen` turns `new` into `seen`. `accept` and `dismiss` close the insight; accepting
  does not run the task, the app does.
- Another subscriber's insight answers `404 not_found`. A closed one answers
  `409 insight_closed`.
