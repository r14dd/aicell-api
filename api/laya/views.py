from rest_framework import serializers

from api.common.docs import doc
from api.common.http import validated
from api.common.routing import route

from . import brain, tasks

TAG = "laya"

INSIGHT = {
    "id": 41,
    "kind": "video_heavy",
    "evidence": {"pack_gb": 12, "days": 2, "youtube_gb": 7},
    "offers": [
        {
            "title": "YouTube 5 GB",
            "price": 5,
            "task": {"name": "activatePack", "params": {"slug": "youtube", "plan": "5gb"}},
        }
    ],
    "recommended": 0,
}


class LayaPlanInput(serializers.Serializer):
    text = serializers.CharField(max_length=500, help_text="What the user said")
    context = serializers.DictField(
        required=False,
        default=dict,
        help_text="balance, dataGb, dataTotalGb, minutes, minutesTotal, tariff, screen; "
        "optionally insights, advisor and pending",
    )


class LayaNarrateInput(serializers.Serializer):
    insight = serializers.DictField(help_text="One server-computed insight")
    language = serializers.ChoiceField(choices=tasks.LANGUAGES, default="az")
    name = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


@doc(
    "Decide what to do with what the user said",
    body=LayaPlanInput,
    example={"text": "where can I top up my balance", "context": {"balance": 16.21}},
    errors=(400, 502),
)
def plan(request):
    """Returns the reply to say, the task the app runs and its params.

    A yes / no / why answers the `pending` insight in the context. Every number
    in `reply` comes from the request; anything else is replaced by a safe answer.
    """
    data = validated(LayaPlanInput, request)
    return brain.plan(data["text"], data["context"])


class LayaDoneInput(serializers.Serializer):
    task = serializers.ChoiceField(choices=tasks.TASKS, help_text="The task the app ran")
    ok = serializers.BooleanField(help_text="Whether the app completed it")
    error = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    language = serializers.ChoiceField(choices=tasks.LANGUAGES, default="az")
    context = serializers.DictField(
        required=False, default=dict, help_text="The account after the task: balance, dataGb ..."
    )


@doc(
    "Report the outcome of a task the app ran",
    body=LayaDoneInput,
    example={"task": "topUp", "ok": True, "language": "en", "context": {"balance": 21.21}},
    errors=(400,),
)
def done(request):
    """Returns one sentence to say about the outcome. Never fails once the body is valid:
    when the model is down or answers badly, a fixed "done" / "did not work" line comes back.
    """
    data = validated(LayaDoneInput, request)
    return brain.done(data["task"], data["ok"], data["error"], data["language"], data["context"])


@doc(
    "Say an insight aloud",
    body=LayaNarrateInput,
    example={"language": "az", "name": "Qüdrət", "insight": INSIGHT},
    errors=(400, 502),
)
def narrate(request):
    """One sentence of evidence, one with the offer and its price, then a yes/no question."""
    data = validated(LayaNarrateInput, request)
    return brain.narrate(data["insight"], data["language"], data["name"])


plan_view = route(TAG, post=plan)
narrate_view = route(TAG, post=narrate)
done_view = route(TAG, post=done)
