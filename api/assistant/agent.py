"""The Gemini responder: route the message, gather facts in code, let the model write the reply.

Same signature as the keyword responder, which it falls back to when Gemini fails:
`respond(subscriber, text) -> Reply`.
"""

import json
import logging

from . import gemini, knowledge, responder
from .responder import Reply

log = logging.getLogger(__name__)

# route -> what the subscriber is asking
ROUTES = {
    "balance": "their account balance",
    "usage": "remaining internet, minutes or SMS in their package",
    "my_tariff": "their own current tariff and renewal date",
    "recommendation": "which tariff or pack would suit or save them money",
    "kredit": "borrowing credit (SimKredit)",
    "roaming": "roaming prices, countries or using the phone abroad",
    "tariffs": "tariff plans of the operator in general: prices, conditions",
    "packs": "internet packs of the operator",
    "campaign": "current offers, campaigns, discounts",
    "service": "a service such as caller tune, call forwarding, SIM",
    "support": "a problem, complaint, how-to or contact with the operator",
    "chat": "greeting, thanks or small talk",
}
# Routes answered from the subscriber's own data (handlers in responder.py).
OWN_DATA = {
    "balance": responder._balance,
    "usage": responder._usage,
    "my_tariff": responder._tariff,
    "recommendation": responder._recommendation,
    "kredit": responder._kredit,
}
# Routes answered from the knowledge base: the page kinds to search, and the screen to offer.
KNOWLEDGE = {
    "roaming": (["roaming-price", "roaming-info", "support"], responder._roaming),
    "tariffs": (["tariff"], None),
    "packs": (["internet-pack"], responder._packs),
    "campaign": (["campaign"], None),
    "service": (["service"], None),
    "support": (["support"], None),
}

ROUTE_SYSTEM = (
    "Route a mobile-operator customer message (Azerbaijani or English) to one route:\n"
    + "\n".join(f"{name}: {about}" for name, about in ROUTES.items())
)
ROUTE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"route": {"type": "STRING", "enum": list(ROUTES)}},
    "required": ["route"],
}
REPLY_SYSTEM = (
    "You are the voice assistant of an Azerbaijani mobile operator. Reply in the language of the "
    "customer's message, in one or two short spoken sentences, no lists or markdown. Answer only "
    "what was asked and do not offer further help. Use only the facts given; never invent "
    "numbers, prices or conditions. If the facts do not answer, say so. For a greeting, greet "
    "back and ask how you can help."
)


def _write(text, facts):
    return gemini.generate(REPLY_SYSTEM, f"Customer message: {text}\n\nFacts:\n{facts}")


def _answer(subscriber, text, route):
    if route in OWN_DATA:
        draft = OWN_DATA[route](subscriber)
        return draft, draft.text
    if route in KNOWLEDGE:
        kinds, handler = KNOWLEDGE[route]
        chunks = knowledge.retrieve(text, kinds)
        facts = "\n\n".join(f"{c['title']}\n{c['text']}" for c in chunks)
        draft = handler(subscriber) if handler else Reply("", route)
        return draft, facts
    return Reply("", "chat"), "No data needed."


def respond(subscriber, text):
    try:
        raw, in_a, out_a = gemini.generate(ROUTE_SYSTEM, text, schema=ROUTE_SCHEMA)
        route = json.loads(raw)["route"]
        draft, facts = _answer(subscriber, text, route)
        reply, in_b, out_b = _write(text, facts)
    except Exception:
        log.exception("Assistant failed, using keyword rules")
        return responder.respond(subscriber, text)
    return Reply(
        reply.strip(), route, draft.action, tokens_in=in_a + in_b, tokens_out=out_a + out_b
    )
