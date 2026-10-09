"""Read side of the invite & earn rules."""

from api.common.cache import cached

from .models import ReferralStep


@cached("referral.steps")
def steps() -> list[dict]:
    return [{"title": step.title, "body": step.body} for step in ReferralStep.objects.active()]
