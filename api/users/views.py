from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.http import MsisdnField
from api.common.routing import Todo, route

TAG = "users"

SIGN_IN = _("Sign in is not part of this prototype yet")
APP_SETTINGS = _("App settings are not part of this prototype yet")


@doc("My profile")
def me(request):
    """The subscriber shown on Home and More. `app_version` echoes `X-App-Version`."""
    user = request.user
    version = request.headers.get("X-App-Version")
    return {
        "id": user.id,
        "msisdn": user.msisdn,
        "display_msisdn": user.display_msisdn,
        "display_name": user.display_name,
        "line_type": user.line_type,
        "language": user.language,
        "app_version": _("Version %(version)s") % {"version": version} if version else None,
        "is_premium": user.is_premium,
    }


class OtpSendInput(serializers.Serializer):
    msisdn = MsisdnField()


class OtpVerifyInput(serializers.Serializer):
    request_id = serializers.CharField()
    code = serializers.CharField()


otp_send = route(
    TAG,
    public=True,
    throttle="otp",
    post=Todo(SIGN_IN, "Send an OTP to a number", body=OtpSendInput),
)
otp_verify = route(
    TAG,
    public=True,
    throttle="otp",
    post=Todo(SIGN_IN, "Verify an OTP and get tokens", body=OtpVerifyInput),
)
token_refresh = route(TAG, public=True, post=Todo(SIGN_IN, "Refresh the access token"))
logout = route(TAG, post=Todo(_("Sign out is not part of this prototype yet"), "Sign out"))
me_view = route(
    TAG,
    get=me,
    patch=Todo(_("Profile settings are not part of this prototype yet"), "Update my profile"),
)
app_settings = route(
    TAG,
    get=Todo(APP_SETTINGS, "App settings: theme, language, push"),
    patch=Todo(APP_SETTINGS, "Update app settings"),
)
devices = route(
    TAG,
    post=Todo(_("Push notifications are not part of this prototype yet"), "Register a push token"),
)
