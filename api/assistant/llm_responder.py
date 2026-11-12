"""Model-backed responder, selected with `ASSISTANT_RESPONDER`.

Same contract as `responder.respond`: `respond(subscriber, text) -> Reply`.
The pipeline is routing -> retrieval -> reply. Until the model, the router and
the vector store are connected, every step falls back to the keyword responder
so the endpoint keeps working.
"""

from . import responder
from .responder import Reply


def respond(subscriber, text) -> Reply:
    return responder.respond(subscriber, text)
