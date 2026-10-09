# API — laya `/api/laya/` `ready`

Laya is the voice assistant in the app. The app sends what the user said and
runs the task that comes back; nothing here moves money. The brain is Gemini
when `GEMINI_API_KEY` is set (`GEMINI_*` models), then Claude when
`ANTHROPIC_API_KEY` is set, and keyword rules otherwise (`LAYA_BRAIN`).

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `plan/` | `ready` | What the user said → reply, task, params |
| POST | `narrate/` | `ready` | A server insight → one spoken message |

Every number in an answer must already be in the request; an answer that
invents one is dropped. `plan/` then answers `task: "none"`, `narrate/`
answers `502 laya_unavailable`.

## `POST plan/`

```json
→ { "text": "hə, qoş",
    "context": { "balance": 16.21, "dataGb": 7.2, "tariff": "IsteSen", "screen": "assistant",
      "pending": { "insight_id": 41, "task": { "name": "activatePack", "params": { "slug": "youtube", "plan": "5gb" } } } } }
← 200 { "reply": "Edirəm.", "task": "activatePack",
        "params": { "slug": "youtube", "plan": "5gb", "insight_id": 41 }, "amount": null, "language": "az" }
```

`context` may also carry `insights` and `advisor`. `task` is one of
`checkBalance`, `checkRemaining`, `topUp`, `openInternetPacks`, `openRoaming`,
`openTariff`, `openNotifications`, `openSupport`, `activatePack`, `buyPack`,
`applyRedesign`, `changeTariff`, `explainInsight`, `dismissInsight`,
`adviseTariff`, `none`. With `pending`, "yes" returns its task unchanged, "no"
returns `dismissInsight` and "why" returns `explainInsight`.

## `POST narrate/`

```json
→ { "language": "az", "name": "Qüdrət", "insight": { "id": 41, "kind": "video_heavy", "evidence": {…}, "offers": […], "recommended": 0 } }
← 200 { "speech": "12 GB-lıq paketinizi 2 gündə bitirdiniz … Qoşum?", "language": "az" }
```

`speech` is at most 45 words and ends with a question.
