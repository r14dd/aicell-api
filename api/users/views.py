from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.http import MsisdnField, validated
from api.common.routing import Todo, route

from . import services

TAG = "users"

APP_SETTINGS = _("App settings are not part of this prototype yet")


def profile_json(user, request):
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


@doc("My profile")
def me(request):
    """The subscriber shown on Home and More. `app_version` echoes `X-App-Version`."""
    return profile_json(request.user, request)


class OtpSendInput(serializers.Serializer):
    msisdn = MsisdnField()


class OtpVerifyInput(serializers.Serializer):
    request_id = serializers.CharField()
    code = serializers.CharField()


class TokenRefreshInput(serializers.Serializer):
    refresh = serializers.CharField()


@doc(
    "Send an OTP to a number",
    body=OtpSendInput,
    example={"msisdn": "994516643342"},
    errors=(400, 404, 429),
)
def otp_send_post(request):
    """Starts a sign-in for a subscriber. No SMS is sent yet: the code is always `000000`
    (`OTP_TEST_CODE`). Unknown numbers answer 404; a second request for the same number
    within `resend_after` seconds answers 429."""
    return services.send(validated(OtpSendInput, request)["msisdn"])


@doc("Verify an OTP and get tokens", body=OtpVerifyInput, errors=(400, 429))
def otp_verify_post(request):
    """A wrong code answers 400 `invalid_code` with `attempts_left`; at 0 the request is gone."""
    data = validated(OtpVerifyInput, request)
    subscriber, tokens = services.verify(data["request_id"], data["code"])
    return {**tokens, "subscriber": profile_json(subscriber, request)}


@doc("Refresh the access token", body=TokenRefreshInput, errors=(400,))
def token_refresh_post(request):
    """`{ "refresh" }` from `otp/verify/` → `{ "access" }`. An invalid or expired refresh
    token answers 400 `invalid_token`: sign in again."""
    return services.refresh(validated(TokenRefreshInput, request)["refresh"])


otp_send = route(TAG, public=True, throttle="otp", post=otp_send_post)
otp_verify = route(TAG, public=True, throttle="otp", post=otp_verify_post)
token_refresh = route(TAG, public=True, post=token_refresh_post)
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
