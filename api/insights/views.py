from api.common.docs import doc
from api.common.http import iso
from api.common.routing import route

from . import services

TAG = "insights"


def insight_json(row):
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "evidence": row.evidence,
        "offers": row.offers,
        "recommended": row.recommended,
        "created_at": iso(row.created_at),
        "decided_at": iso(row.decided_at),
    }


@doc("What the usage says, most urgent first")
def insights(request):
    """The open insights for the subscriber, recomputed from the usage on each call.

    `evidence` holds the numbers behind the insight (JSON numbers or money strings).
    Each entry of `offers` is a Laya task the app can run as it is: `task.name` and
    `task.params`. `recommended` is the index of the offer to show first. An insight the
    subscriber accepted or dismissed is not listed again for 7 days, and one that no longer
    applies disappears from the list.
    """
    return {"insights": [insight_json(row) for row in services.refresh(request.user)]}


@doc("Mark an insight as seen", path={"id": 9101}, errors=(404, 409))
def insight_seen(request, id):
    """`new` becomes `seen`. A closed insight answers `409 insight_closed`."""
    return {"insight": insight_json(services.seen(request.user, id))}


@doc("Accept an insight", path={"id": 9101}, errors=(404, 409))
def insight_accept(request, id):
    """Closes the insight as `accepted`. The app runs the offer's task itself."""
    return {"insight": insight_json(services.decide(request.user, id, "accepted"))}


@doc("Dismiss an insight", path={"id": 9101}, errors=(404, 409))
def insight_dismiss(request, id):
    """Closes the insight as `dismissed`; it stays out of the list for 7 days."""
    return {"insight": insight_json(services.decide(request.user, id, "dismissed"))}


@doc("Compare the current tariff with the ones that would cost less")
def advisor(request):
    """The current monthly cost, the tariffs and the redesign that would have cost less
    over the last 30 days with their saving, which one to take (`recommended`, or `current`
    when nothing beats it) and the date it would start (`effective_from`, the next renewal).
    """
    return services.advise(request.user)


insights_view = route(TAG, get=insights)
advisor_view = route(TAG, get=advisor)
seen_view = route(TAG, post=insight_seen)
accept_view = route(TAG, post=insight_accept)
dismiss_view = route(TAG, post=insight_dismiss)
