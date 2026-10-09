"""The brain without a model: keyword rules, used when no `ANTHROPIC_API_KEY` is set.

It covers the screens and the yes / no / why answers to a pending insight, and
it is what tests and `record_examples` run on. Same two functions as `claude`.
"""

import re

AGREE = {"hə", "he", "bəli", "qoş", "et", "keç", "yes", "yeah", "ok", "okay"}
DECLINE = {"yox", "sonra", "no", "xeyr"}
DECLINE_PHRASES = ("lazım deyil", "no thanks")
WHY = {"niyə", "nəyə", "why"}

# First match wins. (keywords, task, {lang: reply})
SCREENS = [
    (
        ("roaming", "rouminq"),
        "openRoaming",
        {
            "az": "Rouminq səhifəsini açıram.",
            "en": "Opening roaming.",
        },
    ),
    (
        ("pack", "paket"),
        "openInternetPacks",
        {
            "az": "İnternet paketlərini açıram.",
            "en": "Opening internet packs.",
        },
    ),
    (
        ("top up", "top-up", "topup", "balansı artır"),
        "topUp",
        {
            "az": "Balans artırma səhifəsini açıram.",
            "en": "Opening top-up.",
        },
    ),
    (
        ("balance", "balans"),
        "checkBalance",
        {
            "az": "Balansınıza baxıram.",
            "en": "Checking your balance.",
        },
    ),
    (
        ("internet", "qalıq", "qaliq", "remaining", "left"),
        "checkRemaining",
        {
            "az": "Qalan limitlərinizə baxıram.",
            "en": "Checking what you have left.",
        },
    ),
    (
        ("tariff", "tarif"),
        "openTariff",
        {
            "az": "Tarifinizi açıram.",
            "en": "Opening your tariff.",
        },
    ),
    (
        ("notification", "bildiriş"),
        "openNotifications",
        {
            "az": "Bildirişləri açıram.",
            "en": "Opening notifications.",
        },
    ),
    (
        ("support", "dəstək"),
        "openSupport",
        {
            "az": "Dəstək səhifəsini açıram.",
            "en": "Opening support.",
        },
    ),
]

ASK = {"az": "Nəyi edim?", "en": "What should I do?"}
DISMISSED = {
    "az": "Yaxşı, fikrinizi dəyişsəniz deyin.",
    "en": "Okay, tell me if you change your mind.",
}
EXPLAIN = {
    "az": "Sübutu göstərirəm.",
    "en": "Here is what I based that on.",
}
DOING = {"az": "Edirəm.", "en": "On it."}
LOST = {
    "az": "Bunu başa düşmədim. Balans, internet qalığı, paket və tarif barədə kömək edə bilərəm.",
    "en": "I did not get that. I can help with balance, remaining internet, packs and tariff.",
}
DONE_OK = {"az": "Hazırdır.", "en": "Done."}
DONE_FAIL = {
    "az": "Alınmadı. Yenidən cəhd edək?",
    "en": "That did not work. Shall we try again?",
}
TELL = {
    "az": "Sizə bir təklifim var. Baxım?",
    "en": "I have a suggestion for you. Shall I?",
}


def detect(text):
    lowered = text.replace("İ", "i").lower()  # "I".lower() is "i", never the dotless "ı"
    if re.search(r"[əıöüşçğ]", lowered):
        return "az"
    words = set(re.findall(r"[a-z']+", lowered))
    if words & {"the", "my", "what", "how", "where", "open", "show", "yes", "no", "why", "ok"}:
        return "en"
    return "az"


def result(reply, task, language, params=None, amount=None):
    return {"reply": reply, "task": task, "params": params, "amount": amount, "language": language}


def plan(payload):
    text = payload["text"]
    context = payload.get("context") or {}
    pending = context.get("pending") or {}
    lang = detect(text)
    lowered = text.replace("İ", "i").lower()
    words = set(re.findall(r"[\w'ə]+", lowered))

    if words & WHY and pending:
        return result(
            EXPLAIN[lang], "explainInsight", lang, {"insight_id": pending.get("insight_id")}
        )
    if words & DECLINE or any(phrase in lowered for phrase in DECLINE_PHRASES):
        if not pending:
            return result(ASK[lang], "none", lang)
        return result(
            DISMISSED[lang], "dismissInsight", lang, {"insight_id": pending.get("insight_id")}
        )
    if words & AGREE:
        task = pending.get("task")
        if not task:
            return result(ASK[lang], "none", lang)
        params = {**(task.get("params") or {}), "insight_id": pending.get("insight_id")}
        return result(DOING[lang], task["name"], lang, params)

    for keywords, task, replies in SCREENS:
        if any(keyword in lowered for keyword in keywords):
            amount = re.search(r"\d+(?:[.,]\d+)?", text) if task == "topUp" else None
            value = float(amount[0].replace(",", ".")) if amount else None
            return result(replies[lang], task, lang, None, value)
    return result(LOST[lang], "none", lang)


def narrate(payload):
    lang = payload.get("language") or "az"
    return {"speech": TELL.get(lang, TELL["az"]), "language": lang}


def done(payload):
    lang = payload.get("language") or "az"
    texts = DONE_OK if payload.get("ok") else DONE_FAIL
    return {"reply": texts.get(lang, texts["az"]), "language": lang}
