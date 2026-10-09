from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from api.common.docs import doc
from api.common.http import money
from api.common.routing import Todo, route

from . import catalogue
from .models import ReferralProfile

TAG = "referral"
SHARE_URL = "https://azercell.com/app?ref={code}"


@doc("Invite & earn page", errors=(404,))
def me(request):
    """The subscriber's code, share link, what they earned and the rules."""
    profile = get_object_or_404(ReferralProfile, subscriber=request.user)
    return {
        "code": profile.code,
        "share_url": SHARE_URL.format(code=profile.code),
        "share_message": _("Join me on the Azercell app and use my referral code %(code)s")
        % {"code": profile.code},
        "earned": money(profile.earned),
        "headline": _("Share Azercell app and get 3.00 ₼ bonus!"),
        "steps": catalogue.steps(),
        "terms_url": None,
    }


me_view = route(TAG, get=me)
terms_view = route(
    TAG, get=Todo(_("Terms of Use are not part of this prototype yet"), "Referral terms of use")
)
# When built: `qualified` credits the bonus to the referrer's wallet (kind=credit,
# title "Referral bonus") and bumps `earned`. Called by services with `Token <key>`.
events_view = route(
    TAG,
    post=Todo(
        _("Referral events are not part of this prototype yet"),
        "Service webhook: a friend registered or qualified",
    ),
)
