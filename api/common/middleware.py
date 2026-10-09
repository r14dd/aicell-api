from django.conf import settings
from django.utils import translation
from django.utils.translation import get_supported_language_variant
from django.utils.translation.trans_real import parse_accept_lang_header

HEALTH_PREFIX = "/api/health/"


def language_from_header(request) -> str:
    """The best supported language of `Accept-Language`; `en` when there is none."""
    header = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for code, _quality in parse_accept_lang_header(header):
        try:
            return get_supported_language_variant(code)
        except LookupError:
            continue
    return settings.LANGUAGE_CODE


class ApiLanguageMiddleware:
    """Answer in the language of `Accept-Language`: `az` or `en`.

    Only the header decides, never a cookie or the session. The chosen language
    is announced in `Content-Language`. Health probes are left alone: their
    answer must not depend on any header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(HEALTH_PREFIX):
            return self.get_response(request)

        language = language_from_header(request)
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        response.headers.setdefault("Content-Language", language)
        vary = [value for value in (response.headers.get("Vary"),) if value]
        response.headers["Vary"] = ", ".join([*vary, "Accept-Language"])
        return response
